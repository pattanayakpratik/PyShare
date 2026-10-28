# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

ctk_datas = collect_data_files('customtkinter')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('host.html', '.'),
        ('client.html', '.'),
        ('login.html', '.'),
        ('index.html', '.'),
        ('guide.html', '.'),
        ('styles.css', '.'),
        ('host_styles.css', '.'),
        ('client_styles.css', '.'),
        ('scripts.js', '.'),
        ('host_scripts.js', '.'),
        ('feedback.js', '.'),
        ('p2p.js', '.'),
        ('peerjs.min.js', '.'),
        ('qrcode.min.js', '.'),
        ('app_icon.ico', '.'),
        ('app_icon.png', '.'),
        ('manifest.json', '.'),
        ('sw.js', '.'),
        ('app_gui.py', '.')
    ] + ctk_datas,
    hiddenimports=[
        'ifaddr',
        'customtkinter',
        'PIL',
        'requests',
        'zeroconf',
        'png',
        'pyqrcode',
        'darkdetect'
    ],
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
    name='PyShare',
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
    icon=['app_icon.ico'],
)
