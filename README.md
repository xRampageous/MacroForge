# MacroForge

A Windows macro automation tool with a modern dark UI, system tray integration, and auto-updates.

## Features

- **Visual Action Timeline** — Add, reorder, and edit keyboard/mouse/image actions
- **Playback Engine** — Run macros with configurable loops, speed, and human-like curves
- **Recording** — Record live keyboard and mouse input
- **System Tray** — Minimize to tray; global hotkeys (F5–F9) for control
- **Auto-Update** — Checks GitHub releases automatically; one-click install
- **Profiles** — Multiple named profiles with automatic save/restore
- **Import / Export** — JSON and CSV support for sharing macros

## Tech Stack

- Python 3.x
- PyQt6 (modern dark theme)
- PIL / OpenCV for image matching
- pynput for global hotkeys and recording
- pyautogui for input simulation
- PyInstaller + Inno Setup for distribution

## Build

```bash
# Requires: Python, PyInstaller, Inno Setup
build.bat
```

Output:
- `dist\MacroForge\MacroForge.exe` — portable app
- `installer\MacroForge-Setup.exe` — Windows installer

## Update System

1. Bump `version.py` and build
2. Create a GitHub Release and upload `dist\MacroForge\MacroForge.exe`
3. Update `update.json` with the new version and download URL
4. Push `update.json` — installed apps will detect it automatically

## License

MIT
