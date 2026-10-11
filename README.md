# SmartPrint · 扫码打印

[![CI](https://github.com/JunyuZhan/smartprint-tools/actions/workflows/ci.yml/badge.svg)](https://github.com/JunyuZhan/smartprint-tools/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

办公室共享打印机改造方案：**墙上贴一张二维码，手机扫码 → 上传文件 → 一键打印**。
支持图片 / PDF / Word 文档，支持彩色/黑白、单双面、份数、页码范围设置，局域网与公网（Cloudflare / FRP）均可使用。完全免费、本地运行、无需注册。

```
┌─────────────┐   扫码      ┌──────────────────────────┐   上传/设置/打印   ┌──────────┐
│  手机浏览器   │ ─────────▶ │  SmartPrint（办公室电脑）  │ ◀──────────────── │  打印机   │
│  （微信扫一扫）│            │  Web 服务 + 打印引擎       │ ──── GDI 打印 ───▶ │ 取件即可   │
└─────────────┘            └──────────────────────────┘                  └──────────┘
   内网：http://192.168.x.x:8866
   外网：Cloudflare 隧道 / FRP / 自定义反代
```

## 快速开始

### 方式一：源码运行（开发/调试）

需要 Python 3.10+。以下命令中 `python` 请替换为你机器上的解释器命令（`py -3`、`python3` 均可）。

```bat
python -m pip install -r requirements.txt
python server.py
```

> 建议在项目目录创建虚拟环境隔离依赖：`python -m venv .venv`，之后用 `.venv\Scripts\python.exe` 运行。

启动后：
- 手机打印页：`http://<本机局域网IP>:8866/`（页面上有二维码）
- 管理页（仅本机）：`http://127.0.0.1:8866/admin`

### 方式二：打包成绿色版 exe（推荐，装到办公室电脑）

```bat
build.bat      # 产物在 dist\SmartPrint\SmartPrint.exe
install.bat    # （可选）一键安装到本机 + 桌面快捷方式
```

把 `dist\SmartPrint` 整个文件夹复制到办公室电脑，双击 `SmartPrint.exe` 即可。

> 首次运行会弹出 Windows 防火墙提示，请勾选「专用网络」允许访问，手机才能连上。

## 使用流程

1. 打开管理页 → 「状态」标签：确认当前地址，点「打印二维码海报」打出一张海报贴到墙上；
2. 手机用微信/相机扫墙上二维码 → 打开打印页面；
3. 选择文件（可多选）→ 设置黑白/彩色、单双面、份数等 → 点「立即打印」；
4. 到打印机取件。

## 网络访问方式（管理页 → 设置）

| 方式 | 适用场景 | 说明 |
|------|---------|------|
| 局域网直连（默认） | 办公室内网 | 零配置；二维码地址为 `http://局域网IP:8866` |
| Cloudflare Quick | 免账号公网 | 自动下载 cloudflared，生成 `xxx.trycloudflare.com` 临时地址；重启后地址变化，需重打海报 |
| Cloudflare Named（token/配置） | 自有域名公网 | 地址固定为 `https://你的域名`，需在 Cloudflare 后台创建 Tunnel |
| FRP | 自有域名公网 | 填写 frpc.exe、frpc.toml、域名，地址固定 |
| 自定义 | 任意反代/端口映射 | 填入已映射到本机端口的公网地址即可 |

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

## 支持的打印设置

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
| 图片 jpg/png/bmp/webp/tiff/gif | 转 PDF 后打印 |
| Word .doc/.docx/.rtf/.wps/.odt | 自动调用 Word / WPS / LibreOffice 转 PDF 后打印（办公室电脑需安装三者之一） |

## 安全提示

- **公网使用时强烈建议在管理页设置访问口令**（手机端首次访问需输入）；
- 本程序仅做「上传即打印」，没有删除/读取电脑文件的能力，但仍请勿把公网地址发给陌生人；
- 上传的文件按「保留天数」（默认 7 天）自动清理。

## 常见问题

**Q：手机打不开页面？**
A：① 确认手机和电脑在同一网络；② 检查 Windows 防火墙是否放行端口（默认 8866）；③ 管理页「状态」查看当前地址是否正确。

**Q：Word 文件打印报「转换失败」？**
A：办公室电脑需安装 Microsoft Word 或 WPS（或 LibreOffice）任一。WPS 官方个人版免费。

**Q：二维码打出来扫不了？**
A：确认打印机选的是「彩色」且二维码完整无褶皱；Quick Tunnel 模式下地址会变，需重新打印海报。

**Q：怎么让电脑关机后自动恢复？**
A：管理页「设置」勾选「随系统开机自动启动」，或托盘菜单里开启。建议办公室电脑关闭自动休眠。

**Q：端口被占用？**
A：管理页修改端口后重启应用；或在命令行 `py -3 server.py --port 9000` 临时指定。

**Q：想用手机打印时看到别人传的文件？**
A：本程序文件列表按设备显示（每个手机看到的是自己上传的任务），且设置口令后更安全。

## 目录结构

```
Smartprint-tools/
├── server.py              # 入口
├── smartprint/
│   ├── app.py             # Web 服务与 API
│   ├── printer.py         # Windows GDI 打印引擎
│   ├── converters.py      # 图片/Word → PDF
│   ├── jobs.py            # 打印任务队列
│   ├── tunnel.py          # 局域网/Cloudflare/FRP
│   ├── qr.py              # 二维码与海报
│   ├── autostart.py       # 开机自启
│   ├── tray.py            # 托盘图标
│   └── web/               # 手机页 + 管理页
├── tests/                 # 自动化测试（63 项）
│   ├── test_core.py       # 纯逻辑：页码/配置/转换/二维码
│   ├── test_app_api.py    # Web API 全部路由（mock 打印机）
│   ├── test_jobs.py       # 打印任务队列与失败路径
│   ├── test_converters.py # 文件转换各格式与失败路径
│   ├── test_tunnel_cfg.py # 隧道配置校验
│   ├── smoke_check.py     # Windows 打印冒烟（手动运行）
│   └── tunnel_check.py    # 真实隧道联调（手动运行）
├── config.json            # 运行配置（自动生成）
├── data/                  # 上传文件（自动清理）
├── logs/                  # 运行日志
├── build.bat / install.bat / smartprint.spec
├── requirements.txt
└── pytest.ini
```

## 开发与测试

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install pytest pyinstaller
python -m pytest tests -v      # 63 项测试，Windows / Linux 均需通过
python -m compileall -q smartprint server.py tests
```

- 提交代码前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)；
- 发现安全问题请走 [SECURITY.md](SECURITY.md) 的私密上报流程；
- 变更记录见 [CHANGELOG.md](CHANGELOG.md)。

## 技术栈

Python 3.10+ · Flask + Waitress · pywin32 (GDI) · PyMuPDF · Pillow · qrcode · pystray · cloudflared/frpc
