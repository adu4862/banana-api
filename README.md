pip install flask playwright camoufox[geoip] browserforge requests colorama
playwright install  # 安装浏览器内核


在 macOS 终端中执行以下命令即可（假设你已经安装了 Python 3）：

1. 克隆/下载项目 到本地。
2. 创建虚拟环境 ：
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. 安装依赖 ：
   ```
   pip install -r requirements.txt
   ```
4. 安装浏览器内核 ：
   ```
   playwright install
   ```
5. 运行项目 ：
   ```
   python3 main.py
   ```
项目启动后，功能体验与 Windows 环境一致。