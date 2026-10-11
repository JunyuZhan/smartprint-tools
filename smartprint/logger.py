# -*- coding: utf-8 -*-
"""SmartPrint 日志模块：文件（轮转）+ 控制台"""
import logging
import logging.handlers
import sys

from . import config

_LOGGER = None


def get_logger() -> logging.Logger:
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER
    config.ensure_dirs()
    logger = logging.getLogger("smartprint")
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    fh = logging.handlers.RotatingFileHandler(
        config.LOG_DIR / "smartprint.log", maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # 有控制台（非 pythonw）时同时输出到控制台
    if sys.stdout is not None and hasattr(sys.stdout, "fileno"):
        try:
            sys.stdout.fileno()
            ch = logging.StreamHandler(sys.stdout)
            ch.setFormatter(fmt)
            logger.addHandler(ch)
        except Exception:
            pass
    _LOGGER = logger
    return logger


def tail(n: int = 200) -> str:
    """读取最近 n 行日志（供管理页展示）"""
    logfile = config.LOG_DIR / "smartprint.log"
    if not logfile.exists():
        return "（暂无日志）"
    try:
        lines = logfile.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-n:])
    except Exception as e:
        return f"（读取日志失败：{e}）"
