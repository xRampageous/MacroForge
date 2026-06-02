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
        action.triggered.connect(lambda checked, n=name: self._switch_profile(n))
    menu.addSeparator()
    menu.addAction(icon("plus", 14, C["accent"]), "New profile\u2026", self._new_profile_dialog)
    menu.addAction(icon("edit", 14, C["accent"]), "Rename\u2026", self._rename_profile_dialog)
    menu.addAction(icon("trash", 14, C["error"]), "Delete", self._delete_profile_confirm)
    menu.exec(self.profile_btn.mapToGlobal(self.profile_btn.rect().bottomLeft()))


def switch_profile(window, name):
    self = window
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
    if ok and name.strip() and name != old:
        self.session_manager.rename_profile(old, name.strip())
        self._switch_profile(name.strip())


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
        self.session_manager.delete_profile(name)
        profiles = self.session_manager.list_profiles()
        if profiles:
            self._switch_profile(profiles[0])
        else:
            self.session_manager.active = "Default"
            self.action_model.clear()
            self.refresh()


def show_action_menu(window):
    self = window
    menu = QMenu(self)
    C = COLORS
    menu.setStyleSheet(f"""
        QMenu {{ background-color: {C['bg_tertiary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 10px; padding: 6px; }}
        QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
        QMenu::item:selected {{ background-color: {C['bg_hover']}; color: {C['accent']}; }}
        QMenu::separator {{ height: 1px; background-color: {C['border']}; margin: 4px 8px; }}
    """)
    def add_heading(text):
        action = QAction(text.upper(), self)
        action.setEnabled(False)
        menu.addAction(action)
        return action

    active = self.session_manager.active
    add_heading("Profiles")
    profiles_menu = QMenu("Profiles", self)
    profiles_menu.setStyleSheet(menu.styleSheet())
    for name in self.session_manager.list_profiles():
        action = QAction(f"  {'>' if name == active else ' '}  {name}", self)
        action.triggered.connect(lambda checked, n=name: self._switch_profile(n))
        profiles_menu.addAction(action)
    profiles_menu.addSeparator()
    profiles_menu.addAction("New profile\u2026", self._new_profile_dialog)
    profiles_menu.addAction("Rename\u2026", self._rename_profile_dialog)
    profiles_menu.addAction("Delete", self._delete_profile_confirm)
    menu.addMenu(profiles_menu)
    menu.addSeparator()

    add_heading("Macro")
    menu.addAction("Save     Ctrl+S", lambda: (self._do_save_session(), self.status(f"Profile '{self.session_manager.active}' saved")))
    menu.addAction("Export JSON\u2026", self.save)
    menu.addAction("Import JSON\u2026", self.load)
    menu.addAction("Export CSV\u2026", self.export_csv)
    menu.addAction("Import CSV\u2026", self.import_csv)
    menu.addSeparator()

    add_heading("Playback")
    menu.addAction("Run pre-flight check\u2026", lambda: self.run_preflight_check(show_success=True, allow_warning_prompt=False))
    menu.addAction("Test selected action", self.test_selected_action)
    menu.addAction("Test from selected row     Ctrl+Enter", self.test_from_selected_row)
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
    menu.addAction("Check for Updates", self._check_update_manual)
    sender = self.sender()
    menu.exec(sender.mapToGlobal(sender.rect().bottomLeft()))
