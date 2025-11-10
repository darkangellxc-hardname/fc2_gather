# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['fc2_gui.py'],
    pathex=[],
    binaries=[],
    datas=[('fc2_core.py', '.'), ('ico.ico', '.')],
    hiddenimports=['fc2_core', 'dukpy', 'pypac'],
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
    name='FC2Gather',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['ico.ico'],
)
