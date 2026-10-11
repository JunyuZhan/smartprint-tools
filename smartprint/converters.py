# -*- coding: utf-8 -*-
"""SmartPrint 文件转换：图片/Word/WPS 文档 → PDF（统一交给打印引擎）"""
import io
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

try:
    import pymupdf as fitz
except ImportError:
    import fitz

from .printer import PrintError

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff", ".gif"}
DOC_EXTS = {".doc", ".docx", ".rtf", ".wps", ".odt"}


def image_to_pdf(src: Path, dst: Path, max_side_pt: float = 1600.0):
    """图片 → A4 页面 PDF（居中适配），打印时再按设置适配页面"""
    try:
        img = Image.open(src)
        img.load()
    except Exception as e:
        raise PrintError(f"无法读取图片 {src.name}：{e}")
    if img.mode in ("RGBA", "LA", "P", "I;16"):
        img = img.convert("RGB")
    w, h = img.size
    # 图片本身较长时按比例缩到单页内（如长截图），否则原尺寸
    scale = min(1.0, max_side_pt / max(w, h))
    w_pt, h_pt = max(1, int(w * scale)), max(1, int(h * scale))
    doc = fitz.open()
    page = doc.new_page(width=w_pt, height=h_pt)
    rect = fitz.Rect(0, 0, w_pt, h_pt)
    # 先用 Pillow 重编码为无损 PNG 字节流，避免 PyMuPDF 对
    # webp/bmp 等格式解码失败（保证所有 Pillow 支持的图片都能转）
    try:
        page.insert_image(rect, filename=str(src))
    except Exception:
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        page.insert_image(rect, stream=buf.getvalue())
    doc.save(str(dst), garbage=3, deflate=True)
    doc.close()


def doc_to_pdf(src: Path, dst: Path):
    """Word/WPS 文档 → PDF：优先 Word COM，其次 WPS COM，最后 LibreOffice"""
    last_err = None
    for progid in ("Word.Application", "KWPS.Application", "wps.Application"):
        try:
            import win32com.client
        except ImportError:
            raise PrintError("缺少 pywin32，无法转换 Word 文档（请重装依赖）")
        try:
            # DispatchEx：创建独立进程实例，避免关闭用户已打开的 Word/WPS
            app = win32com.client.DispatchEx(progid)
        except Exception as e:
            last_err = e
            continue
        try:
            app.Visible = False
            try:
                app.DisplayAlerts = 0
            except Exception:
                pass
            doc = app.Documents.Open(str(src), ReadOnly=True)
            try:
                try:
                    doc.SaveAs2(str(dst), FileFormat=17)  # wdFormatPDF
                except Exception:
                    doc.SaveAs(str(dst), FileFormat=17)
            finally:
                try:
                    doc.Close(False)
                except Exception:
                    pass
            if Path(dst).exists() and Path(dst).stat().st_size > 0:
                return
            last_err = RuntimeError("转换后未生成 PDF")
        except Exception as e:
            last_err = e
        finally:
            try:
                app.Quit()
            except Exception:
                pass
    # LibreOffice 兜底
    soffice = shutil.which("soffice") or shutil.which("soffice.exe")
    if soffice:
        try:
            with tempfile.TemporaryDirectory() as td:
                subprocess.run(
                    [soffice, "--headless", "--convert-to", "pdf", "--outdir", td, str(src)],
                    check=True, timeout=180, capture_output=True,
                )
                pdfs = list(Path(td).glob("*.pdf"))
                if pdfs:
                    shutil.move(str(pdfs[0]), str(dst))
                    return
                last_err = RuntimeError("LibreOffice 未输出 PDF")
        except Exception as e:
            last_err = e
    raise PrintError(
        "转换 Word 文档失败：电脑上未检测到可用的 Microsoft Word / WPS / LibreOffice。"
        f"（{last_err}）"
    )


def ensure_pdf(src: Path, tmp_dir: Path) -> Path:
    """任何支持的文件 → PDF 路径（PDF 原样返回）"""
    ext = src.suffix.lower()
    if ext == ".pdf":
        return src
    dst = tmp_dir / f"{src.stem}_{src.stat().st_mtime_ns}.pdf"
    if ext in IMG_EXTS:
        image_to_pdf(src, dst)
        return dst
    if ext in DOC_EXTS:
        doc_to_pdf(src, dst)
        return dst
    raise PrintError(f"不支持的文件类型：{ext or '（无扩展名）'}")
