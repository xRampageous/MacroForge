import sys
import os
import json
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict
from copy import deepcopy
from datetime import datetime
from collections import deque
from PyQt6.QtCore import QAbstractListModel, Qt, QModelIndex, QVariant

# =========================================================
# DATA MODEL
# =========================================================
@dataclass(slots=True)
class Action:
    key: str
    duration: float
    hold_mode: bool = False
    lane: int = 0
    random_delay: float = 0.0
    random_key: bool = False
    # Image-search fields
    action_type: str = "key"          # "key" | "pause" | "image" | "click"
    image_data: str = ""              # base64-encoded PNG template
    similarity: float = 0.95          # match confidence 0.0–1.0
    search_region: str = ""           # "" = whole screen, or "x,y,w,h"
    on_not_found: str = "skip"        # "skip" | "stop" | "warn"
    on_found_action: str = "continue" # "continue" | "press_key" | "click" | "double_click" | "move_to"
    on_found_key: str = ""            # key to press if on_found_action=press_key
    wait_timeout: float = 0.0         # seconds to poll for image (0 = single shot)
    click_offset_x: int = 0           # pixel offset from match centre X
    click_offset_y: int = 0           # pixel offset from match centre Y
    random_click: bool = False        # randomise click within match bbox (human-like)
    loop_until_found: bool = False    # loop whole sequence until image is found
    extra_images: str = ""            # "|"-separated additional base64 templates (OR match)
    position_mouse: bool = False      # move mouse to match before performing on_found_action
    label: str = ""                   # optional user-visible label shown on timeline
    repeat_count: int = 1             # how many times to execute this action before moving on
    jump_to_on_found: int = -1        # jump to action index N when image found (-1 = no jump)
    jump_to_on_not_found: int = -1    # jump to action index N when image not found (-1 = no jump)
    # Click action fields
    click_x: int = 0                  # absolute X coordinate to click
    click_y: int = 0                  # absolute Y coordinate to click
    click_button: str = "left"        # "left" | "right" | "middle" | "double"
    click_coord_mode: str = "absolute" # "absolute" | "foreground" | "offset" | "current"
    click_rand_radius: int = 0        # randomise click within ±N pixels
    # Conditional logic fields
    condition_type: str = "none"      # "none" | "pixel_color" | "variable"
    condition_x: int = 0              # screen X for pixel color check
    condition_y: int = 0              # screen Y for pixel color check
    condition_color: str = ""         # expected hex color (#RRGGBB)
    condition_var_name: str = ""      # variable name for comparison
    condition_var_value: str = ""     # expected variable value
    condition_jump_true: int = -1     # jump index if condition is true (-1 = fall through)
    condition_jump_false: int = -1    # jump index if condition is false (-1 = fall through)
    # Editor / premium timeline fields
    enabled: bool = True              # disabled actions remain in the timeline but are skipped at runtime
    group_name: str = ""             # folder/group header display name
    group_collapsed: bool = False     # collapsed group headers visually hide their member rows
    group_id: str = ""               # stable folder/group identifier shared by header + member rows
    group_color: str = ""            # optional accent color for group badges/header
    loop_count: int = 2               # loop block repeat count
    loop_target: int = -1             # row index to jump back to when this loop block runs
    block_depth: int = 0              # visual indent level for groups/blocks
    screen_width: int = 0             # source screen width when coordinate action was recorded/created
    screen_height: int = 0            # source screen height when coordinate action was recorded/created
    anchor_mode: str = "absolute"    # "absolute" | "scaled" reserved for screen adaptation
    # Power editor polish fields
    group_role: str = "normal"        # "normal" | "recovery"
    retry_attempts: int = 1            # smart retry attempts for image/condition actions
    retry_delay: float = 0.25          # delay between smart retries
    on_fail_action: str = "default"   # "default" | "continue" | "stop" | "jump" | "recovery_group"
    on_fail_target: int = -1           # group/header/row target for jump/recovery

    def is_condition(self):
        return self.action_type == "condition"

    def is_group(self) -> bool:
        return self.action_type == "group"

    def is_loop(self) -> bool:
        return self.action_type == "loop"

    def is_runnable(self) -> bool:
        return bool(self.enabled) and not (self.is_group() or self.is_loop())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> 'Action':
        return Action(
            d["key"],
            d["duration"],
            d.get("hold_mode", False),
            d.get("lane", 0),
            d.get("random_delay", 0.0),
            d.get("random_key", False),
            d.get("action_type", "key"),
            d.get("image_data", ""),
            d.get("similarity", 0.95),
            d.get("search_region", ""),
            d.get("on_not_found", "skip"),
            d.get("on_found_action", "continue"),
            d.get("on_found_key", ""),
            d.get("wait_timeout", 0.0),
            d.get("click_offset_x", 0),
            d.get("click_offset_y", 0),
            d.get("random_click", False),
            d.get("loop_until_found", False),
            d.get("extra_images", ""),
            d.get("position_mouse", False),
            d.get("label", ""),
            d.get("repeat_count", 1),
            d.get("jump_to_on_found", -1),
            d.get("jump_to_on_not_found", -1),
            d.get("click_x", 0),
            d.get("click_y", 0),
            d.get("click_button", "left"),
            d.get("click_coord_mode", "absolute"),
            d.get("click_rand_radius", 0),
            d.get("condition_type", "none"),
            d.get("condition_x", 0),
            d.get("condition_y", 0),
            d.get("condition_color", ""),
            d.get("condition_var_name", ""),
            d.get("condition_var_value", ""),
            d.get("condition_jump_true", -1),
            d.get("condition_jump_false", -1),
            d.get("enabled", True),
            d.get("group_name", ""),
            d.get("group_collapsed", False),
            d.get("group_id", ""),
            d.get("group_color", ""),
            d.get("loop_count", 2),
            d.get("loop_target", -1),
            d.get("block_depth", 0),
            d.get("screen_width", 0),
            d.get("screen_height", 0),
            d.get("anchor_mode", "absolute"),
            d.get("group_role", "normal"),
            d.get("retry_attempts", 1),
            d.get("retry_delay", 0.25),
            d.get("on_fail_action", "default"),
            d.get("on_fail_target", -1),
        )

    def is_pause(self) -> bool:
        return self.action_type == "pause" or self.key in ("[PAUSE]", "[DELAY]")

    def is_image(self) -> bool:
        return self.action_type == "image"

    def is_click(self) -> bool:
        return self.action_type == "click"

# =========================================================
# REACTIVE ACTION MODEL
# =========================================================
class ActionListModel(QAbstractListModel):
    ActionRole = Qt.ItemDataRole.UserRole + 1

    def __init__(self, actions=None):
        super().__init__()
        self._actions = actions or []

    # -------------------------
    # REQUIRED MODEL METHODS
    # -------------------------
    def rowCount(self, parent=QModelIndex()):
        return len(self._actions)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() < 0 or index.row() >= len(self._actions):
            return QVariant()

        action = self._actions[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            return (getattr(action, "label", "") or getattr(action, "key", "") or "")

        if role == self.ActionRole:
            return action

        return QVariant()

    def flags(self, index):
        base = super().flags(index)
        if index.isValid():
            return base | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsDragEnabled
        return base | Qt.ItemFlag.ItemIsDropEnabled

    def roleNames(self):
        return {
            self.ActionRole: b"action"
        }

    # -------------------------
    # API (REACTIVE UPDATES)
    # -------------------------
    def add_action(self, action):
        self.insert_action(len(self._actions), action)

    def insert_action(self, row, action):
        row = max(0, min(row, len(self._actions)))
        self.beginInsertRows(QModelIndex(), row, row)
        self._actions.insert(row, action)
        self.endInsertRows()
        return row

    def remove_action(self, row):
        if 0 <= row < len(self._actions):
            self.beginRemoveRows(QModelIndex(), row, row)
            self._actions.pop(row)
            self.endRemoveRows()

    def clear(self):
        self.beginResetModel()
        self._actions.clear()
        self.endResetModel()

    def get(self, row):
        return self._actions[row]

    def set_actions(self, actions):
        """Replace the backing list while preserving Qt model reset semantics."""
        self.beginResetModel()
        self._actions = list(actions or [])
        self.endResetModel()

    def replace_action(self, row, action):
        """Replace one action and notify any attached views/delegates."""
        if 0 <= row < len(self._actions):
            self._actions[row] = action
            idx = self.index(row, 0)
            self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DisplayRole, self.ActionRole])
            return True
        return False

    def move_action(self, source, target):
        if source == target or source < 0 or source >= len(self._actions):
            return False
        target = max(0, min(target, len(self._actions) - 1))
        self.beginResetModel()
        action = self._actions.pop(source)
        self._actions.insert(target, action)
        self.endResetModel()
        return True

    def actions(self):
        return self._actions

# HISTORY / UNDO-REDO
# =========================================================
class HistoryManager:
    def __init__(self, max_size=50):
        self.undo_stack = deque()
        self.redo_stack = deque()
        self.max_size = max_size

    def _snapshot(self, actions: List[Action], timeline_state=None) -> dict:
        return {
            "actions": [a.to_dict() for a in actions],
            "timeline_state": deepcopy(timeline_state) if timeline_state is not None else None,
            "with_timeline": timeline_state is not None,
        }

    def _restore(self, snapshot: dict, force_timeline: bool = False):
        actions = [Action.from_dict(d) for d in snapshot["actions"]]
        timeline_state = deepcopy(snapshot.get("timeline_state"))
        if force_timeline or snapshot.get("with_timeline"):
            return actions, timeline_state
        return actions

    def undo(self, current, current_timeline_state=None):
        if not self.undo_stack:
            return None
        self.redo_stack.append(self._snapshot(current, current_timeline_state))
        return self._restore(self.undo_stack.pop(), current_timeline_state is not None)

    def redo(self, current, current_timeline_state=None):
        if not self.redo_stack:
            return None
        self.undo_stack.append(self._snapshot(current, current_timeline_state))
        return self._restore(self.redo_stack.pop(), current_timeline_state is not None)

    def push(self, actions: List[Action], timeline_state=None):
        """Save current state for undo"""
        self.undo_stack.append(self._snapshot(actions, timeline_state))
        self.redo_stack.clear()
        if len(self.undo_stack) > self.max_size:
            self.undo_stack.popleft()
 
    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0
 
    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0

class ProfileManager:
    """
    Multi-profile persistence.
    Profiles are stored as JSON files in:
      %APPDATA%/MacroForge/profiles/<name>.json   (installed)
      <script_dir>/profiles/<name>.json           (dev / portable)
    settings.json in the root stores the last active profile name.
    """
    DEFAULT_PROFILE = "default"

    def __init__(self):
        if getattr(sys, "frozen", False):
            base = os.path.join(os.environ.get("APPDATA", os.path.dirname(sys.executable)),
                                "MacroForge")
        else:
            base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MacroForge")
        self.base_dir     = base
        self.profiles_dir = os.path.join(base, "profiles")
        self.settings_file = os.path.join(base, "settings.json")
        os.makedirs(self.profiles_dir, exist_ok=True)

        self._active: str = self._load_last_active()

    # ── internal ──────────────────────────────────────────────────
    def _profile_path(self, name: str) -> str:
        safe = "".join(c for c in name if c.isalnum() or c in " _-").strip() or "profile"
        return os.path.join(self.profiles_dir, safe + ".json")

    def _load_last_active(self) -> str:
        try:
            with open(self.settings_file, "r", encoding="utf-8") as f:
                return json.load(f).get("active_profile", self.DEFAULT_PROFILE)
        except Exception:
            return self.DEFAULT_PROFILE

    def _persist_active(self):
        try:
            data = {}
            if os.path.exists(self.settings_file):
                try:
                    with open(self.settings_file, "r", encoding="utf-8") as f:
                        data = json.load(f) or {}
                except Exception:
                    data = {}
            data["active_profile"] = self._active
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    # ── public API ────────────────────────────────────────────────
    @property
    def active(self) -> str:
        return self._active

    def list_profiles(self) -> list:
        """Return sorted list of profile names (without .json)."""
        try:
            names = [os.path.splitext(f)[0]
                     for f in os.listdir(self.profiles_dir)
                     if f.endswith(".json")]
            return sorted(names) or [self.DEFAULT_PROFILE]
        except Exception:
            return [self.DEFAULT_PROFILE]

    def save_profile(self, actions, settings, name: str = None):
        name = name or self._active
        try:
            data = {
                "profile":   name,
                "actions":   [a.to_dict() for a in actions],
                "settings":  settings,
                "timestamp": datetime.now().isoformat(),
            }
            with open(self._profile_path(name), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def load_profile(self, name: str = None) -> Optional[Dict[str, Any]]:
        name = name or self._active
        try:
            path = self._profile_path(name)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    def switch_profile(self, name: str):
        self._active = name
        self._persist_active()

    def rename_profile(self, old: str, new: str) -> bool:
        try:
            src = self._profile_path(old)
            dst = self._profile_path(new)
            if not os.path.exists(src) or os.path.exists(dst):
                return False
            os.rename(src, dst)
            if self._active == old:
                self._active = new
                self._persist_active()
            return True
        except Exception:
            return False

    def delete_profile(self, name: str) -> bool:
        if name == self.DEFAULT_PROFILE:
            return False
        try:
            path = self._profile_path(name)
            if os.path.exists(path):
                os.remove(path)
            if self._active == name:
                self._active = self.DEFAULT_PROFILE
                self._persist_active()
            return True
        except Exception:
            return False

    def new_profile(self, name: str) -> bool:
        """Create empty profile file; returns False if name already taken."""
        path = self._profile_path(name)
        if os.path.exists(path):
            return False
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"profile": name, "actions": [], "settings": {},
                           "timestamp": datetime.now().isoformat()}, f, indent=2)
            return True
        except Exception:
            return False

    # Legacy shims so existing call-sites keep working
    def save_session(self, actions, settings):
        self.save_profile(actions, settings)

    def load_session(self):
        return self.load_profile()

    def clear_session(self):
        self.delete_profile(self._active)


class SettingsManager:
    """
    Persistent application-wide settings stored in
    %APPDATA%/MacroForge/settings.json alongside the active profile key.
    """

    DEFAULTS = {
        "hotkeys": {
            "start": "f5",
            "stop": "f6",
            "record": "f7",
            "toggle": "f9",
            "esc": "esc",
            "undo": "Ctrl+Z",
            "redo": "Ctrl+Y",
            "copy": "Ctrl+C",
            "paste": "Ctrl+V",
            "duplicate": "Ctrl+D",
            "delete": "Delete",
            "delete_alt": "Ctrl+Delete",
            "select_all": "Ctrl+A",
            "group": "Ctrl+G",
            "ungroup": "Ctrl+Shift+G",
            "play_pause": "Space",
            "stop_deselect": "Escape",
            "save": "Ctrl+S",
            "search": "Ctrl+F",
            "run_from_selected": "Ctrl+Enter",
            "macro_editor": "Ctrl+E",
            "preflight": "Ctrl+Shift+P",
            "toggle_runtime_log": "Ctrl+Shift+L",
            "variables": "Ctrl+Alt+V",
            "profile_library": "Ctrl+Alt+P",
        },
        "start_minimized": False,
        "auto_save": True,
        "default_loops": 1,
        "default_speed": 1.0,
    }

    def __init__(self, base_dir: str = None):
        if base_dir is None:
            if getattr(sys, "frozen", False):
                base_dir = os.path.join(
                    os.environ.get("APPDATA", os.path.dirname(sys.executable)),
                    "MacroForge",
                )
            else:
                base_dir = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), "MacroForge"
                )
        self._file = os.path.join(base_dir, "settings.json")
        os.makedirs(base_dir, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        try:
            with open(self._file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                # Deep-merge with defaults so new keys get defaults automatically
                merged = deepcopy(self.DEFAULTS)
                merged.update(raw)
                if "hotkeys" in raw and isinstance(raw["hotkeys"], dict):
                    merged["hotkeys"] = {**self.DEFAULTS["hotkeys"], **raw["hotkeys"]}
                return merged
        except Exception:
            pass
        return deepcopy(self.DEFAULTS)

    def _save(self):
        try:
            # Preserve externally-managed keys (e.g. active_profile from ProfileManager)
            out = dict(self._data)
            if os.path.exists(self._file):
                try:
                    with open(self._file, "r", encoding="utf-8") as f:
                        existing = json.load(f) or {}
                    if "active_profile" in existing:
                        out["active_profile"] = existing["active_profile"]
                except Exception:
                    pass
            with open(self._file, "w", encoding="utf-8") as f:
                json.dump(out, f, indent=2)
        except Exception:
            pass

    @property
    def settings(self) -> dict:
        return self._data

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value):
        self._data[key] = value
        self._save()

    def save(self):
        self._save()

    def all(self) -> dict:
        return deepcopy(self._data)
