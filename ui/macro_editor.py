"""Macro editor mode dialog.

This is intentionally table-based and compact so it fits MacroForge's current
single-window layout without forcing a full layout rewrite. It provides the
multi-action editing tools missing from the main sidebar while keeping the
runtime timeline as the source of truth.
"""

from __future__ import annotations

from copy import deepcopy

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from models import Action
from ui.icons import icon
from ui.theme import COLORS, TYPE_COLORS


def _kind(action: Action) -> str:
    if action.is_pause():
        return "pause"
    return getattr(action, "action_type", "key") or "key"


def _details(action: Action) -> str:
    kind = _kind(action)
    if kind == "key":
        return f"{action.key} · {float(action.duration or 0):.2f}s"
    if kind == "click":
        return f"{action.click_button} @ {action.click_x}, {action.click_y}"
    if kind == "pause":
        return f"Delay {float(action.duration or 0):.2f}s"
    if kind == "image":
        return f"confidence ≥ {int(float(action.similarity or 0.95) * 100)}% · wait {float(action.wait_timeout or 0):.1f}s"
    if kind == "condition":
        return f"{action.condition_type} · true→{action.condition_jump_true + 1 if action.condition_jump_true >= 0 else 'next'} · false→{action.condition_jump_false + 1 if action.condition_jump_false >= 0 else 'next'}"
    if kind == "loop":
        return f"x{getattr(action, 'loop_count', action.repeat_count)} → row {getattr(action, 'loop_target', -1) + 1 if getattr(action, 'loop_target', -1) >= 0 else 'unset'}"
    if kind == "group":
        return getattr(action, "group_name", "") or action.label or "Folder"
    return kind


class MacroEditorDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle("Macro Editor Mode")
        self.resize(880, 560)
        C = COLORS
        self.setStyleSheet(
            f"QDialog {{ background-color: {C['bg']}; color: {C['text']}; }}"
            f"QTableWidget {{ background-color: {C['bg_card']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 10px; gridline-color: {C['border']}; }}"
            f"QHeaderView::section {{ background-color: {C['bg_tertiary']}; color: {C['text_dim']}; border: none; border-bottom: 1px solid {C['border']}; padding: 6px; font-weight: 800; }}"
            f"QPushButton {{ background-color: {C['bg_card']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 8px; padding: 7px 10px; font-weight: 800; }}"
            f"QPushButton:hover {{ border-color: {C['accent']}; color: {C['accent']}; background-color: {C['bg_tertiary']}; }}"
            f"QPushButton:disabled {{ color: {C['text_dark']}; border-color: {C['border']}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("Macro Editor Mode")
        title.setStyleSheet(f"color: {C['text']}; font-size: 20px; font-weight: 950;")
        subtitle = QLabel("Multi-select rows to duplicate, delete, move, folder, enable/disable, bulk-adjust delay, or run a chosen section.")
        subtitle.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["#", "On", "Type", "Label", "Details", "Duration", "Screen"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._sync_main_selection)
        self.table.doubleClicked.connect(lambda idx: self.window._open_active_dialog(idx.row()))
        layout.addWidget(self.table, 1)

        row = QHBoxLayout()
        row.setSpacing(8)
        self._button(row, "Enable/Disable", "check", self.toggle_enabled, C["success"])
        self._button(row, "Duplicate", "duplicate", self.duplicate_selected, C["accent"])
        self._button(row, "Delete", "trash", self.delete_selected, C["error"])
        self._button(row, "Move Up", "chevron", lambda: self.move_selected(-1), C["text_dim"])
        self._button(row, "Move Down", "chevron", lambda: self.move_selected(1), C["text_dim"])
        self._button(row, "Folder", "folder", self.group_selected, C.get("group", C["neon_purple"]))
        self._button(row, "Bulk Delay", "clock", self.bulk_delay, C["pause"])
        row.addStretch()
        layout.addLayout(row)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        self._button(row2, "Run From Row", "play", self.run_from_first_selected, C["success"])
        self._button(row2, "Run Selected Block", "play", self.run_selected_block, C["success"])
        self._button(row2, "Image Preview", "image", self.image_preview, C["image"])
        row2.addStretch()
        done = QPushButton("Done")
        done.clicked.connect(self.accept)
        row2.addWidget(done)
        layout.addLayout(row2)

        self.reload()

    def _button(self, layout, text, icon_name, slot, color):
        btn = QPushButton(text)
        btn.setIcon(icon(icon_name, 14, color))
        btn.clicked.connect(slot)
        layout.addWidget(btn)
        return btn

    def _selected_rows(self):
        return sorted({idx.row() for idx in self.table.selectedIndexes()})

    def reload(self):
        actions = self.window.action_model.actions()
        self.table.setRowCount(len(actions))
        for row, action in enumerate(actions):
            kind = _kind(action)
            values = [
                str(row + 1),
                "Yes" if bool(getattr(action, "enabled", True)) else "No",
                kind.title(),
                getattr(action, "label", "") or getattr(action, "group_name", "") or getattr(action, "key", ""),
                _details(action),
                f"{float(getattr(action, 'duration', 0.0) or 0.0):.2f}s",
                self._screen_text(action),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col in (0, 1, 2, 5, 6):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if not bool(getattr(action, "enabled", True)):
                    item.setForeground(Qt.GlobalColor.gray)
                elif col == 2:
                    item.setForeground(Qt.GlobalColor.white)
                self.table.setItem(row, col, item)
        self.table.resizeRowsToContents()

    def _screen_text(self, action):
        w = int(getattr(action, "screen_width", 0) or 0)
        h = int(getattr(action, "screen_height", 0) or 0)
        if w and h:
            return f"{w}×{h}"
        return "—"

    def _commit(self, msg="Updated macro"):
        self.window.refresh()
        self.window.update_statistics(immediate=True)
        self.window.save_session()
        self.window.status(msg)
        self.reload()

    def _sync_main_selection(self):
        rows = self._selected_rows()
        self.window.timeline.selected_indices = set(rows)
        if len(rows) == 1:
            self.window.select(rows[0])
        else:
            self.window.timeline.viewport().update()

    def toggle_enabled(self):
        rows = self._selected_rows()
        if not rows:
            return
        actions = self.window.action_model.actions()
        self.window.history.push(actions, self.window._timeline_history_state())
        # If all selected are enabled, disable them; otherwise enable all.
        new_state = not all(bool(getattr(actions[r], "enabled", True)) for r in rows if 0 <= r < len(actions))
        for r in rows:
            if 0 <= r < len(actions):
                actions[r].enabled = new_state
        self._commit("Updated enabled state")

    def duplicate_selected(self):
        rows = self._selected_rows()
        if not rows:
            return
        actions = self.window.action_model.actions()
        self.window.history.push(actions, self.window._timeline_history_state())
        insert_at = rows[-1] + 1
        for offset, row in enumerate(rows):
            self.window.action_model.insert_action(insert_at + offset, deepcopy(actions[row]))
        self._commit(f"Duplicated {len(rows)} action(s)")

    def delete_selected(self):
        rows = self._selected_rows()
        if not rows:
            return
        if QMessageBox.question(self, "Delete Actions", f"Delete {len(rows)} selected action(s)?") != QMessageBox.StandardButton.Yes:
            return
        self.window.history.push(self.window.action_model.actions(), self.window._timeline_history_state())
        for row in sorted(rows, reverse=True):
            self.window.action_model.remove_action(row)
        self.window.active_index = -1
        self.window.timeline.selected_indices.clear()
        self._commit(f"Deleted {len(rows)} action(s)")

    def move_selected(self, direction: int):
        rows = self._selected_rows()
        if not rows:
            return
        if self.window.engine.running:
            self.window.status("Stop playback before reordering actions")
            return
        actions = self.window.action_model.actions()
        self.window.history.push(actions, self.window._timeline_history_state())
        if direction < 0:
            for row in rows:
                if row > 0 and row - 1 not in rows:
                    actions[row - 1], actions[row] = actions[row], actions[row - 1]
            new_rows = [max(0, r - 1) for r in rows]
        else:
            for row in reversed(rows):
                if row < len(actions) - 1 and row + 1 not in rows:
                    actions[row + 1], actions[row] = actions[row], actions[row + 1]
            new_rows = [min(len(actions) - 1, r + 1) for r in rows]
        self.window.action_model.set_actions(actions)
        self._commit("Moved selected action(s)")
        self.table.clearSelection()
        for r in new_rows:
            self.table.selectRow(r)

    def group_selected(self):
        rows = self._selected_rows()
        if not rows:
            return
        self.window.timeline.selected_indices = set(rows)
        self.window.create_group_from_rows(rows)
        self.refresh_table()

    def bulk_delay(self):
        rows = self._selected_rows()
        if not rows:
            return
        value, ok = QInputDialog.getDouble(self, "Bulk Delay", "Set duration/delay seconds:", 0.25, 0.0, 99999.0, 2)
        if not ok:
            return
        self.window.history.push(self.window.action_model.actions(), self.window._timeline_history_state())
        for r in rows:
            if 0 <= r < self.window.action_model.rowCount():
                a = self.window.action_model.get(r)
                if not a.is_group() and not a.is_loop() and not a.is_condition():
                    a.duration = float(value)
        self._commit("Bulk delay applied")

    def run_from_first_selected(self):
        rows = self._selected_rows()
        if not rows:
            return
        self.accept()
        self.window.select(rows[0])
        self.window.test_from_selected_row()

    def run_selected_block(self):
        rows = self._selected_rows()
        if not rows:
            return
        self.accept()
        self.window.run_selected_actions(rows)

    def image_preview(self):
        rows = self._selected_rows()
        if not rows:
            return
        row = rows[0]
        if row < 0 or row >= self.window.action_model.rowCount():
            return
        action = self.window.action_model.get(row)
        if not action.is_image():
            QMessageBox.information(self, "Image Preview", "Select an image action first.")
            return
        self.window.open_image_confidence_preview(row)
