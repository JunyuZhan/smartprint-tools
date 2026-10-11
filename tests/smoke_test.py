# -*- coding: utf-8 -*-
"""打印引擎冒烟测试：验证打印机枚举 / DEVMODE / DC / 页面渲染（仅 Windows 手动运行）"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

print("\n== 打印机枚举 ==")
from smartprint import printer
names = printer.list_printers()
print("打印机列表：", names)
print("默认打印机：", printer.get_default_printer())

print("\n== 页码解析 ==")
print('1-3,5 →', printer.parse_page_range("1-3,5", 10))
print('空 →', printer.parse_page_range("", 5))

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
print(f"渲染页数：{len(images)}")

print("\n== DEVMODE / DC ==")
pname = printer.resolve_printer("")
print("目标打印机：", pname)
dev = printer.build_devmode(pname, {"color": "mono", "duplex": "long", "copies": 2})
print("DEVMODE 长度：", len(dev))
with printer.PrinterDC(pname, {"color": "mono", "duplex": "single", "copies": 1}) as dc:
    print("DC 分辨率：", dc.dpi_x, "x", dc.dpi_y, " 页面：", dc.page_w, "x", dc.page_h)

print("\n== 实际打印（约 10 秒） ==")
printer.print_pdf(smoke_pdf, pname, settings)
print("已提交打印，请检查打印机输出。")
