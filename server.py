# -*- coding: utf-8 -*-
"""SmartPrint 服务入口：
    python server.py            # 开发/直接运行（带托盘）
    python server.py --no-tray  # 无托盘运行
"""
import argparse
import sys
import threading
import time

from waitress import serve

from smartprint import autostart, config, logger, tunnel
from smartprint.app import create_app
from smartprint.logger import get_logger

log = get_logger()


def main():
    ap = argparse.ArgumentParser(description="SmartPrint 扫码打印服务")
    ap.add_argument("--port", type=int, help="监听端口（覆盖 config.json）")
    ap.add_argument("--no-tray", action="store_true", help="不显示系统托盘图标")
    ap.add_argument("--no-tunnel", action="store_true", help="不启动隧道/地址管理")
    args = ap.parse_args()

    cfg = config.load()
    if args.port:
        cfg["port"] = args.port
        config.save(cfg)

    # 同步开机自启
    try:
        autostart.apply(cfg)
    except Exception as e:
        log.error(f"设置开机自启失败：{e}")

    app = create_app(cfg)
    port = int(cfg.get("port", 8866))
    host = cfg.get("host", "0.0.0.0")

    def serve_http():
        log.info(f"HTTP 服务启动：http://127.0.0.1:{port}（管理页 /admin）")
        try:
            serve(app, host=host, port=port, threads=16)
        except Exception as e:
            log.error(f"HTTP 服务异常退出：{e}")

    threading.Thread(target=serve_http, daemon=True).start()

    tunnel_mgr = tunnel.TunnelManager(cfg)
    if not args.no_tunnel:
        tunnel_mgr.start()

    if args.no_tray:
        log.info("运行中（无托盘）…")
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            log.info("已退出")
    else:
        try:
            from smartprint.tray import TrayApp
            tray_app = TrayApp(tunnel_mgr, config.load)
            tray_app.run()
        except Exception as e:
            log.error(f"托盘启动失败（不影响服务）：{e}")
            while True:
                time.sleep(60)


if __name__ == "__main__":
    main()
