# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ctk_datas = collect_data_files('customtkinter')
ctk_submodules = collect_submodules('customtkinter')

spec_dir = os.path.dirname(os.path.abspath(SPEC))
root_dir = os.path.abspath(os.path.join(spec_dir, ".."))
web_dir = os.path.join(root_dir, "web")

web_files = [
    'index.html', 'client.html', 'host.html', 'login.html', 'guide.html',
    'styles.css', 'client_styles.css', 'host_styles.css',
    'scripts.js', 'host_scripts.js', 'feedback.js', 'p2p.js',
    'peerjs.min.js', 'qrcode.min.js', 'manifest.json', 'sw.js',
    'app_icon.png', 'app_icon.ico'
]

datas = [
    (os.path.join(spec_dir, 'app_icon.ico'), '.'),
    (os.path.join(spec_dir, 'app_icon.png'), '.'),
    (os.path.join(spec_dir, 'main.py'), '.'),
]

for wf in web_files:
    full_path = os.path.join(web_dir, wf)
    if os.path.exists(full_path):
        datas.append((full_path, 'web'))
        datas.append((full_path, '.'))

datas += ctk_datas

a = Analysis(
    [os.path.join(spec_dir, 'app_gui.py')],
    pathex=[spec_dir, root_dir],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'ifaddr',
        'customtkinter',
        'PIL',
        'requests',
        'zeroconf',
        'png',
        'pyqrcode',
        'darkdetect',
        'windnd',
        'main'
    ] + ctk_submodules,
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
    icon=[os.path.join(spec_dir, 'app_icon.ico')],
)
