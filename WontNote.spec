# -*- mode: python ; coding: utf-8 -*-
block_cipher = None

datas = [
    # Web UI assets
    ('wontnote/gui/web/index.html',     'wontnote/gui/web'),
    ('wontnote/gui/web/style.css',      'wontnote/gui/web'),
    ('wontnote/gui/web/icons.js',       'wontnote/gui/web'),
    ('wontnote/gui/web/preferences.js', 'wontnote/gui/web'),
    # pythonnet runtime DLL (required by pywebview WinForms backend)
    ('.venv/Lib/site-packages/pythonnet/runtime', 'pythonnet/runtime'),
]

hiddenimports = [
    'webview',
    'webview.platforms.winforms',
    'webview.platforms.edgechromium',
    'clr',
    'clr_loader',
    'argon2',
    'argon2.low_level',
    'cryptography',
    'cryptography.hazmat.primitives.ciphers.aead',
    'cryptography.hazmat.primitives.kdf.hkdf',
    'cryptography.hazmat.primitives.hashes',
    'cryptography.hazmat.backends',
    'platformdirs',
]

a = Analysis(
    ['wontnote/__main__.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=['.venv/Lib/site-packages/pythonnet/_pyinstaller'],
    hooksconfig={},
    runtime_hooks=['pyi_rth_pythonnet.py'],
    excludes=['pytest', 'tkinter', 'unittest', '_tkinter'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WontNote',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WontNote',
)
