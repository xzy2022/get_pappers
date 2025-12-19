# step1_fetch_dblp.py (路径增强版)
import requests
import pandas as pd
import re
import os  # 用于处理文件路径和文件夹创建

def extract_doi(url):
    if not url: return ""
    # 匹配 https://doi.org/ 之后的字符串
    match = re.search(r'doi.org/(10\.\d{4,}/[-._;()/:a-zA-Z0-9]+)', url)
    return match.group(1) if match else ""

def fetch_and_save_from_dblp(stream_key, keyword, start_year=2022, filename="papers.xlsx", save_path="output/"):
    """
    save_path: 默认为 "output/"
    """
    url = "https://dblp.org/search/publ/api"
    query = f"stream:{stream_key}: {keyword}"
    params = {'q': query, 'format': 'json', 'h': 1000}
    
    response = requests.get(url, params=params)
    if response.status_code != 200: 
        print("请求 DBLP 失败")
        return

    data = response.json()
    hits = data.get('result', {}).get('hits', {}).get('hit', [])
    
    rows = []
    for hit in hits:
        info = hit.get('info', {})
        year = int(info.get('year', 0))
        if year >= start_year:
            # 获取作者信息（恢复了之前的逻辑）
            authors_data = info.get('authors', {}).get('author', [])
            if isinstance(authors_data, dict):
                authors_str = authors_data.get('text', '')
            else:
                authors_str = ", ".join([a.get('text', '') for a in authors_data])

            ee_url = info.get('ee', '')
            rows.append({
                'Year': year,
                'Title': info.get('title'),
                'Authors': authors_str,
                'Venue': info.get('venue'),
                'DOI': extract_doi(ee_url),
                'URL': ee_url
            })
            
    if not rows:
        print("未找到符合条件的论文")
        return

    # --- 核心修改：处理保存路径 ---
    # 1. 确保文件夹存在 (exist_ok=True 表示如果文件夹已存在则不报错)
    os.makedirs(save_path, exist_ok=True)
    
    # 2. 拼接完整路径
    full_path = os.path.join(save_path, filename)
    
    # 3. 保存文件
    df = pd.DataFrame(rows)
    df.to_excel(full_path, index=False)
    print(f"成功保存 {len(rows)} 篇论文到: {full_path}")

# step1_fetch_dblp.py 的执行逻辑建议
if __name__ == "__main__":
    # 定义任务列表：(Stream_Key, 简称)
    tasks = [
        ("journals/ijrr", "IJRR"),
        ("journals/trob", "TRO"),
        ("journals/jfr",  "JFR"),
        ("conf/rss",      "RSS"),
        ("conf/icra",     "ICRA")
    ]
    
    keyword = "planning|semantic segmentation|traversability"
    start_year = 2022
    
    for stream_key, short_name in tasks:
        filename = f"{short_name}_test_{start_year}_2025.xlsx"
        print(f"\n--- 正在抓取 {short_name} ---")
        fetch_and_save_from_dblp(stream_key, keyword, start_year, filename)