# -*- coding: utf-8 -*-
"""SmartPrint 开机自启（当前用户注册表 Run 键）"""
import sys

try:
    import winreg
except ImportError:  # 非 Windows（CI / 单元测试环境）
    winreg = None

from . import config
from .logger import get_logger

log = get_logger()
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "SmartPrint"


def _command() -> str:
    if getattr(sys, "frozen", False):  # PyInstaller 打包
        return f'"{sys.executable}"'
    server = config.APP_DIR / "server.py"
    return f'"{sys.executable}" "{server}"'


def enable():
    if winreg is None:
        log.warning("开机自启仅支持 Windows，已跳过")
        return
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, VALUE_NAME, 0, winreg.REG_SZ, _command())
    log.info("已开启开机自启")


def disable():
    if winreg is None:
        return
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, VALUE_NAME)
    except FileNotFoundError:
        pass
    log.info("已关闭开机自启")


def enabled() -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_QUERY_VALUE) as k:
            winreg.QueryValueEx(k, VALUE_NAME)
        return True
    except FileNotFoundError:
        return False


def apply(cfg: dict):
    """按配置同步自启状态"""
    want = bool(cfg.get("autostart", True))
    now = enabled()
    if want and not now:
        enable()
    elif not want and now:
        disable()
