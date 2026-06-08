# MacroForge v3.9.8 Hotfix — UI Theme Packaging

## Fixed

- Added `ui/theme.py` to the changed-files patch package so partial patch installs do not crash at startup.
- Hardened both PyInstaller specs to collect every `ui.*` module through `collect_submodules('ui')`.
- Added `ui/theme.py` as a data file fallback in both build specs.
- Added a build preflight check that stops early if `ui/theme.py` or the `ui.theme` import is missing.

## Notes

If you already built once and still see `ModuleNotFoundError: No module named 'ui.theme'`, rebuild without the fast cache once:

```bat
build.bat --no-installer
```

After that, `build.bat --fast` can be used again.
