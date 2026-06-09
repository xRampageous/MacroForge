# Patch: Prevent extra MacroForge.exe popup window

## Issue

A small, separate-looking MacroForge.exe window could appear beside the main client. The likely cause was internal helper UI being promoted to native top-level Qt `Tool` windows on Windows.

## Changes

- Timeline search popup is now a child overlay of the main workspace instead of a `Qt.WindowType.Tool` top-level frame.
- Timeline search popup positioning now converts from global coordinates back into the parent widget's coordinates and clamps the popup inside the main window.
- Lightweight recorder `REC` badge is now a child overlay of the main window instead of a separate always-on-top tool window.
- Added a static regression test that checks these helper overlays are not configured as `Qt.Tool` windows.

## Smoke test

1. Launch MacroForge.
2. Confirm only the main MacroForge window appears.
3. Click the timeline search button and confirm the search popup opens inside the app, not as a separate executable window.
4. Start recording and confirm the small `REC` badge appears inside the main window, not as a separate executable window.

## Test run

```text
pytest -q tests/test_no_extra_exe_window.py
3 passed
```
