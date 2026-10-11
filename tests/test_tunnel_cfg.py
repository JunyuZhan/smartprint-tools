# -*- coding: utf-8 -*-
"""tunnel 配置校验测试：模式缺失参数必须报错，局域网地址识别正确。

全部 mock（不真正启动 cloudflared/frpc、不访问网络）。
"""
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from smartprint.tunnel import TunnelManager


def _fake_addrs(family=socket.AF_INET, addr="192.168.1.5"):
    """构造 psutil.snicaddr 形状对象"""
    import types
    return types.SimpleNamespace(family=family, address=addr)


def test_detect_lan_urls_basic(monkeypatch):
    import psutil
    fake = {
        "以太网": [_fake_addrs(addr="192.168.1.5")],
        "WLAN": [_fake_addrs(addr="10.0.0.8")],
    }
    monkeypatch.setattr(psutil, "net_if_addrs", lambda: fake)
    urls = TunnelManager.detect_lan_urls(8866)
    assert "http://192.168.1.5:8866" in urls
    assert "http://10.0.0.8:8866" in urls


def test_detect_lan_urls_skips_virtual(monkeypatch):
    import psutil
    fake = {
        "以太网": [_fake_addrs(addr="192.168.1.5")],
        "vEthernet (WSL)": [_fake_addrs(addr="172.20.0.1")],
        "VMware Network Adapter VMnet8": [_fake_addrs(addr="192.168.123.1")],
        "Loopback": [_fake_addrs(addr="127.0.0.1")],
        "VirtualBox Host-Only": [_fake_addrs(addr="192.168.56.1")],
    }
    monkeypatch.setattr(psutil, "net_if_addrs", lambda: fake)
    urls = TunnelManager.detect_lan_urls(8866)
    assert urls == ["http://192.168.1.5:8866"]


def test_detect_lan_urls_skips_apipa_and_non_ipv4(monkeypatch):
    import psutil
    fake = {
        "以太网": [_fake_addrs(addr="169.254.13.5"), _fake_addrs(family=socket.AF_INET6, addr="fe80::1")],
        "WLAN": [_fake_addrs(addr="192.168.3.7")],
    }
    monkeypatch.setattr(psutil, "net_if_addrs", lambda: fake)
    urls = TunnelManager.detect_lan_urls(9000)
    assert urls == ["http://192.168.3.7:9000"]


def test_detect_lan_urls_prefers_private_order(monkeypatch):
    """192.168 优先于 10.，10. 优先于 172."""
    import psutil
    fake = {
        "eth0": [_fake_addrs(addr="172.16.0.2")],
        "eth1": [_fake_addrs(addr="10.1.1.1")],
        "eth2": [_fake_addrs(addr="192.168.0.1")],
    }
    monkeypatch.setattr(psutil, "net_if_addrs", lambda: fake)
    urls = TunnelManager.detect_lan_urls(8866)
    assert urls == ["http://192.168.0.1:8866", "http://10.1.1.1:8866", "http://172.16.0.2:8866"]


# ---------- 各模式参数校验（不真正启动进程） ----------

def test_cloudflare_token_missing_token(monkeypatch, tmp_path):
    cfg = {"access_mode": "cloudflare", "port": 8866,
           "cloudflare": {"mode": "token", "token": "", "domain": "print.example.com"}}
    tm = TunnelManager(cfg)
    monkeypatch.setattr(tm, "ensure_cloudflared", lambda **k: str(tmp_path / "cloudflared.exe"))
    with pytest.raises(RuntimeError, match="token"):
        tm.start_cloudflare()


def test_cloudflare_config_missing_file(monkeypatch, tmp_path):
    cfg = {"access_mode": "cloudflare", "port": 8866,
           "cloudflare": {"mode": "config", "config_path": str(tmp_path / "nope.yml"), "domain": ""}}
    tm = TunnelManager(cfg)
    monkeypatch.setattr(tm, "ensure_cloudflared", lambda **k: str(tmp_path / "cloudflared.exe"))
    with pytest.raises(RuntimeError, match="配置文件"):
        tm.start_cloudflare()


def test_cloudflare_config_missing_domain(monkeypatch, tmp_path):
    cpath = tmp_path / "t.yml"
    cpath.write_text("tunnel: x")
    cfg = {"access_mode": "cloudflare", "port": 8866,
           "cloudflare": {"mode": "config", "config_path": str(cpath), "domain": ""}}
    tm = TunnelManager(cfg)
    monkeypatch.setattr(tm, "ensure_cloudflared", lambda **k: str(tmp_path / "cloudflared.exe"))
    with pytest.raises(RuntimeError, match="域名"):
        tm.start_cloudflare()


def test_frp_missing_exe(tmp_path):
    cfg = {"access_mode": "frp", "port": 8866,
           "frp": {"exe_path": str(tmp_path / "no_frpc.exe"), "config_path": "", "domain": ""}}
    tm = TunnelManager(cfg)
    with pytest.raises(RuntimeError, match="frpc"):
        tm.start_frp()


def test_frp_missing_config(tmp_path):
    exe = tmp_path / "frpc.exe"
    exe.write_bytes(b"MZ")  # 假装存在
    cfg = {"access_mode": "frp", "port": 8866,
           "frp": {"exe_path": str(exe), "config_path": str(tmp_path / "no.toml"), "domain": ""}}
    tm = TunnelManager(cfg)
    with pytest.raises(RuntimeError, match="配置文件"):
        tm.start_frp()


def test_frp_missing_domain(tmp_path):
    exe = tmp_path / "frpc.exe"
    exe.write_bytes(b"MZ")
    cpath = tmp_path / "frpc.toml"
    cpath.write_text("[common]")
    cfg = {"access_mode": "frp", "port": 8866,
           "frp": {"exe_path": str(exe), "config_path": str(cpath), "domain": ""}}
    tm = TunnelManager(cfg)
    with pytest.raises(RuntimeError, match="域名"):
        tm.start_frp()


def test_state_lan(tmp_path, monkeypatch):
    import psutil
    fake = {"WLAN": [_fake_addrs(addr="192.168.1.9")]}
    monkeypatch.setattr(psutil, "net_if_addrs", lambda: fake)
    tm = TunnelManager({"access_mode": "lan", "port": 8866})
    st = tm.state()
    assert st["mode"] == "lan"
    assert st["lan_urls"] == ["http://192.168.1.9:8866"]
