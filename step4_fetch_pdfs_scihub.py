"""
step4_fetch_pdfs_selenium.py
利用本地 Edge 浏览器 + 学校权限批量下载 PDF。
支持 IEEE Xplore 自动下载。
"""

import os

import time
import re
import pandas as pd
from tqdm import tqdm

from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from webdriver_manager.microsoft import EdgeChromiumDriverManager

# ================= 配置区域 =================
INPUT_EXCEL = "output/Literature_Review_Results.xlsx" # 您的分析结果文件
OUTPUT_PDF_DIR = os.path.abspath("output/pdf")        # 必须是绝对路径
MIN_AI_SCORE = 4                                      # 下载评分阈值
# ===========================================

def slugify(value: str) -> str:
    """文件名合法化"""
    if not isinstance(value, str): return "untitled"
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[-\s]+", "_", value)

def init_driver(download_dir):
    """初始化 Edge 驱动，配置自动下载 PDF 而非预览"""
    edge_options = Options()
    
    # 关键配置：设置下载路径，并禁止 PDF 内置预览（强制下载）
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True, # 关键：禁止预览，直接下载
        "plugins.plugins_list": [{"enabled": False, "name": "Chrome PDF Viewer"}]
    }
    edge_options.add_experimental_option("prefs", prefs)

    # --- 直接指向当前目录下的驱动 ---
    # 假设你已经把 msedgedriver.exe 放在了脚本旁边
    driver_path = os.path.join(os.getcwd(), "msedgedriver.exe")
    
    
    if os.path.exists(driver_path):
        print(f"检测到本地驱动，直接使用: {driver_path}")
        # 这里直接指定 executable_path，不再调用 install()
        service = Service(executable_path=driver_path)
    else:
        print("未找到本地驱动，尝试联网下载（可能会失败）...")
        try:
            service = Service(EdgeChromiumDriverManager().install())
        except Exception as e:
            raise FileNotFoundError(f"驱动下载失败且本地未找到 msedgedriver.exe。请手动下载放入脚本目录。\n错误信息: {e}")
    
    # 启动浏览器
    driver = webdriver.Edge(service=service, options=edge_options)
    return driver

def wait_for_download(save_dir, expected_filename, timeout=30):
    """
    等待文件下载完成，并重命名为目标文件名
    Selenium 下载的文件名通常是原始文件名（如 09746358.pdf），我们需要把它改成标题名
    """
    # 记录下载前的文件夹状态
    # 这种方法比较简单粗暴：轮询文件夹里最新的 .pdf 文件
    end_time = time.time() + timeout
    
    while time.time() < end_time:
        # 查找目录下最新的 pdf 文件（忽略已命名的文件，假设下载的是随机名或ID名）
        files = [os.path.join(save_dir, f) for f in os.listdir(save_dir) if f.endswith(".pdf")]
        if not files:
            time.sleep(1)
            continue
            
        # 找到修改时间最新的文件
        latest_file = max(files, key=os.path.getmtime)
        
        # 检查是否还在下载 (.crdownload 或 .tmp) - 这里只列出了 pdf，所以要检查文件是否被占用或大小稳定
        # 简单判定：如果是最近 5 秒内生成的，且不是我们已经重命名过的文件
        if os.path.basename(latest_file) == expected_filename:
            return True # 已经是目标文件了
            
        # 尝试重命名
        try:
            os.rename(latest_file, os.path.join(save_dir, expected_filename))
            return True
        except OSError:
            # 文件占用中（下载未完成），继续等待
            time.sleep(1)
            
    return False

def process_ieee(driver, doi, target_filename):
    """专门处理 IEEE 的逻辑"""
    # 1. 访问 DOI 跳转
    driver.get(f"https://doi.org/{doi}")
    time.sleep(3) # 等待跳转
    
    current_url = driver.current_url
    
    # 2. 提取 arnumber (IEEE 文章 ID)
    # URL 格式通常是: https://ieeexplore.ieee.org/document/9746006/
    match = re.search(r"document/(\d+)", current_url)
    if match:
        arnumber = match.group(1)
        # 3. 构造直接下载链接
        download_url = f"https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber={arnumber}"
        print(f"  -> 识别为 IEEE, 尝试直接下载: {arnumber}")
        driver.get(download_url)
        return True
    return False

def main():
    # 1. 准备数据
    if not os.path.exists(INPUT_EXCEL):
        # 尝试寻找
        files = [f for f in os.listdir("output") if "analysis" in f and f.endswith(".xlsx")]
        if files:
            input_path = os.path.join("output", files[0])
        else:
            print("找不到输入 Excel 文件")
            return
    else:
        input_path = INPUT_EXCEL

    if not os.path.exists(OUTPUT_PDF_DIR):
        os.makedirs(OUTPUT_PDF_DIR)

    df = pd.read_excel(input_path)
    if 'AI_Score' in df.columns:
        df['AI_Score'] = pd.to_numeric(df['AI_Score'], errors='coerce').fillna(0)
        target_df = df[df['AI_Score'] >= MIN_AI_SCORE]
    else:
        target_df = df
        
    print(f"待下载文献数: {len(target_df)}")

    # 2. 启动浏览器
    print("\n正在启动 Edge 浏览器...")
    driver = init_driver(OUTPUT_PDF_DIR)
    
    # 3. *** 关键交互步骤 ***
    print("\n" + "="*60)
    print("【请注意】浏览器已打开！")
    print("请在弹出的 Edge 窗口中，手动打开一个新标签页，登录您的学校认证系统/图书馆入口。")
    print("确保您能正常访问 IEEE Xplore 并下载任意一篇论文的 PDF。")
    print("登录完成后，请回到这里按下 [Enter/回车] 键开始自动下载。")
    print("="*60 + "\n")
    input("登录完成后，请按回车键继续...")

    # 4. 开始批量下载
    success_count = 0
    
    for _, row in tqdm(target_df.iterrows(), total=len(target_df), unit="paper"):
        title = row.get('Title', 'Untitled')
        doi = row.get('DOI', '')
        
        if not doi or pd.isna(doi):
            continue
            
        safe_name = slugify(title[:80]) + ".pdf"
        save_path = os.path.join(OUTPUT_PDF_DIR, safe_name)
        
        if os.path.exists(save_path):
            continue

        # print(f"正在处理: {title[:30]}...")
        
        try:
            # 尝试 IEEE 逻辑
            if "10.1109" in str(doi) or "IEEE" in str(row.get('Venue', '')):
                is_triggered = process_ieee(driver, doi, safe_name)
            else:
                # 非 IEEE，简单尝试访问 DOI (如果有些数据库点击直接下载)
                driver.get(f"https://doi.org/{doi}")
                is_triggered = True # 假定触发了，依靠后面 wait_for_download 验证
            
            # 等待下载并重命名
            # 我们给脚本一点时间去“捕捉”新下载的文件
            if is_triggered:
                if wait_for_download(OUTPUT_PDF_DIR, safe_name, timeout=15):
                    # print(f"  [√] 下载成功")
                    success_count += 1
                else:
                    pass
                    # print(f"  [x] 下载超时或未找到文件")
            
            time.sleep(2) # 稍微休息防止请求过快
            
        except Exception as e:
            print(f"  [Error] {e}")

    print(f"\n任务结束，共成功下载 {success_count} 篇。")
    print("请手动关闭浏览器窗口。")
    # driver.quit() # 暂时不自动关闭，方便查看残留情况

if __name__ == "__main__":
    main()