"""Regression tests for the image capture OK/apply path and owned timers."""
import base64
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image
from PyQt6 import sip
from PyQt6.QtCore import QEvent, QPoint, Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDialog, QFrame, QLabel, QMenu, QPushButton, QWidget

from debugger import DebugLogger
from models import Action, ActionListModel, ProfileManager
from ui.dialogs.image_dialog import ImageDialog
from ui.main_window import MainWindow
from ui.timeline import TimelineView, _action_text


PNG_1X1 = base64.b64encode(
    base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUB"
        "AScY42YAAAAASUVORK5CYII="
    )
).decode()


class QtTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)


class TestCaptureApply(QtTestCase):
    def test_ok_builds_image_action_and_adds_timeline_row(self):
        dialog = ImageDialog()
        dialog._img_data = PNG_1X1

        dialog._on_ok_clicked()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)

        action = dialog.get_action()
        self.assertIsNotNone(action)
        self.assertEqual(action.action_type, "image")
        self.assertEqual(action.image_data, PNG_1X1)

        model = ActionListModel()
        timeline = TimelineView(model=model)
        model.add_action(action)
        self.assertEqual(model.rowCount(), 1)
        self.assertEqual(timeline.model().rowCount(), 1)
        self.assertIs(timeline.model().get(0), action)

        timeline.deleteLater()
        dialog.deleteLater()

    def test_capture_keeps_outer_modal_dialog_alive_until_ok(self):
        class FakeOverlay:
            region = (10, 20, 4, 5)

            def exec(self):
                return QDialog.DialogCode.Accepted

        dialog = ImageDialog()

        def capture_then_accept():
            dialog._capture_image()
            QTimer.singleShot(0, dialog._on_ok_clicked)

        with (
            patch("ui.dialogs.image_dialog.CaptureOverlay", FakeOverlay),
            patch("PIL.ImageGrab.grab", return_value=Image.new("RGB", (4, 5), "white")),
        ):
            QTimer.singleShot(0, capture_then_accept)
            result = dialog.exec()

        self.assertEqual(result, QDialog.DialogCode.Accepted)
        self.assertTrue(dialog._img_data)
        self.assertIsNotNone(dialog.get_action())
        dialog.deleteLater()

    def test_logger_accepts_standard_format_arguments(self):
        self.assertEqual(
            DebugLogger._format_message("captured image len=%s", 42),
            "captured image len=42",
        )


class TestTimelineRows(QtTestCase):
    def test_delay_detail_does_not_duplicate_duration_column(self):
        title, detail = _action_text(Action("[DELAY]", 4.0, action_type="pause"))
        self.assertEqual(title, "Delay")
        self.assertEqual(detail, "")

    def test_running_duration_column_counts_down(self):
        timeline = TimelineView(model=ActionListModel([Action("[DELAY]", 4.0, action_type="pause")]))
        timeline.set_playing(0, 4.0)
        with patch("ui.timeline.time.monotonic", return_value=timeline._playing_started + 1.5):
            self.assertEqual(timeline.duration_text(0, timeline.model().get(0)), "2.5s")
        timeline.clear_playing()
        timeline.deleteLater()

    def test_pause_resume_countdown_does_not_skip_paused_time(self):
        action = Action("[DELAY]", 4.0, action_type="pause")
        timeline = TimelineView(model=ActionListModel([action]))
        timeline.set_playing(0, 4.0)
        timeline._playing_started = 100.0
        with patch("ui.timeline.time.monotonic", return_value=101.25):
            timeline.set_paused(True)
        self.assertEqual(timeline.duration_text(0, action), "2.8s")
        with patch("ui.timeline.time.monotonic", return_value=110.0):
            timeline.set_paused(False)
        with patch("ui.timeline.time.monotonic", return_value=111.0):
            self.assertEqual(timeline.duration_text(0, action), "1.8s")
        timeline.clear_playing()
        timeline.deleteLater()

    def test_drag_target_uses_drop_position_between_rows(self):
        timeline = TimelineView(model=ActionListModel([
            Action("a", 0.1), Action("b", 0.1), Action("c", 0.1),
        ]))
        timeline.resize(700, 300)
        timeline.show()
        self.app.processEvents()
        timeline._drag_start_row = 0
        third_rect = timeline.visualRect(timeline.model().index(2, 0))
        self.assertEqual(timeline._drop_target_row(QPoint(third_rect.center().x(), third_rect.bottom() - 1)), 2)
        self.assertEqual(timeline._drop_insert_row(QPoint(third_rect.center().x(), third_rect.bottom() - 1)), 3)
        timeline.hide()
        timeline.deleteLater()

    def test_drag_target_supports_upward_reorder(self):
        timeline = TimelineView(model=ActionListModel([
            Action("a", 0.1), Action("b", 0.1), Action("c", 0.1),
        ]))
        timeline.resize(700, 300)
        timeline.show()
        self.app.processEvents()
        timeline._drag_start_row = 2
        first_rect = timeline.visualRect(timeline.model().index(0, 0))
        self.assertEqual(timeline._drop_insert_row(QPoint(first_rect.center().x(), first_rect.top() + 1)), 0)
        self.assertEqual(timeline._drop_target_row(QPoint(first_rect.center().x(), first_rect.top() + 1)), 0)
        timeline.hide()
        timeline.deleteLater()

    def test_hover_highlight_clears_when_cursor_leaves_timeline(self):
        timeline = TimelineView(model=ActionListModel([Action("a", 0.1)]))
        timeline.hover_row = 0
        timeline.leaveEvent(QEvent(QEvent.Type.Leave))
        self.assertEqual(timeline.hover_row, -1)
        timeline.deleteLater()

    def test_drop_flash_fades_before_clearing(self):
        timeline = TimelineView(model=ActionListModel([Action("a", 0.1)]))
        timeline.flash_drop(0)
        timeline._fade_drop_flash()
        self.assertEqual(timeline.flash_row, 0)
        self.assertLess(timeline.flash_opacity, 1.0)
        for _ in range(20):
            timeline._fade_drop_flash()
        self.assertEqual(timeline.flash_row, -1)
        timeline.deleteLater()

    def test_playback_disables_drag_sorting_and_restores_it_when_cleared(self):
        timeline = TimelineView(model=ActionListModel([Action("a", 0.1)]))
        timeline.setDragEnabled(True)
        timeline._drag_allowed = True
        timeline.set_playing(0, 0.1)
        self.assertFalse(timeline.dragEnabled())
        self.assertFalse(timeline._drag_allowed)
        timeline.clear_playing()
        self.assertFalse(timeline.dragEnabled())
        self.assertEqual(timeline.playing_index, -1)
        timeline.deleteLater()

    def test_badges_follow_rows_when_indices_are_remapped(self):
        timeline = TimelineView(model=ActionListModel([
            Action("[IMAGE]", 0.1, action_type="image"),
            Action("a", 0.1),
            Action("[IMAGE]", 0.1, action_type="image"),
        ]))
        timeline.image_states = {0: "Found", 2: "Waiting"}
        timeline.remap_after_move(0, 2)
        self.assertEqual(timeline.image_states, {2: "Found", 1: "Waiting"})
        timeline.deleteLater()

    def test_drag_edge_auto_scroll_moves_viewport(self):
        timeline = TimelineView(model=ActionListModel([Action(str(i), 0.1) for i in range(30)]))
        timeline.resize(700, 180)
        timeline.show()
        self.app.processEvents()
        timeline.verticalScrollBar().setValue(0)
        timeline._update_auto_scroll(QPoint(10, timeline.viewport().height() - 1))
        self.assertEqual(timeline._auto_scroll_direction, 1)
        self.assertTrue(timeline._auto_scroll_timer.isActive())
        timeline._auto_scroll_tick()
        self.assertGreater(timeline.verticalScrollBar().value(), 0)
        timeline._stop_auto_scroll()
        timeline.hide()
        timeline.deleteLater()

    def test_drag_edge_auto_scroll_recomputes_insertion_marker(self):
        timeline = TimelineView(model=ActionListModel([Action(str(i), 0.1) for i in range(30)]))
        timeline.resize(700, 180)
        timeline.show()
        self.app.processEvents()
        pos = QPoint(10, timeline.viewport().height() - 1)
        timeline._last_drag_pos = pos
        timeline._update_auto_scroll(pos)
        timeline._auto_scroll_tick()
        self.assertEqual(timeline.drop_insert_row, timeline._drop_insert_row(pos))
        timeline._stop_drag_feedback()
        timeline.hide()
        timeline.deleteLater()


class TestOwnedTimers(QtTestCase):
    def test_main_window_startup_smoke_create_and_dispose(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_manager = SimpleNamespace(base_dir=tmpdir)
            with (
                patch.object(MainWindow, "_check_update_silent"),
                patch.object(MainWindow, "load_last_session"),
                patch.object(MainWindow, "_restore_window_geometry"),
                patch.object(MainWindow, "_setup_tray"),
            ):
                window = MainWindow(profile_manager=profile_manager)

            self.assertEqual(window.windowTitle(), "MacroForge")
            window._save_session_timer.stop()
            window._update_check_timer.stop()
            window.deleteLater()

    def test_app_diagnostics_lines_include_release_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_manager = SimpleNamespace(base_dir=tmpdir)
            with (
                patch.object(MainWindow, "_check_update_silent"),
                patch.object(MainWindow, "load_last_session"),
                patch.object(MainWindow, "_restore_window_geometry"),
                patch.object(MainWindow, "_setup_tray"),
            ):
                window = MainWindow(profile_manager=profile_manager)

            text = "\n".join(window._app_diagnostics_lines())
            self.assertIn("Version:", text)
            self.assertIn("Update URL:", text)
            self.assertIn("Log path:", text)
            self.assertIn("Update health file:", text)
            window._save_session_timer.stop()
            window._update_check_timer.stop()
            window.deleteLater()

    def test_main_window_owns_debounce_and_repeating_update_timers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_manager = SimpleNamespace(base_dir=tmpdir)
            with (
                patch.object(MainWindow, "_check_update_silent"),
                patch.object(MainWindow, "load_last_session"),
                patch.object(MainWindow, "_restore_window_geometry"),
                patch.object(MainWindow, "_setup_tray"),
            ):
                window = MainWindow(profile_manager=profile_manager)

            self.assertTrue(window._save_session_timer.isSingleShot())
            self.assertEqual(window._save_session_timer.interval(), 500)
            self.assertTrue(window._update_check_timer.isActive())
            self.assertFalse(window._update_check_timer.isSingleShot())
            self.assertEqual(window._update_check_timer.interval(), 60 * 1000)

            window.save_session()
            self.assertTrue(window._save_session_timer.isActive())
            window._save_session_timer.stop()
            window._update_check_timer.stop()
            window.deleteLater()

    def test_real_exit_uses_qapplication_quit_not_os_exit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_manager = SimpleNamespace(base_dir=tmpdir)
            with (
                patch.object(MainWindow, "_check_update_silent"),
                patch.object(MainWindow, "load_last_session"),
                patch.object(MainWindow, "_restore_window_geometry"),
                patch.object(MainWindow, "_setup_tray"),
                patch("ui.main_window.QApplication.topLevelWidgets", return_value=[]),
                patch("ui.main_window.QApplication.quit") as quit_mock,
                patch("ui.main_window.os._exit") as os_exit_mock,
            ):
                window = MainWindow(profile_manager=profile_manager)
                window._real_exit()

            quit_mock.assert_called_once()
            os_exit_mock.assert_not_called()
            window._save_session_timer.stop()
            window._update_check_timer.stop()
            window.deleteLater()


class TestPlaybackVisibility(QtTestCase):
    def _make_window(self, tmpdir):
        profile_manager = SimpleNamespace(base_dir=tmpdir)
        patches = (
            patch.object(MainWindow, "_check_update_silent"),
            patch.object(MainWindow, "load_last_session"),
            patch.object(MainWindow, "_restore_window_geometry"),
            patch.object(MainWindow, "_setup_tray"),
        )
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        return MainWindow(profile_manager=profile_manager)

    def _dispose_window(self, window):
        window._save_session_timer.stop()
        window._update_check_timer.stop()
        window.timeline._progress_timer.stop()
        window.timeline._auto_scroll_timer.stop()
        window.timeline._flash_timer.stop()
        if hasattr(window.timeline, "_drop_flash_timer"):
            window.timeline._drop_flash_timer.stop()
        self.app.processEvents()
        window.hide()
        sip.delete(window)

    def test_summary_and_bottom_panel_collapse(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            window.action_model.set_actions([
                Action("enter", 1.0),
                Action("[IMAGE]", 0.05, action_type="image", image_data=PNG_1X1, wait_timeout=10.0),
                Action("[DELAY]", 47.0, action_type="pause"),
            ])
            window.refresh()

            self.assertEqual(window.macro_summary.text(), "3 rows · 1 image · 0 groups · 0 loops · ~48s")
            window._set_playback_collapsed(True)
            self.assertEqual(window.playback_panel.height(), 36)
            self.assertFalse(window.playback_dock.isVisible())
            self.assertFalse(window.playback_restore_btn.isHidden())
            window._set_playback_collapsed(False)
            self.assertEqual(window.playback_panel.height(), 175)
            self._dispose_window(window)

    def test_autosave_chip_marks_unsaved_then_saved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_manager = ProfileManager()
            profile_manager.base_dir = tmpdir
            profile_manager.profiles_dir = os.path.join(tmpdir, "profiles")
            profile_manager.settings_file = os.path.join(tmpdir, "settings.json")
            os.makedirs(profile_manager.profiles_dir, exist_ok=True)
            patches = (
                patch.object(MainWindow, "_check_update_silent"),
                patch.object(MainWindow, "load_last_session"),
                patch.object(MainWindow, "_restore_window_geometry"),
                patch.object(MainWindow, "_setup_tray"),
            )
            for item in patches:
                item.start()
                self.addCleanup(item.stop)
            window = MainWindow(profile_manager=profile_manager)
            window.save_session()
            self.assertEqual(window.autosave_label.text(), "Unsaved")
            window._save_session_timer.stop()
            window._do_save_session()
            self.assertEqual(window.autosave_label.text(), "Saved")
            self._dispose_window(window)

    def test_playback_status_lives_in_bottom_panel_not_top_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            window.status("Profile 'alpha' loaded")
            window.playback_feedback("Playing · Row 1 Enter")
            self.app.processEvents()
            self.assertEqual(window.status_text.toolTip(), "Profile 'alpha' loaded")
            self.assertTrue(window.status_text.text().startswith("Profile 'a"))
            self.assertNotIn("Playing", window.status_text.text())
            self.assertEqual(window.playback_feedback_label.text(), "Playing · Row 1 Enter")
            self._dispose_window(window)

    def test_image_inspector_uses_editor_cards_and_ms_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            action = Action(
                "[IMAGE]",
                0.05,
                action_type="image",
                image_data=PNG_1X1,
                similarity=0.85,
                wait_timeout=1.0,
                retry_delay=0.25,
            )
            window.action_model.set_actions([action])
            window.select(0)

            self.assertEqual(window.inspector_selector.itemText(0), "Image Action")
            self.assertEqual(window.inspector_type_badge.text(), "IMAGE")
            self.assertFalse(window.insp_image.isHidden())
            self.assertEqual(window.ii_sim.text(), "0.85")
            self.assertEqual(window.ii_wait.text(), "1000")
            self.assertEqual(window.ii_retry_delay.text(), "250")

            old_toolbar_tips = {"Apply", "Test selected action", "Cancel", "Delete", "Duplicate", "Edit"}
            inspector_buttons = window.insp_image.parentWidget().findChildren(QPushButton)
            self.assertFalse(old_toolbar_tips.intersection({button.toolTip() for button in inspector_buttons}))

            window.ii_wait.setText("1500")
            window.ii_retry_delay.setText("125")
            window.ii_fail_mode.setCurrentText("Continue")
            window._apply_inspector()
            self.assertAlmostEqual(window.action_model.get(0).wait_timeout, 1.5)
            self.assertAlmostEqual(window.action_model.get(0).retry_delay, 0.125)
            self.assertEqual(window.action_model.get(0).on_fail_action, "continue")
            self._dispose_window(window)

    def test_image_inspector_visual_smoke_uses_captured_preview(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            action = Action(
                "[IMAGE]",
                0.05,
                action_type="image",
                image_data=PNG_1X1,
                similarity=0.85,
                wait_timeout=1.0,
                retry_delay=0.25,
            )
            window.action_model.set_actions([action])
            window.resize(985, 1100)
            window.select(0)
            window.show()
            self.app.processEvents()

            sidebar = window.findChild(QFrame, "mf3_sidebar")
            self.assertIsNotNone(sidebar)
            self.assertEqual(sidebar.width(), 260)
            self.assertTrue(window.image_preview_label.property("has_template"))
            self.assertIsNotNone(window.image_preview_label.pixmap())
            self.assertFalse(window.image_preview_label.pixmap().isNull())
            for object_name in (
                "image_inspector_preview",
                "inspector_group_matching",
                "inspector_group_retry",
                "inspector_group_on_fail",
                "inspector_group_fail_target",
            ):
                self.assertIsNotNone(window.insp_image.findChild(QFrame, object_name), object_name)
            for button in (window.ii_zoom_btn, window.ii_fit_btn, window.ii_capture_btn):
                self.assertFalse(button.isHidden())
                self.assertGreater(button.width(), 0)

            grab = window.insp_image.grab()
            self.assertFalse(grab.isNull())
            self.assertGreater(grab.width(), 0)
            self.assertGreater(grab.height(), 0)
            window.hide()
            self._dispose_window(window)

    def test_add_action_buttons_use_compact_qt_stacked_layout_without_png_assets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            expected = {
                "add_key": ("Key", 84),
                "add_click": ("Click", 84),
                "add_pause": ("Delay", 84),
                "add_image": ("Image", 84),
                "add_condition": ("Condition", 84),
                "add_loop": ("Loop", 84),
                "add_group": ("Folder", 172),
            }
            for name, (label, width) in expected.items():
                button = window.findChild(QPushButton, name)
                self.assertIsNotNone(button, name)
                self.assertNotEqual(button.property("neon_add_action"), True, name)
                self.assertNotEqual(button.property("stacked_content"), True, name)
                self.assertTrue(button.property("qt_stacked_add_action"), name)
                self.assertNotIn("neon_buttons", button.styleSheet(), name)
                self.assertNotIn("border-image", button.styleSheet(), name)
                self.assertIn("qlineargradient", button.styleSheet(), name)
                self.assertEqual(button.text(), "", name)
                self.assertEqual(button.size().width(), width, name)
                self.assertEqual(button.size().height(), 45, name)
                icon_label = button.findChild(QLabel, f"{name}_icon")
                text_label = button.findChild(QLabel, f"{name}_label")
                self.assertIsNotNone(icon_label, name)
                self.assertIsNotNone(text_label, name)
                self.assertEqual(text_label.text(), label, name)
            self._dispose_window(window)

    def test_timeline_row_clicks_keep_window_alive_and_select_row(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            window.action_model.set_actions([
                Action("enter", 1.0),
                Action("[IMAGE]", 0.05, action_type="image", image_data=PNG_1X1, wait_timeout=1.0),
                Action("[DELAY]", 4.0, action_type="pause"),
                Action("x", 1.0),
            ])
            window.refresh()
            window.resize(985, 1100)
            window.show()
            self.app.processEvents()

            for row in (0, 1, 2, 3, 1, 0):
                idx = window.timeline.model().index(row, 0)
                rect = window.timeline.visualRect(idx)
                self.assertTrue(rect.isValid(), f"row {row} should be visible")
                QTest.mouseClick(
                    window.timeline.viewport(),
                    Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier,
                    rect.center(),
                )
                self.app.processEvents()
                self.assertFalse(window.isHidden(), f"window closed after row {row} click")
                self.assertEqual(window.active_index, row)
                self.assertEqual(window.timeline.currentIndex().row(), row)

            window.hide()
            self._dispose_window(window)

    def test_timeline_click_tolerates_malformed_saved_action_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            bad_key = Action("enter", "bad-duration")
            bad_key.key = None
            bad_image = Action(
                "[IMAGE]",
                0.05,
                action_type="image",
                image_data=PNG_1X1,
                similarity="not-a-number",
                wait_timeout="",
            )
            bad_image.jump_to_on_found = "bad-target"
            window.action_model.set_actions([bad_key, bad_image])
            window.refresh()
            window.resize(985, 1100)
            window.show()
            self.app.processEvents()

            for row in (0, 1):
                idx = window.timeline.model().index(row, 0)
                rect = window.timeline.visualRect(idx)
                self.assertTrue(rect.isValid(), f"row {row} should be visible")
                QTest.mouseClick(
                    window.timeline.viewport(),
                    Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier,
                    rect.center(),
                )
                self.app.processEvents()
                self.assertFalse(window.isHidden(), f"window closed after malformed row {row}")
                self.assertEqual(window.active_index, row)

            window.hide()
            self._dispose_window(window)

    def test_compact_layout_keeps_header_and_bottom_panel_readable_at_target_size(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            window.action_model.set_actions([
                Action("enter", 1.0),
                Action("[DELAY]", 4.0, action_type="pause"),
                Action("w", 21.0, hold_mode=True),
                Action("[IMAGE]", 0.05, action_type="image", image_data=PNG_1X1, wait_timeout=10.0),
            ])
            window.refresh()
            window.resize(985, 1100)
            window.show()
            self.app.processEvents()

            self.assertEqual(window.size().width(), 985)
            self.assertEqual(window.size().height(), 1100)

            def rect_in_window(widget: QWidget):
                top_left = widget.mapTo(window, widget.rect().topLeft())
                return widget.rect().translated(top_left)

            def assert_visible(widget: QWidget, name: str):
                self.assertFalse(widget.isHidden(), name)
                self.assertGreater(widget.width(), 0, name)
                self.assertGreater(widget.height(), 0, name)
                rect = rect_in_window(widget)
                self.assertGreaterEqual(rect.left(), 0, name)
                self.assertGreaterEqual(rect.top(), 0, name)
                self.assertLessEqual(rect.right(), window.width(), name)
                self.assertLessEqual(rect.bottom(), window.height(), name)
                return rect

            header_rect = assert_visible(window.status_pill.parentWidget(), "header dock")
            timeline_rect = assert_visible(window.timeline, "timeline")
            playback_rect = assert_visible(window.playback_panel, "playback panel")
            dock_rect = assert_visible(window.playback_dock, "playback dock")

            self.assertLess(header_rect.bottom(), timeline_rect.top())
            self.assertLess(timeline_rect.bottom(), playback_rect.top())
            self.assertGreaterEqual(window.height() - playback_rect.bottom(), 0)
            self.assertLessEqual(window.height() - playback_rect.bottom(), 2)
            self.assertEqual(dock_rect.bottom(), playback_rect.bottom() - 6)

            profile_x = window.profile_btn.mapToGlobal(window.profile_btn.rect().topLeft()).x()
            update_x = window.update_top_btn.mapToGlobal(window.update_top_btn.rect().topLeft()).x()
            menu_x = window.menu_top_btn.mapToGlobal(window.menu_top_btn.rect().topLeft()).x()
            status_x = window.status_pill.mapToGlobal(window.status_pill.rect().topLeft()).x()
            self.assertGreater(update_x, profile_x)
            self.assertGreater(menu_x, update_x)
            self.assertGreater(status_x, menu_x)

            self.assertGreaterEqual(window.status_pill.width(), 108)
            self.assertLessEqual(window.status_pill.width(), 150)
            self.assertEqual(window.playback_panel.height(), 175)
            for widget, name in (
                (window.profile_btn, "profile selector"),
                (window.update_top_btn, "update button"),
                (window.menu_top_btn, "menu button"),
                (window.start_btn, "start button"),
                (window.pause_btn, "pause button"),
                (window.stop_btn, "stop button"),
                (window.speed_combo, "speed selector"),
                (window.loops_spin, "loop selector"),
                (window.sim_check, "sim checkbox"),
                (window.human_check, "human checkbox"),
                (window.focus_check, "focus checkbox"),
                (window.playback_feedback_frame, "playback status frame"),
                (window.playback_feedback_icon, "playback status icon"),
                (window.playback_feedback_label, "playback status label"),
                (window.progress_bar, "global progress bar"),
                (window._stat_actions_w, "played stat"),
                (window._stat_loops_w, "loops stat"),
                (window._stat_seq_w, "sequence stat"),
                (window._stat_time_w, "time stat"),
            ):
                assert_visible(widget, name)

            self.assertGreaterEqual(window.start_btn.width(), 52)
            self.assertGreaterEqual(window.speed_combo.width(), 50)
            self.assertLessEqual(window.playback_feedback_frame.width(), 216)
            self.assertGreaterEqual(window.playback_feedback_frame.width(), 190)
            self.assertLess(window.playback_feedback_label.width(), window.playback_feedback_frame.width())
            self.assertGreaterEqual(window.progress_bar.width(), 200)
            self.assertEqual(window.progress_bar.parentWidget().height(), window._stat_actions_w.height())
            self.assertEqual(window.progress_bar.parentWidget().height(), window._stat_time_w.height())
            self.assertLessEqual(window.progress_bar.height(), 12)
            self.assertGreaterEqual(window._stat_time_w.width(), 78)
            window.status("Ready")
            self.app.processEvents()
            short_status_w = window.status_pill.width()
            window.status("Profile SP Farm loaded and playback options synced")
            self.app.processEvents()
            self.assertGreater(window.status_pill.width(), short_status_w)
            self.assertLessEqual(window.status_pill.width(), 390)
            self.assertGreater(window.timeline.model().rowCount(), 0)
            window.hide()
            self._dispose_window(window)

    def test_from_selected_row_uses_remaining_actions_and_maps_timeline_index(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            window.action_model.set_actions([
                Action("a", 0.0),
                Action("b", 0.0),
                Action("[IMAGE]", 0.0, action_type="image", image_data=PNG_1X1),
            ])
            window.active_index = 1
            with patch.object(window.engine, "start"):
                window.test_from_selected_row()

            self.assertEqual([action.key for action in window.engine.actions], ["b", "[IMAGE]"])
            self.assertEqual(window._run_from_index, 1)
            window._do_play_cb(0, 0.0)
            self.assertEqual(window.timeline.playing_index, 1)
            window._do_image_match_state(1, "Found")
            self.assertEqual(window.timeline.image_states[2], "Found")
            self._dispose_window(window)

    def test_drag_move_preserves_selection_and_flashes_destination(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            window.action_model.set_actions([Action("a", 0.0), Action("b", 0.0), Action("c", 0.0)])
            window.move_action_to(0, 2)
            self.assertEqual([action.key for action in window.action_model.actions()], ["b", "c", "a"])
            self.assertEqual(window.active_index, 2)
            self.assertEqual(window.timeline.currentIndex().row(), 2)
            self.assertEqual(window.timeline.flash_row, 2)
            self._dispose_window(window)

    def test_drag_sort_is_undoable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            window.action_model.set_actions([Action("a", 0.0), Action("b", 0.0), Action("c", 0.0)])
            window.move_action_to(0, 2)
            self.assertEqual([action.key for action in window.action_model.actions()], ["b", "c", "a"])
            window.undo()
            self.assertEqual([action.key for action in window.action_model.actions()], ["a", "b", "c"])
            self._dispose_window(window)

    def test_drag_sort_is_blocked_during_playback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            window.action_model.set_actions([Action("a", 0.0), Action("b", 0.0), Action("c", 0.0)])
            window.timeline.set_playing(0, 1.0)
            window.move_action_to(0, 2)
            self.assertEqual([action.key for action in window.action_model.actions()], ["a", "b", "c"])
            window.timeline.clear_playing()
            self._dispose_window(window)

    def test_drag_sort_badges_selection_and_next_highlight_survive_undo_redo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            window.action_model.set_actions([
                Action("[IMAGE]", 0.0, action_type="image"),
                Action("b", 0.0),
                Action("[IMAGE]", 0.0, action_type="image"),
            ])
            window.active_index = 0
            window.timeline.set_active(0)
            window.timeline.next_index = 2
            window.timeline.image_states = {0: "Found", 2: "Waiting"}

            window.move_action_to(0, 2)
            self.assertEqual(window.timeline.image_states, {2: "Found", 1: "Waiting"})
            self.assertEqual(window.timeline.next_index, 1)
            self.assertEqual(window.timeline.currentIndex().row(), 2)

            window.undo()
            self.assertEqual(window.timeline.image_states, {0: "Found", 2: "Waiting"})
            self.assertEqual(window.timeline.next_index, 2)
            self.assertEqual(window.timeline.currentIndex().row(), 0)

            window.redo()
            self.assertEqual(window.timeline.image_states, {2: "Found", 1: "Waiting"})
            self.assertEqual(window.timeline.next_index, 1)
            self.assertEqual(window.timeline.currentIndex().row(), 2)
            self._dispose_window(window)

    def test_upward_drag_sort_survives_undo_redo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            window.action_model.set_actions([Action("a", 0.0), Action("b", 0.0), Action("c", 0.0)])
            window.active_index = 2
            window.timeline.set_active(2)
            window.move_action_to(2, 0)
            self.assertEqual([action.key for action in window.action_model.actions()], ["c", "a", "b"])
            window.undo()
            self.assertEqual([action.key for action in window.action_model.actions()], ["a", "b", "c"])
            self.assertEqual(window.timeline.currentIndex().row(), 2)
            window.redo()
            self.assertEqual([action.key for action in window.action_model.actions()], ["c", "a", "b"])
            self.assertEqual(window.timeline.currentIndex().row(), 0)
            self.assertEqual(window.timeline.flash_row, 0)
            self._dispose_window(window)

    def test_multiple_drag_sorts_support_multiple_undo_redo_steps(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            window.action_model.set_actions([
                Action("a", 0.0), Action("b", 0.0), Action("c", 0.0), Action("d", 0.0),
            ])
            window.move_action_to(0, 3)
            window.move_action_to(1, 0)
            self.assertEqual([action.key for action in window.action_model.actions()], ["c", "b", "d", "a"])
            window.undo()
            self.assertEqual([action.key for action in window.action_model.actions()], ["b", "c", "d", "a"])
            window.undo()
            self.assertEqual([action.key for action in window.action_model.actions()], ["a", "b", "c", "d"])
            window.redo()
            self.assertEqual([action.key for action in window.action_model.actions()], ["b", "c", "d", "a"])
            window.redo()
            self.assertEqual([action.key for action in window.action_model.actions()], ["c", "b", "d", "a"])
            self._dispose_window(window)

    def test_long_timeline_sort_near_bottom_preserves_scroll_position(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            window.action_model.set_actions([Action(str(i), 0.0) for i in range(40)])
            window.resize(760, 1050)
            window.show()
            self.app.processEvents()
            scrollbar = window.timeline.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            before = scrollbar.value()
            self.assertGreater(before, 0)

            window.move_action_to(39, 35)
            self.assertEqual(window.timeline.scroll_position(), before)
            window.undo()
            self.assertEqual(window.timeline.scroll_position(), before)
            window.redo()
            self.assertEqual(window.timeline.scroll_position(), before)
            window.hide()
            self._dispose_window(window)

    def test_first_and_last_rows_can_be_sorted_repeatedly(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            window.action_model.set_actions([
                Action("a", 0.0), Action("b", 0.0), Action("c", 0.0), Action("d", 0.0),
            ])
            window.move_action_to(0, 3)
            window.move_action_to(3, 0)
            window.move_action_to(0, 3)
            self.assertEqual([action.key for action in window.action_model.actions()], ["b", "c", "d", "a"])
            window.undo()
            window.undo()
            window.undo()
            self.assertEqual([action.key for action in window.action_model.actions()], ["a", "b", "c", "d"])
            self._dispose_window(window)

    def test_edit_after_sort_undo_clears_redo_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            window.action_model.set_actions([Action("a", 0.0), Action("b", 0.0), Action("c", 0.0)])
            window.move_action_to(0, 2)
            window.undo()
            self.assertTrue(window.history.can_redo())
            window.history.push(window.action_model.actions())
            window.action_model.replace_action(0, Action("edited", 0.0))
            self.assertFalse(window.history.can_redo())
            self._dispose_window(window)

    def test_badges_survive_chained_image_row_moves(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            window.action_model.set_actions([
                Action("[I1]", 0.0, action_type="image"),
                Action("[I2]", 0.0, action_type="image"),
                Action("key", 0.0),
                Action("[I3]", 0.0, action_type="image"),
            ])
            window.timeline.image_states = {0: "Found", 1: "Waiting", 3: "Missed"}
            window.move_action_to(0, 3)
            window.move_action_to(0, 2)
            self.assertEqual(window.timeline.image_states, {3: "Found", 2: "Waiting", 1: "Missed"})
            window.undo()
            window.undo()
            self.assertEqual(window.timeline.image_states, {0: "Found", 1: "Waiting", 3: "Missed"})
            window.redo()
            window.redo()
            self.assertEqual(window.timeline.image_states, {3: "Found", 2: "Waiting", 1: "Missed"})
            self._dispose_window(window)

    def test_undo_only_scrolls_restored_selection_when_outside_viewport(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            window.action_model.set_actions([Action(str(i), 0.0) for i in range(40)])
            window.resize(760, 1050)
            window.show()
            self.app.processEvents()
            window.active_index = 39
            window.timeline.set_active(39)
            window.move_action_to(39, 35)
            window.timeline.verticalScrollBar().setValue(0)
            window.undo()
            self.assertGreater(window.timeline.scroll_position(), 0)
            window.hide()
            self._dispose_window(window)

    def test_context_menu_move_actions_are_disabled_during_playback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            window.action_model.set_actions([Action("a", 0.0), Action("b", 0.0), Action("c", 0.0)])
            window.timeline.set_playing(1, 1.0)
            captured = {}

            def capture_menu(menu, _pos):
                captured.update({action.text(): action.isEnabled() for action in menu.actions()})

            with patch.object(QMenu, "exec", capture_menu):
                window._timeline_context_menu(1, QPoint())

            self.assertFalse(captured["Move Up"])
            self.assertFalse(captured["Move Down"])
            window.timeline.clear_playing()
            self._dispose_window(window)

    def test_profile_switcher_menu_stays_quick_profile_menu(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            window.session_manager.active = "alpha"
            window.session_manager.list_profiles = lambda: ["alpha", "beta"]
            captured = []

            def capture_menu(menu, _pos):
                captured.extend(action.text() for action in menu.actions() if not action.isSeparator())

            with patch.object(QMenu, "exec", capture_menu):
                window._show_profile_menu()

            self.assertIn("\u2713  alpha", captured)
            self.assertIn("     beta", captured)
            self.assertIn("Open Profile / Macro Library     Ctrl+Alt+P", captured)
            self.assertNotIn("Macro health / pre-flight     Ctrl+Shift+P", captured)
            self._dispose_window(window)

    def test_top_right_action_menu_exposes_profile_macro_library(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            captured = []

            def capture_menu(menu, _pos):
                captured.extend(action.text() for action in menu.actions() if not action.isSeparator())

            with patch.object(QMenu, "exec", capture_menu):
                window._show_action_menu()

            self.assertIn("LIBRARY", captured)
            self.assertIn("Profile / macro library     Ctrl+Alt+P", captured)
            self.assertIn("Macro health / pre-flight     Ctrl+Shift+P", captured)
            self.assertNotIn("Export MacroForge macro…", captured)
            self.assertNotIn("Import MacroForge macro…", captured)
            self._dispose_window(window)

    def test_profile_library_smoke_exposes_repair_import_export_controls(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_manager = ProfileManager()
            profile_manager.base_dir = tmpdir
            profile_manager.profiles_dir = os.path.join(tmpdir, "profiles")
            profile_manager.settings_file = os.path.join(tmpdir, "settings.json")
            os.makedirs(profile_manager.profiles_dir, exist_ok=True)
            profile_manager.save_profile([Action("a", 0.1)], {}, "alpha")
            patches = (
                patch.object(MainWindow, "_check_update_silent"),
                patch.object(MainWindow, "load_last_session"),
                patch.object(MainWindow, "_restore_window_geometry"),
                patch.object(MainWindow, "_setup_tray"),
            )
            for item in patches:
                item.start()
                self.addCleanup(item.stop)
            window = MainWindow(profile_manager=profile_manager)
            captured = {}

            def capture_dialog(dlg):
                captured["title"] = dlg.windowTitle()
                captured["buttons"] = [button.text() for button in dlg.findChildren(QPushButton)]
                return QDialog.DialogCode.Accepted

            with patch.object(QDialog, "exec", capture_dialog):
                window.open_profile_library()

            self.assertEqual(captured["title"], "Profile / Macro Library")
            for label in ("Open", "New", "Duplicate", "Rename", "Repair", "Export", "Import", "Delete", "Close"):
                self.assertIn(label, captured["buttons"])
            self._dispose_window(window)

    def test_profile_switch_loads_actions_and_exact_speed_settings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_manager = ProfileManager()
            profile_manager.base_dir = tmpdir
            profile_manager.profiles_dir = os.path.join(tmpdir, "profiles")
            profile_manager.settings_file = os.path.join(tmpdir, "settings.json")
            os.makedirs(profile_manager.profiles_dir, exist_ok=True)
            profile_manager.save_profile(
                [Action("alpha", 1.0)],
                {"loops": 3, "speed": 1.25, "infinite_loop": False, "human_curve": True},
                "alpha",
            )
            profile_manager.save_profile(
                [Action("beta", 2.0)],
                {"loops": 4, "speed": 0.75, "infinite_loop": True, "human_curve": False},
                "beta",
            )
            profile_manager.switch_profile("alpha")
            patches = (
                patch.object(MainWindow, "_check_update_silent"),
                patch.object(MainWindow, "_restore_window_geometry"),
                patch.object(MainWindow, "_setup_tray"),
            )
            for item in patches:
                item.start()
                self.addCleanup(item.stop)
            window = MainWindow(profile_manager=profile_manager)

            self.assertEqual(window.action_model.get(0).key, "alpha")
            self.assertEqual(window.loops_spin.value(), 3)
            self.assertEqual(window.speed_combo.currentText(), "1.25x")

            window._switch_profile("beta")
            self.assertEqual(window.session_manager.active, "beta")
            self.assertEqual(window.action_model.rowCount(), 1)
            self.assertEqual(window.action_model.get(0).key, "beta")
            self.assertEqual(window.loops_spin.value(), 4)
            self.assertEqual(window.speed_combo.currentText(), "0.75x")
            self.assertTrue(window.inf_check.isChecked())
            self.assertFalse(window.human_check.isChecked())
            self.assertIn("beta", window.profile_btn.text())
            self._dispose_window(window)


if __name__ == "__main__":
    unittest.main()
