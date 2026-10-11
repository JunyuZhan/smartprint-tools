# -*- coding: utf-8 -*-
"""打印引擎冒烟测试：验证打印机枚举 / DEVMODE / DC / 页面渲染（仅 Windows 手动运行）"""
# 手动脚本，不作为 pytest 测试模块收集（Windows 专用，顶层代码会调用打印 API）
__test__ = False

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from smartprint import printer

print("== 打印机列表 ==")
print(printer.list_printers())
pname = printer.resolve_printer("")
print("resolve ->", pname)

print("\n== DEVMODE 构造 ==")
dm_bytes = printer.build_devmode(pname, {"color": "mono", "duplex": "long", "copies": 3})
print("DEVMODE 字节数:", len(dm_bytes))

print("\n== PrinterDC 创建 + 页面参数 ==")
pdc = printer.PrinterDC(pname, {"color": "mono", "duplex": "long", "copies": 2})
print("页面(px):", pdc.page_size())
print("打印机DPI:", pdc.dpi())
pdc.close()
print("PrinterDC OK")

print("\n== 页码范围解析 ==")
assert printer.parse_page_range("1-3,5", 10) == [0, 1, 2, 4]
assert printer.parse_page_range("", 5) == [0, 1, 2, 3, 4]
assert printer.parse_page_range("8-9", 5) == [0, 1, 2, 3, 4]
assert printer.parse_page_range("3", 5) == [2]
print("parse_page_range OK")

print("\n== PDF 渲染 ==")
import pymupdf as fitz
tmp_dir = os.path.join(BASE, "data", "tmp")
os.makedirs(tmp_dir, exist_ok=True)
smoke_pdf = os.path.join(tmp_dir, "smoke.pdf")
doc = fitz.open()
page = doc.new_page(width=595, height=842)
page.insert_text((100, 200), "SmartPrint Smoke Test", fontsize=24, fontname="china-s")
page.insert_text((100, 260), "打印引擎冒烟测试第二行", fontsize=16, fontname="china-s")
doc.save(smoke_pdf)
doc.close()
settings = {"color": "color", "duplex": "single", "copies": 1, "fit": "fit", "pages": ""}
images = list(printer.pdf_page_images(smoke_pdf, settings))
print("渲染页数:", len(images), "首页尺寸:", images[0][2].size)
print("\n全部通过 ✅")
