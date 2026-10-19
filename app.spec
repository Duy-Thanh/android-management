# -*- mode: python ; coding: utf-8 -*-

import os
import sys

block_cipher = None

# Determine the current directory
spec_dir = os.path.dirname(os.path.abspath(SPEC))

# Include the bin/platform-tools directory in the bundle, if present.
datas = []
local_bin = os.path.join(spec_dir, 'bin')
if os.path.exists(local_bin):
    datas.append((local_bin, 'bin'))

a = Analysis(
    ['app.py'],
    pathex=[spec_dir],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'urllib.request',
        'zipfile',
        'shutil',
        'sys',
        'subprocess',
        'os',
        'urllib',
        'urllib.request',
        'time'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'matplotlib', 'numpy', 'IPython'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AndroidDeviceManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to False to hide the black terminal window when the GUI is launched.
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # If you have an .ico or .png icon file, enter its path here.
)
