# -*- mode: python ; coding: utf-8 -*-
# Build:  pyinstaller --noconfirm relisto.spec
import os
import sys

HERE = os.path.abspath(SPECPATH)
LOGO = os.path.join(HERE, "assets", "logo.png")
ICNS = os.path.join(HERE, "assets", "relisto.icns")
ICO = os.path.join(HERE, "assets", "relisto.ico")

datas = [(LOGO, "assets")] if os.path.exists(LOGO) else []
if sys.platform == "darwin":
    icon = ICNS if os.path.exists(ICNS) else None
else:
    icon = ICO if os.path.exists(ICO) else None

a = Analysis(
    [os.path.join(HERE, "relisto.py")],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Relisto",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Relisto",
)
app = BUNDLE(
    coll,
    name="Relisto.app",
    icon=icon,
    bundle_identifier="app.relisto",
    info_plist={
        "CFBundleDisplayName": "Relisto",
        "CFBundleName": "Relisto",
        "CFBundleShortVersionString": "1.0.0",
        "NSHighResolutionCapable": True,
    },
)
