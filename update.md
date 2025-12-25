

#### 手动下载 Edge 驱动

Edge webDriver驱动用于让python代码模拟操作浏览器。

1.  打开你的 Edge 浏览器，在地址栏输入 `edge://settings/help`，查看版本号（例如：`120.0.2210.91`）。
2.  访问 [Microsoft Edge WebDriver 下载页面](https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/)。
3.  找到与你浏览器版本号 **完全一致**（或者大版本号一致）的驱动，点击 "x64" 下载。
4.  解压下载的压缩包，将里面的 `msedgedriver.exe` 文件放到你的脚本 `step4_fetch_pdfs_selenium.py` **同级目录下**。

本次实现IEEE文献的自动抓取，但是比较慢。之后需要测试IEEE文章寻找抓取的逻辑并尝试优化；随后再逐步扩展到非IEEE的期刊会议。