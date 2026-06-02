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

from PyQt6.QtWidgets import QApplication, QDialog

from debugger import DebugLogger
from models import ActionListModel
from ui.dialogs.image_dialog import ImageDialog
from ui.main_window import MainWindow
from ui.timeline import TimelineView


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

    def test_logger_accepts_standard_format_arguments(self):
        self.assertEqual(
            DebugLogger._format_message("captured image len=%s", 42),
            "captured image len=42",
        )


class TestOwnedTimers(QtTestCase):
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


if __name__ == "__main__":
    unittest.main()
