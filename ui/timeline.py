"""MacroForge Timeline — robust, smooth QListView-based action list.

This module intentionally keeps the public API used by main_window.py that the
old timeline exposed: selected_indices, zoom, set_active, set_playing,
clear_playing, set_paused, set_search, refresh, ensure_visible, and action_* signals.
"""

from PyQt6.QtWidgets import QStyledItemDelegate, QListView, QAbstractItemView
from PyQt6.QtCore import Qt, pyqtSignal, QModelIndex, QSize, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter

from ui.theme import COLORS, TYPE_COLORS
from models import ActionListModel


class TimelineDelegate(QStyledItemDelegate):
    """Lightweight delegate. Avoid widgets-per-row for large timelines."""

    def paint(self, painter: QPainter, option, index):
        painter.save()
        try:
            rect = option.rect
            action = index.data(ActionListModel.ActionRole)
            view = option.widget

            selected = bool(option.state & option.StateFlag.State_Selected) if hasattr(option, "StateFlag") else False
            # PyQt exposes the flags through QStyle.StateFlag; the fallback below keeps this
            # robust across PyQt minor versions.
            try:
                from PyQt6.QtWidgets import QStyle
                selected = bool(option.state & QStyle.StateFlag.State_Selected)
            except Exception:
                pass

            bg = COLORS.get("bg_hover") if selected else COLORS.get("bg_secondary")
            painter.setBrush(QColor(bg))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(rect)

            if not action:
                return

            action_type = getattr(action, "action_type", "key") or "key"
            color = QColor(TYPE_COLORS.get(action_type, COLORS.get("accent", "#5aa9ff")))
            painter.setBrush(color)
            painter.drawRect(rect.left(), rect.top(), 4, rect.height())

            # Playing indicator overlay/accent.
            playing_index = getattr(view, "playing_index", -1)
            if index.row() == playing_index:
                painter.setBrush(QColor(COLORS.get("accent", "#5aa9ff")))
                painter.drawRect(rect.left(), rect.top(), rect.width(), 2)

            painter.setPen(QColor(COLORS.get("text", "#ffffff")))
            painter.setFont(QFont("Segoe UI", 9))

            label = getattr(action, "label", "") or ""
            key = getattr(action, "key", "") or ""
            text = label or key or "Unknown"

            # Useful secondary detail without expensive rich rendering.
            duration = getattr(action, "duration", None)
            if action_type == "pause":
                text = f"Pause · {duration:.2f}s" if isinstance(duration, (int, float)) else "Pause"
            elif action_type == "click":
                text = label or f"Click · {getattr(action, 'click_button', 'left')} @ {getattr(action, 'click_x', 0)}, {getattr(action, 'click_y', 0)}"
            elif action_type == "image":
                text = label or "Image match"

            text_rect = rect.adjusted(12, 0, -8, 0)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
        except Exception as e:
            # A delegate must never raise during paint; Qt can otherwise stop repainting the view.
            painter.setBrush(QColor(COLORS.get("bg_secondary", "#202020")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(option.rect)
            painter.setPen(QColor(COLORS.get("text", "#ffffff")))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(option.rect.adjusted(10, 0, -8, 0), Qt.AlignmentFlag.AlignVCenter, f"Timeline error: {e}")
        finally:
            painter.restore()

    def sizeHint(self, option, index):
        # IMPORTANT: Qt expects QSize here. Returning an int makes the list unable
        # to compute row geometry correctly in PyQt6, which is why the timeline rows
        # can appear blank/missing.
        view = option.widget
        zoom = float(getattr(view, "zoom", 1.0) or 1.0)
        height = max(24, int(36 * zoom))
        return QSize(100, height)


class TimelineView(QListView):
    action_clicked = pyqtSignal(int)
    action_double_clicked = pyqtSignal(int)
    action_context_menu = pyqtSignal(int, object)
    action_dragged = pyqtSignal(int, int)

    def __init__(self, parent=None, model=None):
        super().__init__(parent)

        self.zoom = 1.0
        self.selected_indices = set()
        self.playing_index = -1
        self.paused = False
        self._search = ""
        self._drag_start_row = -1

        self.setModel(model or ActionListModel())
        self.setItemDelegate(TimelineDelegate(self))
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setFrameShape(QListView.Shape.NoFrame)
        self.setAlternatingRowColors(False)
        self.setUniformItemSizes(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setMinimumHeight(160)
        self.setStyleSheet(
            f"QListView {{ border: 1px solid {COLORS['border']}; "
            f"background-color: {COLORS['bg']}; outline: none; }}"
            f"QListView::item {{ border: none; }}"
        )

        self.clicked.connect(self._on_clicked)
        self.doubleClicked.connect(self._on_double_clicked)
        self.customContextMenuRequested.connect(self._on_context_menu)
        sel = self.selectionModel()
        if sel is not None:
            sel.currentChanged.connect(self._on_current_changed)

    def _on_current_changed(self, current, previous):
        if current.isValid():
            self.selected_indices = {current.row()}
        else:
            self.selected_indices.clear()
        self.viewport().update()

    def _on_clicked(self, index):
        if index.isValid():
            self.selected_indices = {index.row()}
            self.action_clicked.emit(index.row())

    def _on_double_clicked(self, index):
        if index.isValid():
            self.action_double_clicked.emit(index.row())

    def _on_context_menu(self, pos):
        index = self.indexAt(pos)
        row = index.row() if index.isValid() else -1
        self.action_context_menu.emit(row, self.viewport().mapToGlobal(pos))

    def mousePressEvent(self, event):
        idx = self.indexAt(event.position().toPoint()) if hasattr(event, "position") else self.indexAt(event.pos())
        self._drag_start_row = idx.row() if idx.isValid() else -1
        super().mousePressEvent(event)

    def dropEvent(self, event):
        source = self._drag_start_row
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        target_index = self.indexAt(pos)
        target = target_index.row() if target_index.isValid() else self.model().rowCount() - 1
        event.ignore()
        if source >= 0 and target >= 0 and source != target:
            QTimer.singleShot(0, lambda s=source, t=target: self.action_dragged.emit(s, t))

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            old = self.zoom
            delta = event.angleDelta().y()
            self.zoom = max(0.5, min(2.5, self.zoom * (1.1 if delta > 0 else 1 / 1.1)))
            if self.zoom != old:
                # Uniform sizes cache must be invalidated after zoom changes.
                self.setUniformItemSizes(False)
                self.doItemsLayout()
                self.setUniformItemSizes(True)
                self.viewport().update()
            event.accept()
            return
        super().wheelEvent(event)

    def set_actions(self, actions):
        m = self.model()
        if not isinstance(m, ActionListModel):
            m = ActionListModel()
            self.setModel(m)
        # Reset order matters: beginResetModel before mutating backing data.
        if hasattr(m, "set_actions"):
            m.set_actions(actions)
        else:
            m.beginResetModel()
            m._actions = list(actions or [])
            m.endResetModel()
        self.selected_indices.clear()
        self.viewport().update()

    def set_active(self, index):
        if index is not None and 0 <= index < self.model().rowCount():
            idx = self.model().index(index, 0)
            self.setCurrentIndex(idx)
            self.selected_indices = {index}
        else:
            self.clearSelection()
            self.setCurrentIndex(QModelIndex())
            self.selected_indices.clear()
        self.viewport().update()

    def set_playing(self, index, duration=0.0):
        self.playing_index = index
        if 0 <= index < self.model().rowCount():
            self.scrollTo(self.model().index(index, 0), QAbstractItemView.ScrollHint.EnsureVisible)
        self.viewport().update()

    def clear_playing(self):
        self.playing_index = -1
        self.paused = False
        self.viewport().update()

    def set_paused(self, paused: bool):
        self.paused = bool(paused)
        self.viewport().update()

    def ensure_visible(self, index):
        if 0 <= index < self.model().rowCount():
            self.scrollTo(self.model().index(index, 0), QAbstractItemView.ScrollHint.EnsureVisible)

    def set_search(self, text: str):
        # Keep the API for the search box. For now this selects the first match
        # instead of hiding rows, avoiding proxy-model complexity and keeping the
        # main window's model indices stable.
        self._search = (text or "").strip().lower()
        if not self._search:
            self.viewport().update()
            return
        for row in range(self.model().rowCount()):
            action = self.model().get(row)
            haystack = " ".join(str(getattr(action, name, "") or "") for name in ("label", "key", "action_type"))
            if self._search in haystack.lower():
                self.set_active(row)
                self.ensure_visible(row)
                break
        self.viewport().update()

    def refresh(self):
        self.doItemsLayout()
        self.viewport().update()
