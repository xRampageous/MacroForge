"""Hotkey manager that integrates global hotkeys with UI settings.

Provides a unified interface for:
- Qt shortcuts (when MacroForge is focused)
- Global hotkeys (via pynput, work even when not focused)
- Settings persistence
- Conflict detection
"""

from typing import Callable, Dict, Optional
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QMainWindow

from debugger import logger

# Import global hotkey module
try:
    import hotkeys
    _PYNPUT_AVAILABLE = True
except Exception as e:
    _PYNPUT_AVAILABLE = False
    logger.warning(f"Global hotkeys unavailable: {e}")


class HotkeyManager:
    """Manages both Qt shortcuts and global hotkeys.
    
    Features:
    - Unified configuration storage via SettingsManager
    - Automatic conflict detection between shortcuts
    - Graceful fallback when pynput is unavailable
    - Thread-safe global hotkey callbacks
    """
    
    # Default hotkey bindings
    DEFAULT_HOTKEYS = {
        "play_pause": "Space",
        "stop_deselect": "Escape",
        "record": "F7",
        "save": "Ctrl+S",
        "undo": "Ctrl+Z",
        "redo": "Ctrl+Y",
        "copy": "Ctrl+C",
        "paste": "Ctrl+V",
        "duplicate": "Ctrl+D",
        "delete": "Delete",
        "select_all": "Ctrl+A",
        "group": "Ctrl+G",
        "ungroup": "Ctrl+Shift+G",
        "search": "Ctrl+F",
        "run_from_selected": "Ctrl+Enter",
        "macro_editor": "Ctrl+E",
        "preflight": "Ctrl+Shift+P",
        "toggle_runtime_log": "Ctrl+Shift+L",
        "variables": "Ctrl+Alt+V",
        "profile_library": "Ctrl+Alt+P",
        "set_click_coordinates": "Ctrl+Shift+M",
        "reset_timeline_zoom": "Ctrl+0",
    }
    
    # Global hotkey support (work even when not focused)
    GLOBAL_HOTKEYS = {"play_pause", "stop_deselect", "record"}
    
    def __init__(self, window: QMainWindow, settings_manager=None):
        self.window = window
        self.settings_manager = settings_manager
        self._shortcuts: Dict[str, QShortcut] = {}
        self._callbacks: Dict[str, Callable] = {}
        self._global_enabled = False
        self._hotkeys = {}
        
        # Load saved or defaults
        self._load_hotkeys()
    
    def _load_hotkeys(self):
        """Load hotkey configuration from settings."""
        if self.settings_manager:
            saved = self.settings_manager.settings.get("hotkeys", {})
            self._hotkeys = {**self.DEFAULT_HOTKEYS, **saved}
        else:
            self._hotkeys = self.DEFAULT_HOTKEYS.copy()
    
    def save_hotkeys(self):
        """Save current hotkey configuration to settings."""
        if self.settings_manager:
            self.settings_manager.settings["hotkeys"] = self._hotkeys.copy()
            self.settings_manager.save()
    
    def register_callback(self, name: str, callback: Callable):
        """Register a callback for a hotkey action.
        
        Args:
            name: Hotkey action name (e.g., "play_pause")
            callback: Function to call when hotkey is triggered
        """
        self._callbacks[name] = callback
        logger.debug(f"Registered callback for {name}")
    
    def unregister_callback(self, name: str):
        """Unregister a callback."""
        self._callbacks.pop(name, None)
    
    def setup_shortcuts(self):
        """Set up Qt shortcuts for the main window.
        
        Call this after UI is built and callbacks are registered.
        """
        # Clear existing
        for shortcut in self._shortcuts.values():
            shortcut.setEnabled(False)
            shortcut.setParent(None)
        self._shortcuts.clear()
        
        # Create new shortcuts
        for name, seq_str in self._hotkeys.items():
            if not seq_str:
                continue
            
            callback = self._callbacks.get(name)
            if not callback:
                logger.debug(f"No callback for hotkey: {name}")
                continue
            
            try:
                seq = QKeySequence(seq_str)
                shortcut = QShortcut(seq, self.window)
                shortcut.activated.connect(callback)
                self._shortcuts[name] = shortcut
                logger.debug(f"Bound shortcut {name} -> {seq_str}")
            except Exception as e:
                logger.warning(f"Failed to bind shortcut {name}={seq_str}: {e}")
    
    def setup_global_hotkeys(self):
        """Set up global hotkeys via pynput.
        
        These work even when MacroForge is not focused.
        """
        if not _PYNPUT_AVAILABLE:
            logger.warning("Global hotkeys unavailable (pynput not installed)")
            return
        
        # Stop existing global hotkeys
        self.stop_global_hotkeys()
        
        # Build mapping for global hotkeys only
        mapping = {}
        for name in self.GLOBAL_HOTKEYS:
            if name in self._hotkeys and name in self._callbacks:
                key = self._hotkeys[name]
                if key:
                    mapping[key.lower()] = self._callbacks[name]
        
        if mapping:
            try:
                hotkeys.start_hotkeys(mapping)
                self._global_enabled = True
                logger.info(f"Global hotkeys started: {list(mapping.keys())}")
            except Exception as e:
                logger.error(f"Failed to start global hotkeys: {e}")
                self._global_enabled = False
    
    def stop_global_hotkeys(self):
        """Stop global hotkey listener."""
        if _PYNPUT_AVAILABLE:
            try:
                hotkeys.stop_hotkeys()
                self._global_enabled = False
                logger.info("Global hotkeys stopped")
            except Exception as e:
                logger.error(f"Error stopping global hotkeys: {e}")
    
    def update_hotkey(self, name: str, key_sequence: str):
        """Update a single hotkey.
        
        Args:
            name: Hotkey action name
            key_sequence: New key sequence (e.g., "Ctrl+Shift+P")
        """
        self._hotkeys[name] = key_sequence
        
        # Re-setup if already initialized
        if self._shortcuts:
            self.setup_shortcuts()
        if self._global_enabled:
            self.setup_global_hotkeys()
    
    def update_hotkeys(self, hotkeys_dict: Dict[str, str]):
        """Update multiple hotkeys at once.
        
        Args:
            hotkeys_dict: Dict of {name: key_sequence}
        """
        self._hotkeys.update(hotkeys_dict)
        self.save_hotkeys()
        
        # Re-setup
        self.setup_shortcuts()
        if self._global_enabled:
            self.setup_global_hotkeys()
    
    def get_hotkey(self, name: str) -> str:
        """Get current key sequence for a hotkey."""
        return self._hotkeys.get(name, self.DEFAULT_HOTKEYS.get(name, ""))
    
    def get_all_hotkeys(self) -> Dict[str, str]:
        """Get all hotkey configurations."""
        return self._hotkeys.copy()
    
    def check_conflicts(self) -> Dict[str, list]:
        """Check for duplicate key bindings.
        
        Returns:
            Dict mapping key sequences to list of action names
        """
        key_to_names: Dict[str, list] = {}
        for name, key in self._hotkeys.items():
            if key:
                key_to_names.setdefault(key, []).append(name)
        
        # Return only conflicts (more than one action per key)
        return {k: v for k, v in key_to_names.items() if len(v) > 1}
    
    def reset_to_defaults(self):
        """Reset all hotkeys to default values."""
        self._hotkeys = self.DEFAULT_HOTKEYS.copy()
        self.setup_shortcuts()
        if self._global_enabled:
            self.setup_global_hotkeys()
        self.save_hotkeys()
    
    def reload(self):
        """Reload hotkeys from settings and re-setup."""
        self._load_hotkeys()
        self.setup_shortcuts()
        if self._global_enabled:
            self.setup_global_hotkeys()
    
    def enable_global_hotkeys(self, enabled: bool = True):
        """Enable or disable global hotkeys."""
        if enabled:
            self.setup_global_hotkeys()
        else:
            self.stop_global_hotkeys()
    
    def is_global_enabled(self) -> bool:
        """Check if global hotkeys are currently active."""
        return self._global_enabled


# Convenience factory function
def create_hotkey_manager(window, settings_manager=None, 
                       callbacks: Optional[Dict[str, Callable]] = None) -> HotkeyManager:
    """Create and configure a HotkeyManager.
    
    Args:
        window: Main window (QMainWindow)
        settings_manager: SettingsManager for persistence
        callbacks: Optional dict of {name: callback} to register
    
    Returns:
        Configured HotkeyManager instance
    """
    mgr = HotkeyManager(window, settings_manager)
    
    if callbacks:
        for name, callback in callbacks.items():
            mgr.register_callback(name, callback)
    
    mgr.setup_shortcuts()
    
    # Try to enable global hotkeys (may fail if pynput unavailable)
    mgr.enable_global_hotkeys(True)
    
    return mgr
