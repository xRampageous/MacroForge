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

2. **Run build** (generates `update.json` + ZIP automatically):
   ```powershell
   cd C:\Users\Andie\MacroForge
   .\build.bat
   ```
   // turbo
   This produces:
   - `dist\MacroForge\MacroForge.exe`
   - `dist\MacroForge-vX.Y.Z.zip` — **full update package** (exe + _internal)
   - `update.json` (auto-bumped version + ZIP URL)
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
   - Upload **both** assets:
     - `dist\MacroForge\MacroForge.exe`
     - `dist\MacroForge-vX.Y.Z.zip`
   - Click **Publish release**

5. **Done** — installed clients auto-detect the update within ~30 seconds of opening. The updater downloads the ZIP, extracts it, and replaces both the `.exe` and `_internal` folder automatically.

## When users MUST reinstall

Users only need to run the installer again if:
- You changed the **installer behavior** (registry, shortcuts, install path, etc.).

**Auto-update now handles everything else** — new Python files, dependency upgrades, code changes — because the ZIP contains the full `dist/MacroForge` folder.
