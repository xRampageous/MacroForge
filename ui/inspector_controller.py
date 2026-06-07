"""Inspector/Side Panel controller for MacroForge.

Manages the side panel inspector for editing action properties.
"""

from PyQt6.QtCore import Qt, QTimer, QSize, QObject
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox,
    QSpinBox, QDoubleSpinBox, QComboBox, QSlider,
    QSizePolicy
)
from PyQt6.QtGui import QFont

from ui.icons import icon
from ui.theme import COLORS
from debugger import logger


class InspectorController:
    """Manages the side panel inspector UI and interactions.
    
    This class handles:
    - Inspector panel visibility and sizing
    - Inspector field autosave
    - Image preview management
    - Inspector type switching (key, image, click, pause, group, condition, loop)
    """
    
    def __init__(self, window, timer_factory=QTimer):
        self.window = window
        self._timer_factory = timer_factory
        self._inspector_loading = False
        self._inspector_autosave_timer = None
        self._image_preview_pixmap = None
        self._setup_autosave_timer()
    
    def _setup_autosave_timer(self):
        """Set up the autosave timer for inspector edits."""
        parent = self.window if isinstance(self.window, QObject) else None
        self._inspector_autosave_timer = self._timer_factory(parent)
        self._inspector_autosave_timer.setSingleShot(True)
        self._inspector_autosave_timer.setInterval(350)
        self._inspector_autosave_timer.timeout.connect(self._autosave_inspector_edits)
    
    def show_inspector(self, show=True, action_type="key"):
        """Show or hide the inspector panel for the given action type."""
        try:
            inspector_stack = getattr(self.window, "inspector_stack", None)
            if not inspector_stack:
                return
            
            # Map action types to widget indices
            type_indices = {
                "key": 0,
                "pause": 1,
                "image": 2,
                "click": 3,
                "group": 4,
                "condition": 5,
                "loop": 6,
            }
            index = type_indices.get(action_type, 0)
            inspector_stack.setCurrentIndex(index if show else 0)
            
            # Trigger autosize
            autosize = getattr(self.window, "_autosize_inspector_panel", None)
            if autosize and callable(autosize):
                QTimer.singleShot(0, autosize)
        except Exception as e:
            logger.debug(f"Show inspector error: {e}")
    
    def _autosave_inspector_edits(self):
        """Apply pending inspector edits."""
        try:
            if getattr(self, "_inspector_loading", False):
                return
            apply = getattr(self.window, "_apply_inspector", None)
            if apply and callable(apply):
                apply(autosave=True)
        except Exception as e:
            logger.debug(f"Autosave inspector error: {e}")
    
    def queue_inspector_autosave(self, *args):
        """Queue an autosave after a short delay."""
        try:
            if getattr(self, "_inspector_loading", False):
                return
            if hasattr(self.window, "active_index"):
                idx = self.window.active_index
                if idx < 0 or idx >= self.window.action_model.rowCount():
                    return
            if self._inspector_autosave_timer:
                self._inspector_autosave_timer.start()
        except Exception as e:
            logger.debug(f"Queue autosave error: {e}")
    
    def setup_inspector_autosave(self):
        """Connect all inspector widgets to autosave."""
        widgets = [
            getattr(self.window, name, None)
            for name in (
                "inspector_label",
                "ik_key", "ik_dur", "ik_repeat", "ik_label", "ik_hold",
                "ip_dur", "ip_label",
                "ic_x", "ic_y", "ic_btn", "ic_rand", "ic_repeat", "ic_label",
                "ii_sim", "ii_sim_slider", "ii_wait", "ii_retry_count", "ii_retry_delay", "ii_fail_mode", "ii_fail_target",
                "ig_name", "ig_collapsed", "ig_recovery",
                "il_label", "il_count", "il_target",
                "ico_label", "ico_type", "ico_x", "ico_y", "ico_color",
                "ico_true", "ico_false", "ico_retry_count", "ico_retry_delay", "ico_fail_mode", "ico_fail_target",
            )
        ]
        for widget in widgets:
            if widget is None:
                continue
            try:
                if isinstance(widget, QLineEdit):
                    widget.textEdited.connect(self.queue_inspector_autosave)
                elif isinstance(widget, QComboBox):
                    widget.currentIndexChanged.connect(self.queue_inspector_autosave)
                elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    widget.valueChanged.connect(self.queue_inspector_autosave)
                elif isinstance(widget, QCheckBox):
                    widget.toggled.connect(self.queue_inspector_autosave)
                elif isinstance(widget, QSlider):
                    widget.valueChanged.connect(self.queue_inspector_autosave)
            except Exception:
                pass
    
    def set_loading(self, loading: bool):
        """Set the inspector loading state to prevent autosave during load."""
        self._inspector_loading = loading
    
    def is_loading(self) -> bool:
        """Check if the inspector is currently loading."""
        return getattr(self, "_inspector_loading", False)


def create_inspector_controller(window, timer_factory=QTimer):
    """Factory function to create and initialize an InspectorController."""
    return InspectorController(window, timer_factory=timer_factory)
