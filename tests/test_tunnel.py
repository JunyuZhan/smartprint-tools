# -*- coding: utf-8 -*-
"""Cloudflare Quick Tunnel 端到端测试（等待 DNS 传播后验证）"""
import os
import socket
import sys
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from smartprint import config, tunnel


def main():
    cfg = config.load()
    cfg["access_mode"] = "cloudflare"
    cfg["cloudflare"] = {"mode": "quick", "exe_path": "", "token": "", "config_path": "", "domain": ""}
    print("启动 Quick Tunnel…")
    mgr = tunnel.TunnelManager(cfg)
    mgr.start()
    url = mgr.get_public_url()
    print("等待隧道就绪…")
    for _ in range(120):
        if mgr.status == "running":
            break
        time.sleep(1)
    url = mgr.get_public_url()
    print("公网地址：", url)
    if not url:
        print("错误：", mgr.error)
        return 1
    print("等待 DNS 传播…")
    time.sleep(60)
    host = url.replace("https://", "").split("/")[0]
    ip = socket.gethostbyname(host)
    print("解析 IP：", ip)
    import requests
    r = requests.get(url + "/api/config", timeout=30)
    print("HTTP 状态：", r.status_code)
    print("返回：", r.text[:120])
    mgr.stop()
    return 0 if r.status_code == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
