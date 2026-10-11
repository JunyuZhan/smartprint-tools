# -*- coding: utf-8 -*-
"""converters 转换器测试：图片→PDF 各种格式、Word 失败路径、不支持类型"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PIL import Image

from smartprint import config
from smartprint.converters import PrintError, doc_to_pdf, ensure_pdf, image_to_pdf


def test_image_to_pdf_png(tmp_path):
    src = tmp_path / "a.png"
    Image.new("RGB", (100, 80), (0, 128, 255)).save(src)
    dst = tmp_path / "a.pdf"
    image_to_pdf(src, dst)
    assert dst.exists() and dst.stat().st_size > 0
    import pymupdf as fitz
    doc = fitz.open(str(dst))
    assert doc.page_count == 1
    doc.close()


def test_image_to_pdf_jpg_bmp_webp(tmp_path):
    for name, mode in [("a.jpg", "RGB"), ("b.bmp", "RGB"), ("c.webp", "RGB")]:
        src = tmp_path / name
        Image.new(mode, (60, 40), (10, 200, 10)).save(src)
        dst = tmp_path / f"{name}.pdf"
        image_to_pdf(src, dst)
        assert dst.exists() and dst.stat().st_size > 0


def test_image_to_pdf_rgba_converted(tmp_path):
    """RGBA 图片必须能转换（转 RGB 逻辑）"""
    src = tmp_path / "r.png"
    Image.new("RGBA", (50, 50), (255, 0, 0, 128)).save(src)
    dst = tmp_path / "r.pdf"
    image_to_pdf(src, dst)
    assert dst.exists() and dst.stat().st_size > 0


def test_image_to_pdf_corrupt_file_raises(tmp_path):
    src = tmp_path / "bad.png"
    src.write_bytes(b"not a real image")
    with pytest.raises(PrintError, match="无法读取图片"):
        image_to_pdf(src, tmp_path / "bad.pdf")


def test_ensure_pdf_passthrough(tmp_path):
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")
    assert ensure_pdf(pdf, tmp_path) == pdf


def test_ensure_pdf_image(tmp_path):
    img = tmp_path / "x.png"
    Image.new("RGB", (30, 30), "white").save(img)
    out = ensure_pdf(img, tmp_path)
    assert out.suffix == ".pdf" and out.exists()


def test_ensure_pdf_unsupported_extension(tmp_path):
    bad = tmp_path / "x.xyz"
    bad.write_bytes(b"data")
    with pytest.raises(PrintError, match="不支持的文件类型"):
        ensure_pdf(bad, tmp_path)


def test_ensure_pdf_no_extension(tmp_path):
    bad = tmp_path / "x"
    bad.write_bytes(b"data")
    with pytest.raises(PrintError, match="不支持的文件类型"):
        ensure_pdf(bad, tmp_path)


def test_doc_to_pdf_no_office(monkeypatch, tmp_path):
    """无 Word/WPS/LibreOffice 时必须抛出明确错误，而不是静默失败"""
    import smartprint.converters as conv

    def fake_which(name):
        return ""  # 找不到 soffice

    monkeypatch.setattr(conv.shutil, "which", fake_which)
    # 模拟无 pywin32 / 无 Office：win32com.client.DispatchEx 全部失败
    import types

    class _FakeDispatchEx:
        def __init__(self, *a, **k):
            raise Exception("no office installed")

    fake_mod = types.SimpleNamespace(client=types.SimpleNamespace(DispatchEx=_FakeDispatchEx))
    monkeypatch.setitem(sys.modules, "win32com", fake_mod)
    monkeypatch.setitem(sys.modules, "win32com.client", fake_mod.client)

    src = tmp_path / "a.docx"
    src.write_bytes(b"fake docx")
    with pytest.raises(PrintError, match="转换 Word 文档失败"):
        doc_to_pdf(src, tmp_path / "a.pdf")
