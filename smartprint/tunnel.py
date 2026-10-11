# -*- coding: utf-8 -*-
"""SmartPrint 访问方式管理：
- lan：局域网直连（自动识别本机 IP）
- cloudflare：Quick Tunnel（免账号）/ Named Tunnel（token 或配置文件，自有域名）
- frp：通过 frpc 客户端穿透（需自有域名）
- custom：自定义公网地址（任意反代/映射到本机端口）
"""
import os
import re
import socket
import subprocess
import threading
import time
from pathlib import Path

import psutil
import requests

from . import config
from .logger import get_logger

log = get_logger()

CF_DOWNLOAD_URL = (
    "https://github.com/cloudflare/cloudflared/releases/latest/download/"
    "cloudflared-windows-amd64.exe"
)
_URL_RE = re.compile(r"(https?://[^\s\"']+)")
_TUNNEL_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


class TunnelManager:
    """管理子进程（cloudflared / frpc）并维护当前公网访问地址"""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.proc = None
        self.public_url = ""
        self.lan_urls = []
        self.error = ""
        self.status = "idle"          # idle | starting | running | error
        self._thread = None
        self._stop = threading.Event()

    # ---------- 局域网 ----------

    @staticmethod
    def detect_lan_urls(port: int) -> list:
        """识别本机局域网地址：过滤虚拟网卡与 APIPA，优先 192.168/10/172 内网段"""
        skip_iface = ("docker", "veth", "vmnet", "vmware", "virtualbox", "loopback",
                      "tailscale", "wireguard", "zerotier", "openvpn", "tun", "tap",
                      "wsl", "hyper-v", "vether", "npcap", "npcapsloopback")
        candidates = []
        for iface, addrs in psutil.net_if_addrs().items():
            low = iface.lower()
            if any(k in low for k in skip_iface):
                continue
            for a in addrs:
                if a.family != socket.AF_INET:
                    continue
                ip = a.address
                if ip.startswith(("127.", "169.254.", "0.0.0.0", "224.", "255.")):
                    continue
                candidates.append((iface, ip))

        def score(ip: str) -> int:
            if ip.startswith("192.168."):
                return 0
            if ip.startswith("10."):
                return 1
            if ip.startswith("172."):
                return 2
            return 3

        candidates.sort(key=lambda c: (score(c[1]), c[0]))
        return [f"http://{ip}:{port}" for _, ip in candidates]

    # ---------- cloudflared ----------

    def _find_cloudflared(self) -> str:
        cfg_exe = (self.cfg.get("cloudflare") or {}).get("exe_path", "")
        if cfg_exe and Path(cfg_exe).exists():
            return cfg_exe
        bundled = config.APP_DIR / "cloudflared.exe"
        if bundled.exists():
            return str(bundled)
        which = shutil_which("cloudflared")
        if which:
            return which
        return ""

    def ensure_cloudflared(self, progress_cb=None) -> str:
        exe = self._find_cloudflared()
        if exe:
            return exe
        target = config.APP_DIR / "cloudflared.exe"
        log.info("未找到 cloudflared.exe，开始自动下载…")
        try:
            with requests.get(CF_DOWNLOAD_URL, stream=True, timeout=60) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                done = 0
                with open(target, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 16):
                        f.write(chunk)
                        done += len(chunk)
                        if progress_cb and total:
                            progress_cb(done / total)
            os.chmod(target, 0o755)
            log.info(f"cloudflared 下载完成：{target}")
            return str(target)
        except Exception as e:
            self.error = f"cloudflared 下载失败：{e}（可手动下载后放入程序目录）"
            log.error(self.error)
            raise RuntimeError(self.error)

    def _spawn(self, cmd: list, ready_check) -> str:
        """启动子进程并等待 ready_check(proc) 返回公网 URL"""
        self.status = "starting"
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self.proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
        )
        deadline = time.time() + 60
        lines = []
        while time.time() < deadline:
            if self._stop.is_set():
                return ""
            if self.proc.poll() is not None:
                raise RuntimeError("隧道进程异常退出：" + "".join(lines[-20:]))
            line = self.proc.stdout.readline()
            if not line:
                time.sleep(0.2)
                continue
            lines.append(line)
            url = ready_check(line)
            if url:
                return url
        raise RuntimeError("60 秒内未获得隧道地址，最近输出：\n" + "".join(lines[-20:]))

    def start_cloudflare(self) -> str:
        cf = self.cfg.get("cloudflare") or {}
        mode = cf.get("mode", "quick")
        exe = self.ensure_cloudflared()
        port = int(self.cfg.get("port", 8866))

        if mode == "token":
            token = (cf.get("token") or "").strip()
            if not token:
                raise RuntimeError("Cloudflare 模式为 token，但未配置 tunnel token")
            url = self._spawn(
                [exe, "tunnel", "--no-autoupdate", "run", "--token", token],
                lambda line: _TUNNEL_URL_RE.search(line).group(0) if _TUNNEL_URL_RE.search(line) else None,
            )
            domain = (cf.get("domain") or "").strip()
            return f"https://{domain}" if domain else url

        if mode == "config":
            cpath = (cf.get("config_path") or "").strip()
            if not cpath or not Path(cpath).exists():
                raise RuntimeError("Cloudflare 配置文件不存在")
            domain = (cf.get("domain") or "").strip()
            if not domain:
                raise RuntimeError("config 模式需要填写自有域名")
            self._spawn(
                [exe, "tunnel", "--config", cpath, "run", "--no-autoupdate"],
                lambda line: None,
            )
            return f"https://{domain}"

        # quick：免账号临时隧道
        return self._spawn(
            [exe, "tunnel", "--url", f"http://127.0.0.1:{port}", "--no-autoupdate"],
            lambda line: _TUNNEL_URL_RE.search(line).group(0) if _TUNNEL_URL_RE.search(line) else None,
        )

    # ---------- frp ----------

    def start_frp(self) -> str:
        frp = self.cfg.get("frp") or {}
        exe = (frp.get("exe_path") or "").strip()
        cpath = (frp.get("config_path") or "").strip()
        domain = (frp.get("domain") or "").strip()
        if not exe or not Path(exe).exists():
            raise RuntimeError("请填写 frpc.exe 路径")
        if not cpath or not Path(cpath).exists():
            raise RuntimeError("请填写 frpc 配置文件路径")
        if not domain:
            raise RuntimeError("FRP 模式需要填写公网域名（二维码将指向它）")
        self._spawn([exe, "-c", cpath], lambda line: None)
        return f"https://{domain}"

    # ---------- 总控 ----------

    def get_public_url(self) -> str:
        return self.public_url

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="tunnel")
        self._thread.start()

    def _run(self):
        while not self._stop.is_set():
            mode = self.cfg.get("access_mode", "lan")
            try:
                if mode == "cloudflare":
                    self.public_url = self.start_cloudflare()
                elif mode == "frp":
                    self.public_url = self.start_frp()
                elif mode == "custom":
                    url = (self.cfg.get("custom_url") or "").strip()
                    if not url:
                        raise RuntimeError("自定义模式需要填写公网地址")
                    self.public_url = url
                else:
                    self.public_url = ""
                self.lan_urls = self.detect_lan_urls(int(self.cfg.get("port", 8866)))
                self.error = ""
                self.status = "running"
                log.info(f"访问方式[{mode}] 就绪，公网地址：{self.public_url or '（无，仅局域网）'}，"
                         f"局域网地址：{self.lan_urls}")
                # 隧道进程存活期间保持 running；LAN/custom 模式直接退出循环
                if mode not in ("cloudflare", "frp"):
                    return
                while self.proc and self.proc.poll() is None and not self._stop.is_set():
                    time.sleep(2)
                if not self._stop.is_set():
                    raise RuntimeError("隧道进程已退出")
                return
            except Exception as e:
                self.error = str(e)
                self.status = "error"
                log.error(f"隧道启动失败：{e}")
                config.set_state(tunnel_status=self.status, tunnel_error=self.error,
                                 public_url=self.public_url)
                if self._stop.is_set():
                    return
                time.sleep(30)  # 30 秒后重试

    def restart(self):
        self.stop()
        self._stop.clear()
        self.start()

    def stop(self):
        self._stop.set()
        if self.proc:
            try:
                if self.proc.poll() is None:
                    self.proc.terminate()
                    try:
                        self.proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self.proc.kill()
            except Exception:
                pass
            self.proc = None
        self.status = "idle"

    def state(self) -> dict:
        return {
            "mode": self.cfg.get("access_mode", "lan"),
            "status": self.status,
            "public_url": self.public_url,
            "lan_urls": self.lan_urls or self.detect_lan_urls(int(self.cfg.get("port", 8866))),
            "error": self.error,
        }


def shutil_which(name: str) -> str:
    import shutil
    return shutil.which(name) or ""
