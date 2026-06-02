# MacroForge 3.0.6 — Pre-flight Check + Log Limits

This patch adds a safer run validation layer and bounded diagnostics/debug logs.

## Added

- Run pre-flight check before normal playback starts.
- New menu command: `Run pre-flight check…`.
- Diagnostics log now records pre-flight results.
- In-app playback diagnostics keeps only the newest 10,000 lines.
- File-based `debug.log` keeps only the newest 10,000 lines.
- Debug log is trimmed on startup and periodically while the app runs.
- Debug viewer `Clear` now clears the in-memory and on-disk log.

## Pre-flight checks

The validator checks for:

- Empty timeline.
- Negative durations.
- Very long durations.
- Invalid repeat counts.
- Unknown key names and invalid key combos.
- Missing image template data.
- Invalid image similarity values.
- Negative image wait timeout values.
- Invalid image on-found key actions.
- Broken image jump targets.
- Invalid click button / coordinate mode.
- Invalid condition jump targets.
- Simulation mode warning.
- Focus lock warning if no target is captured.

## Playback behavior

Errors block playback.
Warnings ask whether to continue.

Engine deployment behavior is not changed by this patch.
