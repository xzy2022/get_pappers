import json
import os

def merge_specific_jsons(input_folder='output', output_folder='merged_output', target_indices=None):
    """
    input_folder: 之前拆分好的json存放的文件夹路径
    output_folder: 拼接后文件存放的路径
    target_indices: 一个包含需要合并的index的列表，如 [1, 2, 36]
    """
    
    # 默认列表，如果未提供
    if target_indices is None:
        target_indices = [1, 2]

    # 1. 检查输入目录
    if not os.path.exists(input_folder):
        print(f"错误: 输入文件夹 '{input_folder}' 不存在。")
        return

    # 2. 创建输出目录
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"已创建输出目录: {output_folder}")

    merged_data = []
    found_count = 0

    print(f"正在准备合并以下 Index 的文件: {target_indices}")

    # 3. 遍历列表并读取文件
    for idx in target_indices:
        # 构造文件名，需要匹配上一个脚本的命名规则 (例如 1 -> 01.json, 36 -> 36.json)
        file_name = f"{idx:02d}.json"
        file_path = os.path.join(input_folder, file_name)

        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    merged_data.append(data)
                    found_count += 1
            except Exception as e:
                print(f"读取文件 {file_name} 时出错: {e}")
        else:
            print(f"警告: 找不到文件 {file_name} (对应 index {idx})，已跳过。")

    # 4. 如果没有找到任何数据，提前结束
    if not merged_data:
        print("未找到任何指定的文件，合并终止。")
        return

    # 5. 生成输出文件名 (例如 1_2_36.json)
    # 将列表中的数字转为字符串，并用下划线连接
    output_filename = "_".join(str(i) for i in target_indices) + ".json"
    output_path = os.path.join(output_folder, output_filename)

    # 6. 保存合并后的文件
    try:
        # 为了保持结构清晰，通常将合并后的列表放在一个 "papers" 键下，或者直接存为一个列表
        # 这里我选择直接存为一个包含多个对象的列表
        with open(output_path, 'w', encoding='utf-8') as out_f:
            json.dump(merged_data, out_f, ensure_ascii=False, indent=4)
        
        print(f"\n成功！")
        print(f"已合并 {found_count} 个文件。")
        print(f"结果已保存至: {output_path}")
        
    except Exception as e:
        print(f"写入文件时出错: {e}")

if __name__ == "__main__":
    # --- 配置区域 ---
    
    # 刚才拆分出来的文件所在的路径
    INPUT_DIR = 'papers2' 
    
    # 结果保存路径
    OUTPUT_DIR = 'merged_output'
    
    # 你想要提取并拼接的论文 Index 列表
    # 你可以在这里修改为你想要的数字，例如 [1, 36, 5]
    TARGET_LIST = [17, 26, 35, 36] 

    # --- 运行脚本 ---
    merge_specific_jsons(INPUT_DIR, OUTPUT_DIR, TARGET_LIST)