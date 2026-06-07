"""Toolbar controller for MacroForge main window.

Manages responsive toolbar behavior, button states, and profile switching.
"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QLabel, QSizePolicy
from PyQt6.QtGui import QFont

from ui.icons import icon
from ui.theme import COLORS
from debugger import logger


class ToolbarController:
    """Manages the main toolbar responsive behavior and interactions.
    
    This class handles:
    - Responsive toolbar sizing (tiny/compact/full modes)
    - Toolbar containment and layout adjustments
    - Profile button text and width management
    - Toolbar button states and visibility
    """
    
    def __init__(self, window):
        self.window = window
        self._toolbar_profile_mode = "full"
        self._toolbar_profile_full_width = 164
        self._toolbar_profile_compact_width = 132
        self._toolbar_profile_tiny_width = 116
        self.toolbar_separators = []
    
    def _toolbar_profile_text(self):
        """Return profile button text for the current toolbar width mode."""
        try:
            name = str(self.window.session_manager.active or "Default")
        except Exception:
            name = "Default"
        mode = str(getattr(self, "_toolbar_profile_mode", "full"))
        if mode == "tiny":
            shown = name if len(name) <= 8 else f"{name[:7]}…"
            return f"{shown}  ▾"
        if mode == "compact":
            shown = name if len(name) <= 12 else f"{name[:10]}..."
            return f"{shown}  ▾"
        shown = name if len(name) <= 18 else f"{name[:15]}..."
        return f"{shown}  ▾"
    
    def update_toolbar_containment(self):
        """Keep the redesigned top toolbar contained in the visible header dock.
        
        The main window width is not enough to determine toolbar fit because the
        expanded side panel steals workspace width. Use the header dock width
        itself, then compact non-status controls first so the right status pill
        stays inside the rounded top panel.
        """
        try:
            header = getattr(self.window, "header_dock", None)
            profile = getattr(self.window, "profile_btn", None)
            layout = getattr(self.window, "toolbar_layout", None)
            status_pill = getattr(self.window, "status_pill", None)
            if not all([header, profile, layout, status_pill]):
                return
            
            width = header.width()
            
            if width < 760:
                mode = "tiny"
                profile_w = int(getattr(self, "_toolbar_profile_tiny_width", 116))
                margins = (5, 5, 7, 5)
                spacing = 2
                separator_visible = False
                status_cap = 230
            elif width < 860:
                mode = "compact"
                profile_w = int(getattr(self, "_toolbar_profile_compact_width", 132))
                margins = (6, 5, 8, 5)
                spacing = 3
                separator_visible = True
                status_cap = 310
            else:
                mode = "full"
                profile_w = int(getattr(self, "_toolbar_profile_full_width", 164))
                margins = (7, 5, 9, 5)
                spacing = 4
                separator_visible = True
                status_cap = 420
            
            # Calculate available space for status pill
            visible_debug = 35
            static_budget = profile_w + visible_debug + 312
            available_status = max(112, width - static_budget)
            status_bounds = (108 if mode == "tiny" else 112, max(112, min(status_cap, available_status)))
            
            if getattr(self, "_toolbar_profile_mode", None) != mode:
                self._toolbar_profile_mode = mode
                profile.setText(self._toolbar_profile_text())
            
            if profile.width() != profile_w:
                profile.setFixedWidth(profile_w)
            
            if status_pill.minimumWidth() != status_bounds[0] or status_pill.maximumWidth() != status_bounds[1]:
                status_pill.setMinimumWidth(status_bounds[0])
                status_pill.setMaximumWidth(status_bounds[1])
            
            if layout.contentsMargins() != margins:
                layout.setContentsMargins(*margins)
            if layout.spacing() != spacing:
                layout.setSpacing(spacing)
            
            for sep in getattr(self, "toolbar_separators", []):
                try:
                    sep.setVisible(separator_visible)
                    sep.setFixedWidth(1 if separator_visible else 0)
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Toolbar containment error: {e}")
    
    def update_selection_chip(self, count):
        """Update the selection chip visibility and count."""
        try:
            chip = getattr(self.window, "selection_chip", None)
            label = getattr(self.window, "selection_count_label", None)
            if chip and label:
                label.setText(f"{count} selected" if count > 1 else "1 selected")
                chip.setVisible(count > 0)
        except Exception as e:
            logger.debug(f"Selection chip update error: {e}")
    
    def update_playback_buttons(self, running, paused):
        """Update playback button states based on engine state."""
        try:
            start_btn = getattr(self.window, "start_btn", None)
            pause_btn = getattr(self.window, "pause_btn", None)
            stop_btn = getattr(self.window, "stop_btn", None)
            
            if start_btn:
                start_btn.setEnabled(not running)
            if pause_btn:
                pause_btn.setEnabled(running)
                pause_btn.setChecked(paused)
            if stop_btn:
                stop_btn.setEnabled(running)
        except Exception as e:
            logger.debug(f"Playback buttons update error: {e}")
    
    def update_profile_button(self):
        """Update profile button text and width."""
        try:
            profile = getattr(self.window, "profile_btn", None)
            if profile:
                profile.setText(self._toolbar_profile_text())
        except Exception as e:
            logger.debug(f"Profile button update error: {e}")


def create_toolbar_controller(window):
    """Factory function to create and initialize a ToolbarController."""
    return ToolbarController(window)
