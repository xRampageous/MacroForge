# MacroForge 2.0 Rebuild Plan

This branch starts the MacroForge 2.0 migration while keeping the current app runnable.
The approach is staged: preserve existing features and layout language, then move core systems into smaller modules one at a time.

## Immediate 2.0 layout change applied

- Removed the old playback card from the left sidebar.
- Added a wider playback panel in the main content area, directly below the timeline.
- Kept the progress bar and stats on the bottom bar.
- Rebuilt the bottom stats as icon chips with clearer labels, tooltips, and stronger visual hierarchy.

## Target architecture

```text
macroforge2/
  core/
    actions.py          # typed action model and normalization
    project.py          # project/profile load/save boundaries
    validation.py       # preflight checks before playback
    history.py          # single undo/redo implementation
  engine/
    runner.py           # playback state machine
    input_backend.py    # keyboard/mouse/window abstractions
    recorder.py         # recorder normalization
    focus.py            # target-window capture and refocus
  ui/
    components/
      playback_panel.py # reusable 2.0 playback deck
      stats_bar.py      # reusable progress/stat chips
    timeline/           # future virtual canvas timeline split
  services/
    autosave.py
    logging_service.py
    hotkeys.py
```

## Migration stages

1. **Layout shell**: decouple the play panel and stats from the sidebar. Done in this patch.
2. **Core model split**: move `Action`, profile/session, validation, and history out of the main window.
3. **Engine split**: turn `engine.py` into a smaller runner with separate input/focus/scheduler backends.
4. **Recorder normalization**: record combos, mouse, scroll, and delays as explicit action types.
5. **Timeline split**: move timeline state, drawing, search, and interaction into separate components.
6. **Preflight validation**: catch broken keys, jumps, loops, missing files, and unsupported actions before playback.
7. **Testable core**: add non-GUI tests that run without launching PyQt6.

## Compatibility rule

During migration, the existing root-level modules remain importable. New 2.0 modules should begin as adapters/re-exports, then absorb logic as features are migrated.
