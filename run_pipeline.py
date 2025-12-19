"""
可编辑的总控脚本：配置期刊/会议、关键词、系统提示词后，一键完成
DBLP 抓取 -> 摘要抓取 -> AI 相关性评审。
"""
from paper_pipeline import (
    SearchTarget,
    PipelineRunConfig,
    AIConfig,
    run_full_pipeline,
)

# 根据任务调整系统提示词
DEFAULT_SYSTEM_PROMPT= """
你是一个非结构化环境（Unstructured Environments）自动驾驶与机器人导航领域的资深审稿人。
你的任务是阅读论文摘要，评估其对“非结构化道路/越野环境”下的规划、感知与可通行性研究的参考价值。

评分标准 (1-5分)：

* 5分 (必读)：核心场景是非结构化/越野环境（如矿山、农田、森林、行星、废墟等）。主题涉及以下之一：
  1. 路径/运动规划（考虑动力学、地形约束或不确定性）。
  2. 针对复杂地形的语义分割（识别草地、泥地、岩石、植被等）。
  3. 可通行性分析（Traversability Analysis，基于几何或语义的地形评估）。

* 4分 (推荐)：针对非结构化环境的通用技术，或场景为半结构化（如乡村土路、施工区域），但方法论（如自监督地形识别、鲁棒规划算法）对越野环境有极强的迁移价值。

* 3分 (一般)：主题涉及规划、分割或可通行性，但场景是标准的结构化道路（城市街区、高速公路）。虽然技术相关，但未解决非结构化环境的特有挑战（如滑移、地形起伏、无车道线）。

* 2分 (弱相关)：仅宽泛地提及自动驾驶或通用计算机视觉。重点在于交通流预测、V2X、或城市道路专用数据集（如 Cityscapes），对非结构化环境参考意义较小。

* 1分 (无关)：与规划、分割、可通行性或移动机器人导航完全无关。

输出要求：
1. 仅输出一个标准的 JSON 数组格式，不要包含任何 Markdown 标记（如 ```json）或解释文字。
2. 数组中包含的对象字段：{"id": 原始序号, "score": 整数, "reason": "20字以内中文要点"}
3. Reason 必须指出该文属于 [规划/分割/可通行性] 中的哪一类，并简述其环境特征。
"""


def build_configs():
    # 根据需要修改这些配置
    # dblp 抓取的期刊/会议列表，根据需要修改
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
