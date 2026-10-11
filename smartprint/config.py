# -*- coding: utf-8 -*-
"""SmartPrint 打印服务 - 配置管理"""
import json
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # PyInstaller 打包：程序目录 = exe 所在目录（可持久写入）
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = APP_DIR / "config.json"
DATA_DIR = APP_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
TMP_DIR = DATA_DIR / "tmp"
LOG_DIR = APP_DIR / "logs"
STATE_PATH = DATA_DIR / "state.json"

DEFAULTS = {
    "host": "0.0.0.0",
    "port": 8866,
    "printer": "",                 # 空 = 使用系统默认打印机
    "office_name": "扫码打印",
    "max_upload_mb": 50,
    "pin": "",                     # 访问口令，空 = 不启用
    "access_mode": "lan",          # lan | cloudflare | frp | custom
    "cloudflare": {
        "exe_path": "",            # cloudflared.exe 路径，空 = 自动查找/下载
        "mode": "quick",           # quick | token | config
        "token": "",               # named tunnel token（mode=token 时使用）
        "config_path": "",         # cloudflared 配置文件（mode=config 时使用）
        "domain": ""               # 自有域名（token/config 模式）
    },
    "frp": {
        "exe_path": "",
        "config_path": "",
        "domain": ""
    },
    "custom_url": "",              # 自定义公网地址
    "autostart": True,             # 开机自启
    "clean_days": 7,               # 打印文件保留天数
    "print_defaults": {
        "color": "color",          # color | mono
        "duplex": "single",        # single | long | short
        "copies": 1,
        "orientation": "auto",     # auto | portrait | landscape（仅图片生效）
        "fit": "fit",              # fit | fill | original（仅图片生效）
        "pages": ""                # 页码范围，如 "1-3,5"，空 = 全部
    }
}


def ensure_dirs():
    for d in (DATA_DIR, UPLOAD_DIR, TMP_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)


def load() -> dict:
    cfg = json.loads(json.dumps(DEFAULTS))  # deep copy
    if CONFIG_PATH.exists():
        try:
            saved = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            cfg.update({k: v for k, v in saved.items() if k in DEFAULTS})
            # 嵌套字典合并
            for key in ("cloudflare", "frp", "print_defaults"):
                if isinstance(saved.get(key), dict):
                    cfg[key].update(saved[key])
        except Exception as e:
            print(f"[config] 读取 config.json 失败：{e}，使用默认配置")
    ensure_dirs()
    return cfg


def save(cfg: dict):
    # 只保存配置项，忽略运行时内部字段（_ 开头）
    out = {k: v for k, v in cfg.items() if not str(k).startswith("_")}
    CONFIG_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


def get_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def set_state(**kwargs):
    st = get_state()
    st.update(kwargs)
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
