"""MacroForge main window."""
import os
import sys
import time
import json
import csv
import queue
import ctypes
import threading
from copy import deepcopy

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QGridLayout, QSizePolicy,
    QLabel, QPushButton, QComboBox, QLineEdit, QCheckBox,
    QProgressBar, QFrame, QMenu,
    QSpinBox, QDoubleSpinBox,
    QFileDialog, QMessageBox,
    QDialog, QPlainTextEdit
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QPen, QKeySequence, QShortcut, QIcon

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

    def __init__(self, profile_manager=None, settings_manager=None):
        super().__init__()
        self.setWindowTitle("MacroForge")
        self.setMinimumSize(760, 1050)
        self.resize(760, 1050)
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

    def _make_playback_panel(self):
        from ui.playback_panel import make_playback_panel
        return make_playback_panel(self)

    def _make_stat_chip(self, icon_name, title, value, color, tooltip):
        """Static bottom-panel stat chip: clear icon + value only."""
        C = COLORS
        chip = QFrame()
        chip.setObjectName("mf2_stat_chip")
        chip.setToolTip(f"{title}: {tooltip}")
        chip.setFixedWidth({"Played": 58, "Loops": 58, "Seq": 82, "Time": 98}.get(title, 60))
        chip.setFixedHeight(36)
        chip.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        chip.setStyleSheet(
            f"QFrame#mf2_stat_chip {{ background-color: {C['bg_card']}; "
            f"border: 1px solid {C['border']}; border-radius: 6px; }}"
            f"QFrame#mf2_stat_chip:hover {{ border-color: {color}; }}"
        )

        lo = QHBoxLayout(chip)
        lo.setContentsMargins(5, 3, 5, 3)
        lo.setSpacing(4)

        ico = QLabel()
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setFixedSize(18, 18)
        ico.setPixmap(icon(icon_name, 17, color).pixmap(17, 17))
        lo.addWidget(ico)

        value_lbl = QLabel(value)
        value_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        value_lbl.setStyleSheet(
            f"color: {C['text']}; font-size: 12px; font-weight: 950; background: transparent;"
        )
        lo.addWidget(value_lbl)
        return chip, value_lbl

    def _add_btn(self, text, callback, color, layout, icon_name="plus"):
        type_map = {"key": "add_key", "click": "add_click", "delay": "add_pause",
                    "image": "add_image", "condition": "add_condition",
                    "loop": "add_loop", "folder": "add_group"}
        obj = type_map.get(icon_name, "action_add")
        btn = QPushButton(text)
        btn.setObjectName(obj)
        btn.setIcon(icon(icon_name, 16, color))
        btn.setIconSize(QSize(16, 16))
        btn.setFixedHeight(46)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        tint = color.lstrip("#")
        btn.setStyleSheet(
            f"QPushButton {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #99{tint}, stop:1 #000000); "
            f"color: {COLORS['text_inverse']}; border: 1px solid #99{tint}; border-radius: 10px; padding: 7px 12px; "
            f"text-align: center; font-size: 14px; font-weight: 700; }}"
            f"QPushButton:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {color}, stop:1 #000000); "
            f"border-color: {color}; }}"
            f"QPushButton:pressed {{ background: #55{tint}; }}"
        )
        btn.clicked.connect(callback)
        layout.addWidget(btn)

    def _label_row(self, text, widget):
        row = QFrame()
        lo = QHBoxLayout(row)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.addWidget(QLabel(text))
        lo.addWidget(widget)
        return row

    def _show_inspector(self, show=True, action_type="key"):
        for w in (self.insp_key, self.insp_pause, self.insp_click, self.insp_image):
            w.setVisible(False)
        self.insp_empty.setVisible(False)
        if show:
            mapping = {
                "key": self.insp_key,
                "pause": self.insp_pause,
                "click": self.insp_click,
                "image": self.insp_image,
            }
            pane = mapping.get(action_type)
            if pane is not None:
                pane.setVisible(True)
            else:
                self.insp_empty.setText("Use Edit for this block")
                self.insp_empty.setVisible(True)

    # ═══════════════════════════════════════════════════════
    #  KEYBOARD SHORTCUTS
    # ═══════════════════════════════════════════════════════

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Z"), self, self.undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, self.redo)
        QShortcut(QKeySequence("Ctrl+C"), self, self.copy_action)
        QShortcut(QKeySequence("Ctrl+V"), self, self.paste_action)
        QShortcut(QKeySequence("Ctrl+D"), self, self._duplicate_inspector)
        QShortcut(QKeySequence("Delete"), self, self._delete_selected)
        QShortcut(QKeySequence("Ctrl+Delete"), self, self._delete_selected)
        QShortcut(QKeySequence("Escape"), self, self._deselect)
        QShortcut(QKeySequence("Ctrl+S"), self, lambda: (self._do_save_session(), self.status("Session saved")))
        QShortcut(QKeySequence("Ctrl+F"), self, lambda: self.timeline.setFocus())
        QShortcut(QKeySequence("Ctrl+Enter"), self, self.test_from_selected_row)
        QShortcut(QKeySequence("Ctrl+E"), self, self.open_macro_editor)
        QShortcut(QKeySequence("Ctrl+Shift+P"), self, self.open_preflight_report)

    def _deselect(self):
        self.select(-1)
        self.timeline.selected_indices.clear()
        self.timeline.refresh()

    def _delete_selected(self):
        self.delete_action(self.active_index)

    # ═══════════════════════════════════════════════════════
    #  TIMELINE CONNECTIONS
    # ═══════════════════════════════════════════════════════

    def _setup_timeline_connections(self):
        self.timeline.action_clicked.connect(self.select)
        self.timeline.action_double_clicked.connect(self._open_active_dialog)
        self.timeline.action_dragged.connect(self.move_action_to)
        self.timeline.action_context_menu.connect(self._timeline_context_menu)

    def _timeline_context_menu(self, index, pos):
        if index < 0 or index >= self.action_model.rowCount():
            return
        self.select(index)
        m = QMenu(self)
        C = COLORS
        m.setStyleSheet(f"""
            QMenu {{ background-color: {C['bg_tertiary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 10px; padding: 6px; }}
            QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
            QMenu::item:selected {{ background-color: {C['bg_hover']}; color: {C['accent']}; }}
        """)
        m.addAction("Edit", lambda: self._open_active_dialog(index))
        m.addAction("Duplicate", lambda: self.duplicate_action(index))
        m.addAction("Enable/Disable", lambda: self.toggle_action_enabled(index))
        m.addSeparator()
        m.addAction("Run from this row", self.test_from_selected_row)
        m.addAction("Preview image confidence", lambda: self.open_image_confidence_preview(index))
        m.addSeparator()
        sorting_locked = self.engine.running or self.timeline.playing_index >= 0
        move_up = m.addAction("Move Up", lambda: self.move_action(index, -1))
        move_down = m.addAction("Move Down", lambda: self.move_action(index, 1))
        move_up.setEnabled(not sorting_locked and index > 0)
        move_down.setEnabled(not sorting_locked and index < self.action_model.rowCount() - 1)
        m.addSeparator()
        m.addAction("Delete", lambda: self.delete_action(index))
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
                settings = session.get("settings", {})
                self.loops_spin.setValue(int(settings.get("loops", 1)))
                self.speed_combo.setCurrentText(f"{float(settings.get('speed', 1.0)):.1f}x")
                self.inf_check.setChecked(settings.get("infinite_loop", False))
                self.human_check.setChecked(settings.get("human_curve", True))
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
        self._save_session_timer.start()

    def _do_save_session(self):
        settings = {
            "loops": self.loops_spin.value(),
            "speed": float(self.speed_combo.currentText().replace("x", "")),
            "infinite_loop": self.inf_check.isChecked(),
            "human_curve": self.human_check.isChecked(),
            "zoom": self.timeline.zoom,
        }
        self.session_manager.save_profile(self.action_model.actions(), settings)
        self._write_recovery_snapshot(clean_shutdown=False)
        self._save_window_geometry()

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
        self.resize(760, 1050)

    def _refresh_profile_btn(self):
        if hasattr(self, "profile_btn"):
            self.profile_btn.setText(f"{self.session_manager.active}  \u25be")

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

    # ═══════════════════════════════════════════════════════
    #  SELECTION & EDITING
    # ═══════════════════════════════════════════════════════

    def select(self, index):
        if index is None or index < 0 or index >= self.action_model.rowCount():
            self.active_index = -1
            self.timeline.set_active(-1)
            self.timeline.selected_indices.clear()
            self.inspector_selector.clear()
            self.inspector_selector.addItem("Select an action")
            self._show_inspector(False)
            return
        self.active_index = index
        self.timeline.selected_indices.clear()
        self.timeline.set_active(index)
        action = self.action_model.get(index)
        self.inspector_selector.clear()
        self.inspector_selector.addItem(getattr(action, "label", "") or getattr(action, "key", "") or f"Action {index + 1}")
        self._show_inspector(True, action.action_type)
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
            self.ii_sim.setText(str(getattr(action, 'similarity', 0.8)))
            self.ii_wait.setText(str(getattr(action, 'wait_timeout', 10.0)))

    def _apply_inspector(self):
        if self.active_index < 0 or self.active_index >= self.action_model.rowCount():
            QMessageBox.warning(self, "No Selection", "Please select an action first")
            return
        try:
            action = self.action_model.get(self.active_index)
            self.history.push(self.action_model.actions())
            if action.action_type == "key":
                action.key = self.ik_key.text().strip()
                action.duration = float(self.ik_dur.text())
                action.hold_mode = self.ik_hold.isChecked()
                action.repeat_count = max(1, int(self.ik_repeat.text() or 1))
                action.label = self.ik_label.text().strip()
            elif action.action_type == "pause":
                action.duration = float(self.ip_dur.text())
                action.label = self.ip_label.text().strip()
            elif action.action_type == "click":
                action.click_x = int(self.ic_x.text())
                action.click_y = int(self.ic_y.text())
                action.click_button = self.ic_btn.currentText()
                action.click_rand_radius = int(self.ic_rand.text() or 0)
                action.repeat_count = max(1, int(self.ic_repeat.text() or 1))
                action.label = self.ic_label.text().strip()
            elif action.action_type == "image":
                action.similarity = float(self.ii_sim.text())
                action.wait_timeout = float(self.ii_wait.text())
            self.refresh()
            self.update_statistics()
            self.save_session()
            self.status("Applied changes")
        except ValueError as e:
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
        selected = self.timeline.selected_indices
        if selected:
            indices = sorted(selected, reverse=True)
            if not indices or indices[0] >= self.action_model.rowCount():
                self.timeline.selected_indices.clear()
                return
            self.history.push(self.action_model.actions())
            for idx in indices:
                if 0 <= idx < self.action_model.rowCount():
                    self.action_model.remove_action(idx)
            self.active_index = -1
            self.timeline.selected_indices.clear()
            self.refresh()
            self.update_statistics()
            self.save_session()
            self.status(f"Deleted {len(indices)} actions")
            return
        if index < 0 or index >= self.action_model.rowCount():
            return
        self.history.push(self.action_model.actions())
        self.action_model.remove_action(index)
        self.active_index = -1
        self.timeline.selected_indices.clear()
        self.refresh()
        self.update_statistics()
        self.save_session()
        self.status("Deleted action")

    def duplicate_action(self, index):
        if index < 0 or index >= self.action_model.rowCount():
            self.status("No action selected to duplicate")
            return
        self.history.push(self.action_model.actions())
        action = deepcopy(self.action_model.get(index))
        insert_at = index + 1
        self.action_model.insert_action(insert_at, action)
        self.active_index = index + 1
        self.refresh()
        self.update_statistics()
        self.save_session()
        self.status("Duplicated action")

    def toggle_action_enabled(self, index):
        if index < 0 or index >= self.action_model.rowCount():
            return
        self.history.push(self.action_model.actions(), self._timeline_history_state())
        action = self.action_model.get(index)
        action.enabled = not bool(getattr(action, "enabled", True))
        self.refresh()
        self.update_statistics()
        self.save_session()
        self.status("Enabled action" if action.enabled else "Disabled action")

    def move_action(self, index, direction):
        if self.engine.running or self.timeline.playing_index >= 0:
            self.status("Stop playback before reordering actions")
            return
        if index < 0 or index >= self.action_model.rowCount():
            return
        new_index = index + direction
        if new_index < 0 or new_index >= self.action_model.rowCount():
            return
        scroll_position = self.timeline.scroll_position()
        self.history.push(self.action_model.actions(), self._timeline_history_state())
        self.action_model.move_action(index, new_index)
        self.timeline.remap_after_move(index, new_index)
        self.active_index = new_index
        self.refresh()
        self.timeline.set_active(new_index)
        self.timeline.restore_scroll_position(scroll_position)
        self.timeline.flash_drop(new_index)
        self.save_session()
        self.status("Moved action")

    def move_action_to(self, index, target_index):
        if self.engine.running or self.timeline.playing_index >= 0:
            self.status("Stop playback before reordering actions")
            return
        if index < 0 or index >= self.action_model.rowCount():
            return
        if target_index < 0 or target_index >= self.action_model.rowCount():
            return
        scroll_position = self.timeline.scroll_position()
        self.history.push(self.action_model.actions(), self._timeline_history_state())
        self.action_model.move_action(index, target_index)
        self.timeline.remap_after_move(index, target_index)
        self.active_index = target_index
        self.refresh()
        self.timeline.set_active(target_index)
        self.timeline.restore_scroll_position(scroll_position)
        self.timeline.flash_drop(target_index)
        self.update_statistics(immediate=True)
        self.save_session()
        self.status("Moved action")

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

    def run_preflight_check(self, show_success=True, allow_warning_prompt=True):
        """Validate the visible timeline before playback.

        Returns True when playback may continue. Errors block playback;
        warnings are shown but can be continued through.
        """
        actions = self.action_model.actions()
        errors = []
        warnings = []
        total = len(actions)

        if total <= 0:
            errors.append("Timeline is empty.")

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
                    errors.append(f"{prefix}: loop count must be 2 or higher.")
                if not (0 <= target < idx - 1):
                    errors.append(f"{prefix}: loop target must be an earlier row.")
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
        self.run_preflight_check(show_success=False, allow_warning_prompt=False)
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
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.status_dot.set_color(COLORS["playing"], glow=True)
        self.status_text.setText("Running block")
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

    def _recovery_path(self):
        base = getattr(self.session_manager, "base_dir", os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, "recovery")
        os.makedirs(path, exist_ok=True)
        return os.path.join(path, "last_session.json")

    def _write_recovery_snapshot(self, clean_shutdown=False):
        try:
            payload = self._macro_export_payload()
            payload["clean_shutdown"] = bool(clean_shutdown)
            payload["active_profile"] = self.session_manager.active
            with open(self._recovery_path(), "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
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
        if not self.run_preflight_check(show_success=False, allow_warning_prompt=True):
            return
        self._diag(f"[PLAY] Starting macro: {len(self.engine.actions)} actions, loops={self.loops_spin.value()}, sim={self.sim_check.isChecked()}")
        self.actions_played = 0
        self.session_elapsed_time = 0.0
        self.session_start_time = time.time()
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.status_dot.set_color(COLORS["playing"], glow=True)
        self.status_text.setText("Playing")
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
        self.status_text.setText("Ready")
        if self.session_start_time:
            self.session_elapsed_time += time.time() - self.session_start_time
            self.session_start_time = None
        self.update_statistics(immediate=True)

    def _status_cb(self, msg):
        self._diag(f"[STATUS] {msg}")
        self._status_msg.emit(msg)

    def _play_cb(self, idx, dur):
        self._play_action.emit(idx, dur)

    def _do_play_cb(self, idx, dur):
        if self._run_index_map and 0 <= idx < len(self._run_index_map):
            display_idx = self._run_index_map[idx]
        else:
            display_idx = self._single_test_index if self._single_test_active and idx == 0 else self._run_from_index + idx
        self.playing_index = display_idx
        self.actions_played += 1
        speed = max(self.engine.speed_multiplier, 0.01)
        adjusted_dur = dur / speed
        self.timeline.set_playing(display_idx, adjusted_dur)
        self._diag(f"[PLAY] Timeline row {display_idx + 1} active for ~{adjusted_dur:.2f}s")
        self.update_statistics()

    def _image_match_cb(self, idx, state):
        self._image_match_state.emit(idx, state)

    def _do_image_match_state(self, idx, state):
        if self._run_index_map and 0 <= idx < len(self._run_index_map):
            display_idx = self._run_index_map[idx]
        else:
            display_idx = self._single_test_index if self._single_test_active and idx == 0 else self._run_from_index + idx
        self.timeline.set_image_state(display_idx, state)

    def _pause_cb(self, paused):
        self._pause_state.emit(paused)

    def _do_pause_cb(self, paused):
        self.timeline.set_paused(paused)
        if paused:
            self.pause_btn.setIcon(icon("play", 14, COLORS["text_inverse"]))
            self.pause_btn.setToolTip("Resume (Esc)")
            self.status_text.setText("Paused")
        else:
            self.pause_btn.setIcon(icon("pause", 14, COLORS["text_inverse"]))
            self.pause_btn.setToolTip("Pause (Esc)")
            self.status_text.setText("Running")

    def _complete_cb(self):
        self._complete.emit()

    def _do_complete_cb(self):
        was_single_test = self._single_test_active
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.playing_index = -1
        self.timeline.clear_playing()
        self.progress_bar.setValue(100)
        self.progress_label.setText("100%")
        self.status_dot.set_color(COLORS["text_dark"])
        self.status_text.setText("Test done" if was_single_test else "Finished")
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

    def _before_action_diag(self, action):
        self._diag(f"[ACTION] Preparing {self._action_diag_summary(action)}")

    def _after_action_diag(self, action):
        sim = " simulated" if getattr(self.engine, "simulation_mode", False) else " deployed"
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
        self.status_text.setText("Testing")

        self.engine.actions = [action]
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
        self.status_text.setText(f"Testing row {idx + 1}+")

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
            self.rec_pause_btn.setStyleSheet(f"background: {COLORS['playing']}; color: #fff; border-radius: 8px;")
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
        self.rec_btn.setText(" Stop")
        self.rec_btn.setStyleSheet(f"background-color: {COLORS['error']}; color: #fff; border-radius: 8px; padding: 6px 12px; font-weight: 600;")
        self.rec_pause_btn.setText(" Pause")
        self.rec_pause_btn.setEnabled(True)
        self.rec_pause_btn.setStyleSheet(f"background: {COLORS['playing']}; color: #fff; border-radius: 8px;")
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
        self.rec_btn.setStyleSheet("")
        self.rec_pause_btn.setText("")
        self.rec_pause_btn.setEnabled(False)
        self.rec_pause_btn.setStyleSheet("")
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
            "actions": [a.to_dict() for a in self.action_model.actions()],
        }

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
                if not isinstance(actions_data, list):
                    raise ValueError("Unsupported macro file format")
                self.history.push(self.action_model.actions(), self._timeline_history_state())
                self.action_model.clear()
                for action_data in actions_data:
                    self.action_model.add_action(Action.from_dict(action_data))
                self.active_index = -1
                self.timeline.refresh()
                self.refresh()
                self.update_statistics()
                self.save_session()
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
        self._prompt_update(manifest)

    def _on_update_not_found(self):
        self._set_update_done()
        self.status("No updates found")

    def _on_update_error(self, error_msg):
        self._set_update_done()
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

    def _check_update_manual(self):
        if getattr(self, "_update_checking", False):
            self.status("Already checking for updates")
            return
        self._update_checking = True
        self._update_prompt_shown = False  # allow re-prompt on fresh check
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
        try:
            # Allow re-prompting on a fresh check (flag is reset when check starts)
            if getattr(self, "_update_prompt_shown", False):
                logger.info("Update prompt already shown, skipping duplicate")
                return
            self._update_prompt_shown = True
            logger.info("Showing update prompt")

            remote_ver = manifest.get("version", "unknown")
            notes = manifest.get("notes", "")
            msg = f"A new version of MacroForge is available.\n\nCurrent: {VERSION}\nLatest: {remote_ver}"
            if notes:
                msg += f"\n\nRelease notes:\n{notes}"
            msg += "\n\nDownload and install now?"

            box = QMessageBox(self)
            box.setWindowTitle("Update Available")
            box.setText(msg)
            box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            box.setDefaultButton(QMessageBox.StandardButton.Yes)
            box.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            reply = box.exec()
            logger.info(f"Update prompt result: {reply}")

            if reply != QMessageBox.StandardButton.Yes:
                return

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

    def status(self, msg):
        # Thread-safe: always marshal Qt widget access to main thread
        def _update():
            self.status_text.setText(msg)
            # Update status icon based on state
            msg_lower = msg.lower()
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
        QTimer.singleShot(0, _update)
        logger.info(msg)

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

    def _set_playback_collapsed(self, collapsed):
        collapsed = bool(collapsed)
        self.playback_dock.setVisible(not collapsed)
        self.playback_restore_btn.setVisible(collapsed)
        self.playback_panel.setFixedHeight(36 if collapsed else 118)

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
            self.engine.actions = self.action_model.actions()
            self._invalidate_seq_dur()
            self.timeline.refresh()
            self.update_statistics()
        except Exception:
            logger.exception("refresh() crashed")

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
