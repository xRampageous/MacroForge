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
    active = self.session_manager.active
    for name in self.session_manager.list_profiles():
        label = f"\u2713  {name}" if name == active else f"     {name}"
        action = menu.addAction(label)
        action.triggered.connect(lambda checked=False, n=name: self._switch_profile(n))
    menu.addSeparator()
    menu.addAction(icon("folder", 14, C["accent"]), "Open Profile / Macro Library     Ctrl+Alt+P", self.open_profile_library)
    menu.exec(self.profile_btn.mapToGlobal(self.profile_btn.rect().bottomLeft()))


def switch_profile(window, name):
    self = window
    if not name or name == self.session_manager.active:
        return
    self._do_save_session()
    self.session_manager.switch_profile(name)
    self.load_last_session()
    self._refresh_profile_btn()
    self.status(f"Switched to '{name}'")


def new_profile_dialog(window):
    self = window
    name, ok = QInputDialog.getText(self, "New Profile", "Profile name:")
    if ok and name.strip():
        name = name.strip()
        self.session_manager.save_profile([], {}, name)
        self._switch_profile(name)


def rename_profile_dialog(window):
    self = window
    old = self.session_manager.active
    name, ok = QInputDialog.getText(self, "Rename Profile", "New name:", text=old)
    if ok and name.strip() and name.strip() != old:
        new = name.strip()
        if self.session_manager.rename_profile(old, new):
            self._refresh_profile_btn()
            self.status(f"Renamed profile '{old}' to '{new}'")
        else:
            QMessageBox.warning(self, "Rename Profile", f"Could not rename '{old}' to '{new}'.")


def delete_profile_confirm(window):
    self = window
    name = self.session_manager.active
    reply = QMessageBox.question(
        self,
        "Delete Profile",
        f"Delete profile '{name}'?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    if reply == QMessageBox.StandardButton.Yes:
        if self.session_manager.delete_profile(name):
            self.load_last_session()
            self._refresh_profile_btn()
        else:
            QMessageBox.information(self, "Delete Profile", f"Profile '{name}' cannot be deleted.")


def _menu_style():
    C = COLORS
    return f"""
        QMenu {{ background-color: {C['bg_tertiary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 10px; padding: 6px; }}
        QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
        QMenu::item:selected {{ background-color: {C['bg_hover']}; color: {C['accent']}; }}
        QMenu::separator {{ height: 1px; background-color: {C['border']}; margin: 4px 8px; }}
    """


def show_action_menu(window):
    self = window
    menu = QMenu(self)
    menu.setStyleSheet(_menu_style())

    def add_heading(text):
        action = QAction(text.upper(), self)
        action.setEnabled(False)
        menu.addAction(action)

    add_heading("Library")
    menu.addAction("Profile / macro library     Ctrl+Alt+P", self.open_profile_library)
    menu.addSeparator()

    add_heading("Macro")
    menu.addAction("Save     Ctrl+S", lambda: (self._do_save_session(), self.status(f"Profile '{self.session_manager.active}' saved")))
    menu.addAction("Open macro editor     Ctrl+E", self.open_macro_editor)
    menu.addAction("Macro variables     Ctrl+Alt+V", self.open_variables_dialog)
    menu.addAction("Recovery / version history…", self.open_recovery_history)
    menu.addSeparator()

    add_heading("Playback")
    menu.addAction("Macro health / pre-flight     Ctrl+Shift+P", self.open_preflight_report)
    menu.addAction("Run from selected row     Ctrl+Enter", self.test_from_selected_row)
    menu.addAction("Scale coordinates to current screen", self.scale_actions_to_current_screen)
    menu.addAction("Reset statistics", self.reset_stats)
    menu.addAction("Clear all actions", self.clear_all)
    menu.addSeparator()

    add_heading("Diagnostics")
    menu.addAction("Playback diagnostics…", self.open_playback_diagnostics)
    menu.addAction("App diagnostics…", self.open_app_diagnostics)
    menu.addSeparator()

    add_heading("App")
    menu.addAction("Settings", self.open_settings_dialog)
    menu.addAction("Debug log", self.open_debug_viewer)
    menu.addAction("Build clean source ZIP…", self.run_clean_release_builder)
    menu.addAction("Check for Updates", self._check_update_manual)

    sender = self.sender()
    anchor = sender if sender is not None else getattr(self, "menu_top_btn", self)
    menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))
