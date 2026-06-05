# MacroForge Final Timeline Polish 28

## Scope
This is a focused final polish pass built on the uploaded `MacroForge(8).zip` source.

It keeps the existing timeline size, row height, colors, action model, save/load data, macro execution behavior, grouping/collapse behavior, and button callbacks intact. The changes are layout polish, transient runtime-visual reset cleanup, and one compact Debug toolbar entry.

## Timeline polish
- Cut grouped child row cards in from the left so the far-left gutter contains only the group connector rail, node, and short branch line.
- Moved grouped child row card painting, active highlights, hover/selection/search borders, stripe, grip, number, icon, text, status, duration, progress, and right controls into the new cut-in card rect.
- Kept normal rows and group header rows full-width.
- Refined group connector rails so they use the untouched gutter, start/stop cleanly, and consider visible child rows.
- Added shared row geometry helpers so delegate painting and drag/kebab hitboxes use the same visible card positions.
- Kept the TRACE text badge removed; trace logic and subtle tint remain.
- Added `TimelineView.clear_runtime_visuals()` as one helper for visual runtime cleanup.

## Toolbar/status polish
- Fixed the top-right status pill so longer status text can expand left from the anchored right edge.
- Reworked status text to use pixel-width elision instead of a fixed 43-character pre-truncation.
- Preserved the full status message in the tooltip.
- Added a narrow-width fallback so the Debug button becomes icon-only before the status pill breaks.

## Add Action panel polish
- Locked the Add Action grid inside a fixed-width host matching the Folder button.
- Aligned the left and right action button columns with the Folder button edges so extra side-panel width no longer makes the columns drift apart.
- Kept Add Action colors, callbacks, visual height, and Folder button treatment intact.

## Debug toolbar addition
- Added a compact `Debug` button beside the existing top-right toolbar buttons.
- Added a fallback Debug tools menu with: Editor, Health, Runtime, Filters, Debug.
- The entries call existing tools/panels only; no heavy new debug system was added.

## Runtime visual reset cleanup
- Stop/start already cleared stale runtime marks; this patch routes visual cleanup through the new shared helper.
- Added loop-boundary visual reset support so trace/image/progress visuals reset at the start of each new top-level playback loop iteration.
- Loop counters and runtime logs are preserved.

## Manual smoke test checklist
1. Expand/collapse G1/G2 and confirm child row cards start after the connector gutter.
2. Confirm only connector rail/node/branch appear in the grouped-row far-left gutter.
3. Drag grouped and ungrouped rows from the grip dots.
4. Right-click or use kebab/chevron controls on normal/group rows.
5. Run a macro with image actions until `Found` appears.
6. Press Stop and confirm `Found`, `Waiting`, `Missed`, trace tint, link highlights, and progress reset.
7. Run multiple playback loops and confirm trace/image visual marks clear between loop passes.
8. Resize the window and confirm the top status pill expands left for longer text.
9. Confirm the Debug button opens the Editor / Health / Runtime / Filters / Debug menu.
10. Confirm all Add Action buttons still open their correct dialogs.
