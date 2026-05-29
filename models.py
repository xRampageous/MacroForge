import sys
import os
import json
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass, asdict
from copy import deepcopy
from datetime import datetime
from collections import deque

@dataclass
class Config:
    """Application configuration"""
    colors: Dict[str, str] = None
    session_file: str = "macroforge_session.json"
    retry_count: int = 3
    retry_delay: float = 0.1
    history_max_size: int = 50
    min_duration: float = 0.1
 
    def __post_init__(self):
        if self.colors is None:
            self.colors = {
                "bg":               "#0b0b11",
                "bg_secondary":     "#111118",
                "bg_tertiary":      "#181824",
                "accent":           "#20b87e",  # Vivid emerald green
                "accent_secondary": "#178a5e",  # Deeper green for hover
                "accent_glow":      "#0d2a1e",
                "text":             "#e8eaf0",
                "text_dim":         "#55566a",
                "border":           "#252535",
                "highlight":        "#20b87e",
                "lane":             "#2a3a4c",
                "lane_glow":        "#1a2535",
                "pause":            "#6b5740",
                "pause_glow":       "#2e2418",
                "error":            "#f05555",
                "hover":            "#1e1e2e",
                "playing":          "#38b4a8",  # Teal for playing row
                "playing_glow":     "#0d2520",
                "success":          "#44ee88",
                "warning":          "#f0a844",
                "neon_blue":        "#38b4ff",
                "neon_purple":      "#d26bff",
                "neon_gold":        "#f0a844",
                "glass":            "#ffffff08",
                "shadow":           "#00000040"
            }

# =========================================================
# DATA MODEL
# =========================================================
@dataclass
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

    def is_condition(self):
        return self.action_type == "condition"

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
        )

    def is_pause(self) -> bool:
        return self.action_type == "pause" or self.key in ("[PAUSE]", "[DELAY]")

    def is_image(self) -> bool:
        return self.action_type == "image"

    def is_click(self) -> bool:
        return self.action_type == "click"

# HISTORY / UNDO-REDO
# =========================================================
class HistoryManager:
    def __init__(self):
        self.undo_stack = deque()
        self.redo_stack = deque()
        self.max_size = 50

    def undo(self, current):
        if not self.undo_stack:
            return None
        self.redo_stack.append(deepcopy(current))
        return self.undo_stack.pop()

    def redo(self, current):
        if not self.redo_stack:
            return None
        self.undo_stack.append(deepcopy(current))
        return self.redo_stack.pop()

    def push(self, actions: List[Action]):
        """Save current state for undo"""
        self.undo_stack.append(deepcopy(actions))
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
            with open(self.settings_file) as f:
                return json.load(f).get("active_profile", self.DEFAULT_PROFILE)
        except Exception:
            return self.DEFAULT_PROFILE

    def _persist_active(self):
        try:
            with open(self.settings_file, "w") as f:
                json.dump({"active_profile": self._active}, f)
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
            with open(self._profile_path(name), "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def load_profile(self, name: str = None) -> Optional[Dict[str, Any]]:
        name = name or self._active
        try:
            path = self._profile_path(name)
            if os.path.exists(path):
                with open(path) as f:
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
            with open(path, "w") as f:
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
