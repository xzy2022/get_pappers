import json
import os

def split_json_papers(input_filename='paper_38.json', output_folder='papers2'):
    # 1. 检查输入文件是否存在
    if not os.path.exists(input_filename):
        print(f"错误: 找不到输入文件 '{input_filename}'。请确保JSON数据已保存为该文件名。")
        return

    # 2. 创建输出目录 (如果不存在)
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"已创建输出目录: {output_folder}")

    try:
        # 3. 读取原始 JSON 文件
        with open(input_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 确保数据中有 "papers" 列表
        if "papers" not in data:
            print("错误: JSON结构中未找到 'papers' 键。")
            return

        papers = data["papers"]
        count = 0

        # 4. 遍历并单独保存
        for paper in papers:
            try:
                # 获取 index
                idx = paper.get("paper_info", {}).get("index")
                
                if idx is None:
                    print(f"警告: 跳过一篇论文，因为它没有 index 字段。标题: {paper.get('paper_info', {}).get('title', 'Unknown')}")
                    continue

                # 格式化文件名：例如 6 -> "06.json", 36 -> "36.json"
                # :02d 表示不足两位数时左侧补零
                file_name = f"{idx:02d}.json"
                file_path = os.path.join(output_folder, file_name)

                # 写入单个 JSON 文件
                with open(file_path, 'w', encoding='utf-8') as out_f:
                    # ensure_ascii=False 确保中文能正常显示，而不是显示 \uXXXX
                    # indent=4 确保输出格式美观
                    json.dump(paper, out_f, ensure_ascii=False, indent=4)
                
                print(f"已保存: {file_path}")
                count += 1

            except Exception as e:
                print(f"处理 index 为 {idx} 的论文时出错: {e}")

        print(f"\n处理完成！共拆分出 {count} 个文件到 '{output_folder}' 文件夹。")

    except json.JSONDecodeError:
        print("错误: 读取 JSON 文件失败，请检查文件格式是否正确（例如结尾是否有多余的逗号或缺少括号）。")
    except Exception as e:
        print(f"发生未知错误: {e}")

if __name__ == "__main__":
    # 运行函数
    split_json_papers()