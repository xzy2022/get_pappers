# step2_fetch_abstracts.py
import pandas as pd
import requests
import time
from tqdm import tqdm  # 用于显示进度条，如果没有请执行 pip install tqdm

def get_abstract_from_ss(title):
    """
    通过 Semantic Scholar API 根据标题查询摘要
    """
    search_url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        'query': title,
        'limit': 1,
        'fields': 'title,abstract'
    }
    
    try:
        response = requests.get(search_url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('total', 0) > 0:
                paper_data = data['data'][0]
                return paper_data.get('abstract', "No abstract found.")
        elif response.status_code == 429:
            print("\n触发 API 频率限制，等待中...")
            time.sleep(1.5) # 遇到限制等待1.5秒
        return "Not Found"
    except Exception as e:
        return f"Error: {str(e)}"

def update_excel_with_abstracts(input_file, output_file):
    # 1. 读取 Excel
    print(f"正在读取 {input_file}...")
    df = pd.read_excel(input_file)

    # 如果已经有 Abstract 列，可以跳过已有的，或者全部重写
    if 'Abstract' not in df.columns:
        df['Abstract'] = ""

    print("开始从 Semantic Scholar 获取摘要 (这可能需要几分钟)...")
    
    # 2. 遍历每一行获取摘要
    # tqdm 可以在终端显示进度条
    for index, row in tqdm(df.iterrows(), total=df.shape[0]):
        # 如果摘要列已经有内容，则跳过（可选）
        if pd.notna(row['Abstract']) and row['Abstract'] != "" and row['Abstract'] != "Not Found":
            continue
            
        title = row['Title']
        abstract = get_abstract_from_ss(title)
        df.at[index, 'Abstract'] = abstract
        
        # 为了遵守 API 限制，每次请求后稍微停顿
        time.sleep(1.1) 

    # 3. 保存结果
    df.to_excel(output_file, index=False)
    print(f"\n处理完成！结果已保存至 {output_file}")

if __name__ == "__main__":
    INPUT_FILE = "IJRR_Planning_2022_2025.xlsx"
    OUTPUT_FILE = "IJRR_Planning_with_Abstracts.xlsx"
    
    update_excel_with_abstracts(INPUT_FILE, OUTPUT_FILE)