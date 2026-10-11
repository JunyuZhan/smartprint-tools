# 更新日志（Changelog）

本项目的所有重要变更均记录在此文件。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.0.0] - 2026-10-11

### 新增
- 扫码打印核心流程：手机扫码 → 上传文件 → 设置打印参数 → 一键打印
- 支持文件类型：PDF、图片（jpg/png/bmp/webp/tiff/gif）、Word 系（doc/docx/rtf/wps/odt）
- 打印设置：彩色/黑白、单双面（长边/短边）、份数（1–99）、页码范围、图片方向与适配方式
- 网络访问方式：局域网直连（自动识别本机 IP）、Cloudflare Quick Tunnel（免账号）、Cloudflare Named Tunnel（token/配置文件，自有域名）、FRP、自定义反代
- 墙上海报二维码生成（A4 竖版，可打印贴墙）
- 开机自启（可关闭）、系统托盘图标、任务队列与后台打印、定时清理上传文件
- 可选访问口令保护；管理页仅限本机访问
- PyInstaller 绿色版打包（build.bat / install.bat）
- GitHub Actions CI：Linux 单元测试 + Windows 打包

### 修复
- 图片转 PDF：对 PyMuPDF 无法直接解码的图片格式（如部分 webp/bmp 编码）回退到 Pillow 重编码，保证所有 Pillow 支持的图片可打印
- Cloudflare config 模式：先校验自有域名再启动隧道进程，避免无效配置白启动子进程
- pytest 收集：Windows 专用冒烟脚本与隧道联调脚本改为 `smoke_check.py` / `tunnel_check.py`，不再被 Linux CI 误收集导致失败

### 测试
- 单元测试从 13 项扩展到 63 项，覆盖：Web API 全部路由（上传/打印/权限/管理端/口令）、打印任务队列状态流转与失败路径、文件转换器各格式与失败路径、隧道各模式参数校验与局域网地址识别
- 双环境验证：Windows（本机）与 Ubuntu（WSL 复现 CI 环境）均 63 项通过
