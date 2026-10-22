# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import ssl

# Some Python runtimes require this file whenever SSLContext is constructed,
# including aiohttp's import-time initialization for a plain HTTP server.
runtime_data = []
certificate = Path(ssl.__file__).with_name('codex-rejected-cas.pem')
if certificate.is_file():
    runtime_data.append((str(certificate), '.'))


a = Analysis(
    ['console_main.py'],
    pathex=[],
    binaries=[],
    datas=[('web', 'web')] + runtime_data,
    hiddenimports=['pynput.keyboard._win32', 'pynput.mouse._win32'],
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
    a.binaries,
    a.datas,
    [],
    name='KeyboardMonitorLab',
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
