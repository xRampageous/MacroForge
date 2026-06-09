from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_timeline_search_popup_is_child_overlay_not_tool_window():
    src = (ROOT / "ui" / "main_window_layout.py").read_text(encoding="utf-8")
    popup_block = src[src.index("self.tl_search_popup = QFrame") : src.index("popup_lo = QVBoxLayout", src.index("self.tl_search_popup = QFrame"))]

    assert "self.tl_search_popup = QFrame(content)" in popup_block
    assert "setWindowFlags" not in popup_block
    assert "Qt.WindowType.Tool" not in popup_block


def test_timeline_search_popup_positions_in_parent_coordinates():
    src = (ROOT / "ui" / "main_window_layout.py").read_text(encoding="utf-8")
    show_block = src[src.index("def _show_timeline_search_popup") : src.index("self._show_timeline_search_popup", src.index("def _show_timeline_search_popup"))]

    assert "parent = self.tl_search_popup.parentWidget() or self" in show_block
    assert "parent.mapFromGlobal(global_pos)" in show_block
    assert "self.tl_search_popup.move(x, y)" in show_block


def test_recording_badge_is_child_overlay_not_tool_window():
    src = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
    badge_block = src[src.index("def _show_rec_badge") : src.index("def _rec_timer_tick", src.index("def _show_rec_badge"))]

    assert "ov = QFrame(self)" in badge_block
    assert "WindowStaysOnTopHint | Qt.WindowType.Tool" not in badge_block
    assert "ov.raise_()" in badge_block
