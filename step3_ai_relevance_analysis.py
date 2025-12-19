import os
import json
import pandas as pd
import time
from tqdm import tqdm
from google import genai
from google.genai import types
from dotenv import load_dotenv  # 新增：引入加载库

# --- 加载隐藏的 API Key ---
load_dotenv()  # 自动寻找项目根目录下的 .env 文件并加载环境变量
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    raise ValueError("错误：未在 .env 文件或环境变量中找到 GOOGLE_API_KEY")


# --- 配置区 ---
# 请确保已设置环境变量 GOOGLE_API_KEY
client = genai.Client(api_key=api_key)
MODEL_ID = "gemini-3-flash-preview"  # 使用当前的 Flash 模型，速度快且成本低

INPUT_INDEX_FILE = "output/IJRR_Indexed_Main.xlsx"
OUTPUT_ANALYSIS_FILE = "output/Literature_Review_Results.xlsx"
ABSTRACT_DIR = "output/abstracts/"

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
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('abstract', "摘要内容为空。")
    return "找不到摘要文件。"

def analyze_batch(batch_data):
    """调用 Gemini 分析 5 篇论文"""
    user_prompt = "请分析以下 5 篇文献的摘要，并返回 JSON 数组：\n\n"
    for i, item in enumerate(batch_data):
        user_prompt += f"[文献 {i+1}]\n标题: {item['Title']}\n摘要: {item['Abstract']}\n\n"

    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.1, # 降低随机性，保证格式稳定
                response_mime_type="application/json" # 强制输出 JSON
            ),
        )
        
        # 解析返回结果
        raw_text = response.text.strip()
        # 移除可能存在的 Markdown 代码块标记
        cleaned_text = raw_text.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned_text)
    except Exception as e:
        print(f"AI 分析出错: {e}")
        return [{"score": 0, "reason": "分析失败"}] * len(batch_data)

def run_analysis():
    # 1. 读取索引表
    df = pd.read_excel(INPUT_INDEX_FILE)
    
    all_scores = []
    all_reasons = []
    
    # 2. 分组处理 (每 5 篇一组)
    batch_size = 5
    for i in tqdm(range(0, len(df), batch_size), desc="AI 正在评审"):
        batch_df = df.iloc[i : i + batch_size]
        
        # 准备本组数据
        batch_list = []
        for _, row in batch_df.iterrows():
            batch_list.append({
                "Title": row['Title'],
                "Abstract": get_abstract_content(row['Abstract_Link'])
            })
        
        # 调用 AI
        results = analyze_batch(batch_list)
        
        # 提取结果（对齐长度，防止 AI 返回缺失）
        for j in range(len(batch_list)):
            if j < len(results):
                all_scores.append(results[j].get('score', 0))
                all_reasons.append(results[j].get('reason', "无理由"))
            else:
                all_scores.append(0)
                all_reasons.append("AI 未能返回结果")
        
        # 稍微停顿，避免触发 API 频率限制
        time.sleep(1)

    # 3. 将结果合并并保存
    df['AI_Score'] = all_scores
    df['AI_Reason'] = all_reasons
    
    # 按照分数降序排列，方便直接看高分论文
    df = df.sort_values(by='AI_Score', ascending=False)
    
    df.to_excel(OUTPUT_ANALYSIS_FILE, index=False)
    print(f"\n分析完成！结果已保存至: {OUTPUT_ANALYSIS_FILE}")

if __name__ == "__main__":
    run_analysis()