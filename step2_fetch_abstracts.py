# step2_fetch_abstracts.py
import pandas as pd
import requests
import time
import os
import json
import re
from tqdm import tqdm

def slugify(value):
    """将标题转换为安全的文件名"""
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    return re.sub(r'[-\s]+', '_', value)

def get_abstract_by_id(doi, title):
    """通过 DOI 或 Title 访问 Semantic Scholar"""
    # 1. 优先使用 DOI
    if pd.notna(doi) and doi != "":
        url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
        try:
            res = requests.get(url, params={'fields': 'abstract'}, timeout=10)
            if res.status_code == 200:
                return res.json().get('abstract')
        except:
            pass

    # 2. 备选标题搜索
    search_url = "https://api.semanticscholar.org/graph/v1/paper/search"
    try:
        res = requests.get(search_url, params={'query': title, 'limit': 1, 'fields': 'abstract'}, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data.get('total', 0) > 0:
                return data['data'][0].get('abstract')
    except:
        pass
    return None

def update_excel_and_save_abstracts(input_file, output_file):
    # 确保文件夹结构存在
    base_path = os.path.dirname(input_file)
    abs_dir = os.path.join(base_path, "abstracts")
    os.makedirs(abs_dir, exist_ok=True)

    df = pd.read_excel(input_file)
    if 'Abstract_Link' not in df.columns:
        df['Abstract_Link'] = ""

    print(f"开始抓取摘要，文件将存入: {abs_dir}")

    for index, row in tqdm(df.iterrows(), total=df.shape[0]):
        # 生成唯一文件名 (基于标题)
        paper_id = slugify(str(row['Title'])[:50])
        filename = f"{paper_id}.json"
        full_abs_path = os.path.join(abs_dir, filename)

        # 如果文件已存在，跳过请求
        if os.path.exists(full_abs_path):
            df.at[index, 'Abstract_Link'] = filename
            continue

        # 获取摘要
        abstract_text = get_abstract_by_id(row.get('DOI'), row['Title'])
        
        if abstract_text:
            # 存储为结构化 JSON
            content = {
                "title": row['Title'],
                "doi": row.get('DOI'),
                "abstract": abstract_text
            }
            with open(full_abs_path, 'w', encoding='utf-8') as f:
                json.dump(content, f, ensure_ascii=False, indent=4)
            
            df.at[index, 'Abstract_Link'] = filename
        else:
            df.at[index, 'Abstract_Link'] = "Not_Found"

        time.sleep(1.2) # API 频率限制

    # 保存更新后的 Excel 索引表
    df.to_excel(output_file, index=False)
    print(f"处理完成！索引表已保存至: {output_file}")

if __name__ == "__main__":
    INPUT = "output/IJRR_Planning_2022_2025.xlsx"
    OUTPUT = "output/IJRR_Indexed_Main.xlsx"
    update_excel_and_save_abstracts(INPUT, OUTPUT)