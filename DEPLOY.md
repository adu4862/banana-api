# Lovart Backend 部署指南

本指南将帮助你在 Windows Server 和 Mac mini 上长期运行该项目。

## 1. 通用准备工作

确保服务器满足以下条件：
- **Python**: 已安装 Python 3.9 或更高版本。
- **网络**: 确保防火墙允许访问 `5000` 端口（或你指定的其他端口）。

---

## 2. Windows Server 部署方案

### 方法 A：使用启动脚本（最简单）

1. 将项目文件夹复制到服务器。
2. 双击运行 `start_server.bat`。
3. 首次运行时，它会自动创建虚拟环境、安装依赖和浏览器内核。
4. 保持窗口开启即可。

### 方法 B：设置开机自启（进阶）

如果你希望服务器重启后自动运行，且不需要登录用户：

1. 打开“任务计划程序” (Task Scheduler)。
2. 点击“创建任务” (Create Task)。
3. **常规**: 输入名称 "LovartBackend"，选择 "不管用户是否登录都要运行" (Run whether user is logged on or not)。
4. **触发器**: 新建 -> "启动时" (At startup)。
5. **操作**: 新建 -> "启动程序" -> 选择 `start_server.bat`。
   - **注意**: 在 "起始于" (Start in) 字段中，**必须**填入脚本所在的完整文件夹路径（例如 `C:\lovart-banana-backend\`），否则会找不到文件。
6. 保存并输入密码。

---

## 3. macOS (Mac mini) 部署方案

### 步骤 1：准备脚本
1. 打开终端，进入项目目录。
2. 给启动脚本添加执行权限：
   ```bash
   chmod +x start_server.sh
   ```
3. 手动运行一次 `./start_server.sh` 确保环境安装无误。

### 步骤 2：配置 Launchd (开机自启 & 进程守护)

1. 打开项目根目录下的 `com.lovart.backend.plist` 文件。
2. 修改文件中的路径，将 `/Users/YOUR_USERNAME/path/to/lovart-banana-backend/` 替换为你实际的绝对路径。
   - 例如：如果你的用户名是 `admin`，项目在桌面，路径可能是 `/Users/admin/Desktop/lovart-banana-backend/`。
3. 将修改后的 `.plist` 文件复制到 LaunchAgents 目录：
   ```bash
   cp com.lovart.backend.plist ~/Library/LaunchAgents/
   ```
4. 加载服务：
   ```bash
   launchctl load ~/Library/LaunchAgents/com.lovart.backend.plist
   ```
5. 验证是否运行：
   ```bash
   # 查看服务状态
   launchctl list | grep lovart
   
   # 或者直接查看日志
   tail -f server.log
   ```

### 停止服务
```bash
launchctl unload ~/Library/LaunchAgents/com.lovart.backend.plist
```

---

## 4. 维护与监控

- **日志**: 
  - macOS 日志默认输出在项目目录下的 `server.log` 和 `server_error.log`（需在 plist 中配置路径）。
  - Windows 控制台会直接显示日志，建议定期检查。
- **端口**: 默认监听 `0.0.0.0:5000`。
- **更新代码**: 拉取新代码后，建议重启服务。
  - Windows: 关闭窗口再打开，或重启任务。
  - macOS: `launchctl unload ...` 然后 `launchctl load ...`。

## 5. 常见问题

**Q: 浏览器启动失败？**
A: 确保首次运行已经完成了 `playwright install`。如果服务器无法联网下载浏览器，可以从本地开发机打包 `.venv/Lib/site-packages/playwright/driver/package/.local-browsers` (Windows) 或对应目录到服务器。

**Q: 端口被占用？**
A: 修改启动脚本中的 `PORT` 环境变量。
