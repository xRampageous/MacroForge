# MacroForge Release Workflow

Bump version, build, and ship a new release with auto-update support.

## Prerequisites

- `version.py` has the version you want to ship
- All changes are committed and pushed to `main`
- GitHub repo: `https://github.com/xRampageous/MacroForge`

## Steps

1. **Bump version** in `version.py`:
   ```python
   VERSION = "X.Y.Z"
   ```

2. **Run build** (generates `update.json` automatically):
   ```powershell
   cd C:\Users\Andie\MacroForge
   .\build.bat
   ```
   // turbo
   This produces:
   - `dist\MacroForge\MacroForge.exe`
   - `update.json` (auto-bumped version + URL)
   - `installer\MacroForge-Setup.exe` (optional, only if Inno Setup is in PATH)

3. **Commit the version bump**:
   ```powershell
   git add version.py update.json
   git commit -m "Bump vX.Y.Z"
   git push
   ```

4. **Create GitHub Release**:
   - Go to `https://github.com/xRampageous/MacroForge/releases`
   - Click **Draft a new release**
   - Choose tag: `vX.Y.Z` (create new)
   - Title: `MacroForge vX.Y.Z`
   - Description: bullet list of changes
   - Upload `dist\MacroForge\MacroForge.exe` as the release asset
   - Click **Publish release**

5. **Done** — installed clients auto-detect the update within ~30 seconds of opening.

## When users MUST reinstall

Users only need to run the installer again if:
- You added a **new Python file** (e.g., `dialogs_settings.py`) — the auto-updater only replaces the `.exe`, not the `_internal` folder where Python modules live.
- You upgraded a **dependency** (e.g., new `cv2` version).
- You changed the **installer behavior** (registry, shortcuts, etc.).

For releases that only change existing `.py` files without adding new ones, the auto-updater handles it (old code in `_internal` gets overwritten when the new `.exe` runs... actually no, `_internal` is NOT replaced).

**Rule of thumb**: if `git status` shows a new `.py` file, users must reinstall. Otherwise, auto-update is enough.
