"""MacroForge 2.0 action-model adapter.

This file intentionally re-exports the current Action class while the rebuild is
staged. Future patches can move typed action subclasses here without breaking the
existing UI or saved profiles.
"""

from models import Action

__all__ = ["Action"]
