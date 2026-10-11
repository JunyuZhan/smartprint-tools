# -*- coding: utf-8 -*-
"""生成端到端测试文件：PDF / 图片 / Word 文档"""
import os
import sys
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

OUT = os.path.join(BASE, "testfiles")


def main():
    import pymupdf as fitz
    from PIL import Image, ImageDraw

    os.makedirs(OUT, exist_ok=True)

    # 1) PDF：两页中文文本
    doc = fitz.open()
    for i in (1, 2):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 120), f"SmartPrint 测试文档 第{i}页", fontsize=22, fontname="china-s")
        page.insert_text((72, 200), "扫码打印：上传文件 → 设置 → 打印", fontsize=14, fontname="china-s")
        page.insert_text((72, 240), "支持彩色/黑白、单双面、份数、页码范围。", fontsize=14, fontname="china-s")
    doc.save(os.path.join(OUT, "测试文档.pdf"))
    doc.close()

    # 2) PNG 图片：240x160 蓝底白字
    img = Image.new("RGB", (240, 160), (30, 90, 200))
    d = ImageDraw.Draw(img)
    d.text((40, 70), "测试图片", fill="white")
    img.save(os.path.join(OUT, "测试图片.png"))

    print("测试文件已生成到", OUT)


if __name__ == "__main__":
    main()
