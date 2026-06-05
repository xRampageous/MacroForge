"""MacroForge main window."""
import os
import sys
import time
import json
import csv
import base64
import queue
import ctypes
import threading
import subprocess
from copy import deepcopy

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QGridLayout, QSizePolicy,
    QLabel, QPushButton, QComboBox, QLineEdit, QCheckBox,
    QProgressBar, QFrame, QMenu,
    QSpinBox, QDoubleSpinBox, QSlider,
    QFileDialog, QMessageBox, QInputDialog,
    QDialog, QPlainTextEdit, QListWidget
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize, QEvent
from PyQt6.QtGui import QFont, QColor, QPen, QKeySequence, QShortcut, QIcon, QPixmap

from engine import ExecutionEngine
from models import Action, ProfileManager, SettingsManager, ActionListModel, HistoryManager
from updater import check_update, perform_update, get_last_update_error
from version import VERSION
# from hotkeys import start_hotkeys, stop_hotkeys  # DISABLED — pynput causes Qt dialog crashes
from debugger import logger, DebugViewer
from ui.theme import build_stylesheet, COLORS
from ui.status_dot import StatusDot
from ui.timeline import TimelineView
from ui.icons import icon
try:
    from ui.icons import timeline_action_icon
except ImportError:
    # Backward-compatible fallback for installs where ui/icons.py was not
    # overwritten by a small overlay patch. The corrected patch includes
    # ui/icons.py too, but this keeps MacroForge bootable after partial updates.
    def timeline_action_icon(kind: str, size: int = 18, color: str = "#F3F6FA"):
        normalized = (kind or "key").lower()
        if normalized == "folder":
            normalized = "group"
        elif normalized == "delay":
            normalized = "pause"
        return icon(normalized, size, color)


class MainWindow(QMainWindow):
    """Modern MacroForge main window."""

    _update_found = pyqtSignal(dict)
    _update_not_found = pyqtSignal()
    _update_error = pyqtSignal(str)
    _download_progress = pyqtSignal(int, str)  # pct, info_text
    _do_exit = pyqtSignal()
    _close_update_dlg = pyqtSignal()

    # Engine -> main thread signals
    _play_action = pyqtSignal(int, float)     # idx, dur
    _pause_state = pyqtSignal(bool)
    _complete = pyqtSignal()
    _progress = pyqtSignal(float)
    _status_msg = pyqtSignal(str)
    _diag_msg = pyqtSignal(str)
    _image_match_state = pyqtSignal(int, str)
    _trace_row = pyqtSignal(int)
    _playback_feedback_msg = pyqtSignal(str)

    def __init__(self, profile_manager=None, settings_manager=None):
        super().__init__()
        self.setWindowTitle("MacroForge")
        # Lower minimum size so responsive side/bottom panel auto-hide can
        # reach the collapsed-panel/header stack while resizing.
        self._base_min_width = 760
        self._base_min_height = 420
        self.setMinimumSize(self._base_min_width, self._base_min_height)
        self.resize(985, 1100)
        self.setStyleSheet(build_stylesheet())

        # Window / taskbar icon
        try:
            if getattr(sys, "frozen", False):
                ico = os.path.join(os.path.dirname(sys.executable), "MacroForge.ico")
            else:
                ico = os.path.join(os.path.dirname(__file__), "..", "MacroForge.ico")
            ico = os.path.abspath(ico)
            if os.path.exists(ico):
                self.setWindowIcon(QIcon(ico))
        except Exception:
            pass

        # Backend refs
        self.session_manager = profile_manager or ProfileManager()
        self.settings_manager = settings_manager or SettingsManager(self.session_manager.base_dir)
        self.action_model = ActionListModel()
        self.engine = ExecutionEngine(
            self._status_cb,
            self._play_cb,
            self._complete_cb,
            self._progress_cb
        )
        self.engine.pause_cb = self._pause_cb
        self.engine.before_action_hook = self._before_action_diag
        self.engine.after_action_hook = self._after_action_diag
        self.engine.image_state_cb = self._image_match_cb
        self.engine.actions = self.action_model.actions()

        # State
        self.active_index = -1
        self.clipboard = None
        self.auto_save_enabled = True
        self._save_session_timer = QTimer(self)
        self._save_session_timer.setSingleShot(True)
        self._save_session_timer.setInterval(500)
        self._save_session_timer.timeout.connect(self._do_save_session)
        self._inspector_loading = False
        self._inspector_autosave_timer = QTimer(self)
        self._inspector_autosave_timer.setSingleShot(True)
        self._inspector_autosave_timer.setInterval(350)
        self._inspector_autosave_timer.timeout.connect(self._autosave_inspector_edits)
        # One-shot unlocked selection reveal state.  Timeline clicks may briefly
        # ask the side panel/Inspector to fit the newly clicked action, but a
        # merely selected row must not keep fighting vertical window resize.
        self._selection_reveal_from_click = False
        self._selection_reveal_clear_timer = QTimer(self)
        self._selection_reveal_clear_timer.setSingleShot(True)
        self._selection_reveal_clear_timer.timeout.connect(self._clear_selection_reveal_from_click)
        self._image_preview_pixmap = QPixmap()
        self._pending_update_manifest = None
        self._update_available = False
        self._update_check_timer = QTimer(self)
        self._update_check_timer.setInterval(60 * 1000)
        self._update_check_timer.timeout.connect(self._check_update_silent)
        self.history = HistoryManager()
        self.actions_played = 0
        self.session_elapsed_time = 0.0
        self.session_start_time = None
        self._seq_dur_cache = 0.0
        self._diag_lines = []
        self._diag_max_lines = 10000
        self._diag_prune_count = 0
        self._diag_dialog = None
        self._diag_edit = None
        self._single_test_active = False
        self._single_test_index = -1
        self._run_from_index = 0
        self._run_index_map = []
        self._last_preflight = {"errors": [], "warnings": []}
        self._runtime_error_dialog_open = False
        self._last_runtime_error = ""
        self.macro_variables = {}


        # Recorder state
        self._recorder = {
            "running": False, "paused": False, "last_time": 0.0,
            "presses": {}, "modifiers": set(), "queue": None,
            "kbd_thread": None, "scroll_thread": None,
            "btn": None, "pause_btn": None, "status_dot": None,
            "status_lbl": None, "time_lbl": None, "actions_lbl": None,
            "overlay": None, "timer_id": None, "poll_id": None,
            "rec_start_time": 0.0,
        }

        # Tray
        self._tray_icon = None

        # Menu ref
        self._action_menu = None
        self._profile_menu = None

        self._build_ui()
        try:
            QApplication.instance().installEventFilter(self)
        except Exception:
            pass
        QTimer.singleShot(0, self._update_responsive_panels)
        self._setup_inspector_autosave()
        self._setup_shortcuts()
        self._setup_timeline_connections()
        # self._setup_hotkeys()  # DISABLED — pynput global hooks interfere with Qt modal dialogs
        self._setup_tray()

        # Wire update-check signals for thread-safe UI callbacks
        self._update_found.connect(self._on_update_found)
        self._update_not_found.connect(self._on_update_not_found)
        self._update_error.connect(self._on_update_error)
        self._do_exit.connect(self._real_exit)
        self._close_update_dlg.connect(self._on_close_update_dlg)

        self._play_action.connect(self._do_play_cb)
        self._pause_state.connect(self._do_pause_cb)
        self._complete.connect(self._do_complete_cb)
        self._progress.connect(self._do_progress_cb)
        self._status_msg.connect(self.status)
        self._diag_msg.connect(self._append_diagnostic)
        self._image_match_state.connect(self._do_image_match_state)
        self._trace_row.connect(self._do_trace_row)
        self._playback_feedback_msg.connect(self._set_playback_feedback)

        self._check_update_silent()
        self.load_last_session()
        self._check_recovery_snapshot()
        self._restore_window_geometry()
        self._update_check_timer.start()

    # ═══════════════════════════════════════════════════════
    #  UI CONSTRUCTION
    # ═══════════════════════════════════════════════════════

    def _hsep(self):
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sep.setStyleSheet(f"background-color: {COLORS['border']}; border: none;")
        return sep

    def _build_ui(self):
        from ui.main_window_layout import build_main_layout
        build_main_layout(self)

    def _deselect_timeline(self, status_text=None):
        """Clear timeline selection and hide the Inspector selection state."""
        if getattr(self, "active_index", -1) < 0:
            try:
                if hasattr(self, "timeline"):
                    self.timeline.set_active(-1)
            except Exception:
                pass
            return
        self.select(-1)
        if status_text:
            self.status(status_text)

    def _widget_is_inside(self, widget, parent):
        while widget is not None:
            if widget is parent:
                return True
            widget = widget.parentWidget() if hasattr(widget, "parentWidget") else None
        return False

    def _maybe_deselect_from_background_click(self, widget):
        """Deselect the timeline for non-editor background clicks.

        Interactive controls and the Inspector stay selected so inline edits are
        not lost.  Empty timeline space is handled directly by TimelineView.
        """
        if widget is None or getattr(self, "active_index", -1) < 0:
            return
        if not hasattr(widget, "window") or widget.window() is not self:
            return
        if hasattr(self, "timeline") and (
            widget is self.timeline
            or widget is self.timeline.viewport()
            or self.timeline.isAncestorOf(widget)
        ):
            return

        interactive_types = (
            QPushButton, QCheckBox, QComboBox, QLineEdit, QSlider,
            QSpinBox, QDoubleSpinBox, QPlainTextEdit, QListWidget,
        )
        if isinstance(widget, interactive_types):
            return

        # Any click inside the expanded side panel should preserve the current
        # timeline selection. The Inspector contains many plain QFrame/QLabel
        # descendants, and global background-click handling can otherwise mistake
        # those blanks for an app-background deselect. Timeline empty-space clicks
        # still deliberately clear selection inside TimelineView itself.
        sidebar = getattr(self, "sidebar_frame", None)
        if sidebar is not None and self._widget_is_inside(widget, sidebar):
            return

        # Inspector blank space should never clear the selected timeline action.
        # Qt can deliver clicks from child frames, stacked panes, labels, or the
        # inspector body itself, so guard the whole Inspector ownership chain.
        inspector = getattr(self, "insp_card", None)
        inspector_body = getattr(self, "insp_body", None)
        inspector_widgets = [
            inspector, inspector_body,
            getattr(self, "inspector_action_row", None),
            getattr(self, "insp_empty", None),
            getattr(self, "insp_key", None), getattr(self, "insp_pause", None),
            getattr(self, "insp_click", None), getattr(self, "insp_image", None),
            getattr(self, "insp_group", None), getattr(self, "insp_loop", None),
            getattr(self, "insp_condition", None),
        ]
        for owner in inspector_widgets:
            if owner is not None and self._widget_is_inside(widget, owner):
                return

        # Do not clear the active action from global background clicks.
        # TimelineView owns its own empty-space deselect gesture; clicks inside
        # the side panel/Inspector or general UI chrome should never interrupt
        # the current inspected action.
        return

    def eventFilter(self, obj, event):
        try:
            if event.type() == QEvent.Type.MouseButtonPress:
                button = event.button() if hasattr(event, "button") else None
                if button == Qt.MouseButton.LeftButton and hasattr(obj, "parentWidget"):
                    self._maybe_deselect_from_background_click(obj)
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        try:
            old_size = event.oldSize() if event is not None else None
            new_size = event.size() if event is not None else None
            if (
                old_size is not None
                and new_size is not None
                and old_size.isValid()
                and old_size.height() != new_size.height()
                and not bool(getattr(self, "_side_panel_locked", False))
                and not bool(getattr(self, "_bottom_panel_locked", False))
                and not bool(getattr(self, "_programmatic_reveal_resize", False))
            ):
                self._clear_selection_reveal_from_click()
        except Exception:
            pass
        self._update_responsive_panels()
        self._update_toolbar_containment()
        self._autosize_inspector_panel()
        self._apply_panel_size_locks()

    def _toolbar_profile_text(self):
        """Return profile button text for the current toolbar width mode."""
        try:
            name = str(self.session_manager.active or "Default")
        except Exception:
            name = "Default"
        mode = str(getattr(self, "_toolbar_profile_mode", "full"))
        if mode == "tiny":
            shown = name if len(name) <= 8 else f"{name[:7]}…"
            return f"{shown}  ▾"
        if mode == "compact":
            shown = name if len(name) <= 11 else f"{name[:10]}…"
            return f"{shown}  ▾"
        shown = name if len(name) <= 18 else f"{name[:15]}..."
        return f"{shown}  ▾"

    def _update_toolbar_containment(self):
        """Keep the redesigned top toolbar contained in the visible header dock.

        The main window width is not enough to determine toolbar fit because the
        expanded side panel steals workspace width.  Use the header dock width
        itself, then compact non-status controls first so the right status pill
        stays inside the rounded top panel.
        """
        try:
            dock = getattr(self, "header_dock", None)
            profile = getattr(self, "profile_btn", None)
            if dock is None or profile is None:
                return
            width = int(dock.width() or self.width())
            if width <= 0:
                return

            if width < 760:
                mode = "tiny"
                profile_w = int(getattr(self, "_toolbar_profile_tiny_width", 116))
                margins = (5, 5, 7, 5)
                spacing = 2
                separator_visible = False
            elif width < 860:
                mode = "compact"
                profile_w = int(getattr(self, "_toolbar_profile_compact_width", 132))
                margins = (6, 5, 8, 5)
                spacing = 3
                separator_visible = True
            else:
                mode = "full"
                profile_w = int(getattr(self, "_toolbar_profile_full_width", 164))
                margins = (7, 5, 9, 5)
                spacing = 4
                separator_visible = True

            if getattr(self, "_toolbar_profile_mode", None) != mode:
                self._toolbar_profile_mode = mode
                profile.setText(self._toolbar_profile_text())

            if profile.width() != profile_w:
                profile.setFixedWidth(profile_w)

            layout = dock.layout()
            if layout is not None:
                left, top, right, bottom = layout.contentsMargins().left(), layout.contentsMargins().top(), layout.contentsMargins().right(), layout.contentsMargins().bottom()
                target_left, target_top, target_right, target_bottom = margins
                if (left, top, right, bottom) != margins:
                    layout.setContentsMargins(target_left, target_top, target_right, target_bottom)
                if layout.spacing() != spacing:
                    layout.setSpacing(spacing)

            for sep in getattr(self, "toolbar_separators", []):
                try:
                    sep.setVisible(separator_visible)
                    sep.setFixedWidth(1 if separator_visible else 0)
                except Exception:
                    pass

            status_pill = getattr(self, "status_pill", None)
            if status_pill is not None:
                try:
                    status_pill.setFixedWidth(int(getattr(self, "_status_pill_fixed_width", 150)))
                except Exception:
                    pass

            # Keep right-side status geometry inside the dock after any compact
            # profile/separator change.  This is intentionally a layout refresh,
            # not a status-pill resize.
            try:
                dock.updateGeometry()
                dock.layout().activate() if dock.layout() is not None else None
            except Exception:
                pass
        except Exception:
            pass

    def _update_responsive_panels(self):
        """Auto-hide panels for both width and height pressure."""
        self._update_responsive_side_panel()
        self._update_responsive_height_panels()

    def _update_responsive_side_panel(self):
        """Auto-collapse the side panel at narrow widths and restore it later."""
        setter = getattr(self, "_set_side_panel_collapsed", None)
        if (
            setter is None
            or bool(getattr(self, "_side_panel_locked", False))
            or bool(getattr(self, "_bottom_panel_locked", False))
        ):
            return
        try:
            width = int(self.width())
            collapse_at = int(getattr(self, "_side_panel_auto_collapse_width", 910))
            expand_at = int(getattr(self, "_side_panel_auto_expand_width", 1040))
            collapsed = bool(getattr(self, "_side_panel_collapsed", False))
            auto_collapsed = bool(getattr(self, "_side_panel_auto_collapsed", False))
            user_collapsed = bool(getattr(self, "_side_panel_user_collapsed", False))

            if width <= collapse_at and not collapsed:
                setter(True, auto=True)
            elif width >= expand_at and auto_collapsed and not user_collapsed:
                setter(False, auto=True)
        except Exception:
            pass

    def _update_responsive_height_panels(self):
        """Auto-collapse side-panel sections when the visible stack reaches the app bottom.

        The side panel keeps its normal full-height layout.  There is no
        artificial guard widget or pixel margin; collapse starts when the
        measured visible side-panel stack reaches the actual application content
        bottom.  Expansion still requires a restore cushion so the UI does not
        bounce between collapse/expand on the same pixel.
        """
        try:
            height = int(self.height())
            side_locked = bool(getattr(self, "_side_panel_locked", False))
            bottom_locked = bool(getattr(self, "_bottom_panel_locked", False))
            any_panel_locked = side_locked or bottom_locked
            set_panel = getattr(self, "_set_collapsible_panel", None)

            if any_panel_locked:
                return

            try:
                suppress_until = float(getattr(self, "_height_auto_collapse_suppressed_until", 0.0) or 0.0)
            except Exception:
                suppress_until = 0.0
            if suppress_until > time.monotonic():
                return

            if bool(getattr(self, "_selection_reveal_from_click", False)):
                return

            if set_panel is not None and not bool(getattr(self, "_side_panel_collapsed", False)):
                controls = getattr(self, "_panel_collapse_controls", {})

                active_anims = getattr(self, "_collapse_animations", {})
                if active_anims:
                    # Do not let the app-bottom policy start another collapse or
                    # expand while the previous section is still moving.  The
                    # layout helper runs a follow-up pass when each animation
                    # finishes; this small queued retry is a safety net for
                    # resize events that arrive mid-animation.
                    if not bool(getattr(self, "_height_panel_recheck_queued", False)):
                        self._height_panel_recheck_queued = True

                        def _retry_height_policy():
                            try:
                                self._height_panel_recheck_queued = False
                                self._update_responsive_height_panels()
                            except Exception:
                                pass

                        QTimer.singleShot(96, _retry_height_policy)
                    return

                def _panel_collapsed(body_name: str) -> bool:
                    ctl = controls.get(body_name)
                    return bool(ctl and ctl[1] and ctl[1].property("collapsed"))

                # Image actions use one collapsible Image Settings block inside
                # the flat Inspector.  Let that block collapse before the main
                # Inspector, then continue with the regular side-panel cards.
                try:
                    image_settings_visible = bool(
                        getattr(self, "insp_image", None) is not None
                        and self.insp_image.isVisible()
                        and "inspector_group_image_settings_body" in controls
                    )
                except Exception:
                    image_settings_visible = False
                collapse_steps = [
                    ("inspector_group_image_settings_body", image_settings_visible),
                    ("inspector_body", True),
                    ("recorder_body", True),
                    ("add_action_body", True),
                ]
                active_steps = [step for step in collapse_steps if bool(step[1])]

                restore_margin = max(0, int(getattr(self, "_side_panel_bottom_restore_margin", 32)))

                def _visible_stack_height():
                    """Return natural visible sidebar stack height and app-bottom available height."""
                    sidebar = getattr(self, "sidebar_frame", None)
                    if sidebar is None:
                        return 0, height
                    layout = sidebar.layout()
                    if layout is None:
                        return max(0, sidebar.sizeHint().height()), max(0, sidebar.height() or height)

                    try:
                        layout.invalidate()
                    except Exception:
                        pass

                    margins = layout.contentsMargins()
                    visible_widgets = []
                    spacer = getattr(self, "_side_panel_bottom_spacer", None)
                    for i in range(layout.count()):
                        item = layout.itemAt(i)
                        widget = item.widget() if item is not None else None
                        if widget is None or widget is spacer:
                            continue
                        if not widget.isVisible():
                            continue
                        visible_widgets.append(widget)

                    natural_h = margins.top() + margins.bottom()
                    if visible_widgets:
                        natural_h += max(0, layout.spacing()) * max(0, len(visible_widgets) - 1)
                    for widget in visible_widgets:
                        try:
                            current_h = int(widget.height())
                        except Exception:
                            current_h = 0
                        try:
                            hint_h = int(widget.sizeHint().height())
                        except Exception:
                            hint_h = 0
                        try:
                            min_hint_h = int(widget.minimumSizeHint().height())
                        except Exception:
                            min_hint_h = 0
                        natural_h += max(0, current_h, hint_h, min_hint_h)

                    # Measure against the actual program content bottom, not the
                    # sidebar widget's internal height.  Collapse triggers when
                    # the visible stack reaches this line exactly; no invisible
                    # guard/margin is subtracted from the content box.
                    try:
                        central = self.centralWidget()
                    except Exception:
                        central = None
                    if central is not None:
                        try:
                            sidebar_top_y = int(sidebar.mapTo(central, sidebar.rect().topLeft()).y())
                            available_h = int(central.rect().bottom()) + 1 - sidebar_top_y
                        except Exception:
                            available_h = 0
                    else:
                        available_h = 0
                    if available_h <= 0:
                        try:
                            available_h = int(sidebar.height())
                        except Exception:
                            available_h = height
                    if available_h <= 0:
                        available_h = height
                    return max(0, natural_h), max(0, available_h)

                def _estimated_expand_delta(body_name: str) -> int:
                    ctl = controls.get(body_name)
                    if not ctl:
                        return 0
                    body, _caret = ctl
                    if body is None:
                        return 0
                    try:
                        hint_h = int(body.sizeHint().height())
                    except Exception:
                        hint_h = 0
                    try:
                        min_hint_h = int(body.minimumSizeHint().height())
                    except Exception:
                        min_hint_h = 0
                    # A small floor avoids reopening a panel when there is only
                    # a few pixels of slack, which would cause resize flicker.
                    return max(24, hint_h, min_hint_h)

                stack_h, available_h = _visible_stack_height()
                hits_app_bottom = stack_h >= max(0, available_h)

                # Collapse one still-open section only when the visible stack
                # reaches the actual application content bottom.  This avoids
                # fixed-height threshold collapses and removes the old 2px
                # invisible guard margin.
                if hits_app_bottom:
                    for body_name, _enabled in active_steps:
                        if not _panel_collapsed(body_name):
                            set_panel(body_name, True, auto=True)
                            break
                else:
                    # Expand in reverse order, but only when the next section's
                    # estimated height can fit with a restore cushion below the
                    # actual application bottom.  The cushion prevents rapid
                    # collapse/expand bouncing on the same pixel.
                    for body_name, _enabled in reversed(active_steps):
                        if _panel_collapsed(body_name):
                            delta_h = _estimated_expand_delta(body_name)
                            if stack_h + delta_h <= max(0, available_h - restore_margin):
                                set_panel(body_name, False, auto=True)
                            break

            if hasattr(self, "playback_panel"):
                if (
                    height <= int(getattr(self, "_height_auto_playback_collapse", 1100))
                    and not bool(getattr(self, "_playback_collapsed", False))
                ):
                    self._set_playback_collapsed(True, auto=True)
                elif (
                    height >= int(getattr(self, "_height_auto_playback_expand", 1170))
                    and bool(getattr(self, "_playback_auto_collapsed", False))
                    and not bool(getattr(self, "_playback_user_collapsed", False))
                ):
                    self._set_playback_collapsed(False, auto=True)
        except Exception:
            pass

    def _expand_side_panel_for_lock(self):
        """Force the side-panel stack open before measuring a locked height."""
        try:
            if bool(getattr(self, "_side_panel_collapsed", False)):
                setter = getattr(self, "_set_side_panel_collapsed", None)
                if setter is not None:
                    setter(False, auto=True)

            set_panel = getattr(self, "_set_collapsible_panel", None)
            if set_panel is not None:
                for body_name in (
                    "add_action_body",
                    "recorder_body",
                    "inspector_body",
                    "inspector_group_key_settings_body",
                    "inspector_group_delay_settings_body",
                    "inspector_group_click_settings_body",
                    "inspector_group_image_settings_body",
                    "inspector_group_group_settings_body",
                    "inspector_group_loop_settings_body",
                    "inspector_group_condition_settings_body",
                    # Legacy names from older Inspector layouts.  Harmless if
                    # absent and keeps patched user trees resilient.
                    "inspector_group_key_action_body",
                    "inspector_group_pause_action_body",
                    "inspector_group_click_action_body",
                    "inspector_group_group_body",
                    "inspector_group_loop_body",
                    "inspector_group_condition_body",
                ):
                    set_panel(body_name, False, auto=True)

            if bool(getattr(self, "_playback_collapsed", False)):
                self._set_playback_collapsed(False, auto=True)
        except Exception:
            pass

    def _set_lock_button_state(self, btn, locked, locked_tip, unlocked_tip):
        if btn is None:
            return
        C = COLORS
        btn.setText("🔒" if locked else "🔓")
        btn.setToolTip(locked_tip if locked else unlocked_tip)
        border = C["accent"] if locked else C["border"]
        fg = "#FFFFFF" if locked else C["text_dim"]
        bg0 = "#0A2538" if locked else C["bg_tertiary"]
        bg1 = "#04121E" if locked else C["bg_secondary"]
        btn.setStyleSheet(
            f"QPushButton {{ color: {fg}; background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            f"stop:0 {bg0}, stop:1 {bg1}); border: 1px solid {border}; "
            "border-radius: 8px; padding: 0; font-size: 13px; font-weight: 900; }}"
            f"QPushButton:hover {{ border-color: {C['accent']}; color: {C['text']}; background-color: {C['bg_hover']}; }}"
            f"QPushButton:pressed {{ background-color: {C['accent_glow']}; }}"
        )
        btn.style().unpolish(btn)
        btn.style().polish(btn)

    def _toggle_side_panel_lock(self):
        locked = not bool(getattr(self, "_side_panel_locked", False))
        self._side_panel_locked = locked
        if locked:
            self._side_panel_user_collapsed = bool(getattr(self, "_side_panel_collapsed", False))
            self._expand_side_panel_for_lock()
        self._set_lock_button_state(
            getattr(self, "side_panel_lock_btn", None),
            locked,
            "Unlock side panel fixed height",
            "Lock side panel fixed height",
        )
        self.status("Side panel fixed-height lock enabled" if locked else "Side panel lock disabled")
        self._apply_panel_size_locks()

    def _toggle_bottom_panel_lock(self):
        locked = not bool(getattr(self, "_bottom_panel_locked", False))
        self._bottom_panel_locked = locked
        if locked:
            self._playback_user_collapsed = bool(getattr(self, "_playback_collapsed", False))
            self._expand_side_panel_for_lock()
        self._set_lock_button_state(
            getattr(self, "bottom_panel_lock_btn", None),
            locked,
            "Unlock fixed window height",
            "Lock fixed window height",
        )
        self.status("Fixed window height enabled" if locked else "Fixed window height disabled")
        self._apply_panel_size_locks()

    def _preferred_panel_lock_height(self):
        """Fixed window height while locked, following the current side-panel size.

        The bottom of the window should hug the current side-panel/Inspector
        layout instead of reserving space for the longest possible Inspector.
        """
        try:
            if not bool(getattr(self, "_measuring_panel_lock_height", False)):
                self._measuring_panel_lock_height = True
                try:
                    self._expand_side_panel_for_lock()
                    self._autosize_inspector_panel()
                finally:
                    self._measuring_panel_lock_height = False

            sidebar = getattr(self, "sidebar_frame", None)
            side_h = 0
            if sidebar is not None:
                sidebar.updateGeometry()
                # Use the actual current side-panel natural height.  Do not use
                # the longest Inspector measurement here; locked height should
                # auto-size to the selected side-panel state.
                side_h = max(
                    int(sidebar.sizeHint().height()),
                    int(sidebar.minimumSizeHint().height()),
                )

            playback_h = 36 if bool(getattr(self, "_playback_collapsed", False)) else 188
            base_min_h = int(getattr(self, "_base_min_height", 420))
            # Small padding accounts for the root layout margins without leaving
            # the bottom of the window far below the side panel.
            target = max(side_h + 8, playback_h + 220, base_min_h)
            return max(base_min_h, min(1800, int(target)))
        except Exception:
            return max(int(getattr(self, "_base_min_height", 420)), int(self.height()))

    def _apply_panel_size_locks(self):
        """When locked, freeze window height to selected action's full side-panel height."""
        try:
            max_w = 16777215
            any_locked = bool(getattr(self, "_side_panel_locked", False)) or bool(getattr(self, "_bottom_panel_locked", False))
            if any_locked:
                locked_h = self._preferred_panel_lock_height()
                if self.minimumHeight() != locked_h:
                    self.setMinimumHeight(locked_h)
                if self.maximumWidth() != max_w or self.maximumHeight() != locked_h:
                    self.setMaximumSize(max_w, locked_h)
                if self.height() != locked_h:
                    self.resize(self.width(), locked_h)
            else:
                base_w = int(getattr(self, "_base_min_width", 760))
                base_h = int(getattr(self, "_base_min_height", 420))
                if self.minimumWidth() != base_w or self.minimumHeight() != base_h:
                    self.setMinimumSize(base_w, base_h)
                if self.maximumWidth() != max_w or self.maximumHeight() != 16777215:
                    self.setMaximumSize(max_w, 16777215)
        except Exception:
            pass

    def _auto_grow_for_collapsed_side_panel(self):
        """When unlocked and the side rail is collapsed at minimum height, grow back to a usable side-panel baseline."""
        try:
            if not bool(getattr(self, "_side_panel_collapsed", False)):
                return
            if bool(getattr(self, "_side_panel_locked", False)) or bool(getattr(self, "_bottom_panel_locked", False)):
                return
            base_h = int(getattr(self, "_base_min_height", 420))
            if int(self.height()) > base_h + 28:
                return
            target_h = max(
                720,
                base_h,
                int(getattr(self, "_height_auto_recorder_expand", 720)),
                int(getattr(self, "_height_auto_inspector_expand", 840)),
            )
            if self.height() < target_h:
                self.resize(self.width(), target_h)
        except Exception:
            pass

    def _grow_window_for_unlocked_selection_content(self, extra_padding=10):
        """One-shot grow so a clicked action can reveal the expanded side panel.

        This is intentionally limited to the short-lived timeline-click reveal
        window. It grows only when the visible side-panel stack would extend past
        the app content bottom, then immediately yields back to normal manual
        resizing once the reveal flag clears.
        """
        try:
            if bool(getattr(self, "_side_panel_locked", False)) or bool(getattr(self, "_bottom_panel_locked", False)):
                return
            if bool(getattr(self, "_side_panel_collapsed", False)):
                return
            if not bool(getattr(self, "_selection_reveal_from_click", False)):
                return
            sidebar = getattr(self, "sidebar_frame", None)
            if sidebar is None or not sidebar.isVisible():
                return
            layout = sidebar.layout()
            if layout is None:
                return
            try:
                layout.invalidate()
            except Exception:
                pass
            margins = layout.contentsMargins()
            spacer = getattr(self, "_side_panel_bottom_spacer", None)
            visible_widgets = []
            for i in range(layout.count()):
                item = layout.itemAt(i)
                widget = item.widget() if item is not None else None
                if widget is None or widget is spacer or not widget.isVisible():
                    continue
                visible_widgets.append(widget)
            natural_h = margins.top() + margins.bottom()
            if visible_widgets:
                natural_h += max(0, layout.spacing()) * max(0, len(visible_widgets) - 1)
            for widget in visible_widgets:
                vals = []
                for getter in (widget.height, widget.sizeHint().height, widget.minimumSizeHint().height):
                    try:
                        vals.append(int(getter()))
                    except Exception:
                        pass
                natural_h += max([0] + vals)
            central = self.centralWidget()
            available_h = 0
            if central is not None:
                try:
                    top_y = int(sidebar.mapTo(central, sidebar.rect().topLeft()).y())
                    available_h = int(central.rect().bottom()) + 1 - top_y
                except Exception:
                    available_h = 0
            if available_h <= 0:
                available_h = int(sidebar.height() or self.height())
            overflow = int(natural_h) - int(available_h)
            if overflow <= 0:
                return
            target_h = int(self.height()) + overflow + int(extra_padding)
            try:
                screen = QApplication.primaryScreen()
                if screen is not None:
                    target_h = min(target_h, int(screen.availableGeometry().height()) - 24)
            except Exception:
                pass
            if target_h > self.height():
                self._programmatic_reveal_resize = True
                try:
                    self.resize(self.width(), target_h)
                finally:
                    QTimer.singleShot(0, lambda: setattr(self, "_programmatic_reveal_resize", False))
        except Exception:
            pass

    def _suppress_height_auto_collapse_for_reveal(self, duration_ms=720):
        """Temporarily keep explicit timeline-click reveals from being auto-collapsed."""
        try:
            ms = max(0, int(duration_ms))
        except Exception:
            ms = 720
        try:
            self._height_auto_collapse_suppressed_until = time.monotonic() + (ms / 1000.0)
        except Exception:
            self._height_auto_collapse_suppressed_until = 0.0

    def _begin_selection_reveal_from_click(self):
        """Allow one unlocked side-panel fit pass for an actual timeline click."""
        try:
            if bool(getattr(self, "_side_panel_locked", False)) or bool(getattr(self, "_bottom_panel_locked", False)):
                self._selection_reveal_from_click = False
                return
            self._selection_reveal_from_click = True
            self._suppress_height_auto_collapse_for_reveal(760)
            timer = getattr(self, "_selection_reveal_clear_timer", None)
            if timer is not None:
                timer.stop()
        except Exception:
            self._selection_reveal_from_click = False

    def _clear_selection_reveal_from_click(self):
        """Stop unlocked selection from holding the side-panel height after the click settles."""
        try:
            self._selection_reveal_from_click = False
            timer = getattr(self, "_selection_reveal_clear_timer", None)
            if timer is not None and timer.isActive():
                timer.stop()
        except Exception:
            self._selection_reveal_from_click = False

    def _finish_selection_reveal_from_click(self):
        """Clear one-shot reveal after Qt has processed the immediate layout updates."""
        try:
            timer = getattr(self, "_selection_reveal_clear_timer", None)
            if timer is not None:
                timer.start(520)
            else:
                QTimer.singleShot(520, self._clear_selection_reveal_from_click)
        except Exception:
            self._clear_selection_reveal_from_click()

    def _expand_inspector_for_timeline_selection(self):
        """Open the full side-panel editor stack after any timeline row click.

        Re-clicking the already-selected row now behaves like the first click:
        ADD ACTION, RECORDER, INSPECTOR, and the selected action settings body
        are forced open as one batch before the height policy is allowed to run.
        """
        try:
            controls = getattr(self, "_panel_collapse_controls", {}) or {}
            if not controls:
                return

            self._suppress_height_auto_collapse_for_reveal(820)

            def _current_action_kind():
                try:
                    if 0 <= int(getattr(self, "active_index", -1)) < self.action_model.rowCount():
                        return getattr(self.action_model.get(self.active_index), "action_type", "") or "key"
                except Exception:
                    pass
                return ""

            body_by_kind = {
                "key": "inspector_group_key_settings_body",
                "pause": "inspector_group_delay_settings_body",
                "click": "inspector_group_click_settings_body",
                "image": "inspector_group_image_settings_body",
                "group": "inspector_group_group_settings_body",
                "loop": "inspector_group_loop_settings_body",
                "condition": "inspector_group_condition_settings_body",
            }

            def _target_body_names():
                names = ["add_action_body", "recorder_body", "inspector_body"]
                selected_body = body_by_kind.get(_current_action_kind())
                if selected_body:
                    names.append(selected_body)
                names.extend([
                    "inspector_group_key_settings_body",
                    "inspector_group_delay_settings_body",
                    "inspector_group_click_settings_body",
                    "inspector_group_image_settings_body",
                    "inspector_group_group_settings_body",
                    "inspector_group_loop_settings_body",
                    "inspector_group_condition_settings_body",
                ])
                ordered = []
                seen = set()
                for name in names:
                    if name in controls and name not in seen:
                        ordered.append(name)
                        seen.add(name)
                return ordered

            def _stop_animation(body_name, body_widget):
                try:
                    anim_key = body_name or str(id(body_widget))
                    anim = getattr(self, "_collapse_animations", {}).pop(anim_key, None)
                    if anim is not None:
                        anim.stop()
                        anim.deleteLater()
                    if not bool(getattr(self, "_collapse_animations", {})):
                        self._panel_motion_suspends_inspector_autosize = False
                except Exception:
                    pass

            def _release_parent_clamps(body_widget):
                try:
                    parent = body_widget.parentWidget()
                except Exception:
                    parent = None
                while parent is not None:
                    try:
                        parent.setMinimumHeight(0)
                        parent.setMaximumHeight(16777215)
                        parent.updateGeometry()
                    except Exception:
                        pass
                    try:
                        if parent in (
                            getattr(self, "add_card", None),
                            getattr(self, "rec_card", None),
                            getattr(self, "insp_card", None),
                        ):
                            break
                    except Exception:
                        pass
                    try:
                        parent = parent.parentWidget()
                    except Exception:
                        parent = None

            def _force_open_body(body_name):
                ctl = controls.get(body_name)
                if not ctl:
                    return False
                body_widget, caret = ctl
                if body_widget is None or caret is None:
                    return False
                _stop_animation(body_name, body_widget)
                try:
                    body_widget.setProperty("user_collapsed", False)
                    body_widget.setProperty("auto_collapsed", False)
                    caret.setProperty("collapsed", False)
                    caret.setText("")
                    caret.setToolTip("Collapse panel")
                except Exception:
                    pass
                try:
                    body_widget.setVisible(True)
                    body_widget.setMinimumHeight(0)
                    body_widget.setMaximumHeight(16777215)
                    body_widget.setGraphicsEffect(None)
                    body_widget.setProperty("panel_transition_state", "expanded")
                    body_widget.updateGeometry()
                except Exception:
                    pass
                _release_parent_clamps(body_widget)
                return True

            def _settle_full_reveal():
                try:
                    self._suppress_height_auto_collapse_for_reveal(820)
                    for body_name in _target_body_names():
                        _force_open_body(body_name)
                    autosize = getattr(self, "_autosize_inspector_panel", None)
                    if callable(autosize):
                        autosize()
                    sidebar = getattr(self, "sidebar_frame", None)
                    if sidebar is not None:
                        try:
                            layout = sidebar.layout()
                            if layout is not None:
                                layout.invalidate()
                                layout.activate()
                        except Exception:
                            pass
                        try:
                            sidebar.updateGeometry()
                        except Exception:
                            pass
                    rebalance = getattr(self, "_rebalance_side_panel_space", None)
                    if callable(rebalance):
                        rebalance(reason="timeline.full_reveal")
                    grow = getattr(self, "_grow_window_for_unlocked_selection_content", None)
                    if callable(grow):
                        grow()
                except Exception:
                    pass

            _settle_full_reveal()
            for delay in (0, 16, 40, 80, 140, 220):
                try:
                    QTimer.singleShot(delay, _settle_full_reveal)
                except Exception:
                    pass
        except Exception:
            pass


    def _select_from_timeline_click(self, index):
        """Timeline click entry point.

        Selecting a row updates Inspector content.  Only this click path gets a
        short-lived reveal/fit pass while panels are unlocked; persistent selected
        rows no longer force side-panel height during vertical resize.
        """
        try:
            if index is None or int(index) < 0:
                self._clear_selection_reveal_from_click()
                self.select(index)
                return
            self._begin_selection_reveal_from_click()
            self.select(index)
            if not (bool(getattr(self, "_side_panel_locked", False)) or bool(getattr(self, "_bottom_panel_locked", False))):
                self._expand_inspector_for_timeline_selection()
                QTimer.singleShot(0, self._grow_window_for_unlocked_selection_content)
                QTimer.singleShot(24, self._grow_window_for_unlocked_selection_content)
                QTimer.singleShot(60, self._grow_window_for_unlocked_selection_content)
                QTimer.singleShot(110, self._grow_window_for_unlocked_selection_content)
            try:
                rows = self._selected_rows(index)
                if len(rows) > 1:
                    self.status(f"{len(rows)} actions selected")
            except Exception:
                pass
        finally:
            if not (bool(getattr(self, "_side_panel_locked", False)) or bool(getattr(self, "_bottom_panel_locked", False))):
                self._finish_selection_reveal_from_click()

    def _refresh_unlocked_selection_height(self):
        """Run the one-shot unlocked side-panel fit pass after an explicit click.

        In unlocked mode, a selected row should not continuously hold the
        side-panel/Inspector height.  The fit/reveal pass is intentionally allowed
        only while ``_selection_reveal_from_click`` is true; vertical window resize
        clears that flag so resize-driven collapse/expand can take control.
        """
        try:
            if bool(getattr(self, "_side_panel_locked", False)) or bool(getattr(self, "_bottom_panel_locked", False)):
                return
            if not bool(getattr(self, "_selection_reveal_from_click", False)):
                return
            self._autosize_inspector_panel()
            if hasattr(self, "sidebar_frame"):
                self.sidebar_frame.updateGeometry()
            if bool(getattr(self, "_side_panel_collapsed", False)):
                self._auto_grow_for_collapsed_side_panel()
            else:
                # Explicit clicks may reveal/fit once, then the reveal flag clears
                # and normal vertical resizing owns the side-panel state again.
                self._grow_window_for_unlocked_selection_content()
                self._update_responsive_height_panels()
        except Exception:
            pass

    def _make_playback_panel(self):
        from ui.playback_panel import make_playback_panel
        return make_playback_panel(self)

    def _make_stat_chip(self, icon_name, title, value, color, tooltip):
        """Static bottom-panel stat chip: compact, readable value-only chip."""
        C = COLORS
        chip = QFrame()
        chip.setObjectName("mf2_stat_chip")
        chip.setToolTip(f"{title}: {tooltip}")
        chip.setFixedWidth({"Played": 50, "Loops": 50, "Seq": 66, "Time": 78}.get(title, 54))
        chip.setFixedHeight(30)
        chip.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        chip.setStyleSheet(
            f"QFrame#mf2_stat_chip {{ background-color: {C['bg_card']}; "
            f"border: 1px solid {C['border']}; border-radius: 6px; }}"
            f"QFrame#mf2_stat_chip:hover {{ border-color: {color}; }}"
        )

        lo = QHBoxLayout(chip)
        lo.setContentsMargins(4, 2, 4, 2)
        lo.setSpacing(3)

        ico = QLabel()
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setFixedSize(15, 15)
        ico.setPixmap(icon(icon_name, 14, color).pixmap(14, 14))
        lo.addWidget(ico)

        value_lbl = QLabel(value)
        value_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        value_lbl.setStyleSheet(
            f"color: {C['text']}; font-size: 13px; background: transparent;"
        )
        lo.addWidget(value_lbl)
        return chip, value_lbl

    def _add_btn(self, text, callback, color, layout, icon_name="plus"):
        type_map = {"key": "add_key", "click": "add_click", "delay": "add_pause",
                    "pause": "add_pause", "image": "add_image", "condition": "add_condition",
                    "loop": "add_loop", "folder": "add_group", "group": "add_group"}
        kind_map = {"delay": "pause", "folder": "group"}
        action_kind = kind_map.get(icon_name, icon_name)
        obj = type_map.get(icon_name, "action_add")

        # Reference-matched Add Action skins.  These values are sampled from the
        # supplied dark button mock-up so the side panel keeps the same action
        # colors, but uses a deeper, less washed-out gaming-style gradient.
        add_action_skins = {
            "key": {
                "border": "#0783D4", "hover_border": "#03B5F5",
                "top": "#0A2853", "mid": "#03162C", "bottom": "#000C1A",
                "hover_top": "#0D346C", "hover_mid": "#041B38", "hover_bottom": "#000E1E",
            },
            "click": {
                "border": "#CB111C", "hover_border": "#FF2330",
                "top": "#53111B", "mid": "#2C0A13", "bottom": "#11060F",
                "hover_top": "#651520", "hover_mid": "#360C16", "hover_bottom": "#160711",
            },
            "pause": {
                "border": "#99A1A2", "hover_border": "#C6D0D2",
                "top": "#242C2F", "mid": "#121A1E", "bottom": "#050C0F",
                "hover_top": "#2F383C", "hover_mid": "#182126", "hover_bottom": "#081014",
            },
            "image": {
                "border": "#EBC310", "hover_border": "#FFD000",
                "top": "#493E0F", "mid": "#24210C", "bottom": "#0F110B",
                "hover_top": "#5A4C12", "hover_mid": "#2E290E", "hover_bottom": "#14160D",
            },
            "condition": {
                "border": "#8C21BB", "hover_border": "#D932FF",
                "top": "#351052", "mid": "#1F0834", "bottom": "#0C041A",
                "hover_top": "#421467", "hover_mid": "#290A43", "hover_bottom": "#110522",
            },
            "loop": {
                "border": "#04AF8A", "hover_border": "#00E5A8",
                "top": "#00413C", "mid": "#002123", "bottom": "#001013",
                "hover_top": "#00524B", "hover_mid": "#002B2D", "hover_bottom": "#001519",
            },
            "group": {
                "border": "#7030BD", "hover_border": "#8B5CF6",
                "top": "#261452", "mid": "#170D36", "bottom": "#0B0820",
                "hover_top": "#31196A", "hover_mid": "#1E1146", "hover_bottom": "#100A2C",
            },
        }
        skin = add_action_skins.get(action_kind, {
            "border": color, "hover_border": color,
            "top": "#04101A", "mid": "#020A13", "bottom": "#000207",
            "hover_top": "#071A2A", "hover_mid": "#03101B", "hover_bottom": "#000309",
        })

        btn = QPushButton(text)
        btn.setObjectName(obj)
        btn.setText("")
        btn.setIcon(QIcon())
        btn_w = int(getattr(self, "_add_action_group_width", 205)) if action_kind == "group" else int(getattr(self, "_add_action_button_width", 100))
        # The stylesheet box renders two pixels taller than this content value.
        btn_h = 43
        btn.setFixedSize(btn_w, btn_h)
        btn.setMinimumSize(btn_w, btn_h)
        btn.setMaximumSize(btn_w, btn_h)
        btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setProperty("qt_stacked_add_action", True)
        btn.setStyleSheet(
            f"QPushButton#{obj} {{"
            "background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            f"stop:0 {skin['top']}, stop:0.52 {skin['mid']}, stop:1 {skin['bottom']});"
            f"color: {COLORS['text_inverse']};"
            f"border: 1px solid {skin['border']};"
            "border-radius: 10px; padding: 0px; margin: 0px; text-align: center; font-weight: 800;"
            f"min-width: {btn_w}px; max-width: {btn_w}px; width: {btn_w}px;"
            f"min-height: {btn_h}px; max-height: {btn_h}px; height: {btn_h}px;"
            "}"
            f"QPushButton#{obj}:hover {{"
            "background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            f"stop:0 {skin['hover_top']}, stop:0.52 {skin['hover_mid']}, stop:1 {skin['hover_bottom']});"
            f"border: 1px solid {skin['hover_border']};"
            "}"
            f"QPushButton#{obj}:pressed {{"
            "background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            f"stop:0 {skin['bottom']}, stop:0.55 {skin['mid']}, stop:1 {skin['top']});"
            f"border: 1px solid {skin['hover_border']};"
            "}"
            f"QPushButton#{obj}:disabled {{"
            f"background: {COLORS['bg_secondary']}; color: {COLORS['text_dark']}; "
            f"border: 1px solid {COLORS['border']};"
            "}"
        )

        # Use fixed child geometry rather than a vertical layout.  This keeps
        # every regular Add Action button the exact same size, lets the label
        # sit 6-7px closer to the glyph, and prevents the Loop button from
        # visually expanding due to layout/style recalculation.
        # Match the Loop button's text/icon proportions across every Add Action
        # button: same glyph size, same vertical offsets, same label box.
        icon_size = 16
        icon_box = icon_size + 2
        icon_y = 5
        label_y = 22
        label_h = 14

        icon_lbl = QLabel(btn)
        icon_lbl.setObjectName(f"{obj}_icon")
        icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_color = skin["hover_border"] if action_kind != "pause" else "#C6D0D2"
        icon_lbl.setPixmap(timeline_action_icon(action_kind, icon_size, icon_color).pixmap(icon_size, icon_size))
        icon_lbl.setGeometry((btn_w - icon_box) // 2, icon_y, icon_box, icon_box)

        text_lbl = QLabel(text, btn)
        text_lbl.setObjectName(f"{obj}_label")
        text_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        text_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_lbl.setGeometry(0, label_y, btn_w, label_h)
        text_lbl.setStyleSheet(
            "QLabel { background: transparent; color: #F4F7FF; "
            "font-size: 11px; font-weight: 900; qproperty-alignment: AlignCenter; }"
        )
        btn.clicked.connect(callback)
        if layout is not None:
            layout.addWidget(btn)
        return btn

    def _label_row(self, text, widget):
        row = QFrame()
        lo = QHBoxLayout(row)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.addWidget(QLabel(text))
        lo.addWidget(widget)
        return row

    def _show_inspector(self, show=True, action_type="key"):
        for w in (
            self.insp_key, self.insp_pause, self.insp_click, self.insp_image,
            self.insp_group, self.insp_loop, self.insp_condition,
        ):
            w.setVisible(False)

        if hasattr(self, "inspector_action_row"):
            self.inspector_action_row.setVisible(bool(show))

        self.insp_empty.setVisible(False)
        if not show:
            self.insp_empty.setText("Select an action to inspect")
            self.insp_empty.setVisible(True)
            self._autosize_inspector_panel()
            return

        mapping = {
            "key": self.insp_key,
            "pause": self.insp_pause,
            "click": self.insp_click,
            "image": self.insp_image,
            "group": self.insp_group,
            "loop": self.insp_loop,
            "condition": self.insp_condition,
        }
        pane = mapping.get(action_type)
        if pane is not None:
            pane.setVisible(True)
        else:
            self.insp_empty.setText("Use Edit for this block")
            self.insp_empty.setVisible(True)
        self._autosize_inspector_panel()

    def _autosize_inspector_panel(self, force=False):
        """Resize Inspector to the selected action pane instead of stretching.

        The Inspector must stay immediately below the panels above it.  It uses
        Maximum vertical policy and the bottom spacer consumes leftover height,
        so collapse is visually upward into the Inspector header and expansion
        grows downward from that header.
        """
        if not force and bool(getattr(self, "_panel_motion_suspends_inspector_autosize", False)):
            self._pending_inspector_autosize = True
            return

        card = getattr(self, "insp_card", None)
        body = getattr(self, "insp_body", None)
        if card is None:
            return

        try:
            card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
            if body is not None:
                body.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

            if body is not None and not body.isVisible():
                # Collapsed Inspector: clamp to the header-only size.
                card.setMinimumHeight(0)
                card.setMaximumHeight(max(32, card.minimumSizeHint().height() + 2))
            else:
                # Expanded Inspector: release clamps, compute current selected
                # pane size, then clamp to that natural size to avoid a tall
                # empty shell.
                if body is not None:
                    body.setMinimumHeight(0)
                    body.setMaximumHeight(16777215)
                card.setMinimumHeight(0)
                card.setMaximumHeight(16777215)
                card.updateGeometry()
                if body is not None:
                    body.updateGeometry()
                natural_h = max(card.sizeHint().height(), card.minimumSizeHint().height())
                if natural_h <= 0:
                    natural_h = 140
                card.setMaximumHeight(natural_h + 4)

            card.updateGeometry()
            if hasattr(self, "sidebar_frame"):
                self.sidebar_frame.updateGeometry()
            if hasattr(self, "_apply_panel_size_locks") and not bool(getattr(self, "_measuring_panel_lock_height", False)):
                self._apply_panel_size_locks()
        except Exception:
            pass

    def _decode_action_image_pixmap(self, action) -> QPixmap:
        pixmap = QPixmap()
        data = getattr(action, "image_data", "") if action is not None else ""
        if not data:
            return pixmap
        try:
            raw = base64.b64decode(data)
            pixmap.loadFromData(raw)
        except Exception:
            pixmap = QPixmap()
        return pixmap

    def _set_image_inspector_preview(self, action=None):
        label = getattr(self, "image_preview_label", None)
        if label is None:
            return
        pixmap = self._decode_action_image_pixmap(action)
        self._image_preview_pixmap = pixmap
        if pixmap.isNull():
            label.setProperty("has_template", False)
            label.setPixmap(icon("image", 62, COLORS["image"]).pixmap(62, 62))
            label.setToolTip("No image template selected")
            return
        label.setProperty("has_template", True)
        label.setToolTip("Current image template")
        target = label.size()
        if target.width() < 20 or target.height() < 20:
            target = QSize(210, 92)
        label.setPixmap(
            pixmap.scaled(
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _zoom_image_preview(self):
        pixmap = getattr(self, "_image_preview_pixmap", QPixmap())
        if pixmap.isNull():
            self.status("No image template to preview")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Image template preview")
        dlg.setStyleSheet(build_stylesheet())
        lo = QVBoxLayout(dlg)
        lo.setContentsMargins(14, 14, 14, 14)
        preview = QLabel()
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setStyleSheet(
            f"background-color: {COLORS['bg_card']}; border: 1px solid {COLORS['border']}; border-radius: 10px;"
        )
        preview.setPixmap(
            pixmap.scaled(
                QSize(720, 520),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        lo.addWidget(preview)
        dlg.resize(760, 560)
        dlg.exec()

    def _fit_image_preview(self):
        if 0 <= self.active_index < self.action_model.rowCount():
            self._set_image_inspector_preview(self.action_model.get(self.active_index))
            self.status("Image preview fit to panel")
        else:
            self.status("No image action selected")

    def _browse_active_image_file(self):
        """Browse for a replacement image template without opening the full dialog."""
        if self.active_index < 0 or self.active_index >= self.action_model.rowCount():
            self.status("No image action selected")
            return
        action = self.action_model.get(self.active_index)
        if getattr(action, "action_type", "") != "image":
            self.status("Selected action is not an image action")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if not path:
            return
        try:
            with open(path, "rb") as f:
                data = f.read()
            if not data:
                QMessageBox.warning(self, "Invalid Image", "The selected image file is empty.")
                return
            self.history.push(self.action_model.actions())
            action.image_data = base64.b64encode(data).decode()
            self._stamp_action_environment(action)
            self.refresh()
            self._set_image_inspector_preview(action)
            self.save_session()
            self.status("Image template updated")
        except Exception as exc:
            logger.exception("Failed to browse active image template")
            QMessageBox.critical(self, "Image Error", str(exc))

    def _capture_active_image_region(self):
        """Capture only the image search region from the side Inspector button."""
        if self.active_index < 0 or self.active_index >= self.action_model.rowCount():
            self.status("No image action selected")
            return
        action = self.action_model.get(self.active_index)
        if getattr(action, "action_type", "") != "image":
            self.status("Selected action is not an image action")
            return
        try:
            from ui.dialogs.image_dialog import CaptureOverlay
            overlay = CaptureOverlay()
            result = overlay.exec()
            if result == QDialog.DialogCode.Accepted and overlay.region:
                x, y, w, h = overlay.region
                self.history.push(self.action_model.actions())
                action.search_region = f"{x},{y},{w},{h}"
                self._stamp_action_environment(action)
                self.refresh()
                self.save_session()
                self.status(f"Image search region captured: {x},{y},{w},{h}")
            else:
                self.status("Capture region cancelled")
        except Exception as exc:
            logger.exception("Failed to capture active image search region")
            QMessageBox.critical(self, "Capture Error", str(exc))

    def _setup_inspector_autosave(self):
        widgets = [
            getattr(self, name, None)
            for name in (
                "inspector_label",
                "ik_key", "ik_dur", "ik_repeat", "ik_label", "ik_hold",
                "ip_dur", "ip_label",
                "ic_x", "ic_y", "ic_btn", "ic_rand", "ic_repeat", "ic_label",
                "ii_sim", "ii_sim_slider", "ii_wait", "ii_retry_count", "ii_retry_delay", "ii_fail_mode", "ii_fail_target",
                "ig_name", "ig_collapsed", "ig_recovery",
                "il_label", "il_count", "il_target",
                "ico_label", "ico_type", "ico_true", "ico_false", "ico_retry_count", "ico_retry_delay", "ico_fail_mode", "ico_fail_target",
            )
        ]
        for widget in widgets:
            if widget is None:
                continue
            try:
                if isinstance(widget, QLineEdit):
                    widget.textEdited.connect(self._queue_inspector_autosave)
                elif isinstance(widget, QComboBox):
                    widget.currentIndexChanged.connect(self._queue_inspector_autosave)
                elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    widget.valueChanged.connect(self._queue_inspector_autosave)
                elif isinstance(widget, QCheckBox):
                    widget.toggled.connect(self._queue_inspector_autosave)
                elif isinstance(widget, QSlider):
                    widget.valueChanged.connect(self._queue_inspector_autosave)
            except Exception:
                pass

    def _queue_inspector_autosave(self, *args):
        if getattr(self, "_inspector_loading", False):
            return
        if self.active_index < 0 or self.active_index >= self.action_model.rowCount():
            return
        self._inspector_autosave_timer.start()

    def _autosave_inspector_edits(self):
        if getattr(self, "_inspector_loading", False):
            return
        self._apply_inspector(autosave=True)

    # ═══════════════════════════════════════════════════════
    #  KEYBOARD SHORTCUTS
    # ═══════════════════════════════════════════════════════

    def _hotkey(self, name: str, default: str) -> str:
        try:
            hotkeys = self.settings_manager.settings.setdefault("hotkeys", {})
            value = (hotkeys.get(name) or default or "").strip()
            return value or default
        except Exception:
            return default

    def _setup_shortcuts(self):
        # Keep shortcut objects alive and make them reloadable from Settings.
        for sc in getattr(self, "_shortcuts", []):
            try:
                sc.setEnabled(False)
                sc.setParent(None)
            except Exception:
                pass
        self._shortcuts = []

        def bind(name, default, slot):
            seq = self._hotkey(name, default)
            if not seq:
                return
            try:
                shortcut = QShortcut(QKeySequence(seq), self)
                shortcut.activated.connect(slot)
                self._shortcuts.append(shortcut)
            except Exception as exc:
                logger.debug(f"Shortcut bind failed for {name}={seq}: {exc}")

        bind("undo", "Ctrl+Z", self.undo)
        bind("redo", "Ctrl+Y", self.redo)
        bind("copy", "Ctrl+C", self.copy_action)
        bind("paste", "Ctrl+V", self.paste_action)
        bind("duplicate", "Ctrl+D", self._duplicate_inspector)
        bind("delete", "Delete", self._delete_selected)
        bind("delete_alt", "Ctrl+Delete", self._delete_selected)
        bind("select_all", "Ctrl+A", self._select_all_actions)
        bind("group", "Ctrl+G", lambda: self.create_group_from_rows())
        bind("ungroup", "Ctrl+Shift+G", self._ungroup_selected)
        bind("play_pause", "Space", self._toggle_play_pause_shortcut)
        bind("stop_deselect", "Escape", self._stop_or_deselect)
        bind("save", "Ctrl+S", lambda: (self._do_save_session(), self.status("Session saved")))
        bind("search", "Ctrl+F", lambda: (self._show_timeline_search_popup() if hasattr(self, "_show_timeline_search_popup") else self.tl_search.setFocus()))
        bind("run_from_selected", "Ctrl+Enter", self.test_from_selected_row)
        bind("macro_editor", "Ctrl+E", self.open_macro_editor)
        bind("record", "F7", self._toggle_record)
        bind("preflight", "Ctrl+Shift+P", self.open_preflight_report)
        bind("toggle_runtime_log", "Ctrl+Shift+L", self.toggle_runtime_log_panel)
        bind("variables", "Ctrl+Alt+V", self.open_variables_dialog)
        bind("profile_library", "Ctrl+Alt+P", self.open_profile_library)

    def reload_shortcuts(self):
        self._setup_shortcuts()
        self.status("Hotkeys updated")

    def _deselect(self):
        self.select(-1)
        self.timeline.selected_indices.clear()
        try:
            if hasattr(self.timeline, "selection_summary_changed"):
                self.timeline.selection_summary_changed.emit([])
        except Exception:
            pass
        if hasattr(self.timeline, "set_link_targets"):
            self.timeline.set_link_targets(-1, [])
        self.timeline.refresh()

    def _stop_or_deselect(self):
        if self.engine.running:
            self.stop()
        else:
            self._deselect()

    def _toggle_play_pause_shortcut(self):
        focus = QApplication.focusWidget()
        if isinstance(focus, (QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit)):
            return
        if self.engine.running:
            self.engine.toggle_pause()
        else:
            self.start()

    def _select_all_actions(self):
        if hasattr(self.timeline, "_is_row_selectable"):
            rows = [r for r in range(self.action_model.rowCount()) if self.timeline._is_row_selectable(r)]
        else:
            rows = list(range(self.action_model.rowCount()))
        if hasattr(self.timeline, "set_selected_rows"):
            self.timeline.set_selected_rows(rows, active=self.active_index if self.active_index in rows else (rows[0] if rows else None))
        else:
            self.timeline.selected_indices = set(rows)
            try:
                self.timeline.selectAll()
            except Exception:
                pass
        self.status(f"Selected {len(rows)} row(s)")

    def _ungroup_selected(self):
        rows = self._selected_rows(self.active_index)
        if len(rows) == 1 and 0 <= rows[0] < self.action_model.rowCount():
            action = self.action_model.get(rows[0])
            if getattr(action, "action_type", "") == "group":
                gid = getattr(action, "group_id", "")
                rows = [i for i, a in enumerate(self.action_model.actions()) if getattr(a, "group_id", "") == gid and getattr(a, "action_type", "") != "group"]
        self.remove_rows_from_group(rows)

    def _delete_selected(self):
        self.delete_action(self.active_index)

    # ═══════════════════════════════════════════════════════
    #  TIMELINE CONNECTIONS
    # ═══════════════════════════════════════════════════════

    def _setup_timeline_connections(self):
        self.timeline.action_clicked.connect(self._select_from_timeline_click)
        self.timeline.action_double_clicked.connect(self._open_active_dialog)
        self.timeline.action_dragged.connect(self.move_action_to)
        if hasattr(self.timeline, "action_dragged_many"):
            self.timeline.action_dragged_many.connect(self.move_actions_to)
        if hasattr(self.timeline, "action_dropped_into_group"):
            self.timeline.action_dropped_into_group.connect(self.move_action_into_group)
        if hasattr(self.timeline, "action_dropped_many_into_group"):
            self.timeline.action_dropped_many_into_group.connect(self.move_actions_into_group)
        self.timeline.action_context_menu.connect(self._timeline_context_menu)
        self.timeline.group_toggle_requested.connect(self.toggle_group_collapsed)
        if hasattr(self.timeline, "selection_summary_changed"):
            self.timeline.selection_summary_changed.connect(self._timeline_selection_summary_changed)

    def _timeline_selection_summary_changed(self, rows):
        try:
            count = len(rows or [])
        except Exception:
            count = 0
        if count > 1:
            self.status(f"{count} actions selected")

    def _expand_rows_for_group_blocks(self, rows):
        """Expand selected group headers into their contiguous group blocks."""
        actions = self.action_model.actions()
        count = len(actions)
        expanded = set()
        for raw in sorted({int(r) for r in (rows or []) if 0 <= int(r) < count}):
            if getattr(actions[raw], "action_type", "") == "group":
                expanded.update(self._contiguous_group_block(raw) or [raw])
            else:
                expanded.add(raw)
        return sorted(r for r in expanded if 0 <= r < count)

    def _selected_rows(self, fallback=None):
        """Return current timeline multi-selection as stable source-model rows."""
        try:
            if hasattr(self.timeline, "sync_selection"):
                self.timeline.sync_selection()
        except Exception:
            pass
        rows = sorted({r for r in getattr(self.timeline, "selected_indices", set()) if 0 <= r < self.action_model.rowCount()})
        if not rows and fallback is not None and 0 <= fallback < self.action_model.rowCount():
            rows = [fallback]
        return rows

    def _group_palette(self):
        C = COLORS
        return [
            C.get("accent", "#1aa7ff"), C.get("neon_purple", "#b45cff"),
            C.get("image", C.get("neon_gold", "#ffd21a")), C.get("success", "#16e085"),
            C.get("click", "#ff3b45"), C.get("pause_cyan", "#45e5ff"),
            "#ff8a3d", "#6ee7ff", "#f472b6", "#a3e635",
        ]

    def _new_group_id(self):
        return f"grp_{int(time.time() * 1000)}_{self.action_model.rowCount()}"

    def _group_color_for_number(self, number: int) -> str:
        palette = self._group_palette()
        return palette[max(0, number) % len(palette)]

    def _group_stats_for_id(self, group_id: str):
        """Return action count and estimated duration for a group id."""
        count = 0
        duration = 0.0
        for action in self.action_model.actions():
            if getattr(action, "action_type", "") == "group":
                continue
            if getattr(action, "group_id", "") != group_id:
                continue
            count += 1
            if not bool(getattr(action, "enabled", True)):
                continue
            kind = getattr(action, "action_type", "key") or "key"
            if kind in {"loop", "condition"}:
                continue
            if kind == "image" and float(getattr(action, "wait_timeout", 0.0) or 0.0) > 0:
                duration += float(getattr(action, "wait_timeout", 0.0) or 0.0)
            else:
                duration += float(getattr(action, "duration", 0.0) or 0.0)
        return count, duration

    def _group_display_label(self, row: int) -> str:
        meta = self._group_header_for_row(row)
        if not meta:
            return f"row {row + 1}"
        return f"{meta['badge']} {meta['name']}"

    def _row_target_text(self, row: int) -> str:
        if row < 0:
            return "Next row"
        if row >= self.action_model.rowCount():
            return f"Row {row + 1}"
        action = self.action_model.get(row)
        if getattr(action, "action_type", "") == "group":
            meta = self._group_header_for_row(row)
            if meta:
                return f"{meta['badge']} {meta['name']}"
        return f"Row {row + 1}"

    def _populate_target_combo(self, combo, selected=-1, *, include_next=True, max_row=None):
        """Populate row/group target combos. Stores zero-based row in itemData, -1 for fall-through."""
        combo.blockSignals(True)
        combo.clear()
        if include_next:
            combo.addItem("Next row", -1)
        group_meta = {m["row"]: m for m in self._group_headers()}
        limit = self.action_model.rowCount() if max_row is None else max(0, min(int(max_row), self.action_model.rowCount()))
        for row in range(limit):
            meta = group_meta.get(row)
            if meta:
                text = f"{meta['badge']} {meta['name']}  · row {row + 1}"
            else:
                text = f"Row {row + 1}"
            combo.addItem(text, row)
        found = False
        for i in range(combo.count()):
            if int(combo.itemData(i)) == int(selected):
                combo.setCurrentIndex(i)
                found = True
                break
        if not found and combo.count():
            combo.setCurrentIndex(0)
        combo.blockSignals(False)


    def _normalize_groups(self):
        """Ensure group headers/members have stable ids, colors, and badges."""
        actions = self.action_model.actions()
        headers = []
        active_gid = ""
        active_color = ""
        changed = False
        for i, action in enumerate(actions):
            kind = getattr(action, "action_type", "key") or "key"
            if kind == "group":
                if not getattr(action, "group_id", ""):
                    action.group_id = self._new_group_id() + f"_{i}"
                    changed = True
                if not getattr(action, "group_color", ""):
                    action.group_color = self._group_color_for_number(len(headers))
                    changed = True
                name = getattr(action, "group_name", "") or getattr(action, "label", "") or f"Group {len(headers) + 1}"
                if getattr(action, "group_name", "") != name:
                    action.group_name = name
                    changed = True
                if getattr(action, "label", "") != name:
                    action.label = inspector_label_text or name
                    changed = True
                if getattr(action, "block_depth", 0) != 0:
                    action.block_depth = 0
                    changed = True
                active_gid = action.group_id
                active_color = action.group_color
                headers.append((i, action))
            else:
                # Legacy support: rows indented under a header before group_id existed
                # are adopted by the nearest previous group.
                if getattr(action, "block_depth", 0) > 0 and not getattr(action, "group_id", "") and active_gid:
                    action.group_id = active_gid
                    action.group_color = active_color
                    changed = True
                if getattr(action, "group_id", ""):
                    if getattr(action, "block_depth", 0) < 1:
                        action.block_depth = 1
                        changed = True
                    if not getattr(action, "group_color", ""):
                        # Mirror the owning group's accent when possible.
                        owner = next((g for _, g in headers if getattr(g, "group_id", "") == action.group_id), None)
                        action.group_color = getattr(owner, "group_color", "") or active_color or self._group_color_for_number(0)
                        changed = True
        valid = {getattr(g, "group_id", "") for _, g in headers}
        for action in actions:
            if getattr(action, "action_type", "") != "group" and getattr(action, "group_id", "") and action.group_id not in valid:
                action.group_id = ""
                action.group_color = ""
                action.block_depth = 0
                changed = True
        return changed

    def _group_headers(self):
        self._normalize_groups()
        headers = []
        for row, action in enumerate(self.action_model.actions()):
            if getattr(action, "action_type", "") == "group":
                headers.append({
                    "row": row,
                    "action": action,
                    "gid": getattr(action, "group_id", "") or f"row-{row}",
                    "name": getattr(action, "group_name", "") or getattr(action, "label", "") or f"Group {len(headers) + 1}",
                    "color": getattr(action, "group_color", "") or self._group_color_for_number(len(headers)),
                    "badge": f"G{len(headers) + 1}",
                    "count": self._group_stats_for_id(getattr(action, "group_id", ""))[0],
                    "duration": self._group_stats_for_id(getattr(action, "group_id", ""))[1],
                    "role": getattr(action, "group_role", "normal"),
                })
        return headers

    def _group_header_for_id(self, group_id: str):
        for meta in self._group_headers():
            if meta["gid"] == group_id:
                return meta
        return None

    def _group_header_for_row(self, row: int):
        if row < 0 or row >= self.action_model.rowCount():
            return None
        action = self.action_model.get(row)
        if getattr(action, "action_type", "") == "group":
            gid = getattr(action, "group_id", "")
        else:
            gid = getattr(action, "group_id", "")
        if not gid:
            return None
        return self._group_header_for_id(gid)

    def _contiguous_group_block(self, header_row: int):
        if header_row < 0 or header_row >= self.action_model.rowCount():
            return []
        header = self.action_model.get(header_row)
        if getattr(header, "action_type", "") != "group":
            return []
        gid = getattr(header, "group_id", "")
        rows = [header_row]
        for r in range(header_row + 1, self.action_model.rowCount()):
            a = self.action_model.get(r)
            if getattr(a, "action_type", "") == "group":
                break
            if getattr(a, "group_id", "") == gid:
                rows.append(r)
                continue
            if getattr(a, "group_id", ""):
                break
            break
        return rows

    def _apply_row_reference_map(self, row_map):
        """Remap loop/jump references after structural row edits."""
        def remap(value):
            try:
                value = int(value)
            except Exception:
                return value
            if value < 0:
                return value
            return row_map.get(value, value)
        for action in self.action_model.actions():
            if hasattr(action, "loop_target"):
                action.loop_target = remap(getattr(action, "loop_target", -1))
            for attr in ("jump_to_on_found", "jump_to_on_not_found", "condition_jump_true", "condition_jump_false"):
                if hasattr(action, attr):
                    setattr(action, attr, remap(getattr(action, attr, -1)))

    def _make_group_action(self, name: str):
        gid = self._new_group_id()
        color = self._group_color_for_number(len(self._group_headers()))
        group = Action("[GROUP]", 0.0, action_type="group", label=name)
        group.group_name = name
        group.group_id = gid
        group.group_color = color
        group.group_collapsed = False
        group.block_depth = 0
        return group

    def create_group_from_rows(self, rows=None):
        rows = self._selected_rows(self.active_index if rows is None else None) if rows is None else sorted(set(rows))
        actions = self.action_model.actions()
        rows = [r for r in rows if 0 <= r < len(actions) and getattr(actions[r], "action_type", "") != "group"]
        if not rows:
            self.status("Select one or more action rows to group")
            return
        first, last = rows[0], rows[-1]
        if rows != list(range(first, last + 1)):
            QMessageBox.information(self, "Create Group", "Select a contiguous block of rows to create a folder group.")
            return
        name, ok = QInputDialog.getText(self, "Create Group", "Group name:")
        if not ok:
            return
        name = name.strip() or f"Group {len(self._group_headers()) + 1}"
        scroll_position = self.timeline.scroll_position()
        self.history.push(actions, self._timeline_history_state())
        group = self._make_group_action(name)
        self.action_model.insert_action(first, group)
        # Existing rows from first..last shifted down by one.
        for r in range(first + 1, last + 2):
            action = self.action_model.get(r)
            action.group_id = group.group_id
            action.group_color = group.group_color
            action.block_depth = max(1, int(getattr(action, "block_depth", 0) or 0))
        self._apply_row_reference_map({i: (i + 1 if i >= first else i) for i in range(self.action_model.rowCount())})
        self.active_index = first
        self.timeline.selected_indices = set(range(first, last + 2))
        self.refresh()
        self.timeline.set_active(first)
        self.timeline.restore_scroll_position(scroll_position)
        self.save_session()
        self.status(f"Created {name} from {len(rows)} action(s)")

    def add_rows_to_group(self, rows, group_id: str):
        rows = [r for r in sorted(set(rows or [])) if 0 <= r < self.action_model.rowCount()]
        meta = self._group_header_for_id(group_id)
        if not rows or not meta:
            return
        self.history.push(self.action_model.actions(), self._timeline_history_state())
        for r in rows:
            action = self.action_model.get(r)
            if getattr(action, "action_type", "") == "group":
                continue
            action.group_id = meta["gid"]
            action.group_color = meta["color"]
            action.block_depth = max(1, int(getattr(action, "block_depth", 0) or 0))
        self.refresh()
        self.save_session()
        self.status(f"Added {len(rows)} row(s) to {meta['badge']} {meta['name']}")

    def remove_rows_from_group(self, rows=None):
        rows = self._selected_rows(self.active_index if rows is None else None) if rows is None else sorted(set(rows))
        rows = [r for r in rows if 0 <= r < self.action_model.rowCount()]
        if not rows:
            return
        self.history.push(self.action_model.actions(), self._timeline_history_state())
        changed = 0
        for r in rows:
            action = self.action_model.get(r)
            if getattr(action, "action_type", "") == "group":
                continue
            if getattr(action, "group_id", ""):
                action.group_id = ""
                action.group_color = ""
                action.block_depth = 0
                changed += 1
        self.refresh()
        self.save_session()
        self.status(f"Removed {changed} row(s) from group")

    def toggle_group_collapsed(self, row=None, collapsed=None):
        row = self.active_index if row is None else row
        meta = self._group_header_for_row(row)
        if not meta:
            self.status("Select a group header or grouped action")
            return
        header = meta["action"]
        self.history.push(self.action_model.actions(), self._timeline_history_state())
        header.group_collapsed = (not bool(getattr(header, "group_collapsed", False))) if collapsed is None else bool(collapsed)
        # Keep active selection on the visible header when collapsing a child.
        self.active_index = meta["row"]
        self.refresh()
        self.timeline.set_active(meta["row"])
        self.save_session()
        self.status(("Collapsed" if header.group_collapsed else "Expanded") + f" {meta['badge']} {meta['name']}")

    def rename_group(self, row=None):
        row = self.active_index if row is None else row
        meta = self._group_header_for_row(row)
        if not meta:
            self.status("Select a group to rename")
            return
        old = meta["name"]
        name, ok = QInputDialog.getText(self, "Rename Group", "Group name:", text=old)
        if ok and name.strip():
            self.history.push(self.action_model.actions(), self._timeline_history_state())
            meta["action"].group_name = name.strip()
            meta["action"].label = name.strip()
            self.refresh(); self.save_session(); self.status(f"Renamed {meta['badge']} to {name.strip()}")

    def duplicate_group(self, row=None):
        row = self.active_index if row is None else row
        meta = self._group_header_for_row(row)
        if not meta:
            self.status("Select a group to duplicate")
            return
        block_rows = self._contiguous_group_block(meta["row"])
        if not block_rows:
            return
        self.history.push(self.action_model.actions(), self._timeline_history_state())
        actions = self.action_model.actions()
        copies = [deepcopy(actions[r]) for r in block_rows]
        old_gid = getattr(copies[0], "group_id", "")
        new_gid = self._new_group_id()
        new_color = self._group_color_for_number(len(self._group_headers()) + 1)
        for i, action in enumerate(copies):
            if getattr(action, "group_id", "") == old_gid:
                action.group_id = new_gid
                action.group_color = new_color
            if i == 0 and getattr(action, "action_type", "") == "group":
                action.group_name = f"{getattr(action, 'group_name', 'Group')} copy"
                action.label = action.group_name
                action.group_collapsed = False
        insert_at = block_rows[-1] + 1
        for offset, action in enumerate(copies):
            self.action_model.insert_action(insert_at + offset, action)
        self.active_index = insert_at
        self.timeline.selected_indices = set(range(insert_at, insert_at + len(copies)))
        self.refresh(); self.timeline.set_active(insert_at); self.save_session()
        self.status(f"Duplicated {meta['badge']} {meta['name']}")

    def ungroup_group(self, row=None):
        row = self.active_index if row is None else row
        meta = self._group_header_for_row(row)
        if not meta:
            self.status("Select a group to ungroup")
            return
        gid = meta["gid"]
        self.history.push(self.action_model.actions(), self._timeline_history_state())
        for action in self.action_model.actions():
            if getattr(action, "action_type", "") != "group" and getattr(action, "group_id", "") == gid:
                action.group_id = ""
                action.group_color = ""
                action.block_depth = 0
        self.action_model.remove_action(meta["row"])
        self.active_index = -1
        self.refresh(); self.save_session(); self.status(f"Ungrouped {meta['badge']} {meta['name']}")

    def delete_group_with_children(self, row=None):
        row = self.active_index if row is None else row
        meta = self._group_header_for_row(row)
        if not meta:
            self.status("Select a group to delete")
            return
        reply = QMessageBox.question(self, "Delete group", f"Delete {meta['badge']} {meta['name']} and all actions inside it?")
        if reply != QMessageBox.StandardButton.Yes:
            return
        gid = meta["gid"]
        self.history.push(self.action_model.actions(), self._timeline_history_state())
        rows = [i for i, a in enumerate(self.action_model.actions()) if i == meta["row"] or getattr(a, "group_id", "") == gid]
        for idx in sorted(rows, reverse=True):
            self.action_model.remove_action(idx)
        self.active_index = -1
        self.refresh(); self.update_statistics(immediate=True); self.save_session()
        self.status(f"Deleted {meta['badge']} and {len(rows)-1} action(s)")

    def set_group_color(self, row, color):
        meta = self._group_header_for_row(row)
        if not meta:
            return
        self.history.push(self.action_model.actions(), self._timeline_history_state())
        gid = meta["gid"]
        for action in self.action_model.actions():
            if getattr(action, "group_id", "") == gid:
                action.group_color = color
        meta["action"].group_color = color
        self.refresh(); self.save_session(); self.status(f"Updated {meta['badge']} color")

    def set_group_recovery_role(self, row=None, enabled=True):
        row = self.active_index if row is None else row
        meta = self._group_header_for_row(row)
        if not meta:
            self.status("Select a group to mark as recovery")
            return
        self.history.push(self.action_model.actions(), self._timeline_history_state())
        meta["action"].group_role = "recovery" if enabled else "normal"
        self.refresh(); self.save_session(); self.status(("Marked" if enabled else "Cleared") + f" {meta['badge']} as recovery")

    def _assign_group_from_position(self, row: int):
        if row < 0 or row >= self.action_model.rowCount():
            return
        action = self.action_model.get(row)
        if getattr(action, "action_type", "") == "group":
            return
        target_meta = None
        # If the previous visible row is a group header/member, treat the drop as into that folder.
        if row > 0:
            prev = self.action_model.get(row - 1)
            if getattr(prev, "action_type", "") == "group":
                target_meta = self._group_header_for_row(row - 1)
            elif getattr(prev, "group_id", ""):
                target_meta = self._group_header_for_id(getattr(prev, "group_id", ""))
        if target_meta:
            action.group_id = target_meta["gid"]
            action.group_color = target_meta["color"]
            action.block_depth = max(1, int(getattr(action, "block_depth", 0) or 0))
        elif getattr(action, "group_id", ""):
            action.group_id = ""
            action.group_color = ""
            action.block_depth = 0

    def _suggest_loop_target(self, loop_row_zero_based: int):
        # Prefer the nearest earlier group header, otherwise row 0.
        for r in range(loop_row_zero_based - 1, -1, -1):
            if getattr(self.action_model.get(r), "action_type", "") == "group":
                return r
        return 0 if loop_row_zero_based > 0 else -1

    def _timeline_context_menu(self, index, pos):
        if index < 0 or index >= self.action_model.rowCount():
            return
        if index not in getattr(self.timeline, "selected_indices", set()):
            self.select(index)
        else:
            self.active_index = index
        rows = self._selected_rows(index)
        action = self.action_model.get(index)
        group_meta = self._group_header_for_row(index)
        m = QMenu(self)
        C = COLORS
        m.setStyleSheet(f"""
            QMenu {{ background-color: {C['bg_tertiary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 10px; padding: 6px; }}
            QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
            QMenu::item:selected {{ background-color: {C['bg_hover']}; color: {C['accent']}; }}
        """)
        selection_label = f" ({len(rows)} selected)" if len(rows) > 1 else ""
        m.addAction(f"Edit{selection_label if len(rows) == 1 else ''}", lambda: self._open_active_dialog(index)).setEnabled(len(rows) == 1)
        m.addAction(f"Duplicate{selection_label}", lambda: self.duplicate_action(index))
        m.addAction("Enable/Disable", lambda: self.toggle_action_enabled(index))
        m.addSeparator()

        group_menu = m.addMenu("Group / folder")
        group_menu.addAction("Create group from selection", lambda r=rows: self.create_group_from_rows(r))
        existing = group_menu.addMenu("Add selected to existing group")
        headers = self._group_headers()
        if headers:
            for meta in headers:
                existing.addAction(f"{meta['badge']}  {meta['name']}", lambda gid=meta['gid'], r=rows: self.add_rows_to_group(r, gid))
        else:
            a = existing.addAction("No groups yet")
            a.setEnabled(False)
        group_menu.addAction("Remove selected from group", lambda r=rows: self.remove_rows_from_group(r))
        if group_meta:
            group_menu.addSeparator()
            header = group_meta["action"]
            group_menu.addAction(("Expand" if getattr(header, "group_collapsed", False) else "Collapse") + f" {group_meta['badge']}", lambda row=group_meta['row']: self.toggle_group_collapsed(row))
            group_menu.addAction("Rename group…", lambda row=group_meta['row']: self.rename_group(row))
            group_menu.addAction("Edit group…", lambda row=group_meta['row']: self._open_group_editor(row))
            group_menu.addAction("Duplicate whole group", lambda row=group_meta['row']: self.duplicate_group(row))
            group_menu.addAction("Ungroup contents", lambda row=group_meta['row']: self.ungroup_group(row))
            group_menu.addAction("Delete group only", lambda row=group_meta['row']: self.delete_action(row))
            group_menu.addAction("Delete group + actions", lambda row=group_meta['row']: self.delete_group_with_children(row))
            group_menu.addSeparator()
            role_txt = "Clear recovery group" if getattr(header, "group_role", "normal") == "recovery" else "Mark as recovery group"
            group_menu.addAction(role_txt, lambda row=group_meta['row'], enabled=getattr(header, "group_role", "normal") != "recovery": self.set_group_recovery_role(row, enabled))
            color_menu = group_menu.addMenu("Change group color")
            for n, color in enumerate(self._group_palette(), 1):
                color_menu.addAction(f"Color {n}", lambda c=color, row=group_meta['row']: self.set_group_color(row, c))
            group_menu.addSeparator()
            move_up_g = group_menu.addAction("Move group up", lambda row=group_meta['row']: self.move_action(row, -1))
            move_down_g = group_menu.addAction("Move group down", lambda row=group_meta['row']: self.move_action(row, 1))
            move_up_g.setEnabled(not self.engine.running and group_meta['row'] > 0)
            move_down_g.setEnabled(not self.engine.running and group_meta['row'] < self.action_model.rowCount() - 1)
        m.addSeparator()

        # Kept for debug workflows, but image preview only enables for image rows.
        preview = m.addAction("Preview image confidence", lambda: self.open_image_confidence_preview(index))
        preview.setEnabled(getattr(action, "action_type", "") == "image")
        m.addSeparator()
        sorting_locked = self.engine.running or self.timeline.playing_index >= 0
        move_up = m.addAction("Move Up", lambda: self.move_action(index, -1))
        move_down = m.addAction("Move Down", lambda: self.move_action(index, 1))
        move_up.setEnabled(not sorting_locked and index > 0 and len(rows) == 1)
        move_down.setEnabled(not sorting_locked and index < self.action_model.rowCount() - 1 and len(rows) == 1)
        m.addSeparator()
        m.addAction(f"Delete{selection_label}", lambda: self.delete_action(index))
        m.exec(pos)

    # ═══════════════════════════════════════════════════════
    #  SESSION & PROFILE
    # ═══════════════════════════════════════════════════════

    def load_last_session(self):
        session = self.session_manager.load_profile()
        if session:
            try:
                self.action_model.clear()
                for action_data in session.get("actions", []):
                    self.action_model.add_action(Action.from_dict(action_data))
                self._normalize_groups()
                settings = session.get("settings", {})
                self.loops_spin.setValue(int(settings.get("loops", 1)))
                speed = float(settings.get("speed", 1.0) or 1.0)
                speed_text = f"{speed:g}x"
                if self.speed_combo.findText(speed_text) >= 0:
                    self.speed_combo.setCurrentText(speed_text)
                self.inf_check.setChecked(settings.get("infinite_loop", False))
                self.human_check.setChecked(settings.get("human_curve", True))
                self.macro_variables = dict(settings.get("macro_variables", {}) or {})
                # Keep the reference layout as the persisted baseline. Users
                # can still compact rows temporarily with Ctrl+wheel.
                self.timeline.zoom = max(1.0, float(settings.get("zoom", 1.0) or 1.0))
                # Window geometry is stored GLOBALLY (see _restore_window_geometry),
                # never per-profile, so switching profiles never moves the window.
                self.engine.actions = self.action_model.actions()
                self._invalidate_seq_dur()
                self.active_index = -1
                self.timeline.selected_indices.clear()
                self.timeline.set_active(-1)
                self.timeline.clear_playing()
                self.timeline.refresh()
                self.refresh()
                self.actions_played = 0
                self.session_elapsed_time = 0.0
                self.session_start_time = None
                self.update_statistics(immediate=True)
                self.status(f"Profile '{self.session_manager.active}' loaded")
            except Exception:
                if not self.action_model.rowCount():
                    self.status("Failed to load profile")
                else:
                    self.status("Profile partially loaded")
        else:
            self.action_model.clear()
            self.timeline.refresh()
            self.update_statistics(immediate=True)
            self.status("Ready")
        self._refresh_profile_btn()

    def save_session(self):
        if not self.auto_save_enabled:
            return
        if hasattr(self, "autosave_label"):
            self.autosave_label.setText("Unsaved")
            self.autosave_label.setStyleSheet(self.autosave_label.styleSheet().replace(COLORS["success"], COLORS["image"]))
        self._save_session_timer.start()

    def _do_save_session(self):
        settings = {
            "loops": self.loops_spin.value(),
            "speed": float(self.speed_combo.currentText().replace("x", "")),
            "infinite_loop": self.inf_check.isChecked(),
            "human_curve": self.human_check.isChecked(),
            "macro_variables": dict(getattr(self, "macro_variables", {}) or {}),
            "zoom": self.timeline.zoom,
        }
        self.session_manager.save_profile(self.action_model.actions(), settings)
        self._write_recovery_snapshot(clean_shutdown=False)
        self._save_window_geometry()
        if hasattr(self, "autosave_label"):
            self.autosave_label.setText("Saved")
            self.autosave_label.setStyleSheet(self.autosave_label.styleSheet().replace(COLORS["image"], COLORS["success"]))

    def _save_window_geometry(self):
        """Persist window geometry GLOBALLY (independent of profile)."""
        try:
            self.settings_manager.set(
                "window_geometry", self.saveGeometry().toHex().data().decode()
            )
        except Exception:
            pass

    def _restore_window_geometry(self):
        """Restore the last global window geometry, if any."""
        try:
            geo = self.settings_manager.get("window_geometry", "")
            if geo:
                self.restoreGeometry(bytes.fromhex(geo))
        except Exception:
            pass
        self.resize(985, 1100)

    def _refresh_profile_btn(self):
        if hasattr(self, "profile_btn"):
            try:
                self.profile_btn.setText(self._toolbar_profile_text())
                self._update_toolbar_containment()
            except Exception:
                name = str(self.session_manager.active or "Default")
                shown = name if len(name) <= 18 else f"{name[:15]}..."
                self.profile_btn.setText(f"{shown}  \u25be")

    def _show_profile_menu(self):
        from ui.main_window_menus import show_profile_menu
        show_profile_menu(self)

    def _switch_profile(self, name):
        from ui.main_window_menus import switch_profile
        switch_profile(self, name)

    def _new_profile_dialog(self):
        from ui.main_window_menus import new_profile_dialog
        new_profile_dialog(self)

    def _rename_profile_dialog(self):
        from ui.main_window_menus import rename_profile_dialog
        rename_profile_dialog(self)

    def _delete_profile_confirm(self):
        from ui.main_window_menus import delete_profile_confirm
        delete_profile_confirm(self)

    def _linked_targets_for_action(self, index: int):
        if index < 0 or index >= self.action_model.rowCount():
            return []
        action = self.action_model.get(index)
        targets = []
        def safe_target(value):
            try:
                return int(value if value not in (None, "") else -1)
            except (TypeError, ValueError):
                return -1
        kind = getattr(action, "action_type", "key") or "key"
        if kind == "loop":
            targets.append(safe_target(getattr(action, "loop_target", -1)))
        elif kind == "condition":
            targets.append(safe_target(getattr(action, "condition_jump_true", -1)))
            targets.append(safe_target(getattr(action, "condition_jump_false", -1)))
        elif kind == "image":
            targets.append(safe_target(getattr(action, "jump_to_on_found", -1)))
            targets.append(safe_target(getattr(action, "jump_to_on_not_found", -1)))
        return [t for t in dict.fromkeys(targets) if 0 <= t < self.action_model.rowCount()]

    def _update_timeline_links(self, index: int):
        if hasattr(self.timeline, "set_link_targets"):
            self.timeline.set_link_targets(index, self._linked_targets_for_action(index))

    def _display_index_from_engine_index(self, idx: int) -> int:
        if self._run_index_map and 0 <= idx < len(self._run_index_map):
            return self._run_index_map[idx]
        return self._single_test_index if self._single_test_active and idx == 0 else self._run_from_index + idx

    def _status_pill_display_text(self, text, limit=None):
        """Return status-pill text capped for the top toolbar.

        The full message is still preserved as the QLabel tooltip by status().
        """
        full_text = str(text or "")
        try:
            if limit is None:
                label = getattr(self, "status_text", None)
                limit = int(label.property("max_chars") or 43) if label is not None else 43
        except Exception:
            limit = 43
        try:
            limit = int(limit)
        except Exception:
            limit = 43
        if limit <= 0 or len(full_text) <= limit:
            return full_text
        return full_text[:max(0, limit - 1)].rstrip() + "…"

    # ═══════════════════════════════════════════════════════
    #  SELECTION & EDITING
    # ═══════════════════════════════════════════════════════

    def select(self, index):
        self._inspector_loading = True
        try:
            if index is None or index < 0 or index >= self.action_model.rowCount():
                self.active_index = -1
                self.timeline.set_active(-1)
                self.timeline.selected_indices.clear()
                self.inspector_selector.clear()
                self.inspector_selector.addItem("Select an action")
                if hasattr(self, "inspector_action_row"):
                    self.inspector_action_row.setVisible(False)
                if hasattr(self, "inspector_type_badge"):
                    self.inspector_type_badge.setText("ACTION")
                    self.inspector_type_badge.setEnabled(False)
                if hasattr(self, "inspector_label"):
                    self.inspector_label.blockSignals(True)
                    self.inspector_label.clear()
                    self.inspector_label.setEnabled(False)
                    self.inspector_label.blockSignals(False)
                self._autosize_inspector_panel()
                QTimer.singleShot(0, self._autosize_inspector_panel)
                self._set_image_inspector_preview(None)
                self._show_inspector(False)
                if hasattr(self.timeline, "set_link_targets"):
                    self.timeline.set_link_targets(-1, [])
                return
            self.active_index = index
            preserve_multi = index in getattr(self.timeline, "selected_indices", set()) and len(getattr(self.timeline, "selected_indices", set())) > 1
            if preserve_multi:
                try:
                    self.timeline.sync_selection()
                except Exception:
                    pass
                self.timeline.viewport().update()
            else:
                self.timeline.selected_indices.clear()
                self.timeline.set_active(index)
            action = self.action_model.get(index)
            self._update_timeline_links(index)
            if hasattr(self, "inspector_action_row"):
                self.inspector_action_row.setVisible(True)
            self.inspector_selector.clear()
            if action.action_type == "image":
                self.inspector_selector.addItem(icon("image", 14, COLORS["image"]), "Image Action")
            else:
                self.inspector_selector.addItem(getattr(action, "label", "") or getattr(action, "key", "") or f"Action {index + 1}")
            if hasattr(self, "inspector_type_badge"):
                self.inspector_type_badge.setText(str(action.action_type or "action").upper())
                self.inspector_type_badge.setEnabled(True)
            if hasattr(self, "inspector_label"):
                timeline_name = (
                    getattr(action, "label", "")
                    or getattr(action, "group_name", "")
                    or getattr(action, "key", "")
                    or f"Action {index + 1}"
                )
                self.inspector_label.blockSignals(True)
                self.inspector_label.setText(str(timeline_name))
                self.inspector_label.setEnabled(True)
                self.inspector_label.blockSignals(False)
            self._show_inspector(True, action.action_type)
            QTimer.singleShot(0, self._autosize_inspector_panel)
            if action.action_type == "key":
                self.ik_key.setText(action.key)
                self.ik_dur.setText(str(action.duration))
                self.ik_hold.setChecked(action.hold_mode)
                self.ik_repeat.setText(str(getattr(action, 'repeat_count', 1)))
                self.ik_label.setText(getattr(action, 'label', ''))
            elif action.action_type == "pause":
                self.ip_dur.setText(str(action.duration))
                self.ip_label.setText(getattr(action, 'label', ''))
            elif action.action_type == "click":
                self.ic_x.setText(str(getattr(action, 'click_x', 0)))
                self.ic_y.setText(str(getattr(action, 'click_y', 0)))
                self.ic_btn.setCurrentText(getattr(action, 'click_button', 'left'))
                self.ic_rand.setText(str(getattr(action, 'click_rand_radius', 0)))
                self.ic_repeat.setText(str(getattr(action, 'repeat_count', 1)))
                self.ic_label.setText(getattr(action, 'label', ''))
            elif action.action_type == "image":
                similarity = float(getattr(action, 'similarity', 0.85) or 0.85)
                self.ii_sim.setText(f"{similarity:.2f}")
                if hasattr(self, "ii_sim_slider"):
                    self.ii_sim_slider.blockSignals(True)
                    self.ii_sim_slider.setValue(max(0, min(100, int(round(similarity * 100)))))
                    self.ii_sim_slider.blockSignals(False)
                self.ii_wait.setText(str(int(round(float(getattr(action, 'wait_timeout', 1.0) or 0.0) * 1000))))
                if hasattr(self, "ii_retry_count"):
                    self.ii_retry_count.setValue(max(1, int(getattr(action, "retry_attempts", 1) or 1)))
                    self.ii_retry_delay.setText(str(int(round(float(getattr(action, "retry_delay", 0.25) or 0.0) * 1000))))
                    fail_mode = (getattr(action, "on_fail_action", "default") or "default").replace("_", " ").title()
                    self.ii_fail_mode.setCurrentText(fail_mode)
                    self._populate_target_combo(self.ii_fail_target, int(getattr(action, "on_fail_target", -1) or -1), include_next=True)
                self._set_image_inspector_preview(action)
            elif action.action_type == "group":
                self.ig_name.setText(getattr(action, "group_name", "") or getattr(action, "label", ""))
                self.ig_collapsed.setChecked(bool(getattr(action, "group_collapsed", False)))
                if hasattr(self, "ig_recovery"):
                    self.ig_recovery.setChecked(getattr(action, "group_role", "normal") == "recovery")
                gid = getattr(action, "group_id", "")
                count, duration = self._group_stats_for_id(gid)
                role = " · Recovery" if getattr(action, "group_role", "normal") == "recovery" else ""
                self.ig_meta.setText(f"{self._group_display_label(index)} · {count} action{'s' if count != 1 else ''} · ~{duration:.1f}s{role}")
            elif action.action_type == "loop":
                self.il_label.setText(getattr(action, "label", ""))
                self.il_count.setValue(max(2, int(getattr(action, "loop_count", getattr(action, "repeat_count", 2)) or 2)))
                self._populate_target_combo(self.il_target, int(getattr(action, "loop_target", -1) or -1), include_next=False, max_row=index)
            elif action.action_type == "condition":
                self.ico_label.setText(getattr(action, "label", ""))
                self.ico_type.setCurrentText(getattr(action, "condition_type", "none") or "none")
                self._populate_target_combo(self.ico_true, int(getattr(action, "condition_jump_true", -1) or -1), include_next=True)
                self._populate_target_combo(self.ico_false, int(getattr(action, "condition_jump_false", -1) or -1), include_next=True)
                if hasattr(self, "ico_retry_count"):
                    self.ico_retry_count.setValue(max(1, int(getattr(action, "retry_attempts", 1) or 1)))
                    self.ico_retry_delay.setText(str(getattr(action, "retry_delay", 0.25)))
                    self.ico_fail_mode.setCurrentText(getattr(action, "on_fail_action", "default") or "default")
                    self._populate_target_combo(self.ico_fail_target, int(getattr(action, "on_fail_target", -1) or -1), include_next=True)
                ctype = getattr(action, "condition_type", "none") or "none"
                if ctype == "pixel_color":
                    self.ico_rule.setText(f"Pixel @ {getattr(action, 'condition_x', 0)}, {getattr(action, 'condition_y', 0)} = {getattr(action, 'condition_color', '') or 'color'}")
                elif ctype == "variable":
                    self.ico_rule.setText(f"{getattr(action, 'condition_var_name', '') or 'variable'} = {getattr(action, 'condition_var_value', '') or 'value'}")
                else:
                    self.ico_rule.setText("No rule selected")
            if action.action_type != "image":
                self._set_image_inspector_preview(None)
        except Exception as exc:
            logger.exception("Failed to select timeline row %s", index)
            try:
                row_label = int(index) + 1
            except Exception:
                row_label = "?"
            try:
                self._show_inspector(False)
                if hasattr(self, "inspector_action_row"):
                    self.inspector_action_row.setVisible(False)
                self.insp_empty.setText(f"Could not inspect row {row_label}. Try profile repair or edit this action.")
                self.insp_empty.setVisible(True)
                self.status(f"Could not inspect row {row_label}")
            except Exception:
                pass
        finally:
            self._inspector_loading = False
            if bool(getattr(self, "_side_panel_locked", False)) or bool(getattr(self, "_bottom_panel_locked", False)):
                QTimer.singleShot(0, self._apply_panel_size_locks)
                QTimer.singleShot(35, self._apply_panel_size_locks)
            elif bool(getattr(self, "_selection_reveal_from_click", False)):
                self._refresh_unlocked_selection_height()
                QTimer.singleShot(35, self._refresh_unlocked_selection_height)

    def _apply_inspector(self, autosave=False):
        if self.active_index < 0 or self.active_index >= self.action_model.rowCount():
            if not autosave:
                QMessageBox.warning(self, "No Selection", "Please select an action first")
            return
        try:
            action = self.action_model.get(self.active_index)
            if not autosave:
                self.history.push(self.action_model.actions())
            inspector_label_text = ""
            if hasattr(self, "inspector_label"):
                inspector_label_text = self.inspector_label.text().strip()
            if action.action_type == "key":
                action.key = self.ik_key.text().strip()
                action.duration = float(self.ik_dur.text())
                action.hold_mode = self.ik_hold.isChecked()
                action.repeat_count = max(1, int(self.ik_repeat.text() or 1))
                action.label = inspector_label_text
            elif action.action_type == "pause":
                action.duration = float(self.ip_dur.text())
                action.label = inspector_label_text
            elif action.action_type == "click":
                action.click_x = int(self.ic_x.text())
                action.click_y = int(self.ic_y.text())
                action.click_button = self.ic_btn.currentText()
                action.click_rand_radius = int(self.ic_rand.text() or 0)
                action.repeat_count = max(1, int(self.ic_repeat.text() or 1))
                action.label = inspector_label_text
            elif action.action_type == "image":
                action.label = inspector_label_text
                action.similarity = float(self.ii_sim.text())
                action.wait_timeout = float(self.ii_wait.text() or 0) / 1000.0
                if hasattr(self, "ii_retry_count"):
                    action.retry_attempts = int(self.ii_retry_count.value())
                    action.retry_delay = float(self.ii_retry_delay.text() or 0) / 1000.0
                    action.on_fail_action = self.ii_fail_mode.currentText().strip().lower().replace(" ", "_")
                    action.on_fail_target = int(self.ii_fail_target.currentData() if self.ii_fail_target.currentData() is not None else -1)
            elif action.action_type == "group":
                name = self.ig_name.text().strip() or "Group"
                action.group_name = name
                action.label = inspector_label_text or name
                action.group_collapsed = self.ig_collapsed.isChecked()
                if hasattr(self, "ig_recovery"):
                    action.group_role = "recovery" if self.ig_recovery.isChecked() else "normal"
            elif action.action_type == "loop":
                action.label = inspector_label_text or f"Loop x{self.il_count.value()}"
                action.loop_count = int(self.il_count.value())
                action.repeat_count = int(self.il_count.value())
                action.loop_target = int(self.il_target.currentData() if self.il_target.currentData() is not None else -1)
            elif action.action_type == "condition":
                action.label = inspector_label_text
                action.condition_type = self.ico_type.currentText()
                action.condition_jump_true = int(self.ico_true.currentData() if self.ico_true.currentData() is not None else -1)
                action.condition_jump_false = int(self.ico_false.currentData() if self.ico_false.currentData() is not None else -1)
                if hasattr(self, "ico_retry_count"):
                    action.retry_attempts = int(self.ico_retry_count.value())
                    action.retry_delay = float(self.ico_retry_delay.text() or 0)
                    action.on_fail_action = self.ico_fail_mode.currentText()
                    action.on_fail_target = int(self.ico_fail_target.currentData() if self.ico_fail_target.currentData() is not None else -1)
            if autosave:
                idx = self.action_model.index(self.active_index, 0)
                self.action_model.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DisplayRole, self.action_model.ActionRole])
                self.engine.actions = self.action_model.actions()
                self._invalidate_seq_dur()
                self.update_statistics()
                self.save_session()
                return
            self.refresh()
            self.update_statistics()
            self.save_session()
            self.status("Applied changes")
        except ValueError as e:
            if not autosave:
                QMessageBox.critical(self, "Invalid Input", f"Invalid value: {e}")

    def _cancel_inspector(self):
        if self.active_index >= 0:
            self.select(self.active_index)
            self.status("Changes cancelled")

    def _open_active_dialog(self, index=None):
        idx = index if index is not None else self.active_index
        if idx < 0 or idx >= self.action_model.rowCount():
            return
        action = self.action_model.get(idx)
        if action.action_type == "image":
            self._open_image_editor(idx)
        elif action.action_type == "click":
            self._open_click_editor(idx)
        elif action.action_type == "pause":
            self._open_pause_editor(idx)
        elif action.action_type == "condition":
            self._open_condition_editor(idx)
        elif action.action_type == "loop":
            self._open_loop_editor(idx)
        elif action.action_type == "group":
            self._open_group_editor(idx)
        else:
            self._open_key_editor(idx)

    def _duplicate_inspector(self):
        self.duplicate_action(self.active_index)

    # ═══════════════════════════════════════════════════════
    #  ACTION MANAGEMENT
    # ═══════════════════════════════════════════════════════

    def delete_action(self, index):
        rows = self._selected_rows(index)
        if not rows:
            return
        self.history.push(self.action_model.actions(), self._timeline_history_state())
        actions = self.action_model.actions()
        # Deleting only a group header keeps the actions and simply ungroups them.
        header_only = len(rows) == 1 and getattr(actions[rows[0]], "action_type", "") == "group"
        if header_only:
            header = actions[rows[0]]
            gid = getattr(header, "group_id", "")
            self.action_model.remove_action(rows[0])
            for action in self.action_model.actions():
                if getattr(action, "group_id", "") == gid:
                    action.group_id = ""
                    action.group_color = ""
                    action.block_depth = 0
            msg = "Removed group header and kept its actions"
        else:
            for idx in sorted(rows, reverse=True):
                if 0 <= idx < self.action_model.rowCount():
                    self.action_model.remove_action(idx)
            msg = f"Deleted {len(rows)} row(s)"
        self.active_index = -1
        self.timeline.selected_indices.clear()
        self.refresh()
        self.update_statistics()
        self.save_session()
        self.status(msg)

    def duplicate_action(self, index):
        rows = self._selected_rows(index)
        if not rows:
            self.status("No action selected to duplicate")
            return
        self.history.push(self.action_model.actions(), self._timeline_history_state())
        actions = self.action_model.actions()
        insert_at = rows[-1] + 1
        copies = [deepcopy(actions[r]) for r in rows if 0 <= r < len(actions)]
        # If the copied block contains a group header, give the duplicate a new group id
        # and remap copied member rows to that id so import/export remains clean.
        copied_group_ids = {}
        for c in copies:
            if getattr(c, "action_type", "") == "group":
                old = getattr(c, "group_id", "")
                new = self._new_group_id()
                copied_group_ids[old] = new
                c.group_id = new
                c.group_color = self._group_color_for_number(len(self._group_headers()) + len(copied_group_ids))
        for c in copies:
            gid = getattr(c, "group_id", "")
            if gid in copied_group_ids and getattr(c, "action_type", "") != "group":
                c.group_id = copied_group_ids[gid]
        for offset, action in enumerate(copies):
            self.action_model.insert_action(insert_at + offset, action)
        self.active_index = insert_at
        self.timeline.selected_indices = set(range(insert_at, insert_at + len(copies)))
        self.refresh()
        self.timeline.set_active(insert_at)
        self.update_statistics()
        self.save_session()
        self.status(f"Duplicated {len(copies)} row(s)")

    def toggle_action_enabled(self, index):
        rows = self._selected_rows(index)
        if not rows:
            return
        self.history.push(self.action_model.actions(), self._timeline_history_state())
        actions = self.action_model.actions()
        new_state = not all(bool(getattr(actions[r], "enabled", True)) for r in rows if 0 <= r < len(actions))
        for r in rows:
            if 0 <= r < len(actions):
                actions[r].enabled = new_state
        self.refresh()
        self.update_statistics()
        self.save_session()
        self.status("Enabled selected row(s)" if new_state else "Disabled selected row(s)")

    def move_action(self, index, direction):
        if self.engine.running or self.timeline.playing_index >= 0:
            self.status("Stop playback before reordering actions")
            return
        if index < 0 or index >= self.action_model.rowCount():
            return
        # Group headers move with their contiguous visible members.
        if getattr(self.action_model.get(index), "action_type", "") == "group":
            block = self._contiguous_group_block(index)
            if not block:
                return
            target = index - 1 if direction < 0 else block[-1] + 1
            self.move_action_to(index, target)
            return
        new_index = index + direction
        if new_index < 0 or new_index >= self.action_model.rowCount():
            return
        scroll_position = self.timeline.scroll_position()
        self.history.push(self.action_model.actions(), self._timeline_history_state())
        self.action_model.move_action(index, new_index)
        self.timeline.remap_after_move(index, new_index)
        self._assign_group_from_position(new_index)
        self.active_index = new_index
        self.refresh()
        self.timeline.set_active(new_index)
        self.timeline.restore_scroll_position(scroll_position)
        self.timeline.flash_drop(new_index)
        self.save_session()
        self.status("Moved action")

    def move_action_into_group(self, index, group_row):
        """Move a dragged action row into the target group/folder.

        Dropping onto the centre of a group header appends the row to that
        group, assigns the member badge/colour, and keeps undo/redo + row
        references stable. Group headers themselves still move as whole groups
        through the normal drag reorder path.
        """
        if self.engine.running or self.timeline.playing_index >= 0:
            self.status("Stop playback before moving actions into groups")
            return
        if index < 0 or index >= self.action_model.rowCount():
            return
        if group_row < 0 or group_row >= self.action_model.rowCount():
            return
        source_action = self.action_model.get(index)
        if getattr(source_action, "action_type", "") == "group":
            self.status("Drag the group header to move the whole folder")
            return
        group_meta = self._group_header_for_row(group_row)
        if not group_meta or getattr(group_meta["action"], "action_type", "") != "group":
            return

        actions_before = list(self.action_model.actions())
        header_action = group_meta["action"]
        if source_action is header_action:
            return

        scroll_position = self.timeline.scroll_position()
        self.history.push(self.action_model.actions(), self._timeline_history_state())

        # Remove the source first, then locate the group header by object identity
        # so drops from above the group and from inside the same group are stable.
        actions = list(actions_before)
        moved = actions.pop(index)
        try:
            header_index = next(i for i, a in enumerate(actions) if a is header_action)
        except StopIteration:
            self.status("Target group no longer exists")
            return

        target_insert = header_index + 1
        gid = group_meta["gid"]
        while target_insert < len(actions):
            candidate = actions[target_insert]
            if getattr(candidate, "action_type", "") == "group":
                break
            if getattr(candidate, "group_id", "") != gid:
                break
            target_insert += 1

        moved.group_id = gid
        moved.group_color = group_meta["color"]
        moved.block_depth = max(1, int(getattr(moved, "block_depth", 0) or 0))
        actions.insert(target_insert, moved)

        # Preserve row-based loop/condition/image references after the structural
        # move, including references to the moved action itself.
        new_index_by_id = {id(a): i for i, a in enumerate(actions)}
        row_map = {old_i: new_index_by_id.get(id(a), old_i) for old_i, a in enumerate(actions_before)}
        self.action_model.set_actions(actions)
        self._apply_row_reference_map(row_map)
        self.timeline.remap_after_move(index, target_insert)
        self._normalize_groups()

        collapsed = bool(getattr(header_action, "group_collapsed", False))
        self.active_index = header_index if collapsed else target_insert
        self.refresh()
        self.timeline.set_active(self.active_index)
        self.timeline.restore_scroll_position(scroll_position)
        self.timeline.flash_drop(header_index if collapsed else target_insert)
        self.update_statistics(immediate=True)
        self.save_session()
        self.status(f"Moved row {index + 1} into {group_meta['badge']} {group_meta['name']}")

    def _select_moved_rows(self, rows, active=None):
        rows = sorted({int(r) for r in (rows or []) if 0 <= int(r) < self.action_model.rowCount()})
        if hasattr(self.timeline, "set_selected_rows"):
            self.timeline.set_selected_rows(rows, active=active if active is not None else (rows[0] if rows else None))
        elif rows:
            self.timeline.selected_indices = set(rows)
            self.timeline.set_active(active if active is not None else rows[0])
        self.active_index = active if active is not None else (rows[0] if rows else -1)

    def move_actions_to(self, rows, target_index):
        """Move multiple selected rows as one ordered block.

        Group headers are expanded to include their contiguous children before
        moving, so a selected folder behaves like a single safe timeline block.
        Normal action-only selections still move only the selected action rows.
        """
        if self.engine.running or self.timeline.playing_index >= 0:
            self.status("Stop playback before reordering actions")
            return
        actions_before = list(self.action_model.actions())
        count = len(actions_before)
        rows = self._expand_rows_for_group_blocks(rows)
        rows = sorted({int(r) for r in rows if 0 <= int(r) < count})
        if not rows:
            return
        if len(rows) == 1:
            return self.move_action_to(rows[0], target_index)

        target_index = max(0, min(int(target_index), count))
        row_set = set(rows)
        if target_index in row_set or target_index == max(rows) + 1:
            self.status("Selection is already there")
            self._select_moved_rows(rows, active=rows[0])
            return

        scroll_position = self.timeline.scroll_position()
        self.history.push(self.action_model.actions(), self._timeline_history_state())

        moved = [actions_before[r] for r in rows]
        remaining = [a for i, a in enumerate(actions_before) if i not in row_set]
        removed_before_target = sum(1 for r in rows if r < target_index)
        insert_at = max(0, min(target_index - removed_before_target, len(remaining)))

        new_actions = remaining[:insert_at] + moved + remaining[insert_at:]
        if [id(a) for a in new_actions] == [id(a) for a in actions_before]:
            self.status("Selection is already there")
            self._select_moved_rows(rows, active=rows[0])
            return

        new_index_by_id = {id(a): i for i, a in enumerate(new_actions)}
        row_map = {old_i: new_index_by_id.get(id(a), old_i) for old_i, a in enumerate(actions_before)}

        self.action_model.set_actions(new_actions)
        self._apply_row_reference_map(row_map)

        # Standalone moved actions should adopt the destination group context.
        # Children of a moved selected group block keep their original group id.
        moved_group_ids = {
            getattr(a, "group_id", "") for a in moved
            if getattr(a, "action_type", "") == "group" and getattr(a, "group_id", "")
        }
        for row in range(insert_at, insert_at + len(moved)):
            action = self.action_model.get(row)
            if getattr(action, "action_type", "") == "group":
                continue
            if getattr(action, "group_id", "") in moved_group_ids:
                continue
            self._assign_group_from_position(row)
        self._normalize_groups()

        new_rows = list(range(insert_at, insert_at + len(moved)))
        self.active_index = new_rows[0] if new_rows else -1
        self.refresh()
        self._select_moved_rows(new_rows, active=self.active_index)
        self.timeline.restore_scroll_position(scroll_position)
        if new_rows:
            self.timeline.flash_drop(new_rows[0])
        self.update_statistics(immediate=True)
        self.save_session()
        self.status(f"Moved {len(moved)} actions")

    def move_actions_into_group(self, rows, group_row):
        """Move multiple selected non-group rows into the target group."""
        if self.engine.running or self.timeline.playing_index >= 0:
            self.status("Stop playback before moving actions into groups")
            return
        actions_before = list(self.action_model.actions())
        count = len(actions_before)
        rows = sorted({int(r) for r in (rows or []) if 0 <= int(r) < count})
        if not rows:
            return
        if len(rows) == 1:
            return self.move_action_into_group(rows[0], group_row)
        if group_row < 0 or group_row >= count:
            return

        group_meta = self._group_header_for_row(group_row)
        if not group_meta or getattr(group_meta["action"], "action_type", "") != "group":
            return
        header_action = group_meta["action"]

        movable_rows = [
            r for r in rows
            if actions_before[r] is not header_action and getattr(actions_before[r], "action_type", "") != "group"
        ]
        if not movable_rows:
            self.status("Multi-drag into group only moves action rows")
            return

        row_set = set(movable_rows)
        scroll_position = self.timeline.scroll_position()
        self.history.push(self.action_model.actions(), self._timeline_history_state())

        moved = [actions_before[r] for r in movable_rows]
        remaining = [a for i, a in enumerate(actions_before) if i not in row_set]
        try:
            header_index = next(i for i, a in enumerate(remaining) if a is header_action)
        except StopIteration:
            self.status("Target group no longer exists")
            return

        target_insert = header_index + 1
        gid = group_meta["gid"]
        while target_insert < len(remaining):
            candidate = remaining[target_insert]
            if getattr(candidate, "action_type", "") == "group":
                break
            if getattr(candidate, "group_id", "") != gid:
                break
            target_insert += 1

        for action in moved:
            action.group_id = gid
            action.group_color = group_meta["color"]
            action.block_depth = max(1, int(getattr(action, "block_depth", 0) or 0))

        new_actions = remaining[:target_insert] + moved + remaining[target_insert:]
        new_index_by_id = {id(a): i for i, a in enumerate(new_actions)}
        row_map = {old_i: new_index_by_id.get(id(a), old_i) for old_i, a in enumerate(actions_before)}

        self.action_model.set_actions(new_actions)
        self._apply_row_reference_map(row_map)
        self._normalize_groups()

        new_rows = list(range(target_insert, target_insert + len(moved)))
        collapsed = bool(getattr(header_action, "group_collapsed", False))
        active = header_index if collapsed else (new_rows[0] if new_rows else header_index)
        self.active_index = active
        self.refresh()
        self._select_moved_rows([header_index] if collapsed else new_rows, active=active)
        self.timeline.restore_scroll_position(scroll_position)
        self.timeline.flash_drop(active)
        self.update_statistics(immediate=True)
        self.save_session()
        self.status(f"Moved {len(moved)} actions into {group_meta['badge']} {group_meta['name']}")

    def move_action_to(self, index, target_index):
        if self.engine.running or self.timeline.playing_index >= 0:
            self.status("Stop playback before reordering actions")
            return
        if index < 0 or index >= self.action_model.rowCount():
            return
        if target_index < 0:
            target_index = 0
        target_index = min(target_index, max(0, self.action_model.rowCount() - 1))
        scroll_position = self.timeline.scroll_position()
        self.history.push(self.action_model.actions(), self._timeline_history_state())
        actions = self.action_model.actions()

        if getattr(actions[index], "action_type", "") == "group":
            block_rows = self._contiguous_group_block(index)
            if target_index in block_rows:
                self.status("Group is already there")
                return
            block = [actions[r] for r in block_rows]
            remaining = [a for i, a in enumerate(actions) if i not in set(block_rows)]
            removed_before_target = sum(1 for r in block_rows if r < target_index)
            insert_at = max(0, min(target_index - removed_before_target, len(remaining)))
            new_actions = remaining[:insert_at] + block + remaining[insert_at:]
            self.action_model.set_actions(new_actions)
            new_index = insert_at
            self.active_index = new_index
            self.timeline.selected_indices = set(range(new_index, new_index + len(block)))
            msg = "Moved group"
        else:
            self.action_model.move_action(index, target_index)
            self.timeline.remap_after_move(index, target_index)
            self._assign_group_from_position(target_index)
            self.active_index = target_index
            new_index = target_index
            msg = "Moved action"

        self.refresh()
        self.timeline.set_active(new_index)
        self.timeline.restore_scroll_position(scroll_position)
        self.timeline.flash_drop(new_index)
        self.update_statistics(immediate=True)
        self.save_session()
        self.status(msg)

    def copy_action(self):
        if self.active_index < 0 or self.active_index >= self.action_model.rowCount():
            self.status("No action selected to copy")
            return
        self.clipboard = deepcopy(self.action_model.get(self.active_index))
        self.status("Copied action")

    def paste_action(self):
        if self.clipboard is None:
            self.status("Clipboard empty")
            return
        self.history.push(self.action_model.actions())
        new_action = deepcopy(self.clipboard)
        if 0 <= self.active_index < self.action_model.rowCount():
            insert_at = self.active_index + 1
        else:
            insert_at = self.action_model.rowCount()
        self.action_model.insert_action(insert_at, new_action)
        self.active_index = insert_at
        self.refresh()
        self.update_statistics()
        self.save_session()
        self.status("Pasted action")

    # ═══════════════════════════════════════════════════════
    #  RUN VALIDATION / PRE-FLIGHT CHECK
    # ═══════════════════════════════════════════════════════

    def _known_key_names(self):
        """Return a conservative key-name set for pre-flight validation.

        This intentionally mirrors the Windows input backend without importing
        it here. Importing the backend can fail on non-Windows development
        machines because it touches ctypes.windll during construction.
        """
        names = {
            "enter", "return", "esc", "escape", "space", "backspace", "tab",
            "delete", "del", "insert", "ins", "home", "end", "pageup", "prior",
            "pagedown", "next", "left", "up", "right", "down", "shift", "ctrl",
            "control", "alt", "menu", "capslock", "numlock", "scrolllock",
            "print", "printscreen", "prtsc", "pause", "win", "command",
            "multiply", "add", "separator", "subtract", "decimal", "divide",
            "[scroll_up]", "[scroll_down]",
        }
        names.update({f"f{i}" for i in range(1, 25)})
        names.update({f"num{i}" for i in range(10)})
        names.update({str(i) for i in range(10)})
        names.update({chr(c) for c in range(ord("a"), ord("z") + 1)})
        return names

    def _validate_key_name(self, key: str):
        key = (key or "").strip().lower()
        if not key:
            return False, "empty key"
        known = self._known_key_names()
        if key in known:
            return True, ""
        if len(key) == 1 and key.isprintable():
            return True, ""
        if "+" in key:
            parts = [p.strip().lower() for p in key.split("+") if p.strip()]
            if not parts:
                return False, "empty combo"
            bad = [p for p in parts if not (p in known or (len(p) == 1 and p.isprintable()))]
            if bad:
                return False, "unknown combo key(s): " + ", ".join(bad)
            return True, ""
        return False, f"unknown key '{key}'"

    def _format_preflight_report(self, errors, warnings):
        lines = []
        if errors:
            lines.append(f"Errors ({len(errors)}):")
            lines.extend(f"  • {x}" for x in errors[:20])
            if len(errors) > 20:
                lines.append(f"  • …and {len(errors) - 20} more")
        if warnings:
            if lines:
                lines.append("")
            lines.append(f"Warnings ({len(warnings)}):")
            lines.extend(f"  • {x}" for x in warnings[:20])
            if len(warnings) > 20:
                lines.append(f"  • …and {len(warnings) - 20} more")
        if not lines:
            lines.append("Ready to run — no validation issues found.")
        return "\n".join(lines)

    def run_preflight_check(self, show_success=True, allow_warning_prompt=True, auto_fix=True):
        """Validate the visible timeline before playback.

        Returns True when playback may continue. Errors block playback;
        warnings are shown but can be continued through.
        """
        actions = self.action_model.actions()
        errors = []
        warnings = []
        total = len(actions)
        autofix_started = False

        def begin_autofix():
            nonlocal autofix_started
            if not autofix_started:
                self.history.push(self.action_model.actions(), self._timeline_history_state())
                autofix_started = True

        if total <= 0:
            errors.append("Timeline is empty.")
        elif not any(bool(getattr(a, "enabled", True)) and getattr(a, "action_type", "key") not in {"group", "loop"} for a in actions):
            errors.append("Timeline has no enabled runnable actions. Group/folder and loop controller rows are skipped during playback.")

        for idx, action in enumerate(actions, start=1):
            prefix = f"Row {idx}"
            try:
                duration = float(getattr(action, "duration", 0.0) or 0.0)
            except (TypeError, ValueError):
                duration = -1.0
            if duration < 0:
                errors.append(f"{prefix}: duration cannot be negative.")
            elif duration > 3600:
                warnings.append(f"{prefix}: duration is over 1 hour; confirm this is intentional.")

            try:
                repeat = int(getattr(action, "repeat_count", 1) or 1)
            except (TypeError, ValueError):
                repeat = 0
            if repeat < 1:
                errors.append(f"{prefix}: repeat count must be at least 1.")
            elif repeat > 1000:
                warnings.append(f"{prefix}: repeat count is very high ({repeat}).")

            kind = getattr(action, "action_type", "key") or "key"

            if not bool(getattr(action, "enabled", True)):
                warnings.append(f"{prefix}: action is disabled and will be skipped.")
                continue

            if getattr(action, "action_type", "") == "group":
                if not (getattr(action, "group_name", "") or getattr(action, "label", "")):
                    warnings.append(f"{prefix}: group has no name.")
                continue

            if getattr(action, "action_type", "") == "loop":
                target = int(getattr(action, "loop_target", -1) or -1)
                count = int(getattr(action, "loop_count", getattr(action, "repeat_count", 1)) or 1)
                if count < 2:
                    if auto_fix:
                        begin_autofix()
                        action.loop_count = 2
                        action.repeat_count = 2
                        warnings.append(f"{prefix}: loop count was auto-fixed to x2.")
                        count = 2
                    else:
                        warnings.append(f"{prefix}: loop count can be auto-fixed to x2.")
                if not (0 <= target < idx - 1):
                    suggested = self._suggest_loop_target(idx - 1)
                    if 0 <= suggested < idx - 1:
                        target_action = actions[suggested]
                        if auto_fix:
                            begin_autofix()
                            action.loop_target = suggested
                            if getattr(target_action, "action_type", "") == "group":
                                group_name = getattr(target_action, "group_name", "") or getattr(target_action, "label", "") or f"row {suggested + 1}"
                                warnings.append(f"{prefix}: loop target auto-fixed to group '{group_name}' on row {suggested + 1}.")
                            else:
                                warnings.append(f"{prefix}: loop target auto-fixed to row {suggested + 1}.")
                        else:
                            warnings.append(f"{prefix}: loop target can be auto-fixed to {self._row_target_text(suggested)}.")
                    else:
                        errors.append(f"{prefix}: loop target must be an earlier row or group header.")
                continue

            if action.is_pause():
                if duration <= 0:
                    warnings.append(f"{prefix}: delay duration is 0 seconds.")
                continue

            if action.is_click():
                button = (getattr(action, "click_button", "left") or "left").lower()
                mode = (getattr(action, "click_coord_mode", "absolute") or "absolute").lower()
                if button not in {"left", "right", "middle", "double"}:
                    errors.append(f"{prefix}: unsupported click button '{button}'.")
                if mode not in {"absolute", "foreground", "offset", "current"}:
                    errors.append(f"{prefix}: unsupported click coordinate mode '{mode}'.")
                if int(getattr(action, "click_rand_radius", 0) or 0) < 0:
                    errors.append(f"{prefix}: click random radius cannot be negative.")
                sw, sh = self._current_screen_size()
                if mode == "absolute" and sw and sh:
                    x = int(getattr(action, "click_x", 0) or 0)
                    y = int(getattr(action, "click_y", 0) or 0)
                    if x < 0 or y < 0 or x >= sw or y >= sh:
                        warnings.append(f"{prefix}: click coordinate {x},{y} is outside the current primary screen ({sw}×{sh}).")
                    saved_w = int(getattr(action, "screen_width", 0) or 0)
                    saved_h = int(getattr(action, "screen_height", 0) or 0)
                    if saved_w and saved_h and (saved_w != sw or saved_h != sh):
                        warnings.append(f"{prefix}: created on {saved_w}×{saved_h}, current screen is {sw}×{sh}; use screen adaptation if needed.")
                continue

            if action.is_image():
                if not (getattr(action, "image_data", "") or getattr(action, "extra_images", "")):
                    errors.append(f"{prefix}: image action has no template data.")
                try:
                    sim = float(getattr(action, "similarity", 0.95) or 0.95)
                except (TypeError, ValueError):
                    sim = -1.0
                if not (0.0 < sim <= 1.0):
                    errors.append(f"{prefix}: image similarity must be between 0 and 1.")
                elif sim < 0.50:
                    warnings.append(f"{prefix}: image similarity is low ({sim:.2f}).")
                try:
                    wait = float(getattr(action, "wait_timeout", 0.0) or 0.0)
                except (TypeError, ValueError):
                    wait = -1.0
                if wait < 0:
                    errors.append(f"{prefix}: image wait timeout cannot be negative.")
                if getattr(action, "on_found_action", "continue") == "press_key":
                    ok, reason = self._validate_key_name(getattr(action, "on_found_key", ""))
                    if not ok:
                        errors.append(f"{prefix}: image on-found key is invalid: {reason}.")
                for attr, label in (("jump_to_on_found", "found jump"), ("jump_to_on_not_found", "not-found jump")):
                    target = int(getattr(action, attr, -1) or -1)
                    if target >= total:
                        errors.append(f"{prefix}: {label} target {target + 1} is outside the timeline.")
                saved_w = int(getattr(action, "screen_width", 0) or 0)
                saved_h = int(getattr(action, "screen_height", 0) or 0)
                sw, sh = self._current_screen_size()
                if saved_w and saved_h and sw and sh and (saved_w != sw or saved_h != sh):
                    warnings.append(f"{prefix}: image template was captured on {saved_w}×{saved_h}, current screen is {sw}×{sh}.")
                continue

            if action.is_condition():
                true_target = int(getattr(action, "condition_jump_true", -1) or -1)
                false_target = int(getattr(action, "condition_jump_false", -1) or -1)
                if true_target >= total:
                    errors.append(f"{prefix}: true jump target {true_target + 1} is outside the timeline.")
                if false_target >= total:
                    errors.append(f"{prefix}: false jump target {false_target + 1} is outside the timeline.")
                ctype = getattr(action, "condition_type", "none") or "none"
                if ctype == "none":
                    warnings.append(f"{prefix}: condition has no condition type selected.")
                continue

            if kind == "key":
                ok, reason = self._validate_key_name(getattr(action, "key", ""))
                if not ok:
                    errors.append(f"{prefix}: {reason}.")
            else:
                warnings.append(f"{prefix}: unknown action type '{kind}' — engine may skip or treat it as a key.")

        if autofix_started:
            self.refresh()
            self.save_session()

        if self.sim_check.isChecked():
            warnings.append("Simulation mode is enabled; actions will animate/log but not deploy to Windows.")
        if self.focus_check.isChecked() and not getattr(self.engine, "_focus_hwnd", None):
            warnings.append("Focus lock is enabled but no target window is currently captured.")

        self._last_preflight = {"errors": errors, "warnings": warnings}
        self._diag(f"[CHECK] Pre-flight complete: {len(errors)} error(s), {len(warnings)} warning(s)")
        for item in errors[:12]:
            self._diag(f"[CHECK][ERROR] {item}")
        for item in warnings[:12]:
            self._diag(f"[CHECK][WARN] {item}")

        if errors:
            QMessageBox.critical(self, "MacroForge pre-flight check", self._format_preflight_report(errors, warnings))
            self.status(f"Pre-flight blocked start: {len(errors)} error(s)")
            return False

        if warnings and allow_warning_prompt:
            reply = QMessageBox.warning(
                self,
                "MacroForge pre-flight warnings",
                self._format_preflight_report(errors, warnings) + "\n\nContinue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self.status("Start cancelled by pre-flight warnings")
                return False

        if show_success:
            QMessageBox.information(self, "MacroForge pre-flight check", self._format_preflight_report(errors, warnings))
        self.status("Pre-flight check passed" if not warnings else f"Pre-flight passed with {len(warnings)} warning(s)")
        return True


    def apply_preflight_autofixes(self):
        """Apply safe pre-flight repairs without starting playback."""
        total = self.action_model.rowCount()
        if total <= 0:
            self.status("No pre-flight fixes available")
            return
        self.history.push(self.action_model.actions(), self._timeline_history_state())
        fixed = 0
        if self._normalize_groups():
            fixed += 1
        for idx, action in enumerate(self.action_model.actions()):
            kind = getattr(action, "action_type", "key") or "key"
            if kind == "group":
                if not (getattr(action, "group_name", "") or getattr(action, "label", "")):
                    action.group_name = f"Group {idx + 1}"
                    action.label = action.group_name
                    fixed += 1
            elif kind == "loop":
                count = int(getattr(action, "loop_count", getattr(action, "repeat_count", 1)) or 1)
                if count < 2:
                    action.loop_count = 2
                    action.repeat_count = 2
                    fixed += 1
                target = int(getattr(action, "loop_target", -1) or -1)
                if not (0 <= target < idx):
                    suggested = self._suggest_loop_target(idx)
                    if 0 <= suggested < idx:
                        action.loop_target = suggested
                        fixed += 1
            elif kind == "condition":
                for attr in ("condition_jump_true", "condition_jump_false"):
                    target = int(getattr(action, attr, -1) or -1)
                    if target >= total:
                        setattr(action, attr, -1)
                        fixed += 1
        self.refresh()
        self.update_statistics(immediate=True)
        self.save_session()
        self.status(f"Applied {fixed} pre-flight auto-fix{'es' if fixed != 1 else ''}")

    def _current_screen_size(self):
        try:
            screen = QApplication.primaryScreen()
            geo = screen.geometry() if screen is not None else None
            if geo is not None:
                return int(geo.width()), int(geo.height())
        except Exception:
            pass
        return 0, 0

    def _stamp_action_environment(self, action):
        """Attach source screen metadata for coordinate-sensitive actions."""
        if action is None:
            return action
        try:
            if getattr(action, "action_type", "key") in {"click", "image"}:
                sw, sh = self._current_screen_size()
                if sw and sh:
                    action.screen_width = sw
                    action.screen_height = sh
                    if not getattr(action, "anchor_mode", ""):
                        action.anchor_mode = "absolute"
        except Exception:
            pass
        return action

    def open_preflight_report(self):
        """Show the macro health checker without asking to continue playback."""
        self.run_preflight_check(show_success=False, allow_warning_prompt=False, auto_fix=False)
        report = self._format_preflight_report(
            self._last_preflight.get("errors", []),
            self._last_preflight.get("warnings", []),
        )
        C = COLORS
        dlg = QDialog(self)
        dlg.setWindowTitle("Macro Health / Pre-flight")
        dlg.resize(620, 460)
        dlg.setStyleSheet(
            f"QDialog {{ background-color: {C['bg']}; color: {C['text']}; }}"
            f"QPlainTextEdit {{ background-color: {C['bg_tertiary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 9px; padding: 10px; font-family: Consolas, monospace; font-size: 11px; }}"
            f"QPushButton {{ background-color: {C['bg_card']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 8px; padding: 7px 12px; font-weight: 800; }}"
            f"QPushButton:hover {{ border-color: {C['accent']}; color: {C['accent']}; }}"
        )
        lo = QVBoxLayout(dlg)
        lo.setContentsMargins(14, 14, 14, 14)
        title = QLabel("Macro Health / Pre-flight")
        title.setStyleSheet(f"color: {C['text']}; font-size: 18px; font-weight: 950;")
        lo.addWidget(title)
        summary = QLabel(f"{self.action_model.rowCount()} rows · {len(self._last_preflight.get('errors', []))} errors · {len(self._last_preflight.get('warnings', []))} warnings")
        summary.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px;")
        lo.addWidget(summary)
        edit = QPlainTextEdit(report)
        edit.setReadOnly(True)
        lo.addWidget(edit, 1)
        row = QHBoxLayout()
        row.addStretch()
        fix_btn = QPushButton("Apply auto-fixes")
        fix_btn.clicked.connect(lambda: (self.apply_preflight_autofixes(), dlg.accept(), self.open_preflight_report()))
        row.addWidget(fix_btn)
        scale_btn = QPushButton("Scale coordinates to screen")
        scale_btn.clicked.connect(lambda: (self.scale_actions_to_current_screen(), dlg.accept()))
        row.addWidget(scale_btn)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        row.addWidget(close_btn)
        lo.addLayout(row)
        dlg.exec()

    def open_macro_editor(self):
        from ui.macro_editor import MacroEditorDialog
        dlg = MacroEditorDialog(self)
        dlg.exec()
        self.refresh()

    def open_variables_dialog(self):
        """Edit macro variables used by condition rules and future variable-aware fields."""
        C = COLORS
        dlg = QDialog(self)
        dlg.setWindowTitle("Macro Variables")
        dlg.resize(460, 440)
        dlg.setStyleSheet(
            f"QDialog {{ background-color: {C['bg']}; color: {C['text']}; }}"
            f"QPlainTextEdit {{ background-color: {C['bg_tertiary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 9px; padding: 9px; font-family: Consolas, monospace; font-size: 12px; }}"
            f"QPushButton {{ background-color: {C['bg_card']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 8px; padding: 7px 12px; font-weight: 700; }}"
            f"QPushButton:hover {{ border-color: {C['accent']}; color: {C['accent']}; }}"
        )
        lo = QVBoxLayout(dlg)
        lo.setContentsMargins(14, 14, 14, 14)
        title = QLabel("Macro Variables")
        title.setStyleSheet(f"color: {C['text']}; font-size: 18px; font-weight: 900;")
        lo.addWidget(title)
        hint = QLabel("One variable per line. Example: loop_count=5 or wait_long=8.0. Condition rows can compare these values.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px;")
        lo.addWidget(hint)
        edit = QPlainTextEdit()
        edit.setPlainText("\n".join(f"{k}={v}" for k, v in sorted((getattr(self, "macro_variables", {}) or {}).items())))
        lo.addWidget(edit, 1)
        row = QHBoxLayout(); row.addStretch()
        save_btn = QPushButton("Save variables")
        cancel_btn = QPushButton("Cancel")
        def save_vars():
            variables = {}
            for raw in edit.toPlainText().splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    QMessageBox.warning(dlg, "Invalid variable", f"Variable line needs name=value:\n{line}")
                    return
                name, value = line.split("=", 1)
                name = name.strip()
                if not name.replace("_", "").isalnum() or not name:
                    QMessageBox.warning(dlg, "Invalid variable", f"Invalid variable name: {name}")
                    return
                variables[name] = value.strip()
            self.macro_variables = variables
            self.save_session()
            self.status(f"Saved {len(variables)} macro variable(s)")
            dlg.accept()
        save_btn.clicked.connect(save_vars)
        cancel_btn.clicked.connect(dlg.reject)
        row.addWidget(save_btn); row.addWidget(cancel_btn); lo.addLayout(row)
        dlg.exec()

    def open_profile_library(self):
        """Compact profile/macro library so the main menu does not duplicate profile actions."""
        C = COLORS
        dlg = QDialog(self)
        dlg.setWindowTitle("Profile / Macro Library")
        dlg.resize(620, 480)
        dlg.setStyleSheet(
            f"QDialog {{ background-color: {C['bg']}; color: {C['text']}; }}"
            f"QListWidget {{ background-color: {C['bg_tertiary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 10px; padding: 6px; }}"
            f"QPushButton {{ background-color: {C['bg_card']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 8px; padding: 7px 11px; font-weight: 700; }}"
            f"QPushButton:hover {{ border-color: {C['accent']}; color: {C['accent']}; }}"
        )
        lo = QVBoxLayout(dlg); lo.setContentsMargins(14, 14, 14, 14); lo.setSpacing(9)
        title = QLabel("Profile / Macro Library")
        title.setStyleSheet(f"color: {C['text']}; font-size: 18px; font-weight: 900;")
        lo.addWidget(title)
        hint = QLabel("Manage, validate, repair, import, and export profiles here. Macro import/export lives in the macro editor to keep the top menu clean.")
        hint.setWordWrap(True); hint.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px;")
        lo.addWidget(hint)
        items = QListWidget(); lo.addWidget(items, 1)

        def profile_summary(name):
            ok, data, issues = self.session_manager.validate_profile(name)
            actions = data.get("actions", []) or []
            ts = data.get("timestamp", "never")
            health = "OK" if ok else f"Needs repair: {', '.join(issues[:2])}"
            return f"{'✓ ' if name == self.session_manager.active else '  '}{name}  ·  {len(actions)} rows  ·  {health}  ·  last edited {ts[:19]}"

        def reload_items():
            items.clear()
            for name in self.session_manager.list_profiles():
                items.addItem(profile_summary(name))

        def selected_name():
            row = items.currentRow()
            profiles = self.session_manager.list_profiles()
            return profiles[row] if 0 <= row < len(profiles) else self.session_manager.active

        def open_selected():
            self._switch_profile(selected_name()); reload_items()

        def new_profile():
            self._new_profile_dialog(); reload_items()

        def duplicate_profile():
            src = selected_name()
            name, ok = QInputDialog.getText(dlg, "Duplicate Profile", "New profile name:", text=f"{src} copy")
            if not ok or not name.strip():
                return
            data = self.session_manager.load_profile(src) or {"actions": [], "settings": {}}
            self.session_manager.save_profile([Action.from_dict(a) for a in data.get("actions", [])], data.get("settings", {}), name.strip())
            reload_items(); self.status(f"Duplicated profile '{src}'")

        def repair_selected():
            ok, issues = self.session_manager.repair_profile(selected_name())
            reload_items()
            if ok:
                self.status(f"Repaired profile '{selected_name()}'")
            else:
                QMessageBox.warning(dlg, "Repair Profile", "\n".join(issues))

        def export_selected():
            name = selected_name()
            data = self.session_manager.load_profile(name)
            if not data:
                QMessageBox.warning(dlg, "Export Profile", f"Profile '{name}' could not be loaded.")
                return
            default_path = os.path.join(os.path.expanduser("~"), f"{name}.macroforge-profile.json")
            path, _ = QFileDialog.getSaveFileName(dlg, "Export Profile", default_path, "MacroForge Profile (*.macroforge-profile.json);;JSON (*.json)")
            if not path:
                return
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                self.status(f"Exported profile '{name}'")
            except Exception as exc:
                QMessageBox.critical(dlg, "Export Profile", str(exc))

        def import_profile():
            path, _ = QFileDialog.getOpenFileName(dlg, "Import Profile", "", "MacroForge Profile (*.macroforge-profile.json);;JSON (*.json)")
            if not path:
                return
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                _ok, data, _issues = self.session_manager.validate_profile_data(raw)
                name = str(data.get("profile") or os.path.splitext(os.path.basename(path))[0]).strip()
                name, ok = QInputDialog.getText(dlg, "Import Profile", "Profile name:", text=name)
                if not ok or not name.strip():
                    return
                self.session_manager.save_profile([Action.from_dict(a) for a in data.get("actions", [])], data.get("settings", {}), name.strip())
                reload_items()
                self.status(f"Imported profile '{name.strip()}'")
            except Exception as exc:
                QMessageBox.critical(dlg, "Import Profile", str(exc))

        def rename_selected():
            self.session_manager.switch_profile(selected_name())
            self._rename_profile_dialog(); reload_items(); self._refresh_profile_btn()

        def delete_selected():
            name = selected_name()
            if name == self.session_manager.DEFAULT_PROFILE:
                QMessageBox.information(dlg, "Delete Profile", "The default profile cannot be deleted.")
                return
            if QMessageBox.question(dlg, "Delete Profile", f"Delete profile '{name}'?") == QMessageBox.StandardButton.Yes:
                self.session_manager.delete_profile(name); reload_items(); self.load_last_session()

        reload_items()
        btn_row = QHBoxLayout(); btn_row.setSpacing(6)
        for text, slot in (("Open", open_selected), ("New", new_profile), ("Duplicate", duplicate_profile), ("Rename", rename_selected), ("Repair", repair_selected), ("Export", export_selected), ("Import", import_profile), ("Delete", delete_selected)):
            b = QPushButton(text); b.clicked.connect(slot); btn_row.addWidget(b)
        btn_row.addStretch()
        close = QPushButton("Close"); close.clicked.connect(dlg.accept); btn_row.addWidget(close)
        lo.addLayout(btn_row)
        dlg.exec()

    def open_image_confidence_preview(self, index=None):
        idx = self.active_index if index is None else index
        if idx is None or idx < 0 or idx >= self.action_model.rowCount():
            self.status("Select an image action first")
            return
        action = self.action_model.get(idx)
        if not action.is_image():
            self.status("Selected row is not an image action")
            return
        C = COLORS
        dlg = QDialog(self)
        dlg.setWindowTitle("Image Confidence Preview")
        dlg.resize(420, 460)
        dlg.setStyleSheet(
            f"QDialog {{ background-color: {C['bg']}; color: {C['text']}; }}"
            f"QLabel {{ background: transparent; }}"
            f"QPushButton {{ background-color: {C['bg_card']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 8px; padding: 7px 12px; }}"
            f"QPushButton:hover {{ border-color: {C['image']}; color: {C['image']}; }}"
        )
        lo = QVBoxLayout(dlg)
        lo.setContentsMargins(14, 14, 14, 14)
        title = QLabel("Image Confidence Preview")
        title.setStyleSheet(f"color: {C['text']}; font-size: 18px; font-weight: 950;")
        lo.addWidget(title)
        meta = QLabel(
            f"Row {idx + 1} · threshold ≥ {float(getattr(action, 'similarity', 0.95) or 0.95) * 100:.0f}% · "
            f"timeout {float(getattr(action, 'wait_timeout', 0.0) or 0.0):.1f}s"
        )
        meta.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px;")
        lo.addWidget(meta)
        preview = QLabel("No template image stored")
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setMinimumHeight(260)
        preview.setStyleSheet(f"background-color: {C['bg_card']}; border: 1px solid {C['border']}; border-radius: 10px; color: {C['text_dim']};")
        try:
            import base64
            raw = base64.b64decode(getattr(action, "image_data", "") or "")
            from PyQt6.QtGui import QPixmap
            pix = QPixmap()
            if raw and pix.loadFromData(raw):
                preview.setPixmap(pix.scaled(360, 260, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        except Exception:
            pass
        lo.addWidget(preview, 1)
        extras = len([x for x in (getattr(action, "extra_images", "") or "").split("|") if x])
        screen = f"{getattr(action, 'screen_width', 0)}×{getattr(action, 'screen_height', 0)}" if getattr(action, 'screen_width', 0) else "not stored"
        info = QLabel(f"Extra templates: {extras} · Capture screen: {screen}")
        info.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px;")
        lo.addWidget(info)
        close = QPushButton("Close")
        close.clicked.connect(dlg.accept)
        lo.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        dlg.exec()

    def toggle_runtime_log_panel(self, show=None):
        if not hasattr(self, "runtime_log_panel"):
            self.open_playback_diagnostics()
            return
        visible = not self.runtime_log_panel.isVisible() if show is None else bool(show)
        self.runtime_log_panel.setVisible(visible)
        if hasattr(self, "runtime_log_btn"):
            self.runtime_log_btn.setChecked(visible)
        if visible and hasattr(self, "runtime_log_edit"):
            self.runtime_log_edit.setPlainText("\n".join(self._diag_lines[-600:]))
            sb = self.runtime_log_edit.verticalScrollBar()
            sb.setValue(sb.maximum())

    def clear_runtime_log_panel(self):
        self._diag_lines.clear()
        if getattr(self, "_diag_edit", None) is not None:
            self._diag_edit.clear()
        if hasattr(self, "runtime_log_edit"):
            self.runtime_log_edit.clear()
        self.status("Runtime log cleared")

    def run_selected_actions(self, rows):
        if self.engine.running:
            self.status("Stop playback before running selected block")
            return
        rows = sorted(r for r in set(rows or []) if 0 <= r < self.action_model.rowCount())
        if not rows:
            self.status("No selected actions to run")
            return
        self._single_test_active = False
        self._single_test_index = -1
        self._run_from_index = 0
        self._run_index_map = rows
        self.engine.actions = [deepcopy(self.action_model.get(r)) for r in rows]
        self.engine.variables = dict(getattr(self, "macro_variables", {}) or {})
        # Validate the whole macro first so references are still caught.
        if not self.run_preflight_check(show_success=False, allow_warning_prompt=True):
            self._run_index_map = []
            return
        self.actions_played = 0
        self.session_elapsed_time = 0.0
        self.session_start_time = time.time()
        self.progress_bar.setValue(0)
        self.progress_label.setText("0%")
        self.timeline.clear_image_states()
        if hasattr(self.timeline, "clear_trace"):
            self.timeline.clear_trace()
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.status_dot.set_color(COLORS["playing"], glow=True)
        self.playback_feedback("Running selected block")
        self.engine.infinite_loop = False
        self.engine.loops = 1
        self.engine.simulation_mode = self.sim_check.isChecked()
        self.engine.human_curve = self.human_check.isChecked()
        self.engine.focus_lock = self.focus_check.isChecked()
        try:
            self.engine.speed = float(self.speed_combo.currentText().replace("x", ""))
        except ValueError:
            self.engine.speed = 1.0
        self._diag(f"[PLAY] Running selected block: rows {', '.join(str(r + 1) for r in rows)}")
        self.engine.start()

    def scale_actions_to_current_screen(self):
        sw, sh = self._current_screen_size()
        if not sw or not sh:
            self.status("Current screen size unavailable")
            return
        changed = 0
        self.history.push(self.action_model.actions(), self._timeline_history_state())
        for action in self.action_model.actions():
            old_w = int(getattr(action, "screen_width", 0) or 0)
            old_h = int(getattr(action, "screen_height", 0) or 0)
            if not old_w or not old_h or (old_w == sw and old_h == sh):
                continue
            if action.is_click() and getattr(action, "click_coord_mode", "absolute") == "absolute":
                action.click_x = int(round(action.click_x * sw / old_w))
                action.click_y = int(round(action.click_y * sh / old_h))
                action.screen_width = sw
                action.screen_height = sh
                action.anchor_mode = "scaled"
                changed += 1
            elif action.is_image() and getattr(action, "search_region", ""):
                try:
                    x, y, w, h = [int(v.strip()) for v in action.search_region.split(",")]
                    action.search_region = f"{round(x * sw / old_w)},{round(y * sh / old_h)},{round(w * sw / old_w)},{round(h * sh / old_h)}"
                    action.screen_width = sw
                    action.screen_height = sh
                    action.anchor_mode = "scaled"
                    changed += 1
                except Exception:
                    pass
        self.refresh()
        self.save_session()
        self.status(f"Scaled {changed} coordinate action(s) to {sw}×{sh}")

    def _recovery_dir(self):
        base = getattr(self.session_manager, "base_dir", os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, "recovery")
        os.makedirs(path, exist_ok=True)
        return path

    def _recovery_path(self):
        return os.path.join(self._recovery_dir(), "last_session.json")

    def _version_history_dir(self):
        path = os.path.join(self._recovery_dir(), "versions")
        os.makedirs(path, exist_ok=True)
        return path

    def _trim_version_history(self, keep=10):
        try:
            files = sorted(
                [os.path.join(self._version_history_dir(), f) for f in os.listdir(self._version_history_dir()) if f.endswith(".json")],
                key=os.path.getmtime, reverse=True,
            )
            for old in files[int(keep):]:
                try:
                    os.remove(old)
                except Exception:
                    pass
        except Exception:
            pass

    def _write_recovery_snapshot(self, clean_shutdown=False):
        try:
            payload = self._macro_export_payload()
            payload["clean_shutdown"] = bool(clean_shutdown)
            payload["active_profile"] = self.session_manager.active
            with open(self._recovery_path(), "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            if not clean_shutdown and payload.get("actions"):
                stamp = time.strftime("%Y%m%d-%H%M%S")
                name = f"{self.session_manager.active}-{stamp}.json".replace("/", "_").replace("\\", "_")
                hist_path = os.path.join(self._version_history_dir(), name)
                with open(hist_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
                self._trim_version_history(keep=10)
        except Exception:
            pass

    def _check_recovery_snapshot(self):
        try:
            path = self._recovery_path()
            if not os.path.exists(path):
                return
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if payload.get("clean_shutdown", True):
                return
            actions = payload.get("actions", [])
            if not actions:
                return
            reply = QMessageBox.question(
                self,
                "Recover unsaved macro?",
                f"MacroForge found an autosaved recovery snapshot with {len(actions)} action(s). Restore it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.history.push(self.action_model.actions(), self._timeline_history_state())
                self.action_model.set_actions([Action.from_dict(d) for d in actions])
                self.refresh()
                self.save_session()
                self.status("Recovered autosaved macro")
            self._write_recovery_snapshot(clean_shutdown=True)
        except Exception as e:
            logger.debug(f"recovery check failed: {e}")

    def open_recovery_history(self):
        """Open saved autosave/version snapshots and restore one."""
        C = COLORS
        dlg = QDialog(self)
        dlg.setWindowTitle("Recovery / Version History")
        dlg.resize(560, 420)
        dlg.setStyleSheet(
            f"QDialog {{ background-color: {C['bg']}; color: {C['text']}; }}"
            f"QListWidget {{ background-color: {C['bg_tertiary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 8px; padding: 6px; }}"
            f"QPushButton {{ background-color: {C['bg_card']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 8px; padding: 7px 12px; }}"
            f"QPushButton:hover {{ border-color: {C['accent']}; color: {C['accent']}; }}"
        )
        lo = QVBoxLayout(dlg)
        lo.setContentsMargins(14, 14, 14, 14)
        title = QLabel("Recovery / Version History")
        title.setStyleSheet(f"color: {C['text']}; font-size: 17px; font-weight: 900; background: transparent;")
        lo.addWidget(title)
        hint = QLabel("Restore one of the latest autosaved macro snapshots. A backup of the current macro is saved before restoring.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px; background: transparent;")
        lo.addWidget(hint)
        items = QListWidget()
        files = []
        try:
            files = sorted(
                [os.path.join(self._version_history_dir(), f) for f in os.listdir(self._version_history_dir()) if f.endswith(".json")],
                key=os.path.getmtime, reverse=True,
            )
            for path in files:
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        payload = json.load(f)
                    ts = payload.get("exported_at", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(path))))
                    count = len(payload.get("actions", []))
                    prof = payload.get("active_profile", payload.get("profile", "Profile"))
                    items.addItem(f"{ts} · {prof} · {count} row(s)")
                except Exception:
                    items.addItem(os.path.basename(path))
        except Exception:
            pass
        lo.addWidget(items, 1)
        row = QHBoxLayout()
        row.addStretch()
        restore = QPushButton("Restore selected")
        close = QPushButton("Close")
        def do_restore():
            idx = items.currentRow()
            if idx < 0 or idx >= len(files):
                self.status("Select a recovery snapshot first")
                return
            try:
                with open(files[idx], "r", encoding="utf-8") as f:
                    payload = json.load(f)
                actions_data = payload.get("actions", [])
                self.history.push(self.action_model.actions(), self._timeline_history_state())
                self._write_recovery_snapshot(clean_shutdown=False)
                self.action_model.set_actions([Action.from_dict(d) for d in actions_data])
                fixes, warnings = self._repair_loaded_macro()
                self.active_index = -1
                self.refresh()
                self.update_statistics(immediate=True)
                self.save_session()
                self.status(f"Restored recovery snapshot with {len(actions_data)} row(s)")
                dlg.accept()
            except Exception as e:
                QMessageBox.critical(self, "Restore failed", str(e))
        restore.clicked.connect(do_restore)
        close.clicked.connect(dlg.accept)
        row.addWidget(restore)
        row.addWidget(close)
        lo.addLayout(row)
        dlg.exec()

    # ═══════════════════════════════════════════════════════
    #  PLAYBACK
    # ═══════════════════════════════════════════════════════

    def _on_speed_change(self, text):
        try:
            self.engine.speed = float(text.replace("x", ""))
        except ValueError:
            pass

    def start(self):
        if self.engine.running:
            self.status("Already running")
            return
        self._single_test_active = False
        self._single_test_index = -1
        self._run_from_index = 0
        self._run_index_map = []
        # Always sync the execution engine from the visible timeline/model
        # immediately before playback. This prevents stale engine lists from
        # looping visually while not deploying the edited/current actions.
        self.engine.actions = self.action_model.actions()
        self.engine.variables = dict(getattr(self, "macro_variables", {}) or {})
        if not self.run_preflight_check(show_success=False, allow_warning_prompt=True):
            return
        self._diag(f"[PLAY] Starting macro: {len(self.engine.actions)} actions, loops={self.loops_spin.value()}, sim={self.sim_check.isChecked()}")
        if hasattr(self.timeline, "clear_trace"):
            self.timeline.clear_trace()
        self.actions_played = 0
        self.session_elapsed_time = 0.0
        self.session_start_time = time.time()
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.status_dot.set_color(COLORS["playing"], glow=True)
        self.playback_feedback("Starting macro…")
        self.progress_bar.setValue(0)
        self.progress_label.setText("0%")
        self.timeline.clear_image_states()
        self.engine.infinite_loop = self.inf_check.isChecked()
        self.engine.simulation_mode = self.sim_check.isChecked()
        self.engine.human_curve = self.human_check.isChecked()
        self.engine.focus_lock = self.focus_check.isChecked()
        self.engine.loops = self.loops_spin.value()
        try:
            self.engine.speed = float(self.speed_combo.currentText().replace("x", ""))
        except ValueError:
            self.engine.speed = 1.0
        self.engine.start()

    def stop(self):
        self._diag("[STOP] Stop requested")
        self._single_test_active = False
        self._single_test_index = -1
        self._run_from_index = 0
        self._run_index_map = []
        self.engine.stop()
        self.timeline.clear_playing()
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.status_dot.set_color(COLORS["text_dark"])
        self.playback_feedback("Stopped")
        if self.session_start_time:
            self.session_elapsed_time += time.time() - self.session_start_time
            self.session_start_time = None
        self.update_statistics(immediate=True)

    def _status_cb(self, msg):
        self._diag(f"[STATUS] {msg}")
        text = str(msg or "")
        lower = text.lower()
        # Keep playback feedback out of the top header. The top capsule is
        # reserved for app/profile/save state and errors.
        if getattr(self.engine, "running", False):
            self._playback_feedback_msg.emit(text)
            if any(word in lower for word in ("error", "failed", "stopped", "not found", "warning")):
                self._status_msg.emit(text)
            return
        self._status_msg.emit(text)

    def _set_playback_feedback(self, msg: str):
        try:
            if hasattr(self, "playback_feedback_label"):
                text = str(msg or "")
                self.playback_feedback_label.setText(text)
                self.playback_feedback_label.setToolTip(text)
        except Exception:
            pass

    def playback_feedback(self, msg: str):
        self._playback_feedback_msg.emit(str(msg or ""))

    def _play_cb(self, idx, dur):
        self._play_action.emit(idx, dur)

    def _do_play_cb(self, idx, dur):
        display_idx = self._display_index_from_engine_index(idx)
        self.playing_index = display_idx
        # Auto-expand a collapsed group when playback reaches one of its member rows;
        # group headers themselves are skipped by the engine and never become active.
        active_group_label = ""
        try:
            meta = self._group_header_for_row(display_idx)
            if meta:
                active_group_label = f"{meta['badge']} {meta['name']}"
                if bool(getattr(meta["action"], "group_collapsed", False)):
                    meta["action"].group_collapsed = False
                    self.timeline.refresh()
        except Exception:
            pass
        self.actions_played += 1
        speed = max(self.engine.speed_multiplier, 0.01)
        adjusted_dur = dur / speed
        self.timeline.set_playing(display_idx, adjusted_dur)
        self._update_timeline_links(display_idx)
        action_name = ""
        try:
            current = self.action_model.get(display_idx)
            action_name = getattr(current, "label", "") or getattr(current, "key", "") or getattr(current, "action_type", "Action")
        except Exception:
            pass
        detail = f"{active_group_label} · Row {display_idx + 1} {action_name}" if active_group_label else f"Row {display_idx + 1} {action_name}"
        self.playback_feedback(f"Playing · {detail}")
        group_log = f" in {active_group_label}" if active_group_label else ""
        self._diag(f"[PLAY] Timeline row {display_idx + 1}{group_log} active for ~{adjusted_dur:.2f}s")
        self.update_statistics()

    def _image_match_cb(self, idx, state):
        self._image_match_state.emit(idx, state)

    def _do_image_match_state(self, idx, state):
        display_idx = self._display_index_from_engine_index(idx)
        self.timeline.set_image_state(display_idx, state)

    def _do_trace_row(self, row):
        if hasattr(self.timeline, "mark_trace"):
            self.timeline.mark_trace(row)

    def _pause_cb(self, paused):
        self._pause_state.emit(paused)

    def _do_pause_cb(self, paused):
        self.timeline.set_paused(paused)
        if paused:
            self.pause_btn.setIcon(icon("play", 14, COLORS["text_inverse"]))
            self.pause_btn.setToolTip("Resume (Esc)")
            label = "Paused"
            try:
                if 0 <= self.playing_index < self.action_model.rowCount():
                    meta = self._group_header_for_row(self.playing_index)
                    if meta:
                        label = f"Paused · {meta['badge']} {meta['name']}"
            except Exception:
                pass
            self.playback_feedback(label)
        else:
            self.pause_btn.setIcon(icon("pause", 14, COLORS["text_inverse"]))
            self.pause_btn.setToolTip("Pause (Esc)")
            self.playback_feedback("Resumed")

    def _complete_cb(self):
        self._complete.emit()

    def _do_complete_cb(self):
        was_single_test = self._single_test_active
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.playing_index = -1
        self.timeline.clear_playing()
        if hasattr(self.timeline, "set_link_targets"):
            self.timeline.set_link_targets(-1, [])
        self.progress_bar.setValue(100)
        self.progress_label.setText("100%")
        self.status_dot.set_color(COLORS["text_dark"])
        self.playback_feedback("Selected action test complete" if was_single_test else "Macro complete")
        self._diag("[TEST] Selected action test complete" if was_single_test else "[PLAY] Macro complete")
        self._single_test_active = False
        self._single_test_index = -1
        self._run_from_index = 0
        self._run_index_map = []
        if self.session_start_time:
            self.session_elapsed_time += time.time() - self.session_start_time
            self.session_start_time = None
        self.update_statistics(immediate=True)

    def _progress_cb(self, pct):
        try:
            pct = float(pct)
        except (TypeError, ValueError):
            pct = 0.0
        self._progress.emit(pct)

    def _do_progress_cb(self, pct):
        try:
            pct = float(pct)
        except (TypeError, ValueError):
            pct = 0.0
        pct = max(0.0, min(100.0, pct))
        self.progress_bar.setValue(round(pct))
        self.progress_label.setText(f"{pct:.0f}%" if pct >= 10 else f"{pct:.1f}%")

    # ═══════════════════════════════════════════════════════
    #  PLAYBACK DIAGNOSTICS / SINGLE ACTION TEST
    # ═══════════════════════════════════════════════════════

    def _action_diag_summary(self, action):
        try:
            if action is None:
                return "Unknown action"
            kind = getattr(action, "action_type", "key") or "key"
            label = (getattr(action, "label", "") or "").strip()
            prefix = f"{kind.upper()}"
            if action.is_pause():
                return f"DELAY {float(getattr(action, 'duration', 0.0) or 0.0):.2f}s" + (f" · {label}" if label else "")
            if action.is_click():
                return f"CLICK {getattr(action, 'click_button', 'left')} @ {getattr(action, 'click_x', 0)},{getattr(action, 'click_y', 0)}" + (f" · {label}" if label else "")
            if action.is_image():
                return f"IMAGE Template.png timeout={float(getattr(action, 'wait_timeout', 0.0) or 0.0):.1f}s" + (f" · {label}" if label else "")
            if action.is_condition():
                return f"CONDITION {getattr(action, 'condition_type', 'none')}" + (f" · {label}" if label else "")
            key = getattr(action, "key", "") or "Unknown"
            hold = " hold" if bool(getattr(action, "hold_mode", False)) else ""
            return f"KEY {key}{hold} {float(getattr(action, 'duration', 0.0) or 0.0):.2f}s" + (f" · {label}" if label else "")
        except Exception as e:
            return f"Action summary failed: {e}"

    def _diag(self, message):
        try:
            stamp = time.strftime("%H:%M:%S")
            self._diag_msg.emit(f"{stamp} {message}")
        except Exception:
            pass

    def _append_diagnostic(self, line):
        self._diag_lines.append(line)
        max_lines = int(getattr(self, "_diag_max_lines", 10000) or 10000)
        if len(self._diag_lines) > max_lines:
            removed = len(self._diag_lines) - max_lines
            del self._diag_lines[:removed]
            self._diag_prune_count += removed
            # Re-seed the visible diagnostics window after pruning so the
            # widget cannot grow forever either.
            if self._diag_edit is not None:
                self._diag_edit.setPlainText("\n".join(self._diag_lines))
        try:
            logger.info(line)
        except Exception:
            pass
        if self._diag_edit is not None:
            self._diag_edit.appendPlainText(line)
            sb = self._diag_edit.verticalScrollBar()
            sb.setValue(sb.maximum())
        try:
            if hasattr(self, "runtime_log_edit") and self.runtime_log_edit is not None:
                self.runtime_log_edit.appendPlainText(line)
                sb = self.runtime_log_edit.verticalScrollBar()
                sb.setValue(sb.maximum())
        except Exception:
            pass

    def _before_action_diag(self, action):
        self._diag(f"[ACTION] Preparing {self._action_diag_summary(action)}")

    def _after_action_diag(self, action):
        sim = " simulated" if getattr(self.engine, "simulation_mode", False) else " deployed"
        try:
            display_idx = self._display_index_from_engine_index(getattr(self.engine, "current_action_index", -1))
            self._trace_row.emit(display_idx)
        except Exception:
            pass
        self._diag(f"[ACTION] {self._action_diag_summary(action)}{sim}")

    def open_playback_diagnostics(self):
        if self._diag_dialog is not None and self._diag_dialog.isVisible():
            self._diag_dialog.raise_()
            self._diag_dialog.activateWindow()
            return

        C = COLORS
        dlg = QDialog(self)
        dlg.setWindowTitle("Playback Diagnostics")
        dlg.resize(620, 420)
        dlg.setStyleSheet(
            f"QDialog {{ background-color: {C['bg']}; color: {C['text']}; }}"
            f"QPlainTextEdit {{ background-color: {C['bg_tertiary']}; color: {C['text']}; "
            f"border: 1px solid {C['border']}; border-radius: 8px; padding: 8px; font-family: Consolas, monospace; font-size: 11px; }}"
            f"QPushButton {{ background-color: {C['bg_card']}; color: {C['text']}; border: 1px solid {C['border']}; "
            f"border-radius: 7px; padding: 7px 12px; }}"
            f"QPushButton:hover {{ border-color: {C['accent']}; color: {C['accent']}; }}"
        )
        lo = QVBoxLayout(dlg)
        lo.setContentsMargins(12, 12, 12, 12)
        lo.setSpacing(8)
        title = QLabel("Playback Diagnostics")
        title.setStyleSheet(f"color: {C['text']}; font-size: 15px; font-weight: 800;")
        lo.addWidget(title)
        hint = QLabel("Shows engine status, active rows, deployment path, and pre-flight checks. Keeps the newest 10,000 lines.")
        hint.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px;")
        lo.addWidget(hint)
        edit = QPlainTextEdit()
        edit.setReadOnly(True)
        edit.setPlainText("\n".join(self._diag_lines))
        lo.addWidget(edit, stretch=1)
        btns = QHBoxLayout()
        btns.addStretch()
        clear_btn = QPushButton("Clear")
        close_btn = QPushButton("Close")
        clear_btn.clicked.connect(lambda: (self._diag_lines.clear(), edit.clear()))
        close_btn.clicked.connect(dlg.close)
        btns.addWidget(clear_btn)
        btns.addWidget(close_btn)
        lo.addLayout(btns)
        self._diag_dialog = dlg
        self._diag_edit = edit
        dlg.finished.connect(lambda _=0: setattr(self, "_diag_edit", None))
        dlg.show()

    def _app_diagnostics_lines(self):
        from ui.diagnostics_panel import app_diagnostics_lines
        return app_diagnostics_lines(self)

    def _export_support_bundle(self, edit=None):
        from ui.diagnostics_panel import export_support_bundle
        export_support_bundle(self, edit)

    def _clear_update_health(self, edit):
        from ui.diagnostics_panel import clear_update_health
        clear_update_health(self, edit)

    def _validate_updater_now(self, edit):
        from ui.diagnostics_panel import validate_updater_now
        validate_updater_now(self, edit)

    def open_app_diagnostics(self):
        from ui.diagnostics_panel import show_app_diagnostics
        show_app_diagnostics(self)

    def test_selected_action(self):
        if self.engine.running:
            self.status("Stop playback before testing a single action")
            return
        idx = self.active_index
        if idx < 0:
            try:
                cur = self.timeline.currentIndex()
                idx = cur.row() if cur and cur.isValid() else -1
            except Exception:
                idx = -1
        if idx < 0 or idx >= self.action_model.rowCount():
            self.status("Select an action to test")
            return

        action = deepcopy(self.action_model.get(idx))
        self._single_test_active = True
        self._single_test_index = idx
        self._run_from_index = 0
        self.actions_played = 0
        self.session_elapsed_time = 0.0
        self.session_start_time = time.time()
        self.progress_bar.setValue(0)
        self.progress_label.setText("0%")
        self.timeline.clear_image_states()
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.status_dot.set_color(COLORS["playing"], glow=True)
        self.playback_feedback(f"Testing row {idx + 1}")

        self.engine.actions = [action]
        self.engine.variables = dict(getattr(self, "macro_variables", {}) or {})
        self.engine.infinite_loop = False
        self.engine.simulation_mode = self.sim_check.isChecked()
        self.engine.human_curve = self.human_check.isChecked()
        self.engine.focus_lock = self.focus_check.isChecked()
        self.engine.loops = 1
        self.engine.loops_completed_count = 0
        try:
            self.engine.speed = float(self.speed_combo.currentText().replace("x", ""))
        except ValueError:
            self.engine.speed = 1.0

        self._diag(f"[TEST] Testing row {idx + 1}: {self._action_diag_summary(action)} sim={self.engine.simulation_mode}")
        self.engine.start()

    def test_from_selected_row(self):
        if self.engine.running:
            self.status("Stop playback before testing from a selected row")
            return
        idx = self.active_index
        if idx < 0:
            try:
                cur = self.timeline.currentIndex()
                idx = cur.row() if cur and cur.isValid() else -1
            except Exception:
                idx = -1
        if idx < 0 or idx >= self.action_model.rowCount():
            self.status("Select a starting row to test")
            return

        self._single_test_active = False
        self._single_test_index = -1
        self._run_from_index = idx
        self.engine.actions = self.action_model.actions()[idx:]
        self.engine.variables = dict(getattr(self, "macro_variables", {}) or {})
        if not self.run_preflight_check(show_success=False, allow_warning_prompt=True):
            self._run_from_index = 0
            return

        self.actions_played = 0
        self.session_elapsed_time = 0.0
        self.session_start_time = time.time()
        self.progress_bar.setValue(0)
        self.progress_label.setText("0%")
        self.timeline.clear_image_states()
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.status_dot.set_color(COLORS["playing"], glow=True)
        self.playback_feedback(f"Testing from row {idx + 1}")

        self.engine.infinite_loop = False
        self.engine.simulation_mode = self.sim_check.isChecked()
        self.engine.human_curve = self.human_check.isChecked()
        self.engine.focus_lock = self.focus_check.isChecked()
        self.engine.loops = 1
        self.engine.loops_completed_count = 0
        try:
            self.engine.speed = float(self.speed_combo.currentText().replace("x", ""))
        except ValueError:
            self.engine.speed = 1.0

        self._diag(f"[TEST] Testing from row {idx + 1}: {len(self.engine.actions)} actions")
        self.engine.start()

    # ═══════════════════════════════════════════════════════
    #  RECORDER BUTTON SKINS
    # ═══════════════════════════════════════════════════════

    def _rec_record_active_style(self):
        """Active Stop/Record button gradient, matched to the dark neon buttons."""
        return (
            "QPushButton {"
            "background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            "stop:0 #66131D, stop:0.52 #2B0810, stop:1 #070306);"
            "color: #F7FAFF; border: 1px solid #FF3142; border-radius: 10px; "
            "padding: 0px; min-width: 100px; max-width: 100px; min-height: 45px; max-height: 45px; font-size: 12px; font-weight: 900; text-align: center;"
            "}"
            "QPushButton:hover {"
            "background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            "stop:0 #7A1823, stop:0.52 #360B14, stop:1 #0B0408);"
            "border-color: #FF5464;"
            "}"
            "QPushButton:pressed {"
            "background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            "stop:0 #18060A, stop:0.55 #3A0B14, stop:1 #7A1823);"
            "border-color: #FF7380;"
            "}"
        )

    def _rec_pause_active_style(self):
        """Active Pause/Resume button gradient, matched to the dark neon buttons."""
        return (
            "QPushButton {"
            "background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            "stop:0 #064756, stop:0.52 #06232B, stop:1 #031014);"
            "color: #F7FAFF; border: 1px solid #25D8FF; border-radius: 10px; "
            "padding: 0px; min-width: 100px; max-width: 100px; min-height: 45px; max-height: 45px; font-size: 12px; font-weight: 900; text-align: center;"
            "}"
            "QPushButton:hover {"
            "background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            "stop:0 #075A6C, stop:0.52 #07303A, stop:1 #03161B);"
            "border-color: #52E5FF;"
            "}"
            "QPushButton:pressed {"
            "background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            "stop:0 #031014, stop:0.55 #07303A, stop:1 #075A6C);"
            "border-color: #7AF0FF;"
            "}"
        )

    def _recorder_reset_button_styles(self):
        """Return recorder buttons to their inactive themed gradients."""
        if hasattr(self, "rec_btn"):
            self.rec_btn.setStyleSheet("")
        if hasattr(self, "rec_pause_btn"):
            self.rec_pause_btn.setStyleSheet("")

    # ═══════════════════════════════════════════════════════
    #  RECORDER
    # ═══════════════════════════════════════════════════════

    def _toggle_record(self):
        rec = self._recorder
        if not rec["running"]:
            self._start_recording()
        else:
            self._stop_recording()

    def _toggle_record_pause(self):
        rec = self._recorder
        if not rec["running"]:
            return
        if rec["paused"]:
            rec["paused"] = False
            rec["last_time"] = time.time()
            self.rec_pause_btn.setText(" Pause")
            self.rec_pause_btn.setStyleSheet(self._rec_pause_active_style())
            self.rec_dot.set_color(COLORS["error"], glow=True)
            self.rec_status.setText("RECORDING")
            self.rec_status.setStyleSheet(f"color: {COLORS['error']}; font-size: 11px; font-weight: 600;")
            self._rec_timer_tick()
            self.status("Recording resumed")
            self._show_rec_badge(True)
        else:
            rec["paused"] = True
            self.rec_pause_btn.setText(" Resume")
            self.rec_dot.set_color(COLORS["pause_cyan"], glow=True)
            self.rec_status.setText("PAUSED")
            self.rec_status.setStyleSheet(f"color: {COLORS['pause_cyan']}; font-size: 11px; font-weight: 600;")
            self.status("Recording paused — click Resume to continue, or Stop to finish")
            self._show_rec_badge(False)

    def _show_rec_badge(self, show):
        rec = self._recorder
        if show:
            if rec["overlay"] is not None:
                return
            # We use a simple QWidget overlay positioned near main window
            ov = QFrame()
            ov.setStyleSheet("background-color: transparent; border: none;")
            ov.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            ov.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
            ov.setFixedSize(60, 28)
            lbl = QLabel("REC")
            lbl.setStyleSheet(f"color: {COLORS['error']}; font-weight: bold; font-size: 12px;")
            lo = QHBoxLayout(ov)
            lo.addWidget(lbl)
            ov.show()
            # Position near top-right of main window
            geo = self.geometry()
            ov.move(geo.x() + geo.width() - 72, geo.y() + 10)
            rec["overlay"] = ov
        else:
            if rec["overlay"] is not None:
                rec["overlay"].close()
                rec["overlay"] = None

    def _rec_timer_tick(self):
        rec = self._recorder
        if not rec["running"] or rec["paused"]:
            return
        elapsed = int(time.time() - rec["rec_start_time"])
        mins, secs = divmod(elapsed, 60)
        hours, mins = divmod(mins, 60)
        self.rec_time.setText(f"{hours:02d}:{mins:02d}:{secs:02d}")
        QTimer.singleShot(1000, self._rec_timer_tick)

    def _update_rec_action_count(self):
        rec = self._recorder
        if rec["running"] and rec["actions_lbl"] is not None:
            rec["actions_lbl"].setText(str(self.action_model.rowCount()))

    def _start_recording(self):
        if self._recorder["running"]:
            return
        rec = self._recorder
        rec["running"] = True
        rec["paused"] = False
        rec["last_time"] = time.time()
        rec["presses"].clear()
        rec["modifiers"].clear()
        rec["queue"] = queue.Queue()
        self.rec_btn.setText("")
        self.rec_btn.setIcon(icon("stop", 16, COLORS["error"]))
        self.rec_btn.setStyleSheet("")
        self.rec_pause_btn.setText(" Pause")
        self.rec_pause_btn.setEnabled(True)
        self.rec_pause_btn.setStyleSheet(self._rec_pause_active_style())
        self.rec_dot.set_color(COLORS["error"], glow=True)
        self.rec_status.setText("RECORDING")
        self.rec_status.setStyleSheet(f"color: {COLORS['error']}; font-size: 11px; font-weight: 600;")
        self.rec_actions.setText("0")
        rec["rec_start_time"] = time.time()
        self._rec_timer_tick()
        self.status("Recording…")
        self._show_rec_badge(True)

        # Cancel stale poll
        if rec["poll_id"]:
            rec["poll_id"].stop()
            rec["poll_id"] = None
        self._poll_queue()

        # Keyboard polling thread
        rec["kbd_thread"] = threading.Thread(target=self._kbd_poll_loop, daemon=True)
        rec["kbd_thread"].start()

        # Scroll hook thread
        rec["scroll_thread"] = threading.Thread(target=self._scroll_hook_loop, daemon=True)
        rec["scroll_thread"].start()
        logger.info("Recording started")

    def _kbd_poll_loop(self):
        user32 = ctypes.windll.user32
        rec = self._recorder
        MODS = {"shift", "ctrl", "alt"}
        vk_name = {}
        for vk in range(0x41, 0x5B):
            vk_name[vk] = chr(vk).lower()
        for vk in range(0x30, 0x3A):
            vk_name[vk] = chr(vk)
        vk_name.update({
            0x08: "backspace", 0x09: "tab", 0x0D: "return",
            0x1B: "esc", 0x20: "space",
            0x25: "left", 0x26: "up", 0x27: "right", 0x28: "down",
            0x10: "shift", 0x11: "ctrl", 0x12: "alt",
            0x01: "mouse_left", 0x02: "mouse_right", 0x04: "mouse_middle",
        })
        for i in range(0x70, 0x7C):
            vk_name[i] = f"f{i - 0x6F}"
        vks = list(vk_name.keys())
        prev = {}
        while rec["running"]:
            for vk in vks:
                name = vk_name[vk]
                down = (user32.GetAsyncKeyState(vk) & 0x8000) != 0
                was_down = prev.get(vk, False)
                if down and not was_down:
                    rec["presses"][name] = time.time()
                    if name in MODS:
                        rec["modifiers"].add(name)
                elif not down and was_down:
                    if name in MODS:
                        rec["modifiers"].discard(name)
                    if name not in rec["presses"]:
                        prev[vk] = down
                        continue
                    press_time = rec["presses"].pop(name)
                    release_time = time.time()
                    hold_dur = release_time - press_time
                    if hold_dur < 0.05:
                        prev[vk] = down
                        continue
                    if name == "backspace" and not rec["modifiers"]:
                        # Use invokeMethod to run on main thread
                        QTimer.singleShot(0, self._rec_delete_last)
                        prev[vk] = down
                        continue
                    if rec["paused"]:
                        prev[vk] = down
                        continue
                    delay = press_time - rec["last_time"]
                    if delay > 0.05:
                        rec["queue"].put(Action("[DELAY]", round(delay, 2), action_type="pause"))
                    if name.startswith("mouse_"):
                        pt = ctypes.wintypes.POINT()
                        user32.GetCursorPos(ctypes.byref(pt))
                        is_hold = hold_dur > 0.3
                        dur = round(hold_dur, 2) if is_hold else 0.05
                        act = Action("[CLICK]", dur, hold_mode=is_hold, action_type="click")
                        act.click_x, act.click_y = pt.x, pt.y
                        act.click_button = name.replace("mouse_", "")
                        act.click_coord_mode = "absolute"
                        rec["queue"].put(act)
                        rec["last_time"] = release_time
                    else:
                        active_mods = rec["modifiers"] - {name}
                        if active_mods and name not in MODS:
                            combo = "+".join(sorted(active_mods)) + "+" + name
                            rec["queue"].put(Action(combo, 0.05, action_type="key"))
                        else:
                            is_hold = hold_dur > 0.3
                            if is_hold:
                                rec["queue"].put(Action(name, round(hold_dur, 2), hold_mode=True, action_type="key"))
                            else:
                                rec["queue"].put(Action(name, 0.05, action_type="key"))
                        rec["last_time"] = release_time
                prev[vk] = down
            time.sleep(1 / 60)

    def _rec_delete_last(self):
        try:
            if self.action_model.rowCount() > 0:
                self.history.push(self.action_model.actions())
                self.action_model.remove_action(self.action_model.rowCount() - 1)
                self.active_index = self.action_model.rowCount() - 1
                self.refresh()
                self.update_statistics()
                self.save_session()
                self._update_rec_action_count()
                self.status("Deleted last recorded action")
        except Exception as e:
            logger.debug(f"rec_delete_last: {e}")

    def _scroll_hook_loop(self):
        user32 = ctypes.windll.user32
        rec = self._recorder
        WH_MOUSE_LL = 14
        WM_MOUSEWHEEL = 0x020A
        WM_MOUSEHWHEEL = 0x020E
        PM_REMOVE = 0x0001
        class MSLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("pt", ctypes.wintypes.POINT),
                ("mouseData", ctypes.c_uint32),
                ("flags", ctypes.c_uint32),
                ("time", ctypes.c_uint32),
                ("dwExtraInfo", ctypes.c_uint64),
            ]
        @ctypes.WINFUNCTYPE(ctypes.c_int64, ctypes.c_int32, ctypes.c_uint64, ctypes.c_int64)
        def hook_proc(nCode, wParam, lParam):
            if nCode >= 0 and rec["running"] and not rec["paused"]:
                if wParam == WM_MOUSEWHEEL or wParam == WM_MOUSEHWHEEL:
                    try:
                        if rec["queue"] is None:
                            return user32.CallNextHookEx(None, nCode, wParam, lParam)
                        data = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                        delta = ctypes.c_int16(data.mouseData >> 16).value
                        direction = "scroll_up" if delta > 0 else "scroll_down"
                        now = time.time()
                        delay = now - rec["last_time"]
                        if delay > 0.05:
                            rec["queue"].put(Action("[DELAY]", round(delay, 2), action_type="pause"))
                        rec["queue"].put(Action(f"[{direction.upper()}]", 0.05, action_type="key"))
                        rec["last_time"] = now
                        self.status(f"Recorded: {direction}")
                    except Exception as e:
                        logger.debug(f"scroll hook: {e}")
            return user32.CallNextHookEx(None, nCode, wParam, lParam)
        hook_id = user32.SetWindowsHookExW(WH_MOUSE_LL, hook_proc, None, 0)
        if not hook_id:
            logger.error("Failed to install scroll hook")
            return
        logger.info("Scroll hook installed")
        msg = ctypes.wintypes.MSG()
        while rec["running"]:
            if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                time.sleep(0.005)
        user32.UnhookWindowsHookEx(hook_id)
        logger.info("Scroll hook removed")

    def _poll_queue(self):
        rec = self._recorder
        try:
            if not rec["running"] and (rec["queue"] is None or rec["queue"].empty()):
                rec["poll_id"] = None
                return
            updated = False
            while rec["queue"] is not None and not rec["queue"].empty():
                try:
                    action = rec["queue"].get_nowait()
                except queue.Empty:
                    break
                self.history.push(self.action_model.actions())
                self.action_model.add_action(action)
                self._update_rec_action_count()
                updated = True
            if updated:
                self.active_index = self.action_model.rowCount() - 1
                self.refresh()
                self.timeline.ensure_visible(self.active_index)
                self.update_statistics()
                self.save_session()
        except Exception as e:
            logger.error(f"_poll_queue: {e}")
        if rec["running"]:
            rec["poll_id"] = QTimer.singleShot(50, self._poll_queue)

    def _stop_recording(self):
        if not self._recorder["running"]:
            return
        rec = self._recorder
        rec["running"] = False
        rec["paused"] = False
        if rec.get("kbd_thread") and rec["kbd_thread"].is_alive():
            rec["kbd_thread"].join(timeout=0.05)
        if rec.get("scroll_thread") and rec["scroll_thread"].is_alive():
            rec["scroll_thread"].join(timeout=0.2)
        self._show_rec_badge(False)
        self.rec_btn.setText("")
        self.rec_btn.setIcon(icon("record", 16, COLORS["error"]))
        self._recorder_reset_button_styles()
        self.rec_pause_btn.setText("")
        self.rec_pause_btn.setEnabled(False)
        self.rec_dot.set_color(COLORS["text_dark"])
        self.rec_status.setText("IDLE")
        self.rec_status.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px; font-weight: 600;")
        self.rec_time.setText("00:00:00")
        self.rec_actions.setText("0")
        if rec["timer_id"]:
            rec["timer_id"].stop()
            rec["timer_id"] = None
        try:
            if rec["queue"] is not None:
                now = time.time()
                for k, t in list(rec["presses"].items()):
                    hold = now - t
                    delay = t - rec["last_time"]
                    if delay > 0.05:
                        rec["queue"].put(Action("[DELAY]", round(delay, 2), action_type="pause"))
                    if k.startswith("mouse_"):
                        pt = ctypes.wintypes.POINT()
                        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
                        act = Action("[CLICK]", 0.05, action_type="click")
                        act.click_x, act.click_y = pt.x, pt.y
                        act.click_button = k.replace("mouse_", "")
                        act.click_coord_mode = "absolute"
                        rec["queue"].put(act)
                    else:
                        rec["queue"].put(Action(k, round(hold, 2), hold_mode=True, action_type="key"))
                    rec["last_time"] = now
            rec["presses"].clear()
            rec["modifiers"].clear()
        except Exception as e:
            logger.error(f"rec flush: {e}")
        if rec["poll_id"]:
            try:
                rec["poll_id"].stop()
            except Exception as e:
                logger.debug(f"after_cancel: {e}")
            rec["poll_id"] = None
        self._poll_queue_final()
        rec["kbd_thread"] = None
        rec["scroll_thread"] = None
        rec["queue"] = None
        self.status("Recording stopped")

    def _poll_queue_final(self):
        rec = self._recorder
        try:
            updated = False
            while rec["queue"] is not None and not rec["queue"].empty():
                try:
                    action = rec["queue"].get_nowait()
                except queue.Empty:
                    break
                self.history.push(self.action_model.actions())
                self.action_model.add_action(action)
                updated = True
            if updated:
                self.active_index = self.action_model.rowCount() - 1
                self.refresh()
                self.update_statistics()
                self.save_session()
        except Exception as e:
            logger.error(f"_poll_queue_final: {e}")

    # ═══════════════════════════════════════════════════════
    #  MENU SYSTEM
    # ═══════════════════════════════════════════════════════

    def _show_action_menu(self):
        from ui.main_window_menus import show_action_menu
        show_action_menu(self)

    # ═══════════════════════════════════════════════════════
    #  FILE OPERATIONS
    # ═══════════════════════════════════════════════════════

    def _macro_export_payload(self):
        sw, sh = self._current_screen_size()
        return {
            "format": "macroforge.macro",
            "format_version": 2,
            "app_version": VERSION,
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "screen": {"width": sw, "height": sh},
            "profile": self.session_manager.active,
            "macro_variables": dict(getattr(self, "macro_variables", {}) or {}),
            "groups": [
                {"row": meta["row"], "id": meta["gid"], "badge": meta["badge"], "name": meta["name"], "color": meta["color"], "collapsed": bool(getattr(meta["action"], "group_collapsed", False)), "action_count": meta.get("count", 0), "duration": meta.get("duration", 0.0)}
                for meta in self._group_headers()
            ],
            "actions": [a.to_dict() for a in self.action_model.actions()],
        }

    def _repair_loaded_macro(self):
        """Apply safe repairs after importing/loading a macro and report reliability issues."""
        fixes = []
        warnings = []
        total = self.action_model.rowCount()
        if self._normalize_groups():
            fixes.append("Normalized group ids, colors, and member badges")
        for idx, action in enumerate(self.action_model.actions()):
            kind = getattr(action, "action_type", "key") or "key"
            if kind == "loop":
                target = int(getattr(action, "loop_target", -1) or -1)
                if not (0 <= target < idx):
                    suggested = self._suggest_loop_target(idx)
                    if 0 <= suggested < idx:
                        action.loop_target = suggested
                        fixes.append(f"Row {idx + 1}: loop target repaired to {self._row_target_text(suggested)}")
                    else:
                        warnings.append(f"Row {idx + 1}: loop target still needs attention")
            elif kind == "condition":
                for attr, label in (("condition_jump_true", "true"), ("condition_jump_false", "false")):
                    target = int(getattr(action, attr, -1) or -1)
                    if target >= total:
                        setattr(action, attr, -1)
                        fixes.append(f"Row {idx + 1}: condition {label} target reset to next row")
            elif kind == "image" and not getattr(action, "image_data", ""):
                warnings.append(f"Row {idx + 1}: image action has no captured template")
        return fixes, warnings

    def _show_load_reliability_report(self, fixes, warnings):
        if not fixes and not warnings:
            return
        text = []
        if fixes:
            text.append(f"Auto-repaired {len(fixes)} issue(s):")
            text.extend(f"• {x}" for x in fixes[:8])
        if warnings:
            if text:
                text.append("")
            text.append(f"Warnings still needing review ({len(warnings)}):")
            text.extend(f"• {x}" for x in warnings[:8])
        QMessageBox.information(self, "Macro import reliability check", "\n".join(text))

    def save(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Macro", "", "MacroForge Macro (*.macroforge);;JSON (*.json)")
        if path:
            try:
                if path.lower().endswith(".json"):
                    payload = [a.to_dict() for a in self.action_model.actions()]
                else:
                    if not path.lower().endswith(".macroforge"):
                        path += ".macroforge"
                    payload = self._macro_export_payload()
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
                self.status(f"Exported {self.action_model.rowCount()} actions")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))

    def load(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Macro", "", "MacroForge Macro (*.macroforge);;JSON (*.json)")
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                actions_data = data.get("actions", []) if isinstance(data, dict) else data
                if isinstance(data, dict):
                    self.macro_variables = dict(data.get("macro_variables", getattr(self, "macro_variables", {})) or {})
                if not isinstance(actions_data, list):
                    raise ValueError("Unsupported macro file format")
                self.history.push(self.action_model.actions(), self._timeline_history_state())
                self.action_model.clear()
                for action_data in actions_data:
                    self.action_model.add_action(Action.from_dict(action_data))
                fixes, warnings = self._repair_loaded_macro()
                self.active_index = -1
                self.timeline.refresh()
                self.refresh()
                self.update_statistics()
                self.save_session()
                self._show_load_reliability_report(fixes, warnings)
                self.status(f"Imported {len(actions_data)} actions")
            except Exception as e:
                QMessageBox.critical(self, "Import Error", str(e))

    def export_macroforge(self):
        self.save()

    def import_macroforge(self):
        self.load()

    def export_csv(self):
        if not self.action_model.rowCount():
            QMessageBox.warning(self, "No Actions", "Nothing to export")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "", "CSV (*.csv)")
        if path:
            try:
                with open(path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["index", "key", "duration", "hold", "lane", "rand_delay", "rand_key", "type", "label"])
                    for i, a in enumerate(self.action_model.actions()):
                        writer.writerow([i+1, a.key, a.duration, a.hold_mode, a.lane, a.random_delay, a.random_key, a.action_type, a.label])
                self.status(f"Exported {self.action_model.rowCount()} actions to CSV")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))

    def import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import CSV", "", "CSV (*.csv)")
        if path:
            try:
                self.history.push(self.action_model.actions())
                new_actions = []
                with open(path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        a = Action(
                            key=row["key"],
                            duration=float(row["duration"]),
                            hold_mode=row.get("hold", "False") == "True",
                            lane=int(row.get("lane", 0)),
                            random_delay=float(row.get("rand_delay", 0)),
                            random_key=row.get("rand_key", "False") == "True",
                            action_type=row.get("type", "key"),
                            label=row.get("label", "")
                        )
                        new_actions.append(a)
                for a in new_actions:
                    self.action_model.add_action(a)
                self.active_index = -1
                self.timeline.refresh()
                self.update_statistics()
                self.save_session()
                self.status(f"Imported {len(new_actions)} actions from CSV")
            except Exception as e:
                QMessageBox.critical(self, "Import Error", str(e))

    def clear_all(self):
        if QMessageBox.question(self, "Clear All",
            "Remove all actions?") == QMessageBox.StandardButton.Yes:
            self.history.push(self.action_model.actions())
            self.action_model.clear()
            self.active_index = -1
            self.refresh()
            self.update_statistics()
            self.save_session()
            self.status("All actions cleared")

    def reset_stats(self):
        self.actions_played = 0
        self.session_elapsed_time = 0.0
        self.session_start_time = None
        self.update_statistics(immediate=True)
        self.status("Statistics reset")

    def _set_update_button_available(self, available=False, checking=False):
        """Refresh the top update/download icon state without showing popups."""
        try:
            btn = getattr(self, "update_top_btn", None)
            if btn is None:
                return
            if checking:
                color = COLORS["text_dim"]
                tip = "Checking for updates…"
            elif available:
                color = COLORS["success"]
                manifest = getattr(self, "_pending_update_manifest", None) or {}
                remote = manifest.get("version", "new version") if isinstance(manifest, dict) else "new version"
                tip = f"Update available: {remote} — click to download"
            else:
                color = COLORS["accent"]
                tip = "Check for updates"
            btn.setIcon(icon("download", 18, color))
            btn.setToolTip(tip)
            btn.setProperty("update_available", bool(available))
            btn.setProperty("checking", bool(checking))
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()
        except Exception:
            pass

    def _mark_update_available(self, manifest):
        """Store an available update and turn the download icon green."""
        try:
            self._pending_update_manifest = dict(manifest or {})
        except Exception:
            self._pending_update_manifest = manifest
        self._update_available = True
        self._set_update_button_available(available=True)
        try:
            remote = (manifest or {}).get("version", "new version") if isinstance(manifest, dict) else "new version"
            self.status(f"Update available: {remote}")
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════
    #  UPDATE CHECKING
    # ═══════════════════════════════════════════════════════

    def _check_update_silent(self):
        self._update_prompt_shown = False  # fresh startup = allow prompt
        def _bg():
            try:
                manifest = check_update(silent=True)
                if manifest:
                    self._update_found.emit(manifest)
            except Exception as e:
                logger.error(f"Silent update check failed: {e}")
        threading.Thread(target=_bg, daemon=True).start()

    def _on_update_found(self, manifest):
        """Slot for _update_found signal — always runs on main thread."""
        self._set_update_done()
        # No popup on discovery: the toolbar download icon turns green and the
        # user can click it when ready to open the download window.
        self._mark_update_available(manifest)

    def _on_update_not_found(self):
        self._set_update_done()
        self._pending_update_manifest = None
        self._update_available = False
        self._set_update_button_available(available=False)
        self.status("No updates found")

    def _on_update_error(self, error_msg):
        self._set_update_done()
        self._set_update_button_available(available=bool(getattr(self, "_update_available", False)))
        self._on_close_update_dlg()
        QMessageBox.warning(self, "Update Check Failed", f"Could not check for updates:\n\n{error_msg}")

    def _on_close_update_dlg(self):
        if hasattr(self, '_update_dlg') and self._update_dlg:
            self._update_dlg.close()
            self._update_dlg = None
        if hasattr(self, '_update_bar'):
            self._update_bar = None
        if hasattr(self, '_update_info'):
            self._update_info = None
        try:
            self._download_progress.disconnect(self._on_download_progress)
        except Exception:
            pass

    def _on_download_progress(self, pct, txt):
        """Slot for _download_progress signal — always runs on main thread."""
        if hasattr(self, '_update_bar') and self._update_bar:
            self._update_bar.setValue(pct)
        if hasattr(self, '_update_info') and self._update_info:
            self._update_info.setText(txt)

    def _set_update_done(self):
        self._update_checking = False
        if not bool(getattr(self, "_update_available", False)):
            self._set_update_button_available(available=False)

    def _check_update_manual(self):
        if bool(getattr(self, "_update_available", False)) and getattr(self, "_pending_update_manifest", None):
            self._start_update_download(self._pending_update_manifest)
            return
        if getattr(self, "_update_checking", False):
            self.status("Already checking for updates")
            return
        self._update_checking = True
        self._update_prompt_shown = False
        self._set_update_button_available(checking=True)
        self.status("Checking for updates…")

        def _bg():
            try:
                manifest = check_update(silent=False)
            except Exception as e:
                self._update_error.emit(str(e))
                return
            if manifest:
                self._update_found.emit(manifest)
            else:
                error = get_last_update_error()
                if error:
                    self._update_error.emit(error)
                else:
                    self._update_not_found.emit()

        threading.Thread(target=_bg, daemon=True).start()
        # Safety net: reset flag after 30s so UI isn't stuck
        QTimer.singleShot(30000, lambda: self._set_update_done() if getattr(self, "_update_checking", False) else None)

    def _prompt_update(self, manifest):
        """Backwards-compatible discovery handler: mark available, no popup."""
        self._mark_update_available(manifest)

    def _start_update_download(self, manifest):
        try:
            if not manifest:
                self.status("No update is ready to download")
                return
            remote_ver = manifest.get("version", "unknown") if isinstance(manifest, dict) else "unknown"
            logger.info(f"Opening update download window for {remote_ver}")

            # Progress dialog
            self._update_dlg = QDialog(self)
            self._update_dlg.setWindowTitle("Updating MacroForge")
            self._update_dlg.setFixedSize(380, 140)
            self._update_dlg.setStyleSheet(f"QDialog {{ background-color: {COLORS['bg_secondary']}; }}")
            self._update_dlg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            lo = QVBoxLayout(self._update_dlg)
            lo.setContentsMargins(16, 16, 16, 16)
            lo.addWidget(QLabel(f"Downloading MacroForge {remote_ver}…"))
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setFixedHeight(8)
            lo.addWidget(bar)
            info = QLabel("Starting…")
            info.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px;")
            lo.addWidget(info)
            self._update_dlg.show()
            self._update_dlg.raise_()
            self._update_dlg.activateWindow()
            self._update_dlg.update()
            self._set_update_button_available(checking=True)
            QApplication.processEvents()

            # Store refs for signal-based updates (thread-safe)
            self._update_bar = bar
            self._update_info = info
            try:
                self._download_progress.disconnect(self._on_download_progress)
            except Exception:
                pass
            self._download_progress.connect(self._on_download_progress)

            def _on_progress(downloaded, total):
                pct = downloaded / total * 100 if total else 0
                mb_down = downloaded / (1024 * 1024)
                if total:
                    mb_total = total / (1024 * 1024)
                    txt = f"{mb_down:.1f} MB / {mb_total:.1f} MB  ({pct:.0f}%)"
                else:
                    txt = f"{mb_down:.1f} MB downloaded"
                self._download_progress.emit(int(pct), txt)

            def _download():
                try:
                    if perform_update(manifest, progress_cb=_on_progress):
                        self._close_update_dlg.emit()
                        self._do_exit.emit()
                    else:
                        self._close_update_dlg.emit()
                        self._update_error.emit("Download or installation failed. See debug log for details.")
                except Exception as e:
                    logger.error(f"perform_update failed: {e}")
                    self._close_update_dlg.emit()
                    self._update_error.emit(f"Update failed: {e}")
            threading.Thread(target=_download, daemon=True).start()
        except Exception as e:
            logger.error(f"_prompt_update crashed: {e}")
            self._update_prompt_shown = False

    # ═══════════════════════════════════════════════════════
    #  STATISTICS & STATUS
    # ═══════════════════════════════════════════════════════

    def _maybe_show_runtime_error(self, msg):
        msg = str(msg or "")
        if not getattr(self.engine, "running", False):
            return
        lower = msg.lower()
        severe = any(token in lower for token in ("engine error", "image search error", "action failed", "failed:", "stopped", "error after"))
        if not severe or msg == self._last_runtime_error or self._runtime_error_dialog_open:
            return
        self._last_runtime_error = msg
        self._show_runtime_error_dialog(msg)

    def _show_runtime_error_dialog(self, msg):
        if self._runtime_error_dialog_open:
            return
        self._runtime_error_dialog_open = True
        try:
            # Expand the current group so the problem row is visible before showing options.
            try:
                if 0 <= self.playing_index < self.action_model.rowCount():
                    meta = self._group_header_for_row(self.playing_index)
                    if meta and bool(getattr(meta["action"], "group_collapsed", False)):
                        meta["action"].group_collapsed = False
                        self.timeline.refresh()
            except Exception:
                pass
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("MacroForge runtime issue")
            box.setText("Playback reported a runtime issue.")
            box.setInformativeText(str(msg))
            stop_btn = box.addButton("Stop macro", QMessageBox.ButtonRole.DestructiveRole)
            inspector_btn = box.addButton("Open Inspector", QMessageBox.ButtonRole.ActionRole)
            log_btn = box.addButton("Show runtime log", QMessageBox.ButtonRole.ActionRole)
            ignore_btn = box.addButton("Ignore", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(ignore_btn)
            box.exec()
            clicked = box.clickedButton()
            if clicked is stop_btn:
                self.stop()
            elif clicked is inspector_btn:
                if 0 <= self.playing_index < self.action_model.rowCount():
                    self.select(self.playing_index)
                    self.timeline.ensure_visible(self.playing_index)
            elif clicked is log_btn:
                self.toggle_runtime_log_panel(True)
        finally:
            self._runtime_error_dialog_open = False

    def status(self, msg):
        full_msg = str(msg or "")
        max_chars = 43
        visible_msg = full_msg if len(full_msg) <= max_chars else (full_msg[: max_chars - 1].rstrip() + "…")
        # Thread-safe: always marshal Qt widget access to main thread
        def _update():
            self.status_text.setText(visible_msg)
            self.status_text.setToolTip(full_msg)
            # Keep the centered status capsule readable without letting it
            # crowd the profile/update/menu cluster on narrow windows.
            def _fit_status_pill_to_visible_text():
                self.status_pill.setFixedWidth(int(getattr(self, "_status_pill_fixed_width", 150)))
            try:
                if hasattr(self, "status_pill"):
                    _fit_status_pill_to_visible_text()
                self._update_toolbar_containment()
            except Exception:
                pass
            # Update status icon based on state
            msg_lower = full_msg.lower()
            C = COLORS
            if "ready" in msg_lower or "idle" in msg_lower:
                self.status_icon.setPixmap(icon("check", 16, C["success"]).pixmap(16, 16))
                self.status_icon.setVisible(True)
                self.status_dot.set_color(C["success"], glow=False)
            elif "playing" in msg_lower or "running" in msg_lower:
                self.status_icon.setPixmap(icon("play", 16, C["playing"]).pixmap(16, 16))
                self.status_icon.setVisible(True)
                self.status_dot.set_color(C["playing"], glow=True)
            elif "paused" in msg_lower:
                self.status_icon.setPixmap(icon("pause", 16, C["warning"]).pixmap(16, 16))
                self.status_icon.setVisible(True)
                self.status_dot.set_color(C["warning"], glow=False)
            elif "record" in msg_lower:
                self.status_icon.setPixmap(icon("record", 16, C["error"]).pixmap(16, 16))
                self.status_icon.setVisible(True)
                self.status_dot.set_color(C["error"], glow=True)
            elif "error" in msg_lower or "failed" in msg_lower:
                self.status_icon.setPixmap(icon("cross", 16, C["error"]).pixmap(16, 16))
                self.status_icon.setVisible(True)
                self.status_dot.set_color(C["error"], glow=True)
            elif "saved" in msg_lower or "imported" in msg_lower or "applied" in msg_lower:
                self.status_icon.setPixmap(icon("save", 16, C["accent"]).pixmap(16, 16))
                self.status_icon.setVisible(True)
                self.status_dot.set_color(C["accent"], glow=False)
            else:
                self.status_icon.setVisible(False)
                self.status_dot.set_color(C["text_dim"], glow=False)
            self._maybe_show_runtime_error(full_msg)
        QTimer.singleShot(0, _update)
        logger.info(full_msg)

    def _invalidate_seq_dur(self):
        self._seq_dur_cache = sum(
            float(getattr(a, "duration", 0.0) or 0.0)
            for a in self.action_model.actions()
            if bool(getattr(a, "enabled", True)) and not (a.is_group() or a.is_loop() or a.is_condition())
        )
        self._update_macro_summary()

    def _update_macro_summary(self):
        if not hasattr(self, "macro_summary"):
            return
        actions = self.action_model.actions()
        image_checks = sum(1 for action in actions if action.is_image())
        groups = sum(1 for action in actions if action.is_group())
        loops = sum(1 for action in actions if action.is_loop())
        disabled = sum(1 for action in actions if not bool(getattr(action, "enabled", True)))
        duration = sum(
            float(getattr(action, "duration", 0.0) or 0.0)
            for action in actions
            if bool(getattr(action, "enabled", True)) and not (action.is_group() or action.is_loop() or action.is_condition())
        )
        duration_text = f"{duration:.0f}s" if abs(duration - round(duration)) < 0.1 else f"{duration:.1f}s"
        parts = [f"{len(actions)} rows", f"{image_checks} image", f"{groups} groups", f"{loops} loops", f"~{duration_text}"]
        if disabled:
            parts.insert(-1, f"{disabled} disabled")
        self.macro_summary.setText(" · ".join(parts))

    def _set_playback_collapsed(self, collapsed, auto=False):
        collapsed = bool(collapsed)
        auto = bool(auto)
        if auto and bool(getattr(self, "_bottom_panel_locked", False)):
            return
        if auto:
            self._playback_auto_collapsed = collapsed
        else:
            self._playback_user_collapsed = collapsed
            self._playback_auto_collapsed = False
        self._playback_collapsed = collapsed
        self.playback_dock.setVisible(not collapsed)
        self.playback_restore_btn.setVisible(collapsed)
        self.playback_panel.setFixedHeight(36 if collapsed else 188)
        if hasattr(self, "_apply_panel_size_locks"):
            self._apply_panel_size_locks()

    @staticmethod
    def _format_hms(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h}:{m:02d}:{s:02d}"

    def update_statistics(self, immediate=False):
        seq_dur = getattr(self, '_seq_dur_cache', 0.0)
        loops_done = getattr(self.engine, 'loops_completed_count', 0)
        session_time = seq_dur * loops_done

        self._stat_actions.setText(str(self.actions_played))
        self._stat_loops.setText(str(loops_done))
        self._stat_seq.setText(f"{seq_dur:.1f}s")
        self._stat_time.setText(self._format_hms(session_time))

    # ═══════════════════════════════════════════════════════
    #  HOTKEYS & SYSTRAY
    # ═══════════════════════════════════════════════════════

    def _setup_hotkeys(self):
        # DISABLED — pynput global hooks interfere with Qt modal dialogs
        logger.info("Hotkeys disabled (pynput causes Qt dialog crashes)")
        pass

    def _hotkey_toggle_play(self):
        if self.engine.running:
            self.stop()
        else:
            self.start()

    def _hotkey_record(self):
        self._toggle_record()

    def _setup_tray(self):
        try:
            from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
            from PyQt6.QtGui import QIcon
            self._tray_menu = QMenu()
            self._tray_menu.addAction("Show", self.showNormal)
            self._tray_menu.addAction("Quit", self._real_exit)
            self._tray_icon = QSystemTrayIcon(self)
            self._tray_icon.setContextMenu(self._tray_menu)
            self._tray_icon.setIcon(self.windowIcon())
            self._tray_icon.activated.connect(self._tray_activated)
            self._tray_icon.show()
        except Exception as e:
            logger.debug(f"Tray not available: {e}")

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.showNormal()

    # ═══════════════════════════════════════════════════════
    #  UTILITIES
    # ═══════════════════════════════════════════════════════

    def refresh(self):
        try:
            # Keep one authoritative backing list. The timeline view already uses
            # self.action_model; resetting it from engine.actions can resurrect a
            # stale list after dialog edits/captures and make new image actions vanish.
            self._normalize_groups()
            self.engine.actions = self.action_model.actions()
            self._invalidate_seq_dur()
            self.timeline.refresh()
            self.update_statistics()
        except Exception:
            logger.exception("refresh() crashed")

    def run_clean_release_builder(self):
        """Run the clean source ZIP builder from the app menu."""
        script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "clean_release.py"))
        if not os.path.exists(script):
            QMessageBox.warning(self, "Clean release", "clean_release.py was not found.")
            return
        try:
            result = subprocess.run([sys.executable, script, "--source-only"], cwd=os.path.dirname(script), capture_output=True, text=True, timeout=90)
            if result.returncode != 0:
                QMessageBox.critical(self, "Clean release failed", result.stderr or result.stdout or "Unknown build error")
                return
            self.status("Clean source ZIP built in dist")
            QMessageBox.information(self, "Clean release", result.stdout.strip() or "Clean source ZIP built in dist.")
        except Exception as e:
            QMessageBox.critical(self, "Clean release failed", str(e))

    def open_debug_viewer(self):
        try:
            from debugger import DebugViewer
            dv = DebugViewer(self)
            dv.show()
        except Exception as e:
            logger.error(f"Debug viewer: {e}")

    def open_settings_dialog(self):
        from ui.dialogs.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self, self.settings_manager)
        dlg.exec()

    # ═══════════════════════════════════════════════════════
    #  DIALOGS
    # ═══════════════════════════════════════════════════════

    def _open_key_dialog(self):
        try:
            from ui.dialogs.key_dialog import KeyDialog
            dlg = KeyDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                act = dlg.get_action()
                if act:
                    self._stamp_action_environment(act)
                    self.history.push(self.action_model.actions())
                    self.action_model.add_action(act)
                    self.active_index = len(self.action_model.actions()) - 1
                    self.timeline.ensure_visible(self.active_index)
                    self.save_session()
                    self.status(f"Added key: {act.key}")
        except Exception as e:
            logger.error(f"_open_key_dialog: {e}")
            raise

    def _open_click_dialog(self):
        try:
            from ui.dialogs.click_dialog import ClickDialog
            dlg = ClickDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                act = dlg.get_action()
                if act:
                    self._stamp_action_environment(act)
                    self.history.push(self.action_model.actions())
                    self.action_model.add_action(act)
                    self.active_index = len(self.action_model.actions()) - 1
                    self.timeline.ensure_visible(self.active_index)
                    self.save_session()
                    self.status("Added click")
        except Exception as e:
            logger.error(f"_open_click_dialog: {e}")
            raise

    def _open_pause_dialog(self):
        try:
            from ui.dialogs.pause_dialog import PauseDialog
            dlg = PauseDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                act = dlg.get_action()
                if act:
                    self._stamp_action_environment(act)
                    self.history.push(self.action_model.actions())
                    self.action_model.add_action(act)
                    self.active_index = len(self.action_model.actions()) - 1
                    self.timeline.ensure_visible(self.active_index)
                    self.save_session()
                    self.status("Added delay")
        except Exception as e:
            logger.error(f"_open_pause_dialog: {e}")
            raise

    def _open_image_dialog(self):
        try:
            logger.info("_open_image_dialog: START")
            from ui.dialogs.image_dialog import ImageDialog
            logger.info("_open_image_dialog: imported")
            dlg = ImageDialog(self)
            logger.info("_open_image_dialog: dialog created")
            rc = dlg.exec()
            logger.info(f"_open_image_dialog: dialog returned rc={rc}")
            if rc:
                logger.info("_open_image_dialog: calling get_action")
                act = dlg.get_action()
                logger.info(f"_open_image_dialog: get_action done act={act is not None}")
                if act is not None:
                    self._stamp_action_environment(act)
                    logger.info("_open_image_dialog: pushing history")
                    self.history.push(self.action_model.actions())
                    logger.info("_open_image_dialog: adding action to model")
                    self.action_model.add_action(act)
                    self.active_index = len(self.action_model.actions()) - 1
                    logger.info("_open_image_dialog: calling ensure_visible")
                    self.timeline.ensure_visible(self.active_index)
                    logger.info("_open_image_dialog: calling save_session")
                    self.save_session()
                    self.status("Added image search")
                    logger.info("_open_image_dialog: DONE")
            else:
                logger.info("_open_image_dialog: dialog cancelled/rejected")
        except Exception:
            logger.exception("_open_image_dialog crashed")

    def _open_key_editor(self, index):
        from ui.dialogs.key_dialog import KeyDialog
        dlg = KeyDialog(self, existing=self.action_model.get(index))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            act = dlg.get_action()
            if act:
                self._stamp_action_environment(act)
                self.history.push(self.action_model.actions())
                self.action_model.replace_action(index, act)
                self.refresh()
                self.save_session()
                self.status("Key action updated")

    def _open_click_editor(self, index):
        from ui.dialogs.click_dialog import ClickDialog
        dlg = ClickDialog(self, existing=self.action_model.get(index))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            act = dlg.get_action()
            if act:
                self._stamp_action_environment(act)
                self.history.push(self.action_model.actions())
                self.action_model.replace_action(index, act)
                self.refresh()
                self.save_session()
                self.status("Click action updated")

    def _open_pause_editor(self, index):
        from ui.dialogs.pause_dialog import PauseDialog
        dlg = PauseDialog(self, existing=self.action_model.get(index))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            act = dlg.get_action()
            if act:
                self._stamp_action_environment(act)
                self.history.push(self.action_model.actions())
                self.action_model.replace_action(index, act)
                self.refresh()
                self.save_session()
                self.status("Delay action updated")

    def _open_image_editor(self, index):
        from ui.dialogs.image_dialog import ImageDialog
        dlg = ImageDialog(self, existing=self.action_model.get(index))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            act = dlg.get_action()
            if act:
                self._stamp_action_environment(act)
                self.history.push(self.action_model.actions())
                self.action_model.replace_action(index, act)
                self.refresh()
                if index == self.active_index:
                    self._set_image_inspector_preview(act)
                self.save_session()
                self.status("Image action updated")


    def _open_condition_dialog(self):
        try:
            from ui.dialogs.condition_dialog import ConditionDialog
            dlg = ConditionDialog(self, row_count=self.action_model.rowCount())
            if dlg.exec() == QDialog.DialogCode.Accepted:
                act = dlg.get_action()
                if act:
                    self.history.push(self.action_model.actions(), self._timeline_history_state())
                    self.action_model.add_action(act)
                    self.active_index = len(self.action_model.actions()) - 1
                    self.timeline.ensure_visible(self.active_index)
                    self.refresh()
                    self.save_session()
                    self.status("Added condition block")
        except Exception:
            logger.exception("_open_condition_dialog crashed")

    def _open_loop_dialog(self):
        try:
            from ui.dialogs.loop_dialog import LoopDialog
            current = self.active_index if self.active_index >= 0 else self.action_model.rowCount()
            dlg = LoopDialog(self, row_count=max(1, self.action_model.rowCount() + 1), current_index=current)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                act = dlg.get_action()
                if act:
                    self.history.push(self.action_model.actions(), self._timeline_history_state())
                    self.action_model.add_action(act)
                    self.active_index = len(self.action_model.actions()) - 1
                    self.timeline.ensure_visible(self.active_index)
                    self.refresh()
                    self.save_session()
                    self.status("Added loop block")
        except Exception:
            logger.exception("_open_loop_dialog crashed")

    def _open_group_dialog(self):
        try:
            from ui.dialogs.group_dialog import GroupDialog
            dlg = GroupDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                act = dlg.get_action()
                if act:
                    self.history.push(self.action_model.actions(), self._timeline_history_state())
                    insert_at = self.active_index if 0 <= self.active_index < self.action_model.rowCount() else self.action_model.rowCount()
                    self.action_model.insert_action(insert_at, act)
                    self.active_index = insert_at
                    self.timeline.ensure_visible(self.active_index)
                    self.refresh()
                    self.save_session()
                    self.status("Added action group")
        except Exception:
            logger.exception("_open_group_dialog crashed")

    def _open_condition_editor(self, index):
        from ui.dialogs.condition_dialog import ConditionDialog
        dlg = ConditionDialog(self, existing=deepcopy(self.action_model.get(index)), row_count=self.action_model.rowCount())
        if dlg.exec() == QDialog.DialogCode.Accepted:
            act = dlg.get_action()
            if act:
                self.history.push(self.action_model.actions(), self._timeline_history_state())
                self.action_model.replace_action(index, act)
                self.refresh()
                self.save_session()
                self.status("Condition block updated")

    def _open_loop_editor(self, index):
        from ui.dialogs.loop_dialog import LoopDialog
        dlg = LoopDialog(self, existing=deepcopy(self.action_model.get(index)), row_count=self.action_model.rowCount(), current_index=index)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            act = dlg.get_action()
            if act:
                self.history.push(self.action_model.actions(), self._timeline_history_state())
                self.action_model.replace_action(index, act)
                self.refresh()
                self.save_session()
                self.status("Loop block updated")

    def _open_group_editor(self, index):
        from ui.dialogs.group_dialog import GroupDialog
        dlg = GroupDialog(self, existing=deepcopy(self.action_model.get(index)))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            act = dlg.get_action()
            if act:
                self.history.push(self.action_model.actions(), self._timeline_history_state())
                self.action_model.replace_action(index, act)
                self.refresh()
                self.save_session()
                self.status("Action group updated")

    def _real_exit(self):
        try:
            self._do_save_session()
            self._write_recovery_snapshot(clean_shutdown=True)
        except Exception:
            pass
        # try:
        #     stop_hotkeys()
        # except Exception:
        #     pass
        try:
            if self._tray_icon:
                self._tray_icon.hide()
                self._tray_icon = None
        except Exception:
            pass
        try:
            for w in QApplication.topLevelWidgets():
                w.close()
        except Exception:
            pass
        try:
            QApplication.quit()
        except Exception:
            pass

    def closeEvent(self, event):
        self._do_save_session()
        self._write_recovery_snapshot(clean_shutdown=True)
        # try:
        #     stop_hotkeys()
        # except Exception:
        #     pass
        event.accept()

    def undo(self):
        if not self.history.can_undo():
            self.status("Nothing to undo")
            return
        result = self.history.undo(self.action_model.actions(), self._timeline_history_state())
        if result is None:
            return
        actions, timeline_state = result
        self.action_model.set_actions(actions)
        self.engine.actions = self.action_model.actions()
        self._restore_timeline_history_state(timeline_state)
        self.refresh()
        if 0 <= self.active_index < self.action_model.rowCount():
            self.timeline.ensure_visible_if_needed(self.active_index)
            self.timeline.flash_drop(self.active_index)
        self.update_statistics()
        self.save_session()
        self.status("Undone")

    def redo(self):
        if not self.history.can_redo():
            self.status("Nothing to redo")
            return
        result = self.history.redo(self.action_model.actions(), self._timeline_history_state())
        if result is None:
            return
        actions, timeline_state = result
        self.action_model.set_actions(actions)
        self.engine.actions = self.action_model.actions()
        self._restore_timeline_history_state(timeline_state)
        self.refresh()
        if 0 <= self.active_index < self.action_model.rowCount():
            self.timeline.ensure_visible_if_needed(self.active_index)
            self.timeline.flash_drop(self.active_index)
        self.update_statistics()
        self.save_session()
        self.status("Redone")

    def _timeline_history_state(self):
        return {
            "active_index": self.active_index,
            "selected_indices": sorted(self.timeline.selected_indices),
            "next_index": self.timeline.next_index,
            "image_states": dict(self.timeline.image_states),
            "scroll_position": self.timeline.scroll_position(),
        }

    def _restore_timeline_history_state(self, state):
        if not state:
            self.active_index = -1
            self.timeline.set_active(-1)
            return
        self.active_index = int(state.get("active_index", -1))
        self.timeline.image_states = dict(state.get("image_states", {}))
        self.timeline.next_index = int(state.get("next_index", -1))
        scroll_position = int(state.get("scroll_position", 0))
        selected = set(state.get("selected_indices", []))
        if 0 <= self.active_index < self.action_model.rowCount():
            self.timeline.set_active(self.active_index)
        else:
            self.timeline.set_active(-1)
            self.timeline.selected_indices = selected
        self.timeline.restore_scroll_position(scroll_position)
        self.timeline.viewport().update()
