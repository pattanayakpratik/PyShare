# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

spec_dir = os.path.dirname(os.path.abspath(SPEC))
root_dir = os.path.abspath(os.path.join(spec_dir, ".."))
web_dir = os.path.join(root_dir, "frontend")

web_files = [
    'index.html', 'landing.html', 'client.html', 'host.html', 'login.html', 'guide.html',
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
        datas.append((full_path, 'frontend'))
        datas.append((full_path, 'web'))
        datas.append((full_path, '.'))

# Collect webview data and submodules
webview_datas = collect_data_files('webview')
webview_submodules = [s for s in collect_submodules('webview') if 'android' not in s]

datas += webview_datas

a = Analysis(
    [os.path.join(spec_dir, 'app_gui.py')],
    pathex=[spec_dir, root_dir],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'ifaddr',
        'PIL',
        'requests',
        'zeroconf',
        'png',
        'pyqrcode',
        'bottle',
        'proxy_tools',
        'clr',
        'pythonnet',
        'pystray',
        'pystray._win32',
        'six',
        'main'
    ] + webview_submodules,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'customtkinter'],
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
    version=os.path.join(spec_dir, 'version_info.txt'),
    icon=[os.path.join(spec_dir, 'app_icon.ico')],
)
