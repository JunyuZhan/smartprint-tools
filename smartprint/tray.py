# -*- coding: utf-8 -*-
"""SmartPrint 系统托盘图标：快速打开管理页 / 打印二维码海报 / 重启隧道 / 退出"""
import threading
import webbrowser

import pystray
from PIL import Image, ImageDraw

from . import autostart, config, qr
from .logger import get_logger

log = get_logger()


def _make_icon() -> Image.Image:
    img = Image.new("RGB", (64, 64), (33, 120, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([16, 10, 48, 54], fill="white")
    d.rectangle([22, 18, 42, 26], fill=(33, 120, 255))
    d.rectangle([22, 32, 42, 40], fill=(33, 120, 255))
    d.polygon([(32, 4), (36, 10), (28, 10)], fill="white")
    return img


class TrayApp:
    def __init__(self, tunnel_mgr, cfg_path_getter):
        self.tunnel = tunnel_mgr
        self.cfg_getter = cfg_path_getter
        self._icon = None
        self._stop = threading.Event()

    def _admin_url(self) -> str:
        cfg = self.cfg_getter()
        return f"http://127.0.0.1:{cfg.get('port', 8866)}/admin"

    def _open_admin(self, icon, item):
        webbrowser.open(self._admin_url())

    def _print_poster(self, icon, item):
        threading.Thread(target=self._poster_job, daemon=True).start()

    def _poster_job(self):
        try:
            cfg = self.cfg_getter()
            url = self.tunnel.get_public_url()
            if not url:
                url = (self.tunnel.lan_urls or ["http://127.0.0.1"])[0]
            pname = cfg.get("printer", "") or "默认打印机"
            settings = dict(cfg.get("print_defaults", {}))
            qr.print_poster(url, cfg.get("office_name", "扫码打印"), pname, settings)
            log.info("已打印二维码海报")
        except Exception as e:
            log.error(f"打印海报失败：{e}")

    def _restart_tunnel(self, icon, item):
        threading.Thread(target=self.tunnel.restart, daemon=True).start()

    def _toggle_autostart(self, icon, item):
        cfg = self.cfg_getter()
        want = not bool(cfg.get("autostart", True))
        cfg["autostart"] = want
        config.save(cfg)
        autostart.apply(cfg)
        log.info(f"开机自启已{'开启' if want else '关闭'}")

    def _quit(self, icon, item):
        icon.stop()
        self._stop.set()

    def run(self):
        cfg = self.cfg_getter()
        menu = pystray.Menu(
            pystray.MenuItem("打开管理页", self._open_admin, default=True),
            pystray.MenuItem("打印二维码海报", self._print_poster),
            pystray.MenuItem("重启隧道", self._restart_tunnel),
            pystray.MenuItem(
                "开机自启",
                self._toggle_autostart,
                checked=lambda item: bool(self.cfg_getter().get("autostart", True)),
            ),
            pystray.MenuItem("退出", self._quit),
        )
        self._icon = pystray.Icon("SmartPrint", _make_icon(), "SmartPrint 扫码打印", menu)
        log.info("托盘图标已启动")
        self._icon.run()
