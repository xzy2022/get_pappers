# 论文自动筛选流水线

本项目提供一键式流程：多源 DBLP 搜索 → Semantic Scholar 摘要拉取 → AI 相关性评审，可断点续跑。

## 快速开始

1) 安装依赖（建议 venv）
```bash
pip install -r requirements.txt
# 若无 requirements.txt，可直接安装：
# pip install pandas requests tqdm openai python-dotenv
```

2) 配置 API Key  
在 `.env` 写入：
```
DEEPSEEK_API_KEY=你的key
```
（默认使用 DeepSeek 的 `deepseek-chat`，可在 `run_pipeline.py` 中修改模型/提示词）

3) 运行全流程
```bash
python run_pipeline.py
```
执行结束会打印输出文件路径，默认在 `output/` 下：
- `<run_name>_search.xlsx`：DBLP 搜索结果（去重、按年排序）
- `<run_name>_indexed.xlsx`：摘要索引表，列 `Abstract_Link` 指向本地 JSON
- `abstracts/`：摘要 JSON 存放目录
- `<run_name>_analysis.xlsx`：AI 打分结果，包含 `AI_Score`、`AI_Reason`

## 主要文件
- `run_pipeline.py`：可编辑的总控入口，调整期刊/会议、关键词、起始年份、模型、提示词等。
- `paper_pipeline.py`：流水线核心逻辑与数据类，提供 `run_full_pipeline` 等可复用函数。
- `step1_fetch_dblp.py` / `step2_fetch_abstracts.py` / `step3_ai_relevance_analysis.py`：旧版分步脚本，保留以供参考。

## 配置要点
- 期刊/会议：`run_pipeline.py` → `build_configs()` 里的 `targets` 列表，元素为 `SearchTarget("stream_key", "简称")`。
- 搜索关键词：`run_pipeline.py` → `build_configs()` 的 `keywords` 列表；起始年份在同处的 `start_year`。
- 模型与 API：`run_pipeline.py` → `AIConfig` 构造处，改 `model`、`base_url`；`paper_pipeline.py` 中 `AIConfig.api_key_env` 控制 API Key 环境变量名（默认 `DEEPSEEK_API_KEY`）。
- AI 分析提示词：`paper_pipeline.py` 中 `DEFAULT_SYSTEM_PROMPT`（可直接改），或在 `run_pipeline.py` 的 `AIConfig(system_prompt=...)` 传入自定义提示词。
- 速率与并发：`run_pipeline.py` → `AIConfig.batch_size`、`AIConfig.max_workers` 控制评分并发；`PipelineRunConfig` 的 `abstract_sleep` 控制摘要抓取节奏；`dblp_limit` 控制单次 DBLP 拉取上限。

## 断点续跑
- **搜索 (Step1)**：`PipelineRunConfig.resume=True` 时，若已有 `<run_name>_search.xlsx` 则直接复用。
- **AI 评分 (Step3)**：每批次会写检查点 `analysis.xlsx.ckpt.json`。重跑时自动跳过已评分条目，仅补缺，保证 RowId 对齐。若需要全量重跑，删除 `analysis.xlsx` 与对应的 `.ckpt.json` 即可。

## 常见问题
- 提示找不到 Key：检查 `.env` 或环境变量 `DEEPSEEK_API_KEY`。
- 想限制抓取量：在 `PipelineRunConfig` 中调小 `dblp_limit` 或关键词范围。
- 想更改存储目录：修改 `PipelineRunConfig.output_dir` 和 `abstract_dir_name`。

## 最小示例（代码内直接调用）
```python
from paper_pipeline import run_full_pipeline, PipelineRunConfig, AIConfig, SearchTarget, DEFAULT_SYSTEM_PROMPT

cfg = PipelineRunConfig(
    run_name="demo",
    keywords=["planning"],
    targets=[SearchTarget("conf/icra", "ICRA")],
    start_year=2023,
)
ai_cfg = AIConfig(system_prompt=DEFAULT_SYSTEM_PROMPT, model="deepseek-chat")
paths = run_full_pipeline(cfg, ai_cfg)
print(paths)
```

跑通后，可根据自己的领域调整提示词、目标列表与关键词，直接复用。***
