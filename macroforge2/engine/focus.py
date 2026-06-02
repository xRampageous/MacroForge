"""Target-window focus helpers for the MacroForge 2.0 engine split."""


def focus_lock_available() -> bool:
    """Return whether the current platform can support focus-lock work.

    The current implementation is Windows-oriented and lives in `engine.py`.
    """
    return True
