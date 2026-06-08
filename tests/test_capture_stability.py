"""Regression tests for the image capture OK/apply path and owned timers."""
import base64
import io
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
from models import Action, ActionListModel, ProfileManager, SettingsManager
from ui.dialogs.click_dialog import ClickDialog
from ui.dialogs.condition_dialog import ConditionDialog
from ui.dialogs.image_dialog import ImageDialog
from ui.main_window import MainWindow
from ui.theme import COLORS
from ui.timeline import TIMELINE_MULTI_SELECT_RAIL_WIDTH, TIMELINE_PROGRESS_COLUMN_SHIFT, TimelineView, _action_text


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

    def test_condition_pixel_detail_names_coordinates(self):
        action = Action("[CONDITION]", 0.0, action_type="condition")
        action.condition_type = "pixel_color"
        action.condition_x = 12
        action.condition_y = 34

        title, detail = _action_text(action)

        self.assertEqual(title, "Condition")
        self.assertEqual(detail, "Pixel 12,34")

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

    def test_folder_row_drag_over_folder_header_is_invalid(self):
        folder_a = Action("[GROUP]", 0.0, action_type="group", label="Folder A")
        folder_a.group_id = "folder-a"
        folder_b = Action("[GROUP]", 0.0, action_type="group", label="Folder B")
        folder_b.group_id = "folder-b"
        timeline = TimelineView(model=ActionListModel([folder_a, folder_b]))
        timeline.resize(700, 220)
        timeline.show()
        self.app.processEvents()
        timeline._drag_start_row = 1
        timeline.drag_source_rows = [1]
        first_rect = timeline.visualRect(timeline.model().index(0, 0))
        point = QPoint(first_rect.center().x(), first_rect.center().y())
        self.assertEqual(timeline._invalid_group_nest_row(point), 0)
        self.assertEqual(timeline._drop_group_row(point), -1)
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

            self.assertEqual(window.macro_summary.text(), "3 rows · 1 image · 0 folders · 0 loops · ~48s")
            window._set_playback_collapsed(True)
            self.assertEqual(window.playback_panel.height(), 36)
            self.assertFalse(window.playback_dock.isVisible())
            self.assertFalse(window.playback_restore_btn.isHidden())
            window._set_playback_collapsed(False)
            self.assertEqual(window.playback_panel.height(), 175)
            self._dispose_window(window)

    def test_playback_panel_lock_blocks_collapse(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            window._playback_panel_locked = True
            window._set_playback_panel_lock_button_state()
            window._set_playback_collapsed(True)

            self.assertFalse(window._playback_collapsed)
            self.assertEqual(window.playback_panel.height(), 175)
            self.assertIn("locked", window.playback_panel_lock_btn.toolTip().lower())
            self._dispose_window(window)

    def test_selection_chip_shows_count_and_quick_actions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            actions = [Action(str(i), 0.1) for i in range(4)]
            window.action_model.set_actions(actions)
            window.timeline.set_selected_rows([1, 2], active=1)
            self.app.processEvents()

            self.assertFalse(window.selection_chip.isHidden())
            self.assertEqual(window.selection_count_label.text(), "2 selected")
            with patch.object(window, "run_selected_actions") as run_mock:
                window.selection_run_btn.click()
            run_mock.assert_called_once_with([1, 2])

            window.disable_selected_actions()

            self.assertFalse(actions[1].enabled)
            self.assertFalse(actions[2].enabled)
            self.assertTrue(actions[0].enabled)
            self._dispose_window(window)

    def test_timeline_bottom_safe_margin_tracks_playback_height(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            window._playback_collapsed = False
            window._update_timeline_bottom_safe_margin(175)
            self.assertEqual(window.timeline.viewportMargins().bottom(), 0)

            window._playback_collapsed = True
            window._update_timeline_bottom_safe_margin(36)
            self.assertEqual(window.timeline.viewportMargins().bottom(), 0)
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
            self.assertEqual(window.status_pill.toolTip(), "Profile 'alpha' loaded")
            self.assertEqual(window.status_pill.property("status_state"), "saved")
            self.assertFalse(window.status_icon.isHidden())
            self.assertIn("border-radius: 12px", window.status_pill.styleSheet())
            self.assertTrue(window.status_text.text().startswith("Profile 'a"))
            self.assertNotIn("Playing", window.status_text.text())
            self.assertEqual(window.playback_feedback_label.text(), "Playing · Row 1 Enter")
            self.assertEqual(window.playback_feedback_frame.property("feedback_state"), "running")
            window.playback_feedback("Paused")
            self.app.processEvents()
            self.assertEqual(window.playback_feedback_frame.property("feedback_state"), "paused")
            self.assertIn("border-radius: 8px", window.playback_feedback_frame.styleSheet())
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
            self.assertEqual(window.ii_capture_btn.text(), "Capture image")
            self.assertGreaterEqual(window.ii_capture_btn.width(), 86)
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

    def test_image_inspector_capture_replaces_timeline_image_template(self):
        class FakeOverlay:
            region = (10, 20, 4, 5)

            def exec(self):
                return QDialog.DialogCode.Accepted

        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            action = Action(
                "[IMAGE]",
                0.05,
                action_type="image",
                image_data=PNG_1X1,
                search_region="1,2,3,4",
                similarity=0.85,
                wait_timeout=1.0,
            )
            window.action_model.set_actions([action])
            window.select(0)

            with (
                patch("ui.dialogs.image_dialog.CaptureOverlay", FakeOverlay),
                patch("PIL.ImageGrab.grab", return_value=Image.new("RGB", (4, 5), "red")),
            ):
                window._capture_active_image_region()

            self.assertNotEqual(action.image_data, PNG_1X1)
            self.assertEqual(action.search_region, "1,2,3,4")
            self.assertTrue(window.image_preview_label.property("has_template"))
            raw = base64.b64decode(action.image_data)
            with Image.open(io.BytesIO(raw)) as captured:
                self.assertEqual(captured.size, (4, 5))
            self.assertTrue(window._save_session_timer.isActive())
            self._dispose_window(window)

    def test_timeline_progress_column_shift_shortens_rail_by_twenty_pixels(self):
        self.assertEqual(TIMELINE_PROGRESS_COLUMN_SHIFT, 20)

    def test_timeline_multi_selection_visual_state_tracks_selected_run(self):
        timeline = TimelineView(model=ActionListModel([Action(str(i), 0.1) for i in range(5)]))
        timeline.selected_indices = {1, 2, 3}

        first = timeline.multi_selection_visual_state(1)
        middle = timeline.multi_selection_visual_state(2)
        last = timeline.multi_selection_visual_state(3)
        outside = timeline.multi_selection_visual_state(4)

        self.assertEqual(TIMELINE_MULTI_SELECT_RAIL_WIDTH, 6)
        self.assertTrue(first["active"])
        self.assertFalse(first["has_previous"])
        self.assertTrue(first["has_next"])
        self.assertEqual(first["count"], 3)
        self.assertTrue(middle["has_previous"])
        self.assertTrue(middle["has_next"])
        self.assertTrue(last["has_previous"])
        self.assertFalse(last["has_next"])
        self.assertFalse(outside["active"])
        timeline.deleteLater()

    def test_main_window_owns_real_controller_instances(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            try:
                self.assertIs(window._timeline_ctrl.timeline, window.timeline)
                self.assertIs(window._timeline_ctrl.action_model, window.action_model)
                self.assertIs(window._playback_ctrl.engine, window.engine)
                self.assertIs(window._toolbar_ctrl.window, window)
                self.assertIs(window._inspector_ctrl.window, window)
            finally:
                self._dispose_window(window)

    def test_timeline_ctrl_click_adds_to_multi_selection(self):
        timeline = TimelineView(model=ActionListModel([Action(str(i), 0.1) for i in range(5)]))
        timeline.resize(700, 360)
        timeline.show()
        self.app.processEvents()
        timeline.set_selected_rows([0], active=0)

        row_two_rect = timeline.visualRect(timeline.model().index(2, 0))
        QTest.mouseClick(
            timeline.viewport(),
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.ControlModifier,
            row_two_rect.center(),
        )
        self.app.processEvents()

        self.assertEqual(timeline.selected_rows(), [0, 2])
        timeline.hide()
        timeline.deleteLater()

    def test_timeline_search_highlight_persists_after_clearing_search(self):
        timeline = TimelineView(model=ActionListModel([
            Action("alpha", 0.1),
            Action("beta", 0.1),
            Action("alpha two", 0.1),
        ]))
        timeline.set_search("alpha")

        self.assertEqual(timeline.search_match_rows(), [0, 2])
        self.assertEqual(timeline._search_highlight_rows, {0, 2})

        timeline.set_search("")

        self.assertEqual(timeline.search_match_rows(), [0, 1, 2])
        self.assertEqual(timeline._search_highlight_rows, {0, 2})
        timeline.deleteLater()

    def test_image_inspector_allows_image_settings_to_collapse_under_height_pressure(self):
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
            window.resize(985, 560)
            window.select(0)
            window.show()
            self.app.processEvents()

            self.assertIn("inspector_group_image_settings_body", window._panel_collapse_controls)
            self.assertEqual(window.ii_image_card.minimumHeight(), 0)
            self.assertEqual(window.insp_image.minimumHeight(), 0)
            self.assertGreaterEqual(window.insp_card.maximumHeight(), window.insp_card.minimumSizeHint().height())
            self._dispose_window(window)

    def test_image_settings_uses_shared_collapsible_inspector_body(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            action = Action("[IMAGE]", 0.05, action_type="image", image_data=PNG_1X1)
            window.action_model.set_actions([action])
            window.select(0)

            body, caret = window._panel_collapse_controls["inspector_group_image_settings_body"]
            window._set_collapsible_panel("inspector_group_image_settings_body", True)
            for _ in range(20):
                self.app.processEvents()
                if body.isHidden():
                    break
                QTest.qWait(20)

            self.assertTrue(caret.property("collapsed"))
            self.assertTrue(body.isHidden())
            window._set_collapsible_panel("inspector_group_image_settings_body", False)
            for _ in range(20):
                self.app.processEvents()
                if not body.isHidden():
                    break
                QTest.qWait(20)
            self.assertFalse(caret.property("collapsed"))
            self.assertFalse(body.isHidden())
            self._dispose_window(window)

    def test_condition_inspector_controls_are_compact_and_aligned(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            action = Action("[CONDITION]", 0.0, action_type="condition")
            action.condition_type = "pixel_color"
            window.action_model.set_actions([action])
            window.select(0)

            self.assertEqual(window.ico_type.width(), 136)
            self.assertEqual(window.ico_true.width(), 136)
            self.assertEqual(window.ico_false.width(), 136)
            self.assertEqual(window.ico_fail_mode.width(), 136)
            self.assertEqual(window.ico_fail_target.width(), 136)
            self.assertEqual(window.ico_retry_count.width(), 50)
            self.assertEqual(window.ico_retry_delay.width(), 80)
            self.assertEqual(window.ico_retry_delay.alignment() & Qt.AlignmentFlag.AlignCenter, Qt.AlignmentFlag.AlignCenter)
            self.assertGreaterEqual(window.ico_rule.minimumHeight(), 30)
            self.assertIn("border", window.ico_rule.styleSheet())
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
                self.assertEqual(button.size().height(), 42, name)
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
                (window.lock_window_combo, "lock target selector"),
                (window.lock_window_health, "lock target health"),
                (window.lock_window_refresh_btn, "lock target refresh"),
                (window.lock_window_pick_btn, "lock target picker"),
                (window.playback_panel_lock_btn, "playback panel lock"),
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
            self.assertEqual(window.human_check.text(), "Humanize")
            self.assertEqual(window.focus_check.text(), "Window")
            self.assertLess(
                window.loops_spin.mapToGlobal(window.loops_spin.rect().topLeft()).x(),
                window.speed_combo.mapToGlobal(window.speed_combo.rect().topLeft()).x(),
            )
            loops_bottom = window.loops_spin.mapToGlobal(window.loops_spin.rect().bottomLeft()).y()
            speed_combo_right = window.speed_combo.mapToGlobal(window.speed_combo.rect().topRight()).x()
            speed_slider_left = window.speed_slider.mapToGlobal(window.speed_slider.rect().topLeft()).x()
            speed_bottom = window.speed_combo.mapToGlobal(window.speed_combo.rect().bottomLeft()).y()
            target_top = window.lock_window_combo.mapToGlobal(window.lock_window_combo.rect().topLeft()).y()
            target_bottom = window.lock_window_combo.mapToGlobal(window.lock_window_combo.rect().bottomLeft()).y()
            modes_top = window.sim_check.mapToGlobal(window.sim_check.rect().topLeft()).y()
            modes_bottom = window.focus_check.mapToGlobal(window.focus_check.rect().bottomLeft()).y()
            progress_top = window.progress_bar.parentWidget().mapToGlobal(window.progress_bar.parentWidget().rect().topLeft()).y()
            self.assertLessEqual(speed_combo_right, speed_slider_left)
            self.assertLess(loops_bottom, modes_top)
            self.assertLess(speed_bottom, target_top)
            self.assertLess(target_bottom, progress_top)
            self.assertLess(modes_bottom, progress_top)
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

    def test_timeline_zoom_persists_from_global_settings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_manager = ProfileManager()
            profile_manager.base_dir = tmpdir
            profile_manager.profiles_dir = os.path.join(tmpdir, "profiles")
            profile_manager.settings_file = os.path.join(tmpdir, "settings.json")
            os.makedirs(profile_manager.profiles_dir, exist_ok=True)
            profile_manager.save_profile([Action("alpha", 1.0)], {"zoom": 1.0}, "alpha")
            settings_manager = SettingsManager(tmpdir)
            settings_manager.set("timeline_zoom", 0.72)
            with (
                patch.object(MainWindow, "_check_update_silent"),
                patch.object(MainWindow, "_restore_window_geometry"),
                patch.object(MainWindow, "_setup_tray"),
            ):
                window = MainWindow(profile_manager=profile_manager, settings_manager=settings_manager)

            self.assertAlmostEqual(window.timeline.zoom, 0.72)
            window.timeline.set_zoom(1.24)
            self.assertAlmostEqual(settings_manager.get("timeline_zoom"), 1.24)
            window.reset_timeline_zoom()
            self.assertAlmostEqual(window.timeline.zoom, 1.0)
            self.assertAlmostEqual(settings_manager.get("timeline_zoom"), 1.0)
            self._dispose_window(window)

    def test_click_coordinate_capture_hotkey_updates_selected_click_only_on_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            action = Action(
                "[CLICK]",
                0.05,
                action_type="click",
                click_x=10,
                click_y=20,
                click_button="left",
            )
            window.action_model.set_actions([action])
            window.show()
            self.app.processEvents()
            window.select(0)

            with patch("ui.main_window.QCursor.pos", return_value=QPoint(333, 444)):
                window._update_click_xy_readout()
                self.assertEqual((action.click_x, action.click_y), (10, 20))
                self.assertIn("333, 444", window.ic_cursor_pos.text())
                window._capture_click_coordinates_from_cursor()

            self.assertEqual((action.click_x, action.click_y), (333, 444))
            self.assertEqual(window.ic_x.text(), "333")
            self.assertEqual(window.ic_y.text(), "444")
            self.assertTrue(window._save_session_timer.isActive())
            self._dispose_window(window)

    def test_condition_coordinate_capture_updates_selected_condition_only_on_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            action = Action("[CONDITION]", 0.0, action_type="condition")
            action.condition_type = "pixel_color"
            action.condition_x = 10
            action.condition_y = 20
            window.action_model.set_actions([action])
            window.show()
            self.app.processEvents()
            window.select(0)

            with patch("ui.main_window.QCursor.pos", return_value=QPoint(333, 444)):
                window._update_click_xy_readout()
                self.assertEqual((action.condition_x, action.condition_y), (10, 20))
                self.assertIn("333, 444", window.ico_cursor_pos.text())
                window._capture_condition_coordinates_from_cursor()

            self.assertEqual((action.condition_x, action.condition_y), (333, 444))
            self.assertEqual(window.ico_x.text(), "333")
            self.assertEqual(window.ico_y.text(), "444")
            self.assertTrue(window._save_session_timer.isActive())
            self._dispose_window(window)

    def test_coordinate_hotkey_dispatch_updates_condition_inspector(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            action = Action("[CONDITION]", 0.0, action_type="condition")
            action.condition_type = "pixel_color"
            window.action_model.set_actions([action])
            window.show()
            self.app.processEvents()
            window.select(0)

            with patch("ui.main_window.QCursor.pos", return_value=QPoint(555, 666)):
                window._capture_active_coordinates_from_cursor()

            self.assertEqual((action.condition_x, action.condition_y), (555, 666))
            self.assertEqual((window.ico_x.text(), window.ico_y.text()), ("555", "666"))
            self._dispose_window(window)

    def test_click_dialog_shows_hotkey_hint_without_auto_overwriting_fields(self):
        class Parent(QWidget):
            def _hotkey(self, name, default):
                return "Ctrl+Shift+M"

        parent = Parent()
        with patch("ui.dialogs.click_dialog.QCursor.pos", return_value=QPoint(10, 20)):
            dialog = ClickDialog(parent=parent)

        dialog.x.setText("1")
        dialog.y.setText("2")
        with patch("ui.dialogs.click_dialog.QCursor.pos", return_value=QPoint(30, 40)):
            dialog._sync_cursor_xy()
            self.assertEqual((dialog.x.text(), dialog.y.text()), ("1", "2"))
            self.assertIn("30, 40", dialog.cursor_pos.text())
            dialog._capture_cursor_xy()

        self.assertEqual((dialog.x.text(), dialog.y.text()), ("30", "40"))
        self.assertIn("Ctrl+Shift+M", dialog.hotkey_hint.text())
        dialog.deleteLater()
        parent.deleteLater()

    def test_condition_dialog_shows_live_coords_and_hotkey_capture(self):
        class Parent(QWidget):
            def _hotkey(self, name, default):
                return "Ctrl+Shift+M"

        parent = Parent()
        dialog = ConditionDialog(parent=parent)

        dialog.x_spin.setValue(1)
        dialog.y_spin.setValue(2)
        with patch("ui.dialogs.condition_dialog.QCursor.pos", return_value=QPoint(30, 40)):
            dialog._sync_cursor_xy()
            self.assertEqual((dialog.x_spin.value(), dialog.y_spin.value()), (1, 2))
            self.assertIn("30, 40", dialog.cursor_pos.text())
            dialog._capture_cursor_xy()

        self.assertEqual((dialog.x_spin.value(), dialog.y_spin.value()), (30, 40))
        self.assertIn("Ctrl+Shift+M", dialog.hotkey_hint.text())
        dialog.deleteLater()
        parent.deleteLater()

    def test_lock_to_window_dropdown_sets_engine_target(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            window = self._make_window(tmpdir)
            with patch.object(window, "_enumerate_target_windows", return_value=[(12345, "Target App · app.exe")]):
                window.refresh_lock_windows()

            self.assertEqual(window.lock_window_combo.count(), 2)
            window.lock_window_combo.setCurrentIndex(1)
            window.focus_check.setChecked(True)

            self.assertEqual(window.engine._focus_hwnd, 12345)
            self.assertIn("Target", window.lock_window_status.text())
            self.assertEqual(window.lock_window_health.toolTip(), "Window target missing")
            self.assertIn(COLORS["error"], window.lock_window_health.styleSheet())
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
