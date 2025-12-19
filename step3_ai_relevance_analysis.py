import os
import json
import pandas as pd
import time
import concurrent.futures
from tqdm import tqdm
from openai import OpenAI
from dotenv import load_dotenv

# --- 加载配置 ---
load_dotenv()
api_key = os.getenv("DEEPSEEK_API_KEY")

if not api_key:
    raise ValueError("错误：未在 .env 文件或环境变量中找到 DEEPSEEK_API_KEY")

# --- 配置区 ---
# --- 修改：初始化 OpenAI 客户端并指向 DeepSeek Base URL ---
client = OpenAI(
    api_key=api_key, 
    base_url="https://api.deepseek.com"
)
MODEL_ID = "deepseek-chat" # --- 修改：使用 deepseek-chat 模型 ---
# deepseek-reasoner
# deepseek-chat

INPUT_INDEX_FILE = "output/IJRR_Indexed_Main.xlsx"
OUTPUT_ANALYSIS_FILE = "output/Literature_Review_Results.xlsx"
ABSTRACT_DIR = "output/abstracts/"

# --- 并行配置 ---
MAX_WORKERS = 5  # 并发线程数。建议设为 5-10，过高可能会频繁触发 429 错误
BATCH_SIZE = 5   # 每次发给 AI 的论文数量

SYSTEM_PROMPT = """
你是一个非结构化环境（Unstructured Environments）自动驾驶与机器人导航领域的资深审稿人。
你的任务是阅读用户提供的论文摘要，并判断其对“非结构化道路路径规划”课题组的参考价值。

评分标准 (1-5分)：
* 5分 (必读)：核心主题是非结构化/越野环境（Off-road, rough terrain, mining, agriculture, planetary）下的路径/运动规划。
* 4分 (推荐)：主题相关，但侧重于感知或控制，或者场景是半结构化但方法可以迁移。
* 3分 (一般)：常规路径规划，但场景主要是结构化道路（城市、高速）。
* 2分 (弱相关)：仅提及自动驾驶，但重点是V2X、交通流预测或纯视觉数据集。
* 1分 (无关)：与路径规划或移动机器人无关。

输出要求：
1. 仅输出一个标准的 JSON 数组格式，不要包含任何 Markdown 标记或解释文字。
2. 数组中包含的对象字段：{"id": 原始序号, "score": 整数, "reason": "20字以内中文要点"}
"""

def get_abstract_content(link):
    """从本地 JSON 读取摘要内容"""
    if pd.isna(link) or link == "Not_Found":
        return "无摘要数据。"
    path = os.path.join(ABSTRACT_DIR, link)
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('abstract', "摘要内容为空。")
        except:
            return "摘要文件损坏。"
    return "找不到摘要文件。"

def call_ai_api(prompt):
    """单纯的 API 调用函数，包含重试逻辑"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=MODEL_ID,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                stream=False,
                timeout=60 # 设置超时防止卡死
            )
            raw_text = response.choices[0].message.content.strip()
            cleaned_text = raw_text.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_text)
        except Exception as e:
            if "429" in str(e) or "rate limit" in str(e).lower():
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1)) # 递增等待：5s, 10s...
                    continue
            # 其他错误或重试耗尽
            print(f"\n[Error] API 调用失败: {e}")
            return None
    return None

def process_batch_task(batch_df_slice):
    """
    线程工作函数：处理一个批次的数据
    输入: DataFrame 切片
    输出: 包含 (index, score, reason) 的结果列表
    """
    # 1. 准备 Prompt
    batch_list = []
    indices = [] # 记录原始索引，确保数据能对齐回去
    
    user_prompt = "请分析以下文献摘要，并返回 JSON 数组：\n\n"
    
    for i, (idx, row) in enumerate(batch_df_slice.iterrows()):
        abstract = get_abstract_content(row['Abstract_Link'])
        user_prompt += f"[文献 {i+1}]\n标题: {row['Title']}\n摘要: {abstract}\n\n"
        indices.append(idx)

    # 2. 调用 AI
    ai_results = call_ai_api(user_prompt)

    # 3. 整理结果
    processed_results = []
    
    if ai_results and isinstance(ai_results, list):
        for j, idx in enumerate(indices):
            if j < len(ai_results):
                processed_results.append({
                    "index": idx,
                    "score": ai_results[j].get('score', 0),
                    "reason": ai_results[j].get('reason', "无理由")
                })
            else:
                processed_results.append({"index": idx, "score": 0, "reason": "AI返回数量不足"})
    else:
        # 如果 API 彻底失败，填入默认值
        for idx in indices:
            processed_results.append({"index": idx, "score": 0, "reason": "API请求失败"})

    return processed_results

def run_analysis_parallel():
    # 1. 读取数据
    print("正在读取索引文件...")
    df = pd.read_excel(INPUT_INDEX_FILE)
    
    # 2. 切分批次
    # 将 DataFrame 切分成多个小的 DataFrame，每块包含 BATCH_SIZE 行
    chunks = [df.iloc[i:i + BATCH_SIZE] for i in range(0, len(df), BATCH_SIZE)]
    
    results_map = {} # 用于存储结果：{index: {'score': x, 'reason': y}}

    print(f"开始并行处理，共 {len(chunks)} 个批次，并发数: {MAX_WORKERS}")

    # 3. 并行执行
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交所有任务
        futures = {executor.submit(process_batch_task, chunk): chunk for chunk in chunks}
        
        # 使用 tqdm 显示进度
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(chunks), desc="AI 评审进度"):
            try:
                batch_results = future.result()
                # 将结果存入字典
                for res in batch_results:
                    results_map[res['index']] = {
                        'score': res['score'],
                        'reason': res['reason']
                    }
            except Exception as e:
                print(f"批次处理发生异常: {e}")

    # 4. 汇总数据 (线程安全地写回)
    print("正在汇总数据...")
    
    # 利用 map 函数根据 index 快速填入数据
    # 如果某个 index 缺失（理论上不应该），给默认值
    df['AI_Score'] = df.index.map(lambda x: results_map.get(x, {}).get('score', 0))
    df['AI_Reason'] = df.index.map(lambda x: results_map.get(x, {}).get('reason', "处理遗漏"))

    # 5. 排序与保存
    df = df.sort_values(by='AI_Score', ascending=False)
    df.to_excel(OUTPUT_ANALYSIS_FILE, index=False)
    print(f"\n并行分析完成！结果已保存至: {OUTPUT_ANALYSIS_FILE}")

if __name__ == "__main__":
    run_analysis_parallel()