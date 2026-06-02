"""MacroForge 2.0 undo/redo home.

The current app still has compatibility history implementations in legacy files.
This module is the planned single source of truth for history as the migration
continues.
"""

from models import HistoryManager

__all__ = ["HistoryManager"]
