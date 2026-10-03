# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules
ROOT = Path.cwd().resolve()
hiddenimports = collect_submodules('PySide6.QtMultimedia')
a = Analysis([str(ROOT/'main.py')], pathex=[str(ROOT)], binaries=[], datas=[], hiddenimports=hiddenimports, hookspath=[], runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='Junba_KTV_MultiTrack_v1.4', debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=False, version=str(ROOT/'packaging'/'version_info.txt'))
