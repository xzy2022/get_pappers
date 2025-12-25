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
你是一个针对“野外移动机器人非结构化道路感知与规划”领域的资深审稿人。
你的任务是评估论文摘要，判断其对于综述“非结构化道路的可通行估计（Traversability Estimation in Unstructured Environments）”的参考价值。

该综述旨在调研如何利用几何信息、视觉语义、自监督学习或不确定性理论，来解决复杂地形（泥泞、碎石、草地、坡度）下的通行能力评估问题。

评分标准 (1-5分)：

* 5分 (必读 - 核心对标)：
  文章必须针对 **非结构化环境(Off-road/Unstructured)**，且满足以下任一条件：
  1. **核心任务**：明确提出了“可通行性估计(Traversability Estimation)”、“地形分类(Terrain Classification)”或“通行代价图构建(Costmap Generation)”的完整方案。
  2. **理论深度**：将“不确定性(Uncertainty)”、“证据理论(Evidential Theory)”或“贝叶斯推断”应用于地形评估（这是高价值的研究点）。
  3. **前沿方法**：使用了“自监督学习(Self-supervised Learning)”利用本体感知(Proprioceptive)信号指导视觉学习。

* 4分 (推荐 - 高度相关)：
  虽未直接提出完整的通行性评估系统，但提供了关键支撑技术：
  1. **关键感知**：针对野外环境的高精度“语义分割(Off-road Segmentation)”或“3D激光雷达地形建图(Elevation Mapping)”。
  2. **数据集**：发布了包含可通行性标注的野外数据集（对于综述很重要）。
  3. **通用技术**：在通用环境中提出的创新可通行性算法，由于方法新颖（如基于Transformer、NeRF），极具迁移价值。

* 3分 (一般 - 上下游文献)：
  1. **下游规划**：假设地图已知，只讨论A*、RRT*等“路径规划”算法（这是综述的下一步，但不是核心）。
  2. **上游SLAM**：仅关注定位精度(Pose Estimation)的野外SLAM，未涉及环境语义或物理属性。
  3. **简单几何**：仅基于简单的坡度或台阶检测，缺乏深度学习或多模态融合。

* 2分 (弱相关)：
  1. **结构化道路**：专注于城市道路（车道线检测、交通灯识别），与野外环境差异过大。
  2. **纯理论**：没有机器人应用背景的纯计算机视觉算法。

* 1分 (无关)：
  与移动机器人、环境感知、自动驾驶完全无关的内容。

输出要求：
1. 仅输出一个标准的 JSON 数组格式，不要包含任何 Markdown 标记。
2. 数组对象格式：{"id": 原始序号, "score": 整数, "reason": "简练中文理由"}
3. Reason 必须包含两部分信息：
   - **场景**：(如“野外”、“城市”、“通用”)
   - **核心技术/流派**：(如“自监督学习”、“语义-几何融合”、“证据理论”、“高程图分析”)。
"""

# -----------------------------------------------------------------------------
# 2. 更新后的 build_configs 函数
# -----------------------------------------------------------------------------

def build_configs():
    targets = [
        SearchTarget("journals/ijrr", "IJRR"),
        SearchTarget("journals/trob", "TRO"),
        SearchTarget("journals/jfr", "JFR"),       # 【核心】越野/野外机器人必看
        SearchTarget("journals/ral", "RA-L"),      # 机器人快报，量大管饱，新颖
        SearchTarget("conf/icra", "ICRA"),
        SearchTarget("conf/iros", "IROS"),         
        SearchTarget("conf/rss", "RSS"),
        SearchTarget("conf/cvpr", "CVPR"),         # 视觉特征提取
        SearchTarget("conf/neurips", "NeurIPS"),   # 理论深度
        SearchTarget("conf/iv", "IV"),           
        # IV (Intelligent Vehicles Symposium) 也是道路(即便是非结构化)规划的常客
    ]

    run_cfg = PipelineRunConfig(
        run_name="evidential_mapping_survey", # 修改运行名称以区分
        # 关键词组合：包含建图、不确定性、核心算法名词
        keywords=[
          # 1. 核心场景与任务 (最直接的命中)
          "off-road traversability",
          "unstructured road traversability",
          "terrain traversability",
          "traversability estimation",

          # 2. 语义与感知驱动 (视觉派)
          "semantic terrain classification",
          "off-road semantic segmentation",
          
          # 3. 几何与建图驱动 (几何派)
          "elevation map traversability",
          "traversability mapping",

          # 4. 学习与自监督 (当前热点，适合综述的"Future Work"或"SOTA"部分)
          "self-supervised traversability",
          "learning traversability",

          # 5. 不确定性与证据理论 (响应你的 evidential 需求)
          "uncertainty-aware traversability",
          "evidential occupancy map", 
          "evidential deep learning mapping" 
        ],     
        targets=targets,
        start_year=2022, # 建议从2022开始，因为EDL在建图的应用比较新
        output_dir="output",
        dblp_sleep=1.0,  # 搜索关键词和期刊会议范围都大时，适当增大间隔以防封禁
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
