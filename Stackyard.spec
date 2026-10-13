# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: builds a single, windowed Stackyard.exe.

Build with:  python -m PyInstaller --noconfirm --clean Stackyard.spec
The executable is written to dist\\Stackyard.exe.
"""
from pathlib import Path

project = Path(SPECPATH)
icon = project / "assets" / "stackyard.ico"

a = Analysis(
    ["stackyard.pyw"],
    pathex=[str(project)],
    binaries=[],
    datas=[("assets", "assets")],   # bundled to _MEIPASS/assets, read via core.RESOURCE_DIR
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
    name="Stackyard",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                 # no console window (GUI app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon),
)
