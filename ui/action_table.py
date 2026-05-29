"""Action table widget for MacroForge PyQt6."""
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView, QMenu
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from ui.theme import COLORS, TYPE_COLORS
from models import Action


class ActionTable(QTableWidget):
    """Table showing macro actions with per-row type coloring."""

    action_selected = pyqtSignal(int)
    action_double_clicked = pyqtSignal(int)
    action_context_menu = pyqtSignal(int, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._actions = []
        self._active_index = -1
        self._playing_index = -1

        self.setColumnCount(5)
        self.setHorizontalHeaderLabels(["#", "Type", "Key / Action", "Duration", "Lane"])
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(0, 40)
        self.setColumnWidth(1, 70)
        self.setColumnWidth(3, 80)
        self.setColumnWidth(4, 50)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(False)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(f"""
            QTableWidget::item:selected {{
                background-color: {COLORS['bg_hover']};
                border: none;
            }}
        """)
        self.itemClicked.connect(self._on_item_click)
        self.itemDoubleClicked.connect(self._on_item_double)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

    def set_actions(self, actions: list):
        self._actions = actions
        self._refresh()

    def set_active_index(self, index: int):
        self._active_index = index
        self._refresh_highlight()

    def set_playing_index(self, index: int):
        self._playing_index = index
        self._refresh_highlight()

    def _refresh(self):
        self.blockSignals(True)
        self.setRowCount(len(self._actions))
        for i, action in enumerate(self._actions):
            self._set_row(i, action)
        self.blockSignals(False)
        self._refresh_highlight()

    def _set_row(self, row: int, action: Action):
        t = getattr(action, "action_type", "key")
        label = action.key
        if t == "pause":
            label = f"Delay {action.duration:.2f}s"
        elif t == "image":
            label = getattr(action, "label", "") or "Image search"
        elif t == "click":
            label = f"Click at ({action.click_x}, {action.click_y})"

        items = [
            (str(row + 1), COLORS["text_dim"]),
            (t.upper(), TYPE_COLORS.get(t, COLORS["text_dim"])),
            (label, COLORS["text"]),
            (f"{action.duration:.3f}s", COLORS["text_dim"]),
            (str(action.lane), COLORS["text_dim"]),
        ]
        for col, (text, color) in enumerate(items):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setForeground(Qt.GlobalColor.transparent)
            font = QFont("Segoe UI", 11)
            item.setFont(font)
            item.setData(Qt.ItemDataRole.UserRole, row)
            self.setItem(row, col, item)

    def _refresh_highlight(self):
        for row in range(self.rowCount()):
            is_active = (row == self._active_index)
            is_playing = (row == self._playing_index)
            if is_playing:
                bg = COLORS["playing_glow"]
            elif is_active:
                bg = COLORS["bg_hover"]
            else:
                bg = COLORS["bg_secondary"]
            for col in range(self.columnCount()):
                item = self.item(row, col)
                if item:
                    item.setBackground(Qt.GlobalColor.transparent)
            self.setStyleSheet("")

    def _on_item_click(self, item):
        row = item.row()
        self._active_index = row
        self.action_selected.emit(row)

    def _on_item_double(self, item):
        self.action_double_clicked.emit(item.row())

    def _on_context_menu(self, pos):
        item = self.itemAt(pos)
        if not item:
            return
        row = item.row()
        self.action_context_menu.emit(row, self.viewport().mapToGlobal(pos))
