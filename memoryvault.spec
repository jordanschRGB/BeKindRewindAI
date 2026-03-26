# -*- mode: python ; coding: utf-8 -*-
import os
import platform

block_cipher = None

# Platform-specific pystray backend
if platform.system() == 'Windows':
    pystray_hidden = ['pystray._win32']
elif platform.system() == 'Darwin':
    pystray_hidden = ['pystray._darwin']
else:
    pystray_hidden = ['pystray._xorg']

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
    ],
    hiddenimports=pystray_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MemoryVault',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
)
