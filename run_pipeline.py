"""
可编辑的总控脚本：配置期刊/会议、关键词、系统提示词后，一键完成
DBLP 抓取 -> 摘要抓取 -> AI 相关性评审。
"""
from paper_pipeline import (
    SearchTarget,
    PipelineRunConfig,
    AIConfig,
    DEFAULT_SYSTEM_PROMPT,
    run_full_pipeline,
)


def build_configs():
    # 根据需要修改这些配置
    targets = [
        SearchTarget("journals/ijrr", "IJRR"),
        SearchTarget("journals/trob", "TRO"),
        SearchTarget("journals/jfr", "JFR"),
        SearchTarget("conf/rss", "RSS"),
        SearchTarget("conf/icra", "ICRA"),
    ]

    run_cfg = PipelineRunConfig(
        run_name="offroad_planning",
        # 下面列表中的关键词是或的关系。
        keywords=["planning", "segmentation", "traversability"],     
        targets=targets,
        start_year=2022,
        output_dir="output",
    )

    ai_cfg = AIConfig(
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        model="deepseek-chat",  # 可改 deepseek-reasoner 等
        base_url="https://api.deepseek.com",
        batch_size=5,
        max_workers=5,
    )
    return run_cfg, ai_cfg


def main():
    run_cfg, ai_cfg = build_configs()
    paths = run_full_pipeline(run_cfg, ai_cfg)
    print("\n=== Pipeline 完成 ===")
    for key, value in paths.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
