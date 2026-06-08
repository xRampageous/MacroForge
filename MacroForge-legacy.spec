# -*- mode: python ; coding: utf-8 -*-
"""Onefile legacy/update asset for MacroForge.

The main release ZIP is built from the onedir bundle in ``MacroForge.spec``.
This spec produces ``dist/MacroForge.exe`` as a true standalone executable for
older clients and manual downloads that still use update.json ``url``.
"""

from PyInstaller.building.build_main import Analysis, PYZ, EXE
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_dynamic_libs

import os

SPEC_DIR = os.path.abspath(os.path.dirname(__name__ if "__file__" not in dir() else __file__))
os.chdir(SPEC_DIR)

pyqt6_hiddenimports = [
    "PyQt6",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
]
pyqt6_binaries = []
pyqt6_datas = []

cv2_binaries, cv2_datas, cv2_hidden = collect_all("cv2")

for pkg in ("PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets"):
    pyqt6_binaries += collect_dynamic_libs(pkg)

ui_hiddenimports = collect_submodules("ui")

project_hiddenimports = [
    "models",
    "engine",
    "debugger",
    "updater",
    "hotkeys",
    "version",
    "ui.theme",
    "ui.main_window",
    "ui.timeline",
    "ui.dialogs",
    "ui.dialogs.key_dialog",
    "ui.dialogs.pause_dialog",
    "ui.dialogs.click_dialog",
    "ui.dialogs.image_dialog",
    "ui.dialogs.settings_dialog",
    "cv2",
    "PIL",
    "PIL.Image",
    "pyautogui",
    "pynput.keyboard._win32",
    "pynput.mouse._win32",
    "requests",
    "urllib3",
    "certifi",
]

datas = [
    ("MacroForge.ico", "."),
    ("MacroForge.png", "."),
    ("version.py", "."),
    ("ui/theme.py", "ui"),
]

a = Analysis(
    ["MacroForge.py"],
    pathex=[SPEC_DIR],
    binaries=pyqt6_binaries + cv2_binaries,
    datas=datas + pyqt6_datas + cv2_datas,
    hiddenimports=pyqt6_hiddenimports + project_hiddenimports + ui_hiddenimports + cv2_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "_tkinter", "Tkinter", "tcl", "tk"],
    module_collection_mode={
        "tkinter": "py",
        "_tkinter": "py",
    },
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=True,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MacroForge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=["MacroForge.ico"],
)
