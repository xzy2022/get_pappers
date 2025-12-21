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
# -----------------------------------------------------------------------------
# 1. 更新后的 System Prompt (放在 build_configs 之前)
# -----------------------------------------------------------------------------

DEFAULT_SYSTEM_PROMPT = """
你是一个针对“机器人环境感知与不确定性建图”领域的资深审稿人。
你的任务是评估论文摘要，判断其对于综述“非结构化环境下的不确定性语义建图（Uncertainty-aware Semantic Mapping）”的参考价值。

该综述关注如何利用贝叶斯推断（Bayesian Inference）、证据理论（Dempster-Shafer Theory）或深度学习不确定性（Evidential Deep Learning）来解决越野环境中的感知噪声问题。

评分标准 (1-5分)：

* 5分 (必读 - 核心对标)：
  文章必须同时涉及以下两点：
  1. **方法论**：明确使用了“贝叶斯核推断(BKI)”、“证据理论(DST/D-S)”、“高斯过程(GP)”或“不确定性量化(Uncertainty Quantification)”进行地图构建。
  2. **任务**：是关于“语义建图(Semantic Mapping)”或“占据栅格地图(Occupancy Grid)”，而不仅仅是图像分割。
  (例如：类似 "Evidential Semantic Mapping", "Bayesian Spatial Kernel Smoothing" 的文章)。

* 4分 (推荐 - 高度相关)：
  场景可能是通用环境，但技术极具参考价值。
  例如：提出了一种新的“Evidential Deep Learning”损失函数，或者一种高效的“3D连续语义建图”方法（如 ConvBKI, S-BKI 的变体），虽然没特指越野，但方法可直接迁移。

* 3分 (一般 - 上下游文献)：
  针对非结构化环境（Off-road）的单纯“语义分割”网络（无建图融合），或者假设地图完美的“路径规划”算法。
  它们是建图的输入或输出，但不是建图本身。

* 2分 (弱相关)：
  泛泛的SLAM（仅关注定位Pose estimation），或者通用的自动驾驶数据集介绍，未深入讨论不确定性建模。

* 1分 (无关)：
  与移动机器人感知、建图、决策完全无关的内容（如人脸识别、纯文本大模型等）。

输出要求：
1. 仅输出一个标准的 JSON 数组格式，不要包含任何 Markdown 标记。
2. 数组对象格式：{"id": 原始序号, "score": 整数, "reason": "简练中文理由"}
3. Reason 必须指出该文采用的【核心数学工具】（如贝叶斯、D-S证据、深度集成等）。
"""

# -----------------------------------------------------------------------------
# 2. 更新后的 build_configs 函数
# -----------------------------------------------------------------------------

def build_configs():
    # 增加 CVPR, IROS, NeurIPS 以覆盖感知前端和理论基础
    targets = [
        SearchTarget("journals/ijrr", "IJRR"),
        SearchTarget("journals/trob", "TRO"),
        SearchTarget("journals/jfr", "JFR"),       # 越野/野外机器人核心期刊
        SearchTarget("journals/ral", "RA-L"),      # 机器人快报，很多建图新文章
        SearchTarget("conf/icra", "ICRA"),
        SearchTarget("conf/iros", "IROS"),         # 补充 IROS
        SearchTarget("conf/rss", "RSS"),
        SearchTarget("conf/cvpr", "CVPR"),         # 视觉顶会（语义分割/不确定性）
        SearchTarget("conf/neurips", "NeurIPS"),   # AI顶会（贝叶斯/证据深度学习理论）
    ]

    run_cfg = PipelineRunConfig(
        run_name="evidential_mapping_survey", # 修改运行名称以区分
        # 关键词组合：包含建图、不确定性、核心算法名词
        keywords=[
            "semantic mapping",           # 核心任务
            "uncertainty quantification", # 核心难点
            "Bayesian kernel inference",  # 核心算法 (BKI)
            "evidential deep learning",   # 核心算法 (EDL)
            "Dempster-Shafer",            # 核心理论 (DST)
            "off-road traversability",    # 应用场景
            "continuous occupancy map",   # 地图表达形式
            "evidential fusion"           # 融合策略
        ],     
        targets=targets,
        start_year=2022, # 建议从2022开始，因为EDL在建图的应用比较新
        output_dir="output",
    )

    ai_cfg = AIConfig(
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        model="deepseek-chat", 
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
