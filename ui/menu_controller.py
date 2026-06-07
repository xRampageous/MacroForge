"""Menu controller for MacroForge.

Handles all menu actions, file operations, and recent files management.
"""

from typing import Optional, List, Callable
from pathlib import Path

from PyQt6.QtWidgets import QMainWindow, QFileDialog, QMessageBox
from PyQt6.QtCore import QObject, pyqtSignal

from debugger import logger


class MenuController(QObject):
    """Controller for menu actions and file operations."""
    
    # Signals
    file_opened = pyqtSignal(str)  # filepath
    file_saved = pyqtSignal(str)   # filepath
    import_requested = pyqtSignal(str)  # filepath
    export_requested = pyqtSignal(str)   # filepath
    recent_file_selected = pyqtSignal(str)  # filepath
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._recent_files: List[str] = []
        self._max_recent = 10
        self._callbacks: dict = {}
    
    def set_callbacks(self, **callbacks: Callable):
        """Set callback functions for menu actions."""
        self._callbacks.update(callbacks)
    
    # ═══════════════════════════════════════════════════════
    #  FILE OPERATIONS
    # ═══════════════════════════════════════════════════════
    
    def new_file(self) -> bool:
        """Create new file, returns True if successful."""
        if 'new_file' in self._callbacks:
            return self._callbacks['new_file']()
        return False
    
    def open_file(self, filepath: Optional[str] = None) -> Optional[str]:
        """Open file dialog and return selected path."""
        if filepath:
            self._add_recent_file(filepath)
            self.file_opened.emit(filepath)
            return filepath
        
        # Show dialog
        if 'open_dialog' in self._callbacks:
            filepath = self._callbacks['open_dialog']()
            if filepath:
                self._add_recent_file(filepath)
                self.file_opened.emit(filepath)
            return filepath
        return None
    
    def save_file(self, filepath: Optional[str] = None) -> Optional[str]:
        """Save file, returns saved path."""
        if 'save_file' in self._callbacks:
            result = self._callbacks['save_file'](filepath)
            if result:
                self.file_saved.emit(result)
            return result
        return None
    
    def save_file_as(self) -> Optional[str]:
        """Save file with new name, returns saved path."""
        if 'save_as' in self._callbacks:
            result = self._callbacks['save_as']()
            if result:
                self._add_recent_file(result)
                self.file_saved.emit(result)
            return result
        return None
    
    # ═══════════════════════════════════════════════════════
    #  RECENT FILES
    # ═══════════════════════════════════════════════════════
    
    def get_recent_files(self) -> List[str]:
        """Get list of recent files."""
        return self._recent_files.copy()
    
    def _add_recent_file(self, filepath: str):
        """Add file to recent files list."""
        # Remove if already exists
        if filepath in self._recent_files:
            self._recent_files.remove(filepath)
        
        # Add to front
        self._recent_files.insert(0, filepath)
        
        # Trim list
        self._recent_files = self._recent_files[:self._max_recent]
    
    def clear_recent_files(self):
        """Clear recent files list."""
        self._recent_files.clear()
    
    def select_recent_file(self, index: int) -> Optional[str]:
        """Select recent file by index."""
        if 0 <= index < len(self._recent_files):
            filepath = self._recent_files[index]
            self.recent_file_selected.emit(filepath)
            return filepath
        return None
    
    # ═══════════════════════════════════════════════════════
    #  IMPORT/EXPORT
    # ═══════════════════════════════════════════════════════
    
    def import_actions(self, filepath: Optional[str] = None) -> Optional[str]:
        """Import actions from file."""
        if filepath:
            self.import_requested.emit(filepath)
            return filepath
        
        if 'import_dialog' in self._callbacks:
            filepath = self._callbacks['import_dialog']()
            if filepath:
                self.import_requested.emit(filepath)
            return filepath
        return None
    
    def export_actions(self, filepath: Optional[str] = None) -> Optional[str]:
        """Export actions to file."""
        if filepath:
            self.export_requested.emit(filepath)
            return filepath
        
        if 'export_dialog' in self._callbacks:
            filepath = self._callbacks['export_dialog']()
            if filepath:
                self.export_requested.emit(filepath)
            return filepath
        return None
    
    # ═══════════════════════════════════════════════════════
    #  MENU STATE
    # ═══════════════════════════════════════════════════════
    
    def is_dirty(self) -> bool:
        """Check if document has unsaved changes."""
        if 'is_dirty' in self._callbacks:
            return self._callbacks['is_dirty']()
        return False
    
    def can_undo(self) -> bool:
        """Check if undo is available."""
        if 'can_undo' in self._callbacks:
            return self._callbacks['can_undo']()
        return False
    
    def can_redo(self) -> bool:
        """Check if redo is available."""
        if 'can_redo' in self._callbacks:
            return self._callbacks['can_redo']()
        return False
