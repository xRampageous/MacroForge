# MacroForge UI PNG Elements

This folder contains PNG slices extracted from the latest MacroForge UI mockup.

Important:
- These are raster assets from a flat screenshot, not editable vector/source layers.
- For the actual PyQt6 app, use these mainly as visual references.
- Buttons, panels, progress bars, and timeline rows should ideally be recreated with QSS/CSS-like styling so they scale cleanly at 680x780.
- The included `manifest.json` lists every asset and its original crop rectangle.
- `color_palette_reference.png` contains the main colours from the design.

Suggested import use:
- Use individual icons/buttons as temporary sprites.
- Use the full mockup/reference PNG beside your PyQt window while implementing.
- Rebuild text in code rather than using cropped text PNGs.
