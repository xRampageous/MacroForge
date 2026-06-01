# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for MacroForge (PyQt6 build).

Usage:
    python -m PyInstaller MacroForge.spec --noconfirm --clean
"""

from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_dynamic_libs

# ── Paths ──
import os
SPEC_DIR = os.path.abspath(os.path.dirname(__name__ if '__file__' not in dir() else __file__))
os.chdir(SPEC_DIR)

# ── Collect PyQt6 plugins & submodules ──
# Only include modules actually used by MacroForge to keep build lean.
pyqt6_hiddenimports = [
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
]
pyqt6_binaries = []
pyqt6_datas = []

cv2_binaries, cv2_datas, cv2_hidden = collect_all('cv2')

# PyInstaller hooks for PyQt6 handle platform plugins automatically.
# We only add extra dynamic libs if the hooks miss anything.
for pkg in ('PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets'):
    pyqt6_binaries += collect_dynamic_libs(pkg)

# ── Project hidden imports ──
project_hiddenimports = [
    # Core modules
    'models',
    'engine',
    'debugger',
    'updater',
    'hotkeys',
    'version',
    # UI package
    'ui.theme',
    'ui.main_window',
    'ui.timeline',
    'ui.dialogs',
    'ui.dialogs.key_dialog',
    'ui.dialogs.pause_dialog',
    'ui.dialogs.click_dialog',
    'ui.dialogs.image_dialog',
    'ui.dialogs.settings_dialog',
    # Third-party
    'cv2',
    'PIL',
    'PIL.Image',
    'pyautogui',
    'pynput.keyboard._win32',
    'pynput.mouse._win32',
    'requests',
    'urllib3',
    'certifi',
]

# ── Data files ──
datas = [
    ('MacroForge.ico', '.'),
    ('MacroForge.png', '.'),
    ('version.py', '.'),
]

# ── Analysis ──
a = Analysis(
    ['MacroForge.py'],
    pathex=[SPEC_DIR],
    binaries=pyqt6_binaries + cv2_binaries,
    datas=datas + pyqt6_datas + cv2_datas,
    hiddenimports=pyqt6_hiddenimports + project_hiddenimports + cv2_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', '_tkinter', 'Tkinter', 'tcl', 'tk'],
    module_collection_mode={
        'tkinter': 'py',
        '_tkinter': 'py',
    },
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# ── EXE (onedir) ──
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MacroForge',
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
    icon=['MacroForge.ico'],
)

# ── COLLECT (onedir output) ──
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MacroForge',
)
