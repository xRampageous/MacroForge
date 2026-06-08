# MacroForge v3.9.8 — Stability + Premium Polish

## Highlights

- Bumped app/update metadata to `3.9.8`.
- Added a dedicated Macro Health / Pre-flight button to the playback controls.
- Improved macro health reporting with a clearer Ready / Needs review / Blocked summary.
- Added pre-flight warnings for empty folders and instant image-match timeouts.
- Polished the playback panel so the progress bar expands with the window while stat chips stay fixed-size.
- Increased playback panel readability with slightly larger controls and stat values.
- Upgraded timeline active-row rendering with richer action-colour gradients, glow, sheen, and scan sweep polish.
- Reworked timeline runtime badges into compact `RUN`, `WAIT`, `DONE`, `FAIL`, `SCAN`, `SKIP`, and `PAUSE` states.
- Improved image action row feedback: engine states now display as friendly `Searching`, `Matched`, `Failed`, or `Timeout` text.
- Added gradient progress fills and an active progress pulse on the running timeline row.

## Changed files

- `version.py`
- `update.json`
- `ui/timeline.py`
- `ui/playback_panel.py`
- `ui/main_window.py`
- `docs/CHANGELOG_3.9.8.md`

## Smoke test notes

Run from the project root on Windows after installing the normal project dependencies:

```bat
py -m pytest
build.bat --fast
```

Manual UI checks:

1. Launch MacroForge and confirm the version reports `3.9.8`.
2. Click the new check button in the playback controls and confirm Macro Health opens.
3. Create an empty folder row and confirm the health checker shows a warning.
4. Create an image action with no template and confirm playback is blocked by pre-flight.
5. Run a short macro and confirm the active timeline row shows the new glow/gradient treatment.
6. Resize the window and confirm the bottom progress bar expands while stat chips stay fixed-size.
