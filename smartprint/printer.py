# -*- coding: utf-8 -*-
"""SmartPrint 打印引擎：
基于 ctypes 直调 winspool.drv / gdi32 实现每作业打印设置控制：
- 彩色/黑白（dmColor + 灰度渲染）
- 单面/双面（dmDuplex）
- 份数（dmCopies）
- 页码范围（parse_page_range，仅 PDF）
- 图片方向/适配（仅图片）
Win32 API 惰性加载：模块可在 Linux/macOS 导入（CI 单测），调用时抛 PrintError。
"""
import ctypes
import ctypes.wintypes as wt
import os
from ctypes import wintypes

from PIL import Image

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff", ".gif"}


class PrintError(Exception):
    pass


class DEVMODEW(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", wt.WCHAR * 32),
        ("dmSpecVersion", wt.WORD),
        ("dmDriverVersion", wt.WORD),
        ("dmSize", wt.WORD),
        ("dmDriverExtra", wt.WORD),
        ("dmFields", wintypes.DWORD),
        ("dmOrientation", ctypes.c_short),
        ("dmPaperSize", ctypes.c_short),
        ("dmPaperLength", ctypes.c_short),
        ("dmPaperWidth", ctypes.c_short),
        ("dmScale", ctypes.c_short),
        ("dmCopies", ctypes.c_short),
        ("dmDefaultSource", ctypes.c_short),
        ("dmPrintQuality", ctypes.c_short),
        ("dmColor", ctypes.c_short),
        ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short),
        ("dmTTOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short),
        ("dmFormName", wt.WCHAR * 32),
        ("dmLogPixels", wt.WORD),
        ("dmBitsPerPel", wintypes.DWORD),
        ("dmPelsWidth", wintypes.DWORD),
        ("dmPelsHeight", wintypes.DWORD),
        ("dmDisplayFlags", wintypes.DWORD),
        ("dmDisplayFrequency", wintypes.DWORD),
        ("dmICMMethod", wintypes.DWORD),
        ("dmICMIntent", wintypes.DWORD),
        ("dmMediaType", wintypes.DWORD),
        ("dmDitherType", wintypes.DWORD),
        ("dmReserved1", wintypes.DWORD),
        ("dmReserved2", wintypes.DWORD),
        ("dmPanningWidth", wintypes.DWORD),
        ("dmPanningHeight", wintypes.DWORD),
    ]


class DOCINFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_int),
        ("lpszDocName", wt.LPCWSTR),
        ("lpszOutput", wt.LPCWSTR),
        ("lpszDatatype", wt.LPCWSTR),
        ("fwType", wintypes.DWORD),
        ("lpszDocName2", wt.LPCWSTR),
    ]


class PRINTER_INFO_1W(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("pDescription", wt.LPWSTR),
        ("pName", wt.LPWSTR),
        ("pComment", wt.LPWSTR),
    ]


# DM_* 常量
DM_ORIENTATION = 0x00000001
DM_PAPERSIZE = 0x00000002
DM_PAPERLENGTH = 0x00000004
DM_PAPERWIDTH = 0x00000008
DM_COPIES = 0x00000100
DM_DEFAULTSOURCE = 0x00000200
DM_PRINTQUALITY = 0x00000400
DM_COLOR = 0x00000800
DM_DUPLEX = 0x00001000
DM_YRESOLUTION = 0x00002000

DMORIENT_PORTRAIT = 1
DMORIENT_LANDSCAPE = 2
DMCOLOR_MONOCHROME = 1
DMCOLOR_COLOR = 2
DMDUP_SIMPLEX = 1
DMDUP_VERTICAL = 2     # 长边翻转（书本）
DMDUP_HORIZONTAL = 3   # 短边翻转（翻页）

PRINTER_ENUM_LOCAL = 0x00000002
PRINTER_ENUM_CONNECTIONS = 0x00000004

_winspool = None
_gdi32 = None


def _ensure_winapi():
    """惰性加载 Win32 打印 API（仅 Windows 可用），供各函数调用。

    模块级不做 WinDLL 加载，便于在 Linux/macOS 上做单元测试与 CI 导入。
    """
    global _winspool, _gdi32
    if _winspool is not None:
        return
    if os.name != "nt":
        raise PrintError("打印功能仅支持 Windows 系统")
    try:
        _winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)
        _gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    except Exception as e:
        raise PrintError(f"无法加载 Windows 打印 API：{e}")

    _winspool.OpenPrinterW.restype = wintypes.BOOL
    _winspool.OpenPrinterW.argtypes = [wt.LPCWSTR, wt.PHANDLE, wt.LPVOID]
    _winspool.DocumentPropertiesW.restype = wintypes.LONG
    _winspool.DocumentPropertiesW.argtypes = [
        wt.HWND, wt.HANDLE, wt.LPCWSTR, wt.LPVOID, wt.LPVOID, wintypes.DWORD
    ]
    _winspool.ClosePrinter.argtypes = [wt.HANDLE]
    _winspool.EnumPrintersW.restype = wintypes.BOOL
    _winspool.EnumPrintersW.argtypes = [
        wintypes.DWORD, wt.LPWSTR, wintypes.DWORD, wt.LPVOID,
        wintypes.DWORD, wt.PDWORD, wt.PDWORD,
    ]
    _winspool.GetDefaultPrinterW.restype = wintypes.BOOL
    _winspool.GetDefaultPrinterW.argtypes = [wt.LPWSTR, wt.PDWORD]
    _gdi32.CreateDCW.restype = wt.HDC
    _gdi32.CreateDCW.argtypes = [wt.LPCWSTR, wt.LPCWSTR, wt.LPCWSTR, wt.LPVOID]
    _gdi32.StartDocW.restype = ctypes.c_int
    _gdi32.StartDocW.argtypes = [wt.HDC, ctypes.POINTER(DOCINFOW)]
    _gdi32.StartPage.argtypes = [wt.HDC]
    _gdi32.EndPage.argtypes = [wt.HDC]
    _gdi32.EndDoc.argtypes = [wt.HDC]
    _gdi32.DeleteDC.argtypes = [wt.HDC]
    _gdi32.GetDeviceCaps.restype = ctypes.c_int
    _gdi32.GetDeviceCaps.argtypes = [wt.HDC, ctypes.c_int]


# ---------------- 打印机枚举 / 默认打印机 ----------------


def list_printers() -> list:
    """枚举本机与网络打印机（level 1 单次调用，缓冲区不足时自动扩大）"""
    _ensure_winapi()
    names = []
    flags = PRINTER_ENUM_LOCAL | PRINTER_ENUM_CONNECTIONS
    needed = wintypes.DWORD(0)
    returned = wintypes.DWORD(0)
    buf_size = 65536
    for _ in range(3):
        buf = ctypes.create_string_buffer(buf_size)
        ok = _winspool.EnumPrintersW(
            flags, None, 1, buf, buf_size, ctypes.byref(needed), ctypes.byref(returned)
        )
        if ok:
            break
        err = ctypes.get_last_error()
        if err == 122:  # ERROR_INSUFFICIENT_BUFFER
            buf_size = needed.value + 4096
            continue
        raise PrintError(f"枚举打印机失败（错误 {err}）")
    else:
        raise PrintError("枚举打印机失败：缓冲区多次不足")
    if not returned.value:
        return names
    entries = ctypes.cast(buf, ctypes.POINTER(PRINTER_INFO_1W * returned.value)).contents
    seen = set()
    for i in range(returned.value):
        pname = entries[i].pName
        if pname:
            name = ctypes.wstring_at(pname)
            if name and name not in seen:
                seen.add(name)
                names.append(name)
    return names


def get_default_printer() -> str:
    _ensure_winapi()
    buf = ctypes.create_unicode_buffer(512)
    needed = wintypes.DWORD(len(buf))
    if not _winspool.GetDefaultPrinterW(buf, ctypes.byref(needed)):
        err = ctypes.get_last_error()
        if err == 5:
            return ""
        raise PrintError(f"获取默认打印机失败（错误 {err}）")
    return buf.value


def resolve_printer(printer_name: str = "") -> str:
    if printer_name:
        return printer_name
    default = get_default_printer()
    if default:
        return default
    printers = list_printers()
    if not printers:
        raise PrintError("未检测到任何打印机")
    return printers[0]


# ---------------- DEVMODE ----------------


def _devmode_size(hprinter) -> int:
    n = _winspool.DocumentPropertiesW(None, hprinter, None, None, None, 0)
    if n < 0:
        raise PrintError(f"获取 DEVMODE 大小失败（错误 {ctypes.get_last_error()}）")
    return n


def _devmode_fetch(hprinter, size: int) -> bytes:
    buf = ctypes.create_string_buffer(size)
    n = _winspool.DocumentPropertiesW(None, hprinter, None, buf, buf, 2)  # DM_OUT_BUFFER
    if n < 0:
        raise PrintError(f"读取打印机默认设置失败（错误 {ctypes.get_last_error()}）")
    return buf.raw[:n]


def _devmode_apply(devmode: bytes, settings: dict) -> bytes:
    """在 DEVMODE 字节流上按设置修改字段"""
    buf = ctypes.create_string_buffer(devmode)
    dm = ctypes.cast(buf, ctypes.POINTER(DEVMODEW)).contents
    dm.dmFields = dm.dmFields | DM_COLOR | DM_DUPLEX | DM_COPIES

    color = (settings.get("color") or "color").lower()
    dm.dmColor = DMCOLOR_MONOCHROME if color == "mono" else DMCOLOR_COLOR

    duplex = (settings.get("duplex") or "single").lower()
    if duplex == "long":
        dm.dmDuplex = DMDUP_VERTICAL
    elif duplex == "short":
        dm.dmDuplex = DMDUP_HORIZONTAL
    else:
        dm.dmDuplex = DMDUP_SIMPLEX

    try:
        copies = int(settings.get("copies", 1))
    except (TypeError, ValueError):
        copies = 1
    dm.dmCopies = max(1, min(99, copies))

    orientation = (settings.get("orientation") or "auto").lower()
    if orientation == "portrait":
        dm.dmFields |= DM_ORIENTATION
        dm.dmOrientation = DMORIENT_PORTRAIT
    elif orientation == "landscape":
        dm.dmFields |= DM_ORIENTATION
        dm.dmOrientation = DMORIENT_LANDSCAPE

    return buf.raw


def build_devmode(printer_name: str, settings: dict) -> bytes:
    """生成字节级 DEVMODE（含按设置的 Color/Duplex/Copies），供 CreateDCW 使用"""
    _ensure_winapi()
    hprinter = wt.HANDLE()
    if not _winspool.OpenPrinterW(printer_name, ctypes.byref(hprinter), None):
        raise PrintError(f"无法打开打印机：{printer_name}（错误 {ctypes.get_last_error()}）")
    try:
        size = _devmode_size(hprinter)
        devmode = _devmode_fetch(hprinter, size)
        return _devmode_apply(devmode, settings)
    finally:
        _winspool.ClosePrinter(hprinter)


# ---------------- 打印作业 ----------------


def _apply_orientation(img: Image.Image, settings: dict) -> Image.Image:
    orientation = (settings.get("orientation") or "auto").lower()
    if orientation == "landscape" and img.width < img.height:
        return img.rotate(90, expand=True)
    if orientation == "portrait" and img.width > img.height:
        return img.rotate(-90, expand=True)
    return img


def _fit_rect(img: Image.Image, pw: int, ph: int, settings: dict):
    """返回图片在页面上的设备像素矩形（适配/填满/原尺寸）"""
    iw, ih = img.size
    fit = (settings.get("fit") or "fit").lower()
    if fit == "fill":
        scale = max(pw / iw, ph / ih)
    elif fit == "original":
        scale = 1
    else:
        scale = min(pw / iw, ph / ih)
    dw, dh = max(1, int(iw * scale)), max(1, int(ih * scale))
    x0 = (pw - dw) // 2
    y0 = (ph - dh) // 2
    return (x0, y0, x0 + dw, y0 + dh)


class PrinterDC:
    """一个打印作业的设备上下文；用完后必须 close()"""

    def __init__(self, printer_name: str, settings: dict):
        _ensure_winapi()
        devmode = build_devmode(printer_name, settings)
        self._hdc = _gdi32.CreateDCW(None, printer_name, None, devmode)
        if not self._hdc:
            raise PrintError(f"创建打印机 DC 失败：{printer_name}（错误 {ctypes.get_last_error()}）")
        self.dpi_x = _gdi32.GetDeviceCaps(self._hdc, 88)   # LOGPIXELSX
        self.dpi_y = _gdi32.GetDeviceCaps(self._hdc, 90)   # LOGPIXELSY
        self.page_w = _gdi32.GetDeviceCaps(self._hdc, 110)  # PHYSICALWIDTH
        self.page_h = _gdi32.GetDeviceCaps(self._hdc, 111)  # PHYSICALHEIGHT
        self.off_x = _gdi32.GetDeviceCaps(self._hdc, 112)   # PHYSICALOFFSETX
        self.off_y = _gdi32.GetDeviceCaps(self._hdc, 113)   # PHYSICALOFFSETY
        self._started = False
        self.settings = dict(settings)

    def start_doc(self, doc_name: str):
        di = DOCINFOW()
        di.cbSize = ctypes.sizeof(DOCINFOW)
        di.lpszDocName = doc_name
        di.lpszOutput = None
        di.lpszDatatype = None
        if _gdi32.StartDocW(self._hdc, ctypes.byref(di)) <= 0:
            raise PrintError(f"StartDoc 失败（错误 {ctypes.get_last_error()}）")
        self._started = True

    def new_page(self):
        if not _gdi32.StartPage(self._hdc):
            raise PrintError(f"StartPage 失败（错误 {ctypes.get_last_error()}）")
        if not _gdi32.EndPage(self._hdc):
            raise PrintError(f"EndPage 失败（错误 {ctypes.get_last_error()}）")

    def close(self):
        try:
            if self._started:
                _gdi32.EndDoc(self._hdc)
        finally:
            _gdi32.DeleteDC(self._hdc)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def _draw_image(hdc: int, img: Image.Image, pw: int, ph: int, settings: dict, dpi: int = 300):
    """把 PIL 图片绘制到打印机 DC（设备像素坐标）"""
    from PIL import ImageWin  # 仅 Windows 使用，惰性导入
    img = _apply_orientation(img, settings)
    if settings.get("color") == "mono":
        img = img.convert("L")
    rect = _fit_rect(img, pw, ph, settings)
    dib = ImageWin.Dib(img)
    dib.draw(hdc, rect)


def parse_page_range(spec, total: int) -> list:
    """解析页码范围，如 "1-3,5" → [0,1,2,4]（0 基）。
    空/非法/越界 → 全部页；重复页去重；倒序区间自动正序。
    """
    if not spec or not str(spec).strip():
        return list(range(total))
    spec = str(spec).strip().replace("，", ",").replace(" ", "")
    pages = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, _, b = part.partition("-")
            try:
                lo, hi = int(a), int(b)
            except ValueError:
                continue
            if lo > hi:
                lo, hi = hi, lo
            for p in range(lo, hi + 1):
                if 1 <= p <= total:
                    pages.append(p - 1)
        else:
            try:
                p = int(part)
            except ValueError:
                continue
            if 1 <= p <= total:
                pages.append(p - 1)
    if not pages:
        return list(range(total))
    return sorted(set(pages))


def pdf_page_images(pdf_path: str, settings: dict):
    """把 PDF 页渲染为设备像素位图（yield 供逐个打印）"""
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    dpi = 300
    zoom = dpi / 72.0
    with fitz.open(pdf_path) as doc:
        total = doc.page_count
        pages = parse_page_range(settings.get("pages", ""), total)
        for i in pages:
            page = doc.load_page(i)
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            if settings.get("color") == "mono":
                img = img.convert("L")
            yield img, i + 1, total


def print_pdf(pdf_path: str, printer_name: str, settings: dict):
    """打印 PDF：按设置渲染每页并逐页送出"""
    _ensure_winapi()
    pages = list(pdf_page_images(pdf_path, settings))
    if not pages:
        raise PrintError("没有可打印的页面")
    copies = max(1, min(99, int(settings.get("copies", 1) or 1)))
    with PrinterDC(printer_name, settings) as dc:
        dc.start_doc("SmartPrint")
        for _ in range(copies):
            for img, pno, total in pages:
                _draw_image(dc._hdc, img, dc.page_w, dc.page_h, settings, dpi=dc.dpi_x)
                dc.new_page()


def print_test_page(printer_name: str, settings: dict):
    """打印测试页（A4 居中一行字）"""
    _ensure_winapi()
    with PrinterDC(printer_name, settings) as dc:
        dc.start_doc("SmartPrint 测试页")
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text((120, 420), "SmartPrint 测试页", fontsize=28, fontname="china-s")
        page.insert_text((120, 470), "打印成功！本页由 SmartPrint 扫码打印服务输出。",
                         fontsize=14, fontname="china-s")
        pix = page.get_pixmap(matrix=fitz.Matrix(300 / 72, 300 / 72), alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        doc.close()
        _draw_image(dc._hdc, img, dc.page_w, dc.page_h, settings, dpi=dc.dpi_x)
        dc.new_page()
