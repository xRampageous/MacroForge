"""Menu and profile actions for MacroForge main window."""

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QInputDialog, QMenu, QMessageBox

from ui.icons import icon
from ui.theme import COLORS


def show_profile_menu(window):
    self = window
    C = COLORS
    menu = QMenu(self)
    menu.setStyleSheet(
        f"QMenu {{ background-color: {C['bg_tertiary']}; color: {C['text']}; "
        f"border: 1px solid {C['border']}; border-radius: 10px; padding: 6px; }} "
        f"QMenu::item {{ padding: 6px 18px; border-radius: 6px; }} "
        f"QMenu::item:selected {{ background-color: {C['bg_hover']}; color: {C['accent']}; }} "
        f"QMenu::separator {{ height: 1px; background-color: {C['border']}; margin: 4px 8px; }}"
    )
    add_heading("Library")
    menu.addAction("Profile / macro library     Ctrl+Alt+P", self.open_profile_library)
    menu.addSeparator()

    add_heading("Macro")
    menu.addAction("Save     Ctrl+S", lambda: (self._do_save_session(), self.status(f"Profile '{self.session_manager.active}' saved")))
    menu.addAction("Open macro editor     Ctrl+E", self.open_macro_editor)
    menu.addAction("Macro variables     Ctrl+Alt+V", self.open_variables_dialog)
    menu.addAction("Export MacroForge macro…", self.export_macroforge)
    menu.addAction("Import MacroForge macro…", self.import_macroforge)
    menu.addAction("Recovery / version history…", self.open_recovery_history)
    menu.addAction("Export CSV…", self.export_csv)
    menu.addAction("Import CSV…", self.import_csv)
    menu.addSeparator()

    add_heading("Playback")
    menu.addAction("Macro health / pre-flight     Ctrl+Shift+P", self.open_preflight_report)
    menu.addAction("Run from selected row     Ctrl+Enter", self.test_from_selected_row)
    menu.addAction("Scale coordinates to current screen", self.scale_actions_to_current_screen)
    menu.addAction("Reset statistics", self.reset_stats)
    menu.addAction("Clear all actions", self.clear_all)
    menu.addSeparator()

    add_heading("Diagnostics")
    menu.addAction("Playback diagnostics\u2026", self.open_playback_diagnostics)
    menu.addAction("App diagnostics\u2026", self.open_app_diagnostics)
    menu.addSeparator()

    add_heading("App")
    menu.addAction("Settings", self.open_settings_dialog)
    menu.addAction("Debug log", self.open_debug_viewer)
    menu.addAction("Build clean source ZIP…", self.run_clean_release_builder)
    menu.addAction("Check for Updates", self._check_update_manual)
    sender = self.sender()
    menu.exec(sender.mapToGlobal(sender.rect().bottomLeft()))
