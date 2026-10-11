# -*- coding: utf-8 -*-
"""Cloudflare Quick Tunnel 端到端测试（等待 DNS 传播后验证）"""
# 真实隧道联调脚本，不作为 pytest 测试模块收集（需要网络与外部服务）
__test__ = False

import os
import socket
import sys
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from smartprint import config, tunnel

cfg = config.load()
cfg["access_mode"] = "cloudflare"
cfg["cloudflare"]["mode"] = "quick"
tm = tunnel.TunnelManager(cfg)
print("启动 Quick Tunnel…")
tm.start()

url = ""
for _ in range(150):
    time.sleep(1)
    if tm.public_url:
        url = tm.public_url
        break
    if tm.status == "error":
        print("错误:", tm.error)
        break

if not url:
    print("未获得公网地址")
    tm.stop()
    sys.exit(1)

print("公网地址:", url)
host = url.split("//")[1].split("/")[0]

# 等待 DNS 传播（最多 90 秒）
resolved = False
for i in range(90):
    try:
        ip = socket.gethostbyname(host)
        print(f"  DNS 解析成功（{i + 1}s）: {ip}")
        resolved = True
        break
    except Exception:
        time.sleep(1)
if not resolved:
    print("  DNS 90 秒内未解析")

if resolved:
    import requests
    for i in range(5):
        try:
            r = requests.get(url + "/api/config", timeout=15)
            print("公网访问 /api/config:", r.status_code, "OK" if r.status_code == 200 else r.text[:200])
            break
        except Exception as e:
            print(f"  第{i + 1}次请求失败: {type(e).__name__}")
            time.sleep(3)

tm.stop()
print("隧道已停止")
