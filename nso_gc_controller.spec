# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for NSO GameCube Controller

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs

block_cipher = None

# Find vgamepad location
import vgamepad
vgamepad_path = os.path.dirname(vgamepad.__file__)

# Manually specify the DLL paths to ensure correct folder structure
vgamepad_datas = [
    # Include the entire vgamepad package with correct structure
    (os.path.join(vgamepad_path, 'win', 'vigem', 'client', 'x64', 'ViGEmClient.dll'),
     os.path.join('vgamepad', 'win', 'vigem', 'client', 'x64')),
    (os.path.join(vgamepad_path, 'win', 'vigem', 'client', 'x86', 'ViGEmClient.dll'),
     os.path.join('vgamepad', 'win', 'vigem', 'client', 'x86')),
]

# Also try to get any install files if they exist
install_path = os.path.join(vgamepad_path, 'win', 'vigem', 'install')
if os.path.exists(install_path):
    for f in os.listdir(install_path):
        vgamepad_datas.append((
            os.path.join(install_path, f),
            os.path.join('vgamepad', 'win', 'vigem', 'install')
        ))

# Collect bleak data files
bleak_datas = collect_data_files('bleak')

a = Analysis(
    ['nso_gc_gui_2.py'],
    pathex=[],
    binaries=[],
    datas=vgamepad_datas + bleak_datas,
    hiddenimports=[
        'bleak.backends.winrt',
        'bleak.backends.winrt.scanner',
        'bleak.backends.winrt.client',
        'asyncio',
        'tkinter',
        'vgamepad',
        'vgamepad.win',
        'vgamepad.win.vigem_commons',
        'vgamepad.win.vigem_client',
        'vgamepad.win.virtual_gamepad',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='NSO_GC_Controller',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window - GUI only
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if you have one: icon='icon.ico'
    version='version_info.txt',  # Version info file (optional)
)
