# 贡献指南（Contributing Guide）

感谢你愿意为 SmartPrint 贡献代码。这是一个免费开源的办公室扫码打印工具，维护者精力有限，遵循下面的约定能让你的 PR 更快被合并。

## 项目速览

- **语言**：Python 3.10+（Windows 部署）、前端为原生 HTML/JS（无构建步骤）
- **核心模块**：`smartprint/printer.py`（Windows GDI 打印引擎）、`smartprint/app.py`（Flask Web 服务）、`smartprint/jobs.py`（打印队列）、`smartprint/converters.py`（图片/Word→PDF）、`smartprint/tunnel.py`（局域网/Cloudflare/FRP）
- **跨平台约束**：打印引擎与开机自启仅 Windows 可用，代码里已做惰性加载/兜底，**新增功能不得破坏 Linux 上 `pytest` 的通过**（CI 在 ubuntu-latest 上运行）

## 环境准备

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install pytest pyinstaller   # 开发额外依赖
```

## 提 PR 前必须完成

1. **新增功能必须配测试**：测试放在 `tests/test_*.py`，用 pytest 编写，覆盖你改动的逻辑；
2. **跑通全量测试**：
   ```bat
   python -m pytest tests -v
   ```
   本机（Windows）与 CI（Linux）都必须通过；只碰 Windows 特有代码时，也要保证 Linux 收集阶段不报错（不要往测试文件顶层放 Windows 调用，参考 `tests/smoke_check.py` 与 `tests/tunnel_check.py` 的处理）；
3. **跑一遍语法检查**：`python -m compileall -q smartprint server.py tests`
4. **更新文档**：涉及使用方式、配置项、文件支持的变化，同步更新 `README.md`；行为变化记入 `CHANGELOG.md`。

## 代码约定

- 中文注释与中文用户可见文案（页面、错误提示、日志），保持与现有代码一致；
- 打印相关操作放 `printer.py`，文件转换放 `converters.py`，Web 路由放 `app.py`，不要跨模块堆砌；
- Windows 特有 API（winspool/gdi32/winreg 等）一律惰性加载并在非 Windows 平台抛出可读错误，参考 `printer._ensure_winapi()`；
- 用户上传文件路径必须经过 `_safe_name()` 清洗，防止路径穿越（`app.py` 已实现，新增上传入口要复用）；
- 不引入新的重量级依赖；确需引入时先在 Issue 说明理由。

## PR 提交

- 一个 PR 只做一件事，标题用中文简述（如「支持 Excel 转 PDF」「修复队列并发问题」）；
- 在 PR 描述里说明：改了什么、为什么、如何验证（贴 pytest 输出）；
- 合并前 CI 必须全绿（test 与 build 两个 job）。

## 文档与行为准则

- 请阅读并遵守 [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)；
- 发现安全问题请走 [`SECURITY.md`](SECURITY.md) 的流程，**不要**公开披露。
