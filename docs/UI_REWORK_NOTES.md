# MacroForge 2.0 UI Rework Notes

This patch is a UI-only modernization layer. It keeps the existing MainWindow variables, playback controls, action model, engine callbacks, recorder hooks, inspector controls, and timeline public API intact.

## Applied in this patch

- Redesigned dark theme palette with deeper navy surfaces, stronger panel contrast, and cleaner cyan accents.
- Enlarged and modernized the left sidebar while keeping the same sections:
  - Add actions
  - Recorder
  - Inspector
- Redesigned Add buttons with large tactile gradient cards and upgraded icon treatment.
- Removed the old sidebar playback card and preserved the MacroForge 2.0 docked playback panel above progress.
- Reworked the playback dock into grouped controls:
  - Start
  - Pause
  - Stop
  - Speed
  - Loops
  - Infinite loop
  - Sim / Human mode
  - Focus lock
- Improved the bottom global progress strip.
- Improved bottom-right stats chips while preserving:
  - Played
  - Loops
  - Seq
  - Time
- Rebuilt the timeline delegate into an information-rich virtual list with:
  - Row cards
  - Drag handles
  - Numbered actions
  - Action type icon tiles
  - Action title and details
  - Status dots
  - Duration metadata
  - Per-action progress bars
  - Active/running row highlight
  - Completed/pending visual states
  - Image threshold metadata chip

## Compatibility notes

- No playback-engine behavior was changed.
- No recorder behavior was changed.
- No project format changes were made.
- The timeline still uses `QListView` with a single custom delegate, avoiding widgets-per-row so it remains suitable for large action lists.
- Existing public timeline API remains in place:
  - `selected_indices`
  - `zoom`
  - `set_active()`
  - `set_playing()`
  - `clear_playing()`
  - `set_paused()`
  - `set_search()`
  - `refresh()`
  - `ensure_visible()`

## Suggested next UI upgrades

1. Add collapsible sidebar sections with remembered expanded/collapsed state.
2. Add timeline density modes: Comfortable, Compact, Ultra-compact.
3. Add a minimap/overview rail for very large macros.
4. Add action-type filters next to search.
5. Add live validation badges on each timeline row.
6. Add row-level duration heatmaps to quickly spot long waits.
7. Add a right-click “Convert to loop/condition” quick action.
8. Add command palette: Ctrl+K for add action, search, jump to action, and project commands.
9. Add theme presets: Neon Blue, Graphite, Midnight Purple, High Contrast.
10. Add an execution log drawer that slides up from the bottom during playback.
