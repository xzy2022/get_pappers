# step1_fetch_dblp.py
import requests
import pandas as pd

def fetch_and_save_from_dblp(stream_key, keyword, start_year=2022, filename="papers.xlsx"):
    url = "https://dblp.org/search/publ/api"
    query = f"stream:{stream_key}: {keyword}"
    params = {'q': query, 'format': 'json', 'h': 1000}
    
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print("DBLP 请求失败")
        return

    data = response.json()
    hits = data.get('result', {}).get('hits', {}).get('hit', [])
    
    rows = []
    for hit in hits:
        info = hit.get('info', {})
        year = int(info.get('year', 0))
        
        if year >= start_year:
            authors_data = info.get('authors', {}).get('author', [])
            if isinstance(authors_data, dict):
                authors_str = authors_data.get('text', '')
            else:
                authors_str = ", ".join([a.get('text', '') for a in authors_data])

            rows.append({
                'Year': year,
                'Title': info.get('title'),
                'Authors': authors_str,
                'Venue': info.get('venue'),
                'URL': info.get('ee'), 
                'DBLP_Key': info.get('key')
            })
            
    df = pd.DataFrame(rows)
    df.to_excel(filename, index=False)
    print(f"成功保存 {len(rows)} 篇论文到 {filename}")

if __name__ == "__main__":
    # 执行抓取
    fetch_and_save_from_dblp("journals/ijrr", "planning", 2022, "IJRR_Planning_2022_2025.xlsx")