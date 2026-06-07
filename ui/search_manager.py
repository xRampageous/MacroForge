"""Search and filter management for MacroForge timeline.

Provides:
- Recent searches history
- Advanced filtering (by type, status, group)
- Search result highlighting
- Persistent search preferences
"""

from typing import List, Dict, Optional, Callable, Set
from dataclasses import dataclass
from datetime import datetime
import json
import os

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QLineEdit, QListWidget, QListWidgetItem, QFrame, QVBoxLayout

from ui.theme import COLORS
from debugger import logger


@dataclass
class SearchHistoryItem:
    """A single search history entry."""
    query: str
    timestamp: datetime
    filters: Dict[str, str]
    result_count: int = 0


class SearchManager:
    """Manages timeline search functionality with history and filters.
    
    Features:
    - Recent searches (last 20)
    - Advanced filters (type, status, group)
    - Search result persistence
    - Quick filter presets
    """
    
    MAX_HISTORY = 20
    
    def __init__(self, window, max_history: int = 20):
        self.window = window
        self.max_history = max_history
        self._history: List[SearchHistoryItem] = []
        self._current_query = ""
        self._current_filters: Dict[str, str] = {}
        self._recent_searches_widget: Optional[QListWidget] = None
        self._search_input: Optional[QLineEdit] = None
        
        # Callbacks
        self._on_search: Optional[Callable] = None
        self._on_filter_change: Optional[Callable] = None
        
        self._load_history()
    
    def set_callbacks(self, on_search=None, on_filter_change=None):
        """Set callback functions."""
        self._on_search = on_search
        self._on_filter_change = on_filter_change
    
    def set_widgets(self, search_input: QLineEdit, recent_list: QListWidget = None):
        """Set the UI widgets."""
        self._search_input = search_input
        self._recent_searches_widget = recent_list
        
        if search_input:
            search_input.textChanged.connect(self._on_query_changed)
            search_input.returnPressed.connect(self._execute_search)
        
        if recent_list:
            recent_list.itemClicked.connect(self._on_history_item_clicked)
            self._populate_recent_searches()
    
    # ═══════════════════════════════════════════════════════
    #  SEARCH EXECUTION
    # ═══════════════════════════════════════════════════════
    
    def search(self, query: str, filters: Dict[str, str] = None) -> List[int]:
        """Execute a search and return matching row indices.
        
        Args:
            query: Search text
            filters: Optional filters (type, status, group)
        
        Returns:
            List of matching row indices
        """
        self._current_query = query
        self._current_filters = filters or {}
        
        results = self._perform_search(query, self._current_filters)
        
        # Add to history
        self._add_to_history(query, self._current_filters, len(results))
        
        # Notify callback
        if self._on_search:
            self._on_search(query, results)
        
        return results
    
    def _perform_search(self, query: str, filters: Dict[str, str]) -> List[int]:
        """Internal search implementation."""
        results = []
        query_lower = query.lower()
        
        try:
            action_model = self.window.action_model
            row_count = action_model.rowCount()
            
            for row in range(row_count):
                action = action_model.get(row)
                if not action:
                    continue
                
                # Check filters
                if not self._passes_filters(action, filters):
                    continue
                
                # Check text query
                if query:
                    match_text = self._get_searchable_text(action).lower()
                    if query_lower not in match_text:
                        continue
                
                results.append(row)
        
        except Exception as e:
            logger.error(f"Search error: {e}")
        
        return results
    
    def _passes_filters(self, action, filters: Dict[str, str]) -> bool:
        """Check if action passes all filters."""
        for key, value in filters.items():
            if key == "type":
                if getattr(action, 'action_type', '') != value:
                    return False
            elif key == "enabled":
                enabled = getattr(action, 'enabled', True)
                if str(enabled).lower() != value.lower():
                    return False
            elif key == "group":
                group_id = getattr(action, 'group_id', '')
                if group_id != value:
                    return False
        
        return True
    
    def _get_searchable_text(self, action) -> str:
        """Get all searchable text from an action."""
        texts = []
        
        # Label
        label = getattr(action, 'label', '')
        if label:
            texts.append(label)
        
        # Key
        key = getattr(action, 'key', '')
        if key:
            texts.append(key)
        
        # Group name
        group_name = getattr(action, 'group_name', '')
        if group_name:
            texts.append(group_name)
        
        # Action type
        action_type = getattr(action, 'action_type', '')
        texts.append(action_type)
        
        return ' '.join(texts)
    
    # ═══════════════════════════════════════════════════════
    #  HISTORY MANAGEMENT
    # ═══════════════════════════════════════════════════════
    
    def _add_to_history(self, query: str, filters: Dict[str, str], result_count: int):
        """Add a search to history."""
        if not query and not filters:
            return
        
        # Remove duplicates
        self._history = [
            h for h in self._history 
            if not (h.query == query and h.filters == filters)
        ]
        
        # Add new entry
        item = SearchHistoryItem(
            query=query,
            timestamp=datetime.now(),
            filters=filters,
            result_count=result_count
        )
        self._history.insert(0, item)
        
        # Trim to max
        if len(self._history) > self.max_history:
            self._history = self._history[:self.max_history]
        
        # Update UI
        if self._recent_searches_widget:
            self._populate_recent_searches()
        
        # Save
        self._save_history()
    
    def _populate_recent_searches(self):
        """Populate the recent searches widget."""
        if not self._recent_searches_widget:
            return
        
        self._recent_searches_widget.clear()
        
        for item in self._history[:10]:  # Show last 10
            display_text = item.query or "(filters only)"
            if item.filters:
                display_text += f" [{len(item.filters)} filters]"
            display_text += f" - {item.result_count} results"
            
            list_item = QListWidgetItem(display_text)
            list_item.setData(Qt.ItemDataRole.UserRole, item)
            self._recent_searches_widget.addItem(list_item)
    
    def _on_history_item_clicked(self, item: QListWidgetItem):
        """Handle click on history item."""
        search_item = item.data(Qt.ItemDataRole.UserRole)
        if search_item and self._search_input:
            self._search_input.setText(search_item.query)
            self.search(search_item.query, search_item.filters)
    
    def get_recent_searches(self) -> List[SearchHistoryItem]:
        """Get recent search history."""
        return self._history.copy()
    
    def clear_history(self):
        """Clear search history."""
        self._history.clear()
        if self._recent_searches_widget:
            self._recent_searches_widget.clear()
        self._save_history()
    
    # ═══════════════════════════════════════════════════════
    #  PERSISTENCE
    # ═══════════════════════════════════════════════════════
    
    def _load_history(self):
        """Load search history from disk."""
        try:
            path = self._get_history_path()
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for item_data in data.get('history', []):
                    item = SearchHistoryItem(
                        query=item_data.get('query', ''),
                        timestamp=datetime.fromisoformat(item_data.get('timestamp', '')),
                        filters=item_data.get('filters', {}),
                        result_count=item_data.get('result_count', 0)
                    )
                    self._history.append(item)
        except Exception as e:
            logger.debug(f"Failed to load search history: {e}")
    
    def _save_history(self):
        """Save search history to disk."""
        try:
            path = self._get_history_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
            data = {
                'history': [
                    {
                        'query': item.query,
                        'timestamp': item.timestamp.isoformat(),
                        'filters': item.filters,
                        'result_count': item.result_count
                    }
                    for item in self._history
                ]
            }
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.debug(f"Failed to save search history: {e}")
    
    def _get_history_path(self) -> str:
        """Get path to history file."""
        base_dir = os.path.expanduser("~/.macroforge")
        return os.path.join(base_dir, "search_history.json")
    
    # ═══════════════════════════════════════════════════════
    #  FILTER PRESETS
    # ═══════════════════════════════════════════════════════
    
    FILTER_PRESETS = {
        "All": {},
        "Enabled Only": {"enabled": "true"},
        "Disabled Only": {"enabled": "false"},
        "Key Actions": {"type": "key"},
        "Image Actions": {"type": "image"},
        "Click Actions": {"type": "click"},
        "In Groups": {"in_group": "true"},
        "Not in Groups": {"in_group": "false"},
    }
    
    def apply_filter_preset(self, preset_name: str) -> List[int]:
        """Apply a filter preset."""
        filters = self.FILTER_PRESETS.get(preset_name, {})
        return self.search(self._current_query, filters)
    
    def get_filter_presets(self) -> List[str]:
        """Get list of available filter presets."""
        return list(self.FILTER_PRESETS.keys())
    
    # ═══════════════════════════════════════════════════════
    #  UI EVENT HANDLERS
    # ═══════════════════════════════════════════════════════
    
    def _on_query_changed(self, text: str):
        """Handle search query text change (with debounce)."""
        self._current_query = text
        
        # Debounce search execution
        QTimer.singleShot(150, lambda: self._execute_search())
    
    def _execute_search(self):
        """Execute search with current query."""
        if self._search_input:
            query = self._search_input.text()
            self.search(query, self._current_filters)


def create_search_manager(window, max_history: int = 20) -> SearchManager:
    """Factory function to create a SearchManager."""
    return SearchManager(window, max_history)
