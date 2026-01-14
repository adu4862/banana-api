# Lovart Backend 部署指南 (BitBrowser 版)

本指南介绍如何配置和部署基于 **比特浏览器 (BitBrowser)** 的自动化环境，支持 **Windows** 和 **macOS**。

## 1. 环境准备 (通用)

### 1.1 安装比特浏览器
1.  **下载**: 访问 [比特浏览器官网](https://www.bitbrowser.cn/) 下载对应系统的版本。
    *   **Windows**: 下载 Windows 版本。
    *   **macOS**: 下载 macOS 版本 (支持 M1/M2/M3 Apple Silicon 及 Intel)。
2.  **安装与登录**: 安装后注册并登录账号。

### 1.2 配置比特浏览器 API
自动化脚本依赖本地 API 接口来控制浏览器。

1.  打开比特浏览器客户端。
2.  进入 **“设置” (Settings)** -> **“本地设置” (Local Settings)**。
3.  找到 **“开启扩展插件/自动化端口”** 选项，将其设置为 **开启** 状态。
4.  确保端口号为 `54345`（这是脚本默认配置，如需修改请同步修改 `lovart_login.py` 中的 `BITBROWSER_API_URL`）。
5.  **重要**: 部署期间必须保持比特浏览器客户端在后台运行。

### 1.3 创建并获取浏览器窗口 ID
你需要预先创建好用于自动化的浏览器窗口，并获取它们的 ID。

1.  在“浏览器窗口”列表中，创建所需的窗口（建议配置好代理 IP）。
2.  在列表表头右键，勾选显示 **“ID”** 列（注意是长字符串 ID，不是序号）。
3.  复制这些 ID。

### 1.4 配置项目代码
打开项目文件 `h:\lovart-banana-backend\lovart_login.py`，找到 `BITBROWSER_IDS` 配置项：

```python
# Configure your Browser IDs here. Ensure you have enough IDs for the pool size.
BITBROWSER_IDS = [
    "你的窗口ID_1", 
    "你的窗口ID_2", 
    "你的窗口ID_3",
    # ... 根据并发池大小添加更多
]
```
将你复制的 ID 填入该列表。如果 ID 数量不足，脚本会尝试自动创建新窗口（需确保 API 可用）。

> **注意**: `LOVART_POOL_SIZE` 环境变量（默认为 6）决定了并发数量，请确保 `BITBROWSER_IDS` 中的 ID 数量足够覆盖并发池大小。

---

## 2. Windows 部署

### 方法 A：使用启动脚本 (推荐)
项目内置了 `start_server.bat` 脚本，可自动处理虚拟环境和依赖安装。

1.  双击运行 `start_server.bat`。
2.  脚本会自动安装 Python 依赖（如果尚未安装）。
3.  看到 `Running on http://0.0.0.0:5005` (或 5000) 即表示服务启动成功。

### 方法 B：手动运行
1.  安装依赖：
    ```bash
    pip install -r requirements.txt
    ```
2.  启动服务：
    ```bash
    python main.py
    ```

---

## 3. macOS 部署

### 3.1 前置要求
*   **Python 3.9+**: 建议使用 `brew install python` 安装。
*   **比特浏览器**: 确保已安装并运行 macOS 版本，且 API 已开启 (端口 54345)。

### 3.2 代理配置 (重要)
脚本 `lovart_login.py` 中针对 macOS 有特定的代理配置逻辑（用于 API 请求，如邮箱验证、图片上传等，**不是**浏览器内的代理）。

*   **默认配置**: 脚本默认假设使用 **Clash Verge**，SOCKS5 端口为 `7898`。
    ```python
    if platform.system().lower() == "darwin": # macOS
        PROXY_PORT = 7898 # Clash Verge SOCKS port
    ```
*   **如何修改**: 如果你使用其他代理工具（如 V2RayU, Surge 等）或端口不同，请修改 `lovart_login.py` 中的 `PROXY_PORT` 变量，或者确保你的代理工具监听 `7898` 端口。

### 3.3 启动服务
项目提供了 `start_server.sh` 脚本，方便在 macOS/Linux 上运行。

1.  打开终端 (Terminal)，进入项目目录。
2.  赋予脚本执行权限：
    ```bash
    chmod +x start_server.sh
    ```
3.  运行脚本：
    ```bash
    ./start_server.sh
    ```
    *脚本会自动创建 `.venv` 虚拟环境，安装依赖，并启动服务。*

### 3.4 后台运行 (可选)
如果希望服务在后台运行，可以使用 `nohup`：

```bash
nohup ./start_server.sh > server.log 2>&1 &
```
查看日志：`tail -f server.log`

---

## 4. 常见问题排查

### Q: macOS 上报错 `Connection refused` (API 连接失败)？
*   确认比特浏览器 macOS 版已启动。
*   确认“本地设置”中 API 端口是否为 `54345`。
*   macOS 的防火墙或安全设置可能拦截本地连接，尝试关闭防火墙或允许比特浏览器连接。

### Q: 报错 `ModuleNotFoundError: No module named 'backend'`？
*   这是 Python 路径问题。请确保在项目根目录下运行 `main.py`。
*   使用 `start_server.bat` (Windows) 或 `start_server.sh` (macOS) 通常能避免此问题，因为它们会自动设置工作目录。

### Q: 脚本运行中途报错 `Target closed`？
*   不要手动关闭由脚本调起的浏览器窗口。
*   脚本会自动管理窗口的开启和关闭。如果窗口意外关闭，脚本会尝试重试。

### Q: 端口被占用？
*   macOS 脚本默认使用 `5005` 端口，并会尝试自动清理占用该端口的进程。
*   如需更改，编辑 `start_server.sh` 或 `start_server.bat` 中的 `PORT` 变量。
