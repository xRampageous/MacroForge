"""MacroForge Timeline — robust, smooth, QListView-based action list with reactive model."""
from PyQt6.QtWidgets import (
    QStyledItemDelegate, QListView
)
from PyQt6.QtCore import Qt, pyqtSignal, QModelIndex
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter
from ui.theme import COLORS, TYPE_COLORS
from models import ActionListModel

class TimelineDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        action = index.data(ActionListModel.ActionRole)
        if not action:
            return

        painter.save()

        rect = option.rect

        # background
        painter.setBrush(QColor(COLORS["bg_secondary"]))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(rect)

        # accent color per type
        t = getattr(action, "action_type", "key")

        color_map = {
            "image": QColor(TYPE_COLORS.get("image", COLORS["accent"])),
            "click": QColor(TYPE_COLORS.get("click", COLORS["accent"])),
            "pause": QColor(TYPE_COLORS.get("pause", COLORS["accent"])),
            "key": QColor(TYPE_COLORS.get("key", COLORS["accent"])),
        }

        color = color_map.get(t, QColor(COLORS["accent"]))

        painter.setBrush(color)
        painter.drawRect(rect.left(), rect.top(), 4, rect.height())

        # text
        painter.setPen(QColor(COLORS["text"]))
        painter.setFont(QFont("Segoe UI", 9))

        text = action.label or action.key
        painter.drawText(rect.adjusted(10, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, text)

        painter.restore()

    def sizeHint(self, option, index):
        return option.fontMetrics.height() + 10


class TimelineView(QListView):
    action_clicked = pyqtSignal(int)
    action_double_clicked = pyqtSignal(int)
    action_context_menu = pyqtSignal(int, object)
    action_dragged = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModel(ActionListModel())
        self.setItemDelegate(TimelineDelegate())
        self.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.setFrameShape(QListView.Shape.NoFrame)
        self.setStyleSheet(f"QListView {{ border: 1px solid {COLORS['border']}; background-color: {COLORS['bg']}; }}")
        self.clicked.connect(self._on_clicked)
        self.doubleClicked.connect(self._on_double_clicked)
        self.setDragDropMode(QListView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def _on_clicked(self, index):
        self.action_clicked.emit(index.row())

    def _on_double_clicked(self, index):
        self.action_double_clicked.emit(index.row())

    def set_actions(self, actions):
        self.model()._actions = actions
        self.model().beginResetModel()
        self.model().endResetModel()

    def set_active(self, index):
        self.setCurrentIndex(self.model().index(index, 0) if index >= 0 else QModelIndex())

    def set_playing(self, index, duration=0.0):
        self.playing_index = index
        self.viewport().update()

    def clear_playing(self):
        self.playing_index = -1
        self.viewport().update()

    def ensure_visible(self, index):
        if index >= 0 and index < self.model().rowCount():
            self.scrollTo(self.model().index(index, 0))

    def set_search(self, text: str):
        self._search = (text or "").strip().lower()

    def refresh(self):
        self.viewport().update()
