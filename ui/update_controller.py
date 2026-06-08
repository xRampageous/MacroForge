"""Update controller for MacroForge.

Keeps update checks, download dialog state, and updater handoff outside the
main window while still using MainWindow signals for thread-safe UI callbacks.
"""

import threading

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication, QDialog, QLabel, QMessageBox, QProgressBar, QVBoxLayout

from debugger import logger
from updater import check_update, perform_update, get_last_update_error
from ui.icons import icon
from ui.theme import COLORS


class UpdateController:
    def __init__(self, window):
        self.window = window
        self._dialog = None
        self._bar = None
        self._info = None

    def set_button_available(self, available=False, checking=False):
        """Refresh the top update/download icon state without showing popups."""
        try:
            btn = getattr(self.window, "update_top_btn", None)
            if btn is None:
                return
            if checking:
                color = COLORS["text_dim"]
                tip = "Checking for updates..."
            elif available:
                color = COLORS["success"]
                manifest = getattr(self.window, "_pending_update_manifest", None) or {}
                remote = manifest.get("version", "new version") if isinstance(manifest, dict) else "new version"
                tip = f"Update available: {remote} - click to download"
            else:
                color = COLORS["accent"]
                tip = "Check for updates"
            btn.setIcon(icon("download", 18, color))
            btn.setToolTip(tip)
            btn.setProperty("update_available", bool(available))
            btn.setProperty("checking", bool(checking))
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()
        except Exception:
            pass

    def mark_available(self, manifest):
        """Store an available update and turn the download icon green."""
        try:
            self.window._pending_update_manifest = dict(manifest or {})
        except Exception:
            self.window._pending_update_manifest = manifest
        self.window._update_available = True
        self.set_button_available(available=True)
        try:
            remote = (manifest or {}).get("version", "new version") if isinstance(manifest, dict) else "new version"
            self.window.status(f"Update available: {remote}")
        except Exception:
            pass

    def check_silent(self):
        self.window._update_prompt_shown = False

        def _bg():
            try:
                manifest = check_update(silent=True)
                if manifest:
                    self.window._update_found.emit(manifest)
            except Exception as exc:
                logger.error(f"Silent update check failed: {exc}")

        threading.Thread(target=_bg, daemon=True).start()

    def on_found(self, manifest):
        """Slot for _update_found signal; always runs on the main thread."""
        self.set_done()
        self.mark_available(manifest)

    def on_not_found(self):
        self.set_done()
        self.window._pending_update_manifest = None
        self.window._update_available = False
        self.set_button_available(available=False)
        self.window.status("No updates found")

    def on_error(self, error_msg):
        self.set_done()
        self.set_button_available(available=bool(getattr(self.window, "_update_available", False)))
        self.close_dialog()
        QMessageBox.warning(self.window, "Update Check Failed", f"Could not check for updates:\n\n{error_msg}")

    def close_dialog(self):
        if self._dialog:
            self._dialog.close()
            self._dialog = None
        self._bar = None
        self._info = None
        try:
            self.window._download_progress.disconnect(self.on_download_progress)
        except Exception:
            pass

    def on_download_progress(self, pct, txt):
        """Slot for _download_progress signal; always runs on the main thread."""
        if self._bar:
            self._bar.setValue(pct)
        if self._info:
            self._info.setText(txt)

    def set_done(self):
        self.window._update_checking = False
        if not bool(getattr(self.window, "_update_available", False)):
            self.set_button_available(available=False)

    def check_manual(self):
        if bool(getattr(self.window, "_update_available", False)) and getattr(self.window, "_pending_update_manifest", None):
            self.start_download(self.window._pending_update_manifest)
            return
        if getattr(self.window, "_update_checking", False):
            self.window.status("Already checking for updates")
            return
        self.window._update_checking = True
        self.window._update_prompt_shown = False
        self.set_button_available(checking=True)
        self.window.status("Checking for updates...")

        def _bg():
            try:
                manifest = check_update(silent=False)
            except Exception as exc:
                self.window._update_error.emit(str(exc))
                return
            if manifest:
                self.window._update_found.emit(manifest)
            else:
                error = get_last_update_error()
                if error:
                    self.window._update_error.emit(error)
                else:
                    self.window._update_not_found.emit()

        threading.Thread(target=_bg, daemon=True).start()
        QTimer.singleShot(
            30000,
            lambda: self.set_done() if getattr(self.window, "_update_checking", False) else None,
        )

    def prompt_update(self, manifest):
        """Backwards-compatible discovery handler: mark available, no popup."""
        self.mark_available(manifest)

    def start_download(self, manifest):
        try:
            if not manifest:
                self.window.status("No update is ready to download")
                return
            remote_ver = manifest.get("version", "unknown") if isinstance(manifest, dict) else "unknown"
            logger.info(f"Opening update download window for {remote_ver}")

            from ui.dialogs._common import dialog_stylesheet, make_header

            accent = COLORS["accent"]
            self._dialog = QDialog(self.window)
            self._dialog.setWindowTitle("Updating MacroForge")
            self._dialog.setFixedSize(420, 170)
            self._dialog.setStyleSheet(
                dialog_stylesheet(accent)
                + f"""
                QProgressBar {{
                    background-color: {COLORS['lane']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 6px;
                    height: 9px;
                    text-align: center;
                }}
                QProgressBar::chunk {{
                    background-color: {accent};
                    border-radius: 6px;
                }}
                """
            )
            self._dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            lo = QVBoxLayout(self._dialog)
            lo.setContentsMargins(16, 16, 16, 14)
            lo.setSpacing(9)
            lo.addWidget(make_header("Downloading Update", accent, "download"))
            title = QLabel(f"MacroForge {remote_ver}")
            title.setStyleSheet(f"color: {COLORS['text']}; font-size: 13px; font-weight: 900; background: transparent;")
            lo.addWidget(title)
            self._bar = QProgressBar()
            self._bar.setRange(0, 100)
            self._bar.setFixedHeight(11)
            lo.addWidget(self._bar)
            self._info = QLabel("Starting...")
            self._info.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px; font-weight: 700; background: transparent;")
            lo.addWidget(self._info)
            self._dialog.show()
            self._dialog.raise_()
            self._dialog.activateWindow()
            self._dialog.update()
            self.set_button_available(checking=True)
            QApplication.processEvents()

            try:
                self.window._download_progress.disconnect(self.on_download_progress)
            except Exception:
                pass
            self.window._download_progress.connect(self.on_download_progress)

            def _on_progress(downloaded, total):
                pct = downloaded / total * 100 if total else 0
                mb_down = downloaded / (1024 * 1024)
                if total:
                    mb_total = total / (1024 * 1024)
                    txt = f"{mb_down:.1f} MB / {mb_total:.1f} MB  ({pct:.0f}%)"
                else:
                    txt = f"{mb_down:.1f} MB downloaded"
                self.window._download_progress.emit(int(pct), txt)

            def _download():
                try:
                    if perform_update(manifest, progress_cb=_on_progress):
                        self.window._close_update_dlg.emit()
                        self.window._do_update_exit.emit()
                    else:
                        self.window._close_update_dlg.emit()
                        self.window._update_error.emit("Download or installation failed. See debug log for details.")
                except Exception as exc:
                    logger.error(f"perform_update failed: {exc}")
                    self.window._close_update_dlg.emit()
                    self.window._update_error.emit(f"Update failed: {exc}")

            threading.Thread(target=_download, daemon=True).start()
        except Exception as exc:
            logger.error(f"_prompt_update crashed: {exc}")
            self.window._update_prompt_shown = False


def create_update_controller(window):
    return UpdateController(window)
