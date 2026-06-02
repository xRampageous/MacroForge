"""App diagnostics panel and support actions."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

import update_health
from support_bundle import create_support_bundle, default_bundle_path
from updater import updater_dry_run
from version import VERSION
from ui.theme import COLORS


def active_profile_path(window):
    manager = window.session_manager
    active = getattr(manager, "active", "default")
    try:
        return manager._profile_path(active)
    except Exception:
        profiles_dir = getattr(manager, "profiles_dir", "")
        return str(Path(profiles_dir) / f"{active}.json") if profiles_dir else None


def latest_manifest_for_validation():
    health = update_health.load()
    manifest = health.get("last_manifest") or {}
    version = manifest.get("remote_version")
    zip_url = manifest.get("zip_url")
    url = manifest.get("url")
    if version and (zip_url or url):
        return {
            "version": version,
            "zip_url": zip_url or "",
            "url": url or "",
            "notes": "from update health",
        }
    return {
        "version": VERSION,
        "zip_url": f"https://github.com/xRampageous/MacroForge/releases/download/v{VERSION}/MacroForge-v{VERSION}.zip",
        "url": f"https://github.com/xRampageous/MacroForge/releases/download/v{VERSION}/MacroForge.exe",
        "notes": "current version fallback",
    }


def app_diagnostics_lines(window):
    from updater import get_last_update_error
    from version import UPDATE_URL
    from debugger import get_log_path

    last_update_error = get_last_update_error() or "None"
    preflight = window._last_preflight or {"errors": [], "warnings": []}
    return [
        f"Version: {VERSION}",
        f"Update URL: {UPDATE_URL or 'Not configured'}",
        f"Profile: {getattr(window.session_manager, 'active', 'unknown')}",
        f"Profile directory: {getattr(window.session_manager, 'profiles_dir', 'unknown')}",
        f"Settings file: {getattr(window.session_manager, 'settings_file', 'unknown')}",
        f"Log path: {get_log_path()}",
        f"Last update error: {last_update_error}",
        f"Preflight errors: {len(preflight.get('errors', []))}",
        f"Preflight warnings: {len(preflight.get('warnings', []))}",
    ] + update_health.summary_lines()


def export_support_bundle(window, edit=None):
    default_path = str(default_bundle_path(Path.home() / "Desktop"))
    path, _ = QFileDialog.getSaveFileName(window, "Export Support Bundle", default_path, "ZIP (*.zip)")
    if not path:
        return
    try:
        lines = edit.toPlainText().splitlines() if edit is not None else app_diagnostics_lines(window)
        create_support_bundle(
            path,
            lines,
            {
                "profile": getattr(window.session_manager, "active", "unknown"),
                "profiles_dir": getattr(window.session_manager, "profiles_dir", "unknown"),
                "settings_file": getattr(window.session_manager, "settings_file", "unknown"),
            },
            active_profile_path=active_profile_path(window),
        )
        window.status("Support bundle exported")
        QMessageBox.information(window, "Support Bundle", f"Support bundle exported:\n\n{path}")
    except Exception as exc:
        QMessageBox.critical(window, "Support Bundle Error", str(exc))


def clear_update_health(window, edit):
    update_health.clear()
    edit.setPlainText("\n".join(app_diagnostics_lines(window)))
    window.status("Update health cleared")


def validate_updater_now(window, edit):
    try:
        manifest = latest_manifest_for_validation()
        result = updater_dry_run(manifest)
        edit.setPlainText("\n".join(app_diagnostics_lines(window)))
        if result["ready"]:
            window.status("Updater validation ready")
            QMessageBox.information(window, "Updater Validation", "Updater dry-run is ready.")
        else:
            window.status("Updater validation failed")
            QMessageBox.warning(window, "Updater Validation", "\n".join(result["errors"]))
    except Exception as exc:
        QMessageBox.critical(window, "Updater Validation Error", str(exc))


def show_app_diagnostics(window):
    C = COLORS
    diagnostics_text = "\n".join(app_diagnostics_lines(window))
    dlg = QDialog(window)
    dlg.setWindowTitle("MacroForge Diagnostics")
    dlg.resize(560, 320)
    dlg.setStyleSheet(
        f"QDialog {{ background-color: {C['bg']}; color: {C['text']}; }}"
        f"QPlainTextEdit {{ background-color: {C['bg_tertiary']}; color: {C['text']}; "
        f"border: 1px solid {C['border']}; border-radius: 8px; padding: 8px; "
        "font-family: Consolas, monospace; font-size: 11px; }}"
        f"QPushButton {{ background-color: {C['bg_card']}; color: {C['text']}; "
        f"border: 1px solid {C['border']}; border-radius: 7px; padding: 7px 12px; }}"
        f"QPushButton:hover {{ border-color: {C['accent']}; color: {C['accent']}; }}"
    )
    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(12, 12, 12, 12)
    title = QLabel("MacroForge Diagnostics")
    title.setStyleSheet(f"color: {C['text']}; font-size: 15px; font-weight: 800;")
    layout.addWidget(title)
    edit = QPlainTextEdit()
    edit.setReadOnly(True)
    edit.setPlainText(diagnostics_text)
    layout.addWidget(edit, stretch=1)
    copy_btn = QPushButton("Copy diagnostics")
    copy_btn.clicked.connect(
        lambda: (
            QApplication.clipboard().setText(edit.toPlainText()),
            window.status("Diagnostics copied"),
        )
    )
    export_btn = QPushButton("Export support bundle")
    export_btn.clicked.connect(lambda: export_support_bundle(window, edit))
    validate_btn = QPushButton("Validate updater")
    validate_btn.clicked.connect(lambda: validate_updater_now(window, edit))
    clear_health_btn = QPushButton("Clear update health")
    clear_health_btn.clicked.connect(lambda: clear_update_health(window, edit))
    close_btn = QPushButton("Close")
    close_btn.clicked.connect(dlg.close)
    action_btns = QHBoxLayout()
    action_btns.addWidget(validate_btn)
    action_btns.addWidget(clear_health_btn)
    action_btns.addWidget(export_btn)
    layout.addLayout(action_btns)
    buttons = QHBoxLayout()
    buttons.addStretch()
    buttons.addWidget(copy_btn)
    buttons.addWidget(close_btn)
    layout.addLayout(buttons)
    window._app_diag_dialog = dlg
    dlg.show()
    return dlg
