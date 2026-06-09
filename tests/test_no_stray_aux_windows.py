from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_timeline_search_popup_is_not_a_tool_window():
    src = _read("ui/main_window_layout.py")
    block = src[src.index("self.tl_search_popup = QFrame") : src.index("popup_lo = QVBoxLayout", src.index("self.tl_search_popup = QFrame"))]

    assert "QFrame(content)" in block
    assert "setWindowFlags" not in block
    assert "Qt.WindowType.Tool" not in block
    assert "WA_DontCreateNativeAncestors" in block


def test_timeline_search_popup_uses_parent_coordinates():
    src = _read("ui/main_window_layout.py")
    block = src[src.index("def _show_timeline_search_popup") : src.index("self._show_timeline_search_popup", src.index("def _show_timeline_search_popup"))]

    assert "parent = self.tl_search_popup.parentWidget() or content" in block
    assert "parent.mapFromGlobal(global_pos)" in block
    assert "self.tl_search_popup.move(x, y)" in block


def test_recording_badge_does_not_spawn_a_window():
    src = _read("ui/main_window.py")
    block = src[src.index("def _show_rec_badge") : src.index("def _rec_timer_tick", src.index("def _show_rec_badge"))]

    assert "QFrame(self)" not in block
    assert "setWindowFlags" not in block
    assert "Qt.WindowType.Tool" not in block
    assert "rec[\"overlay\"] = None" in block


def test_system_tray_is_disabled_for_single_window_startup():
    src = _read("ui/main_window.py")
    block = src[src.index("def _setup_tray") : src.index("def _tray_activated", src.index("def _setup_tray"))]

    assert "QSystemTrayIcon(" not in block
    assert "_tray_icon.show" not in block
    assert "self._tray_icon = None" in block
    assert "single-window startup mode" in block


def test_startup_guard_exists_for_tiny_helper_windows():
    src = _read("ui/main_window.py")

    assert "def _start_startup_window_guard" in src
    assert "def _remove_startup_aux_windows" in src
    assert "width <= 120 and height <= 180" in src
    assert "Closing stray startup Qt helper window" in src


def test_no_widgets_are_created_with_qt_tool_flags():
    offenders = []
    for path in (ROOT / "ui").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "setWindowFlags" in text and "Qt.WindowType.Tool" in text:
            # main_window.py may inspect Tool flags in the startup guard; this
            # test only rejects widgets that are created with the Tool flag.
            offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []
