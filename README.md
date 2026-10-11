# SmartPrint · 扫码打印

> 办公室共享打印机改造方案：**墙上贴一张二维码，手机扫码 → 上传文件 → 一键打印**。
> 完全免费、本地运行、无需注册，局域网与公网（Cloudflare / FRP）均可使用。

[![CI](https://github.com/JunyuZhan/smartprint-tools/actions/workflows/ci.yml/badge.svg)](https://github.com/JunyuZhan/smartprint-tools/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

---

## 特性

- 📱 **扫码即用**：手机扫码打开网页，上传文件、设置参数、一键打印，无需安装任何 App
- 🖨️ **格式全面**：PDF / 图片（jpg、png、bmp、webp、tiff、gif）/ Word 系（doc、docx、rtf、wps、odt）
- ⚙️ **打印设置**：彩色/黑白、单双面（长边/短边）、份数（1–99）、页码范围、图片方向与适配
- 🌐 **多网络方式**：局域网直连（零配置）/ Cloudflare Quick Tunnel（免账号）/ Cloudflare Named Tunnel（自有域名）/ FRP / 自定义反代
- 🧹 **省心运维**：随系统开机自启（可关闭）、系统托盘、任务队列、上传文件定时清理、管理页仅限本机
- 🆓 **免费开源**：MIT 协议，绿色免安装（PyInstaller 打包），中文界面

```
┌─────────────┐   扫码      ┌──────────────────────────┐   上传/设置/打印   ┌──────────┐
│  手机浏览器   │ ─────────▶ │  SmartPrint（办公室电脑）  │ ◀──────────────── │  打印机   │
│  （微信扫一扫）│            │  Web 服务 + 打印引擎       │ ──── GDI 打印 ───▶ │ 取件即可   │
└─────────────┘            └──────────────────────────┘                  └──────────┘
   内网：http://192.168.x.x:8866
   外网：Cloudflare 隧道 / FRP / 自定义反代
```

---

## 快速开始

### 方式一：源码运行（开发 / 调试）

需要 Python 3.10+。

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python server.py
```

启动后：

- 手机打印页：`http://<本机局域网IP>:8866/`（页面上自带二维码）
- 管理页（仅本机可访问）：`http://127.0.0.1:8866/admin`

### 方式二：绿色版 exe（推荐，装到办公室电脑）

```bat
build.bat      # 产物在 dist\SmartPrint\SmartPrint.exe
install.bat    # （可选）一键安装到本机 + 桌面快捷方式
```

把 `dist\SmartPrint` 整个文件夹复制到办公室电脑，双击 `SmartPrint.exe` 即可运行。

> 首次运行会弹出 Windows 防火墙提示，请勾选「专用网络」允许访问，手机才能连上。

---

## 使用流程

1. 打开管理页 → 「状态」标签：确认当前地址，点「打印二维码海报」打出一张海报贴到墙上；
2. 手机用微信 / 相机扫墙上二维码 → 打开打印页面；
3. 选择文件（可多选）→ 设置黑白/彩色、单双面、份数等 → 点「立即打印」；
4. 到打印机取件。

---

## 网络访问方式（管理页 → 设置）

| 方式 | 适用场景 | 说明 |
|------|---------|------|
| 局域网直连（默认） | 办公室内网 | 零配置；二维码地址为 `http://局域网IP:8866` |
| Cloudflare Quick | 免账号公网 | 自动下载 cloudflared，生成 `xxx.trycloudflare.com` 临时地址；重启后地址变化，需重打海报 |
| Cloudflare Named（token / 配置） | 自有域名公网 | 地址固定为 `https://你的域名`，需在 Cloudflare 后台创建 Tunnel |
| FRP | 自有域名公网 | 填写 frpc.exe、frpc.toml、域名，地址固定 |
| 自定义 | 任意反代 / 端口映射 | 填入已映射到本机端口的公网地址即可 |

### Cloudflare Named Tunnel（固定域名）示例

```bat
cloudflared tunnel login
cloudflared tunnel create smartprint
cloudflared tunnel route dns smartprint print.example.com
cloudflared tunnel run --token <管理页填写的 token>
```

管理页选择「Cloudflare 隧道 → Named Tunnel(token)」，填入 token 与域名。

### FRP 示例（frpc.toml）

```toml
serverAddr = "你的frps服务器"
serverPort = 7000
auth.token = "你的token"

[[proxies]]
name = "smartprint"
type = "http"
localIP = "127.0.0.1"
localPort = 8866
customDomains = ["print.example.com"]
```

管理页选择「FRP」，填入 frpc.exe、frpc.toml、域名。

---

## 打印设置

- **色彩**：彩色 / 黑白（黑白时按灰度渲染）
- **双面**：单面 / 双面·长边 / 双面·短边
- **份数**：1–99
- **图片方向**：自动 / 纵向 / 横向（仅图片生效）
- **图片大小**：适合页面 / 填满页面 / 原尺寸（仅图片生效）
- **页码范围**：仅 PDF 生效，如 `1-3,5`

## 文件支持

| 类型 | 处理方式 |
|------|---------|
| PDF | PyMuPDF 直接渲染打印 |
| 图片 jpg/png/bmp/webp/tiff/gif | 转 PDF 后打印（自动处理 RGBA、长截图缩放） |
| Word .doc/.docx/.rtf/.wps/.odt | 自动调用 Word / WPS / LibreOffice 转 PDF 后打印（电脑需安装三者之一） |

---

## 安全说明

- **公网使用时强烈建议在管理页设置访问口令**（手机端首次打开需输入）；
- 上传文件名经安全清洗（防路径穿越），文件按保留天数（默认 7 天）自动清理；
- 管理页与管理端 API 仅允许本机访问；
- 本程序只做「上传即打印」，没有读取 / 删除电脑文件的能力；仍请勿把公网地址发给陌生人。

---

## 目录结构

```
Smartprint-tools/
├── server.py              # 入口
├── smartprint/
│   ├── app.py             # Web 服务与 API（Flask）
│   ├── printer.py         # Windows GDI 打印引擎（ctypes 直调 winspool/gdi32）
│   ├── converters.py      # 图片/Word → PDF
│   ├── jobs.py            # 打印任务队列（后台线程）
│   ├── tunnel.py          # 局域网/Cloudflare/FRP 访问管理
│   ├── qr.py              # 二维码与墙上海报
│   ├── autostart.py       # 开机自启（注册表）
│   ├── tray.py            # 系统托盘
│   └── web/               # 手机打印页 + 管理页
├── tests/                 # 自动化测试（63 项）
│   ├── test_core.py       # 纯逻辑：页码/配置/图片转PDF/二维码
│   ├── test_app_api.py    # Web API 全部路由（mock 打印机）
│   ├── test_jobs.py       # 任务队列状态流转与失败路径
│   ├── test_converters.py # 文件转换各格式与失败路径
│   ├── test_tunnel_cfg.py # 隧道配置校验与局域网地址识别
│   ├── smoke_check.py     # Windows 打印引擎冒烟（手动运行）
│   └── tunnel_check.py    # 真实隧道联调（手动运行）
├── config.json            # 运行配置（首次启动自动生成）
├── data/                  # 上传文件（自动清理）
├── logs/                  # 运行日志
├── build.bat / install.bat / smartprint.spec
├── requirements.txt
├── pytest.ini
└── .github/workflows/ci.yml  # Linux 测试 + Windows 打包
```

---

## 测试与可靠性

- **63 项自动化测试**，覆盖 Web API 全部路由、任务队列与失败路径、文件转换、隧道配置、核心逻辑；
- **双环境验证**：Windows 本机与 Ubuntu（GitHub Actions / WSL 复现）均全量通过；
- **CI 流水线**：每次 push 自动跑 Linux 单元测试 + Windows PyInstaller 打包；
- 测试已逼出并修复 3 个真实缺陷（图片解码兜底、隧道配置校验顺序、跨平台文件名清洗），详见 [CHANGELOG.md](CHANGELOG.md)。

```bat
python -m pytest tests -v      # 全量测试（Windows / Linux 均需通过）
python -m compileall -q smartprint server.py tests   # 语法检查
```

---

## 常见问题

**Q：手机打不开页面？**
A：① 确认手机和电脑在同一网络；② 检查 Windows 防火墙是否放行端口（默认 8866）；③ 管理页「状态」查看当前地址。

**Q：Word 文件打印报「转换失败」？**
A：办公室电脑需安装 Microsoft Word 或 WPS（或 LibreOffice）任一，WPS 官方个人版免费。

**Q：二维码打出来扫不了？**
A：确认打印机选的是「彩色」且二维码完整无褶皱；Quick Tunnel 模式下地址会变，需重新打印海报。

**Q：电脑关机后怎么自动恢复？**
A：管理页「设置」勾选「随系统开机自动启动」，或托盘菜单开启；建议办公室电脑关闭自动休眠。

**Q：端口被占用？**
A：管理页修改端口后重启应用；或命令行 `py -3 server.py --port 9000` 临时指定。

**Q：手机端能看到别人传的文件吗？**
A：不能。手机端只显示自己上传的任务（按设备会话隔离），且设置口令后更安全。

---

## 贡献与文档

- 提交代码前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)（跨平台约束、测试要求、PR 规范）
- 社区行为准则见 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- 发现安全问题请走 [SECURITY.md](SECURITY.md) 的私密上报流程（72h 响应承诺）
- 变更记录见 [CHANGELOG.md](CHANGELOG.md)
- 问题 / 需求欢迎开 [Issue](https://github.com/JunyuZhan/smartprint-tools/issues)（内置模板）

## 技术栈

Python 3.10+ · Flask + Waitress · pywin32（GDI）· PyMuPDF · Pillow · qrcode · pystray · cloudflared / frpc

## License

[MIT](LICENSE) © JunyuZhan
