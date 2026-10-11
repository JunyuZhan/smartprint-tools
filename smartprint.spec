# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包配置：生成 dist\SmartPrint\SmartPrint.exe（免安装绿色版）
from PyInstaller.utils.hooks import collect_submodules

a = Analysis(
    ['server.py'],
    pathex=[],
    binaries=[],
    datas=[('smartprint/web', 'smartprint/web')],
    hiddenimports=['win32timezone'] + collect_submodules('win32com'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SmartPrint',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # 无控制台窗口（托盘运行）
    disable_windowed_traceback=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name='SmartPrint',
)
