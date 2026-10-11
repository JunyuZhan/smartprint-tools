# -*- coding: utf-8 -*-
"""SmartPrint 二维码与墙上海报生成"""
import io

import qrcode
from PIL import Image, ImageDraw, ImageFont

from . import printer

# 中文字体候选（Windows）
_FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",      # 微软雅黑
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/simhei.ttf",    # 黑体
    "C:/Windows/Fonts/simsun.ttc",    # 宋体
]
_FONT_CACHE = {}


def _font(size: int, bold: bool = False):
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    for path in _FONT_CANDIDATES:
        try:
            f = ImageFont.truetype(path, size)
            _FONT_CACHE[key] = f
            return f
        except Exception:
            continue
    f = ImageFont.load_default()
    _FONT_CACHE[key] = f
    return f


def qr_bytes(url: str, size: int = 420) -> bytes:
    qr = qrcode.QRCode(
        version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=12, border=2
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    if size and img.size[0] != size:
        img = img.resize((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def build_poster(url: str, office_name: str, extra: str = "") -> bytes:
    """生成 A4 竖版墙上海报 PNG（1600x2264，约 150 DPI）"""
    W, H = 1600, 2264
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    # 顶部色块
    d.rectangle([0, 0, W, 320], fill=(33, 120, 255))
    d.text((W // 2, 130), office_name or "扫码打印", font=_font(110, True),
           fill="white", anchor="mm")
    d.text((W // 2, 235), "手机扫码 · 上传文件 · 一键打印", font=_font(46),
           fill=(220, 235, 255), anchor="mm")

    # 二维码
    qr = qrcode.QRCode(
        version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=16, border=3
    )
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_size = 1150
    qr_img = qr_img.resize((qr_size, qr_size), Image.LANCZOS)
    img.paste(qr_img, ((W - qr_size) // 2, 430))

    # 提示文字
    lines = ["1. 手机连接本打印机所在网络", "2. 用相机 / 微信扫一扫上方二维码",
             "3. 选择要打印的文件（图片 / PDF / Word）",
             "4. 设置黑白彩色、单双面、份数", "5. 点击「打印」，即可到打印机取件"]
    if extra:
        lines.append(extra)
    y = 430 + qr_size + 90
    for ln in lines:
        d.text((W // 2, y), ln, font=_font(52), fill=(40, 40, 40), anchor="mm")
        y += 110
    # 底部 URL 展示
    d.text((W // 2, H - 150), url, font=_font(40), fill=(120, 120, 120), anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def print_poster(url: str, office_name: str, printer_name: str, settings: dict):
    """把海报打印出来（供贴墙使用）"""
    from pathlib import Path
    import tempfile
    from . import converters
    pname = printer.resolve_printer(printer_name)
    with tempfile.TemporaryDirectory() as td:
        png = Path(td) / "poster.png"
        png.write_bytes(build_poster(url, office_name))
        pdf = converters.ensure_pdf(png, Path(td))
        printer.print_pdf(str(pdf), pname, settings)
