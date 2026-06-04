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

4. **Create GitHub Release** (automated if `gh` CLI is in PATH):

   `build.bat` will automatically create the release and upload assets if `gh` is available:
   ```
   [AUTO] GitHub CLI found — creating release vX.Y.Z...
   [AUTO] Uploading assets...
   [AUTO] Release vX.Y.Z published with assets.
   ```

   If `gh` is **not** found, do it manually:
   ```powershell
   gh release create vX.Y.Z --repo xRampageous/MacroForge --title "MacroForge vX.Y.Z" --notes "Release vX.Y.Z"
   gh release upload vX.Y.Z --repo xRampageous/MacroForge --clobber dist\MacroForge\MacroForge.exe dist\MacroForge-vX.Y.Z.zip
   ```

   > **Why two commands?** `gh release create --attach` sometimes silently drops files. Using `create` then `upload` is bulletproof.

5. **Done** — installed clients auto-detect the update within ~30 seconds of opening. The updater downloads the ZIP, extracts it, and replaces both the `.exe` and `_internal` folder automatically.

## When users MUST reinstall

Users only need to run the installer again if:
- You changed the **installer behavior** (registry, shortcuts, install path, etc.).

**Auto-update now handles everything else** — new Python files, dependency upgrades, code changes — because the ZIP contains the full `dist/MacroForge` folder.
