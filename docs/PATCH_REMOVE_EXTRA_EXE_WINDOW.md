# Patch: Remove extra MacroForge.exe helper window

## Purpose

This patch removes the tiny secondary window that could appear beside the main
MacroForge client on Windows. The visible symptom looked like a narrow vertical
pill/scrollbar and was advertised by Windows as another `MacroForge.exe` window.

## Changes

- Timeline search no longer uses `Qt.WindowType.Tool` or any native top-level
  popup flags. It stays as a child overlay inside the main client.
- The old floating `REC` badge no longer creates any frameless helper widget.
  Recording status remains available inside the main MacroForge UI.
- The optional system tray icon is disabled because `QSystemTrayIcon` can create
  a tiny native helper window on some Windows/PyInstaller/PyQt combinations.
- The unused recording overlay no longer uses `Qt.WindowType.Tool`.
- Added a startup-only guard that closes tiny, untitled, auxiliary Qt helper
  windows during the first few seconds of launch. It does not run during normal
  app use.

## Validation

Run:

```bash
pytest -q tests/test_no_stray_aux_windows.py
```

Expected result:

```text
6 passed
```

## Rebuild note

This changes source code. If you are testing the packaged Windows app, rebuild
`MacroForge.exe`; launching an older packaged `.exe` will still show whatever
was baked into that build.
