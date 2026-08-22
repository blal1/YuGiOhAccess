# -*- mode: python ; coding: utf-8 -*-

import sys
sys.path.append('specs')
import common



a = Analysis(
    ['../src/YuGiOhAccess.py'],
    pathex=[],
    binaries=common.binaries,
    datas=common.datas,
    hiddenimports=common.hiddenimports,
    hookspath=common.hookspath,
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [('O', None, 'OPTION'), ('O', None, 'OPTION')],
    exclude_binaries=True,
    name='YuGiOhAccess',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='YuGiOhAccess',
)
app = BUNDLE(
    coll,
    name='YuGiOhAccess.app',
    icon=None,
    bundle_identifier="com.yugiohaccess.client",
             info_plist={
                "NSAppleEventsUsageDescription": "YuGiOh Access needs automation access to control VoiceOver.",
                "NSAccessibilityUsageDescription": "YuGiOh Access needs accessibility access to control VoiceOver.",
             },
)
