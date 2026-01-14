# Lovart Backend (BitBrowser Edition)

此项目是一个基于 Python + Playwright + BitBrowser 的 Lovart 自动化后端服务。

## 快速开始

请查看 [DEPLOY.md](DEPLOY.md) 获取详细的部署和配置指南。

## 核心依赖

- **Flask**: 提供 API 接口
- **Playwright**: 浏览器自动化控制
- **BitBrowser**: 提供指纹浏览器环境和本地 API

## 运行要求

1.  **操作系统**: Windows (推荐，因为 BitBrowser 主要在 Windows 上运行) 或 macOS。
2.  **软件**: 必须安装并运行 [比特浏览器 (BitBrowser)](https://www.bitbrowser.cn/)。
3.  **Python**: 3.9+

## 常用命令

安装依赖：
```bash
pip install -r requirements.txt
```

启动服务：
```bash
python main.py
```
