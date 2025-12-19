# step2_fetch_abstracts.py (优化版)
import pandas as pd
import requests
import time
from tqdm import tqdm

def get_abstract_by_id(doi, title):
    """
    优先用 DOI 查，没有 DOI 再用 Title 查
    """
    # 1. 尝试使用 DOI
    if pd.notna(doi) and doi != "":
        url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
        params = {'fields': 'abstract'}
        try:
            res = requests.get(url, params=params, timeout=10)
            if res.status_code == 200:
                return res.json().get('abstract', "No abstract in SS database")
        except:
            pass # 失败了进入下一步标题查询

    # 2. 尝试使用标题搜索
    search_url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {'query': title, 'limit': 1, 'fields': 'abstract'}
    try:
        res = requests.get(search_url, params=params, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data.get('total', 0) > 0:
                return data['data'][0].get('abstract', "No abstract found")
    except:
        pass
    
    return "Not Found"

def update_excel(input_file, output_file):
    df = pd.read_excel(input_file)
    if 'Abstract' not in df.columns: df['Abstract'] = ""

    for index, row in tqdm(df.iterrows(), total=df.shape[0]):
        if pd.isna(row['Abstract']) or row['Abstract'] == "" or row['Abstract'] == "Not Found":
            # 传入 DOI 和 Title
            abstract = get_abstract_by_id(row.get('DOI'), row['Title'])
            df.at[index, 'Abstract'] = abstract
            time.sleep(1.2) # 严格遵守频率限制

    df.to_excel(output_file, index=False)
    print("更新完成")

if __name__ == "__main__":
    update_excel("output/IJRR_Planning_2022_2025.xlsx", "IJRR_Final_Results.xlsx")