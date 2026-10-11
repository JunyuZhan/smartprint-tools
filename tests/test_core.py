# -*- coding: utf-8 -*-
"""SmartPrint 跨平台单元测试。

只覆盖纯逻辑与不依赖真实打印机 / Windows 的路径：
- 页码范围解析
- 配置默认值
- 图片 → PDF 转换
- 二维码 / 海报 PNG 生成
真实打印机冒烟测试见 tests/smoke_test.py（仅 Windows 手动运行）。
"""
import sys
import tempfile
from pathlib import Path

# 保证从项目根目录导入 smartprint 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from smartprint import config, printer, qr
from smartprint.converters import image_to_pdf


# ---------- 页码范围解析 ----------

def test_parse_page_range_empty():
    assert printer.parse_page_range("", 10) == list(range(10))
    assert printer.parse_page_range(None, 10) == list(range(10))
    assert printer.parse_page_range("   ", 10) == list(range(10))


def test_parse_page_range_single():
    assert printer.parse_page_range("1", 10) == [0]
    assert printer.parse_page_range("10", 10) == [9]


def test_parse_page_range_span():
    assert printer.parse_page_range("1-3", 10) == [0, 1, 2]


def test_parse_page_range_mixed():
    assert printer.parse_page_range("1-3,5", 10) == [0, 1, 2, 4]


def test_parse_page_range_chinese_comma():
    assert printer.parse_page_range("1，3-4", 10) == [0, 2, 3]


def test_parse_page_range_reversed():
    assert printer.parse_page_range("5-2", 10) == [1, 2, 3, 4]


def test_parse_page_range_out_of_bounds():
    assert printer.parse_page_range("99-100", 5) == list(range(5))
    assert printer.parse_page_range("1-99", 5) == list(range(5))


def test_parse_page_range_invalid():
    assert printer.parse_page_range("abc", 10) == list(range(10))
    assert printer.parse_page_range("1,abc,3", 10) == [0, 2]


def test_parse_page_range_no_duplicates():
    assert printer.parse_page_range("1,1,1-2", 10) == [0, 1]


# ---------- 配置默认值 ----------

def test_config_defaults():
    cfg = config.load()
    assert cfg["port"] == 8866
    assert cfg["access_mode"] == "lan"
    assert cfg["max_upload_mb"] == 50
    assert cfg["print_defaults"]["duplex"] == "single"
    assert cfg["print_defaults"]["color"] == "color"
    assert cfg["host"] == "0.0.0.0"


# ---------- 图片 → PDF ----------

def test_image_to_pdf():
    import pymupdf as fitz
    from PIL import Image

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        src = td / "sample.png"
        Image.new("RGB", (120, 80), (255, 0, 0)).save(src)
        dst = td / "sample.pdf"
        image_to_pdf(src, dst)
        assert dst.exists() and dst.stat().st_size > 0
        doc = fitz.open(str(dst))
        assert doc.page_count == 1
        assert doc[0].rect.width > 0
        doc.close()


# ---------- 二维码与海报 ----------

def test_qr_bytes():
    png = qr.qr_bytes("http://127.0.0.1:8866/")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 100


def test_build_poster():
    png = qr.build_poster("http://127.0.0.1:8866/", "测试办公室")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 1000
