# -*- mode: python ; coding: utf-8 -*-
import os
import sys

platform_tag = "windows" if sys.platform == "win32" else "macos"
version_tag = os.environ.get("LOUDSCAN_VERSION")

a = Analysis(
    ["sound_report.py"],
    pathex=["."],
    binaries=[],
    datas=[("reference_models.json", ".")],
    hiddenimports=[],
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
    a.binaries,
    a.datas,
    [],
    name=f"LoudScan-{platform_tag}" + (f"-{version_tag}" if version_tag else ""),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
