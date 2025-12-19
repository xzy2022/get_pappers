"""
Unified pipeline that covers:
1) Fetching papers from DBLP for multiple venues/keywords.
2) Pulling abstracts from Semantic Scholar and indexing them locally.
3) Scoring relevance via a configurable AI prompt.
"""
import os
import re
import json
import time
import concurrent.futures
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional

import pandas as pd
import requests
from tqdm import tqdm
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class SearchTarget:
    """期刊/会议信息"""
    stream_key: str  # e.g. "journals/ijrr"
    name: str        # e.g. "IJRR"


@dataclass
class PipelineRunConfig:
    """单次全流程的配置"""
    run_name: str
    keywords: List[str]
    targets: List[SearchTarget]
    start_year: int = 2022
    output_dir: str = "output"
    abstract_dir_name: str = "abstracts"
    dblp_limit: int = 1000
    abstract_sleep: float = 1.2
    resume: bool = True  # 允许复用已有中间结果


@dataclass
class AIConfig:
    """AI 评审配置"""
    system_prompt: str
    model: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com"
    temperature: float = 0.1
    batch_size: int = 5
    max_workers: int = 5
    timeout: int = 60
    api_key_env: str = "DEEPSEEK_API_KEY"
    api_key: Optional[str] = None


# ---------------------------------------------------------------------------
# Step 1: DBLP 抓取
# ---------------------------------------------------------------------------
def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def extract_doi(url: str) -> str:
    if not url:
        return ""
    match = re.search(r"doi.org/(10\.\d{4,}/[-._;()/:a-zA-Z0-9]+)", url)
    return match.group(1) if match else ""


def fetch_dblp_once(stream_key: str, keyword: str, start_year: int, limit: int) -> List[Dict]:
    url = "https://dblp.org/search/publ/api"
    query = f"stream:{stream_key}: {keyword}"
    params = {"q": query, "format": "json", "h": limit}

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        print(f"[DBLP] 请求失败 ({stream_key}, {keyword}): {exc}")
        return []

    hits = data.get("result", {}).get("hits", {}).get("hit", [])
    rows = []
    for hit in hits:
        info = hit.get("info", {})
        year = int(info.get("year", 0) or 0)
        if year < start_year:
            continue

        authors_data = info.get("authors", {}).get("author", [])
        if isinstance(authors_data, dict):
            authors_str = authors_data.get("text", "")
        else:
            authors_str = ", ".join([a.get("text", "") for a in authors_data])

        ee_url = info.get("ee", "")
        rows.append(
            {
                "Year": year,
                "Title": info.get("title", ""),
                "Authors": authors_str,
                "Venue": info.get("venue", ""),
                "DOI": extract_doi(ee_url),
                "URL": ee_url,
            }
        )
    return rows


def fetch_from_dblp(cfg: PipelineRunConfig) -> Tuple[pd.DataFrame, str]:
    ensure_dir(cfg.output_dir)
    search_path = os.path.join(cfg.output_dir, f"{cfg.run_name}_search.xlsx")

    # 若启用恢复且搜索结果已存在，直接复用
    if cfg.resume and os.path.exists(search_path):
        df_cached = pd.read_excel(search_path)
        print(f"[Step1] 复用已有搜索结果: {search_path} (共 {len(df_cached)} 条)")
        return df_cached, search_path

    all_rows = []
    for keyword in cfg.keywords:
        for target in cfg.targets:
            rows = fetch_dblp_once(target.stream_key, keyword, cfg.start_year, cfg.dblp_limit)
            for row in rows:
                row.update({"Keyword": keyword, "Source": target.name})
            all_rows.extend(rows)

    if not all_rows:
        raise RuntimeError("DBLP 未找到符合条件的论文")

    df = pd.DataFrame(all_rows)
    df = df.sort_values(by=["Year"], ascending=False)
    df = df.drop_duplicates(subset=["DOI", "Title"], keep="first")
    df.to_excel(search_path, index=False)
    print(f"[Step1] 共 {len(df)} 条记录写入 {search_path}")
    return df, search_path


# ---------------------------------------------------------------------------
# Step 2: 抓取摘要 (Semantic Scholar)
# ---------------------------------------------------------------------------
def slugify(value: str) -> str:
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[-\s]+", "_", value)


def get_abstract_by_id(doi: Optional[str], title: str) -> Optional[str]:
    if doi:
        url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
        try:
            res = requests.get(url, params={"fields": "abstract"}, timeout=10)
            if res.status_code == 200:
                return res.json().get("abstract")
        except Exception:
            pass

    search_url = "https://api.semanticscholar.org/graph/v1/paper/search"
    try:
        res = requests.get(
            search_url,
            params={"query": title, "limit": 1, "fields": "abstract"},
            timeout=10,
        )
        if res.status_code == 200:
            data = res.json()
            if data.get("total", 0) > 0:
                return data["data"][0].get("abstract")
    except Exception:
        pass
    return None


def fetch_and_index_abstracts(df: pd.DataFrame, cfg: PipelineRunConfig) -> Tuple[pd.DataFrame, str, str]:
    abs_dir = ensure_dir(os.path.join(cfg.output_dir, cfg.abstract_dir_name))
    df = df.copy()
    if "Abstract_Link" not in df.columns:
        df["Abstract_Link"] = ""

    print(f"[Step2] 抓取摘要并保存至 {abs_dir}")
    for index, row in tqdm(df.iterrows(), total=df.shape[0]):
        paper_id = slugify(str(row["Title"])[:50])
        filename = f"{paper_id}.json"
        full_abs_path = os.path.join(abs_dir, filename)

        if os.path.exists(full_abs_path):
            df.at[index, "Abstract_Link"] = filename
            continue

        abstract_text = get_abstract_by_id(row.get("DOI"), row["Title"])

        if abstract_text:
            content = {"title": row["Title"], "doi": row.get("DOI"), "abstract": abstract_text}
            with open(full_abs_path, "w", encoding="utf-8") as f:
                json.dump(content, f, ensure_ascii=False, indent=4)
            df.at[index, "Abstract_Link"] = filename
        else:
            df.at[index, "Abstract_Link"] = "Not_Found"

        time.sleep(cfg.abstract_sleep)

    indexed_path = os.path.join(cfg.output_dir, f"{cfg.run_name}_indexed.xlsx")
    df.to_excel(indexed_path, index=False)
    return df, indexed_path, abs_dir


# ---------------------------------------------------------------------------
# Step 3: AI 相关性评估
# ---------------------------------------------------------------------------

def _load_ai_client(cfg: AIConfig) -> OpenAI:
    api_key = cfg.api_key or os.getenv(cfg.api_key_env)
    if not api_key:
        raise ValueError(f"未找到 API Key，请设置环境变量 {cfg.api_key_env}")
    return OpenAI(api_key=api_key, base_url=cfg.base_url)


def _read_abstract(abstract_dir: str, link: str) -> str:
    if not link or link == "Not_Found" or pd.isna(link):
        return "无摘要数据。"
    path = os.path.join(abstract_dir, link)
    if not os.path.exists(path):
        return "找不到摘要文件。"
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("abstract", "摘要内容为空。")
    except Exception:
        return "摘要文件损坏。"


def _call_ai(client: OpenAI, ai_cfg: AIConfig, prompt: str):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=ai_cfg.model,
                messages=[{"role": "system", "content": ai_cfg.system_prompt}, {"role": "user", "content": prompt}],
                temperature=ai_cfg.temperature,
                stream=False,
                timeout=ai_cfg.timeout,
            )
            raw_text = response.choices[0].message.content.strip()
            cleaned_text = raw_text.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_text)
        except Exception as exc:
            if "429" in str(exc) or "rate limit" in str(exc).lower():
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))
                    continue
            print(f"[AI] 调用失败: {exc}")
            return None
    return None


def _build_prompt(batch_df: pd.DataFrame, abstract_dir: str) -> Tuple[str, List[int]]:
    user_prompt = "请分析以下文献摘要，并返回 JSON 数组：\n\n"
    indices: List[int] = []

    for i, (idx, row) in enumerate(batch_df.iterrows()):
        abstract = _read_abstract(abstract_dir, row["Abstract_Link"])
        user_prompt += f"[文献 {i+1}]\n标题: {row['Title']}\n摘要: {abstract}\n\n"
        indices.append(idx)
    return user_prompt, indices


def _load_checkpoint(path: str) -> Dict[int, Dict[str, str]]:
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {int(k): v for k, v in data.items()}
    except Exception:
        return {}


def _save_checkpoint(path: str, data: Dict[int, Dict[str, str]]):
    ensure_dir(os.path.dirname(path) or ".")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in data.items()}, f, ensure_ascii=False, indent=2)


def _load_existing_results_from_output(path: str) -> Dict[int, Dict[str, str]]:
    if not os.path.exists(path):
        return {}
    try:
        df_existing = pd.read_excel(path)
        if "AI_Score" not in df_existing.columns or "AI_Reason" not in df_existing.columns:
            return {}
        results = {}
        for _, row in df_existing.iterrows():
            row_id = int(row["RowId"]) if "RowId" in df_existing.columns else _
            if pd.notna(row.get("AI_Score")):
                results[row_id] = {"score": row.get("AI_Score", 0), "reason": row.get("AI_Reason", "")}
        return results
    except Exception:
        return {}


def run_ai_scoring(df: pd.DataFrame, abstract_dir: str, ai_cfg: AIConfig, output_path: str) -> pd.DataFrame:
    client = _load_ai_client(ai_cfg)
    df = df.copy()

    # 为每行创建稳定的行标识，便于恢复
    if "RowId" not in df.columns:
        df["RowId"] = df.index

    # 准备已有结果（输出文件 + 检查点）
    checkpoint_path = output_path + ".ckpt.json"
    results_map: Dict[int, Dict[str, str]] = {}
    results_map.update(_load_existing_results_from_output(output_path))
    results_map.update(_load_checkpoint(checkpoint_path))

    pending_df = df[df["RowId"].map(lambda x: x not in results_map)]

    if len(pending_df) == 0:
        print(f"[Step3] 检测到已有评分，跳过 API 调用，直接写入 {output_path}")
        df["AI_Score"] = df["RowId"].map(lambda x: results_map.get(x, {}).get("score", 0))
        df["AI_Reason"] = df["RowId"].map(lambda x: results_map.get(x, {}).get("reason", "处理遗漏"))
        df = df.sort_values(by="AI_Score", ascending=False)
        df.to_excel(output_path, index=False)
        return df

    chunks = [pending_df.iloc[i : i + ai_cfg.batch_size] for i in range(0, len(pending_df), ai_cfg.batch_size)]

    print(f"[Step3] AI 评审，待处理 {len(pending_df)} 条，共 {len(chunks)} 个批次，并发数 {ai_cfg.max_workers}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=ai_cfg.max_workers) as executor:
        future_to_indices = {}
        for chunk in chunks:
            prompt, indices = _build_prompt(chunk, abstract_dir)
            future = executor.submit(_call_ai, client, ai_cfg, prompt)
            # 将 RowId 对齐
            row_ids = [int(chunk.iloc[j]["RowId"]) for j in range(len(indices))]
            future_to_indices[future] = row_ids

        for future in tqdm(concurrent.futures.as_completed(future_to_indices), total=len(future_to_indices), desc="AI 评审进度"):
            indices = future_to_indices[future]
            try:
                ai_results = future.result()
            except Exception as exc:
                print(f"[AI] 批次异常: {exc}")
                ai_results = None

            for j, row_id in enumerate(indices):
                if ai_results and isinstance(ai_results, list) and j < len(ai_results):
                    results_map[row_id] = {
                        "score": ai_results[j].get("score", 0),
                        "reason": ai_results[j].get("reason", "无理由"),
                    }
                else:
                    results_map[row_id] = {"score": 0, "reason": "AI返回不足或失败"}

            # 每处理一批就落盘检查点，支持断点续跑
            _save_checkpoint(checkpoint_path, results_map)

    df["AI_Score"] = df["RowId"].map(lambda x: results_map.get(x, {}).get("score", 0))
    df["AI_Reason"] = df["RowId"].map(lambda x: results_map.get(x, {}).get("reason", "处理遗漏"))
    df = df.sort_values(by="AI_Score", ascending=False)
    df.to_excel(output_path, index=False)
    print(f"[Step3] 结果写入 {output_path} (检查点保存在 {checkpoint_path})")
    return df


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def run_full_pipeline(run_cfg: PipelineRunConfig, ai_cfg: Optional[AIConfig] = None) -> Dict[str, str]:
    if ai_cfg is None:
        ai_cfg = AIConfig(system_prompt=DEFAULT_SYSTEM_PROMPT)

    df_search, search_path = fetch_from_dblp(run_cfg)
    df_indexed, indexed_path, abs_dir = fetch_and_index_abstracts(df_search, run_cfg)

    analysis_path = os.path.join(run_cfg.output_dir, f"{run_cfg.run_name}_analysis.xlsx")
    run_ai_scoring(df_indexed, abs_dir, ai_cfg, analysis_path)

    return {
        "search_path": search_path,
        "indexed_path": indexed_path,
        "analysis_path": analysis_path,
        "abstract_dir": abs_dir,
    }


__all__ = [
    "SearchTarget",
    "PipelineRunConfig",
    "AIConfig",
    "fetch_from_dblp",
    "fetch_and_index_abstracts",
    "run_ai_scoring",
    "run_full_pipeline",
]
