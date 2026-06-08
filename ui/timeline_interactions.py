"""Timeline interactions controller for MacroForge.

Manages timeline selection, drag/drop, context menus, and keyboard navigation.
"""

from typing import List, Set, Optional, Callable
from PyQt6.QtCore import Qt, QModelIndex
from PyQt6.QtWidgets import QMenu, QMessageBox, QInputDialog

from debugger import logger


class TimelineInteractions:
    """Manages timeline user interactions.
    
    This class handles:
    - Row selection (single, multi, range)
    - Drag and drop reordering
    - Context menu actions
    - Keyboard navigation
    - Group operations
    """
    
    def __init__(self, window):
        self.window = window
        self.timeline = None
        self.action_model = None
        
        # Selection state
        self._selected_rows: Set[int] = set()
        self._active_index = -1
        self._last_selected = -1
        
        # Callbacks
        self._on_selection_changed: Optional[Callable] = None
        self._on_action_clicked: Optional[Callable] = None
        self._on_action_double_clicked: Optional[Callable] = None
        self._on_row_moved: Optional[Callable] = None
        self._on_show_context_menu: Optional[Callable] = None
    
    def set_timeline(self, timeline):
        """Set the timeline widget reference."""
        self.timeline = timeline
        self._connect_timeline_signals()
    
    def set_action_model(self, model):
        """Set the action model reference."""
        self.action_model = model
    
    def set_callbacks(self, on_selection_changed=None, on_action_clicked=None,
                     on_action_double_clicked=None, on_row_moved=None,
                     on_show_context_menu=None):
        """Set callback functions."""
        self._on_selection_changed = on_selection_changed
        self._on_action_clicked = on_action_clicked
        self._on_action_double_clicked = on_action_double_clicked
        self._on_row_moved = on_row_moved
        self._on_show_context_menu = on_show_context_menu
    
    def _connect_timeline_signals(self):
        """Connect timeline widget signals."""
        if not self.timeline:
            return
        
        try:
            self.timeline.action_clicked.connect(self._on_timeline_click)
            self.timeline.action_double_clicked.connect(self._on_timeline_double_click)
            self.timeline.action_dragged.connect(self._on_row_dragged)
            
            if hasattr(self.timeline, 'action_dragged_many'):
                self.timeline.action_dragged_many.connect(self._on_multi_row_dragged)
            
            if hasattr(self.timeline, 'action_context_menu'):
                self.timeline.action_context_menu.connect(self._on_context_menu)
            
            if hasattr(self.timeline, 'selection_summary_changed'):
                self.timeline.selection_summary_changed.connect(self._on_selection_summary)
        except Exception as e:
            logger.debug(f"Timeline signal connection error: {e}")
    
    # ═══════════════════════════════════════════════════════
    #  SELECTION
    # ═══════════════════════════════════════════════════════
    
    def select_row(self, row: int, add_to_selection=False):
        """Select a single row.
        
        Args:
            row: Row index to select
            add_to_selection: If True, add to current selection (Ctrl+Click)
        """
        if not self._is_valid_row(row):
            return
        
        if not add_to_selection:
            self._selected_rows.clear()
        
        self._selected_rows.add(row)
        self._active_index = row
        self._last_selected = row
        
        self._update_timeline_selection()
        self._notify_selection_changed()
    
    def select_rows(self, rows: List[int], active=None):
        """Select multiple rows.
        
        Args:
            rows: List of row indices to select
            active: The active row (for inspector focus)
        """
        valid_rows = [r for r in rows if self._is_valid_row(r)]
        if not valid_rows:
            return
        
        self._selected_rows = set(valid_rows)
        self._active_index = active if active in valid_rows else valid_rows[0]
        self._last_selected = self._active_index
        
        self._update_timeline_selection()
        self._notify_selection_changed()
    
    def select_range(self, start: int, end: int):
        """Select a range of rows (Shift+Click)."""
        if start > end:
            start, end = end, start
        
        rows = list(range(max(0, start), min(end + 1, self._get_row_count())))
        self.select_rows(rows)
    
    def toggle_row_selection(self, row: int):
        """Toggle selection of a row (Ctrl+Click)."""
        if row in self._selected_rows:
            if len(self._selected_rows) > 1:
                self._selected_rows.remove(row)
                if self._active_index == row:
                    self._active_index = next(iter(self._selected_rows))
        else:
            self._selected_rows.add(row)
            self._active_index = row
        
        self._last_selected = row
        self._update_timeline_selection()
        self._notify_selection_changed()
    
    def select_all(self):
        """Select all rows."""
        count = self._get_row_count()
        if count > 0:
            self.select_rows(list(range(count)))
    
    def deselect_all(self):
        """Clear all selections."""
        self._selected_rows.clear()
        self._active_index = -1
        self._last_selected = -1
        self._update_timeline_selection()
        self._notify_selection_changed()
    
    def get_selected_rows(self) -> List[int]:
        """Get list of selected row indices."""
        return sorted(self._selected_rows)
    
    def get_active_row(self) -> int:
        """Get the active (inspector-focused) row."""
        return self._active_index
    
    def has_selection(self) -> bool:
        """Check if any rows are selected."""
        return len(self._selected_rows) > 0
    
    def get_selection_count(self) -> int:
        """Get number of selected rows."""
        return len(self._selected_rows)
    
    def _is_valid_row(self, row: int) -> bool:
        """Check if row index is valid."""
        return 0 <= row < self._get_row_count()
    
    def _get_row_count(self) -> int:
        """Get total number of rows."""
        if self.action_model:
            return self.action_model.rowCount()
        return 0
    
    def _update_timeline_selection(self):
        """Update timeline widget visual selection."""
        if not self.timeline:
            return
        
        try:
            if hasattr(self.timeline, 'set_selected_rows'):
                self.timeline.set_selected_rows(
                    list(self._selected_rows),
                    active=self._active_index if self._active_index >= 0 else None
                )
            else:
                self.timeline.selected_indices = self._selected_rows.copy()
                self.timeline.refresh()
        except Exception as e:
            logger.debug(f"Timeline selection update error: {e}")
    
    def _notify_selection_changed(self):
        """Notify that selection has changed."""
        if self._on_selection_changed:
            self._on_selection_changed(
                list(self._selected_rows),
                self._active_index
            )
    
    # ═══════════════════════════════════════════════════════
    #  DRAG/DROP
    # ═══════════════════════════════════════════════════════
    
    def _on_timeline_click(self, index):
        """Handle timeline row click."""
        row = index.row() if hasattr(index, 'row') else index
        self._sync_from_timeline(active=row)
        if self._on_action_clicked:
            self._on_action_clicked(row)
    
    def _on_timeline_double_click(self, index):
        """Handle timeline row double click."""
        row = index.row() if hasattr(index, 'row') else index
        self._sync_from_timeline(active=row)
        if self._on_action_double_clicked:
            self._on_action_double_clicked(row)
    
    def _on_row_dragged(self, from_row, to_row):
        """Handle single row drag and drop."""
        if self._on_row_moved:
            self._on_row_moved([from_row], to_row)
    
    def _on_multi_row_dragged(self, rows, to_row):
        """Handle multi-row drag and drop."""
        if self._on_row_moved:
            self._on_row_moved(rows, to_row)
    
    # ═══════════════════════════════════════════════════════
    #  CONTEXT MENU
    # ═══════════════════════════════════════════════════════
    
    def _on_context_menu(self, index, global_pos):
        """Show context menu for timeline row."""
        if self._on_show_context_menu:
            row = index.row() if hasattr(index, 'row') else index
            self._on_show_context_menu(row, global_pos)
    
    def _on_selection_summary(self, rows):
        """Handle selection summary update."""
        self._sync_from_timeline(rows=rows)
        self._notify_selection_changed()

    def _sync_from_timeline(self, rows=None, active=None):
        """Mirror selection state owned by the timeline widget."""
        if rows is None and self.timeline is not None:
            try:
                if hasattr(self.timeline, "sync_selection"):
                    self.timeline.sync_selection()
                if hasattr(self.timeline, "selected_rows"):
                    rows = self.timeline.selected_rows()
                else:
                    rows = sorted(getattr(self.timeline, "selected_indices", set()))
            except Exception:
                rows = []
        valid_rows = [r for r in (rows or []) if self._is_valid_row(int(r))]
        self._selected_rows = set(valid_rows)
        if active is not None and self._is_valid_row(int(active)):
            self._active_index = int(active)
        elif valid_rows:
            self._active_index = valid_rows[0]
        else:
            self._active_index = -1
    
    # ═══════════════════════════════════════════════════════
    #  KEYBOARD NAVIGATION
    # ═══════════════════════════════════════════════════════
    
    def move_selection_up(self):
        """Move selection up one row."""
        if self._active_index > 0:
            self.select_row(self._active_index - 1)
    
    def move_selection_down(self):
        """Move selection down one row."""
        if self._active_index < self._get_row_count() - 1:
            self.select_row(self._active_index + 1)
    
    def extend_selection_up(self):
        """Extend selection up one row (Shift+Up)."""
        if self._last_selected > 0:
            new_row = self._last_selected - 1
            if new_row not in self._selected_rows:
                self._selected_rows.add(new_row)
                self._last_selected = new_row
                self._update_timeline_selection()
                self._notify_selection_changed()
    
    def extend_selection_down(self):
        """Extend selection down one row (Shift+Down)."""
        if self._last_selected < self._get_row_count() - 1:
            new_row = self._last_selected + 1
            if new_row not in self._selected_rows:
                self._selected_rows.add(new_row)
                self._last_selected = new_row
                self._update_timeline_selection()
                self._notify_selection_changed()


def create_timeline_interactions(window) -> TimelineInteractions:
    """Factory function to create TimelineInteractions."""
    return TimelineInteractions(window)
