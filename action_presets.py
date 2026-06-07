"""Action presets system for MacroForge.

Provides reusable action templates with pre-configured settings.
"""

import json
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from copy import deepcopy

from debugger import logger


@dataclass
class ActionPreset:
    """A reusable action preset with pre-configured settings."""
    
    name: str
    description: str
    action_type: str  # "key", "image", "click", "pause", "group", "condition", "loop"
    
    # Common fields
    duration: float = 0.1
    label: str = ""
    
    # Key action fields
    key: str = ""
    hold_mode: bool = False
    random_delay: float = 0.0
    random_key: bool = False
    repeat_count: int = 1
    
    # Image action fields
    similarity: float = 0.95
    wait_timeout: float = 0.0
    on_not_found: str = "skip"
    on_found_action: str = "continue"
    search_region: str = ""
    click_offset_x: int = 0
    click_offset_y: int = 0
    random_click: bool = False
    loop_until_found: bool = False
    retry_attempts: int = 1
    retry_delay: float = 0.25
    on_fail_action: str = "default"
    
    # Click action fields
    click_button: str = "left"
    click_rand_radius: int = 0
    click_coord_mode: str = "absolute"
    
    # Pause action fields
    # (uses duration)
    
    # Group fields
    group_color: str = ""
    group_collapsed: bool = False
    
    # Condition fields
    condition_type: str = "none"
    condition_x: int = 0
    condition_y: int = 0
    condition_color: str = ""
    
    # Loop fields
    loop_count: int = 2
    
    # Metadata
    tags: List[str] = None
    category: str = "General"
    icon: str = ""
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert preset to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ActionPreset':
        """Create preset from dictionary."""
        # Filter to only valid fields
        valid_fields = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**valid_fields)
    
    def apply_to_action(self, action):
        """Apply preset values to an action object."""
        fields = [
            'duration', 'label', 'key', 'hold_mode', 'random_delay', 'random_key',
            'repeat_count', 'similarity', 'wait_timeout', 'on_not_found',
            'on_found_action', 'search_region', 'click_offset_x', 'click_offset_y',
            'random_click', 'loop_until_found', 'retry_attempts', 'retry_delay',
            'on_fail_action', 'click_button', 'click_rand_radius', 'click_coord_mode',
            'group_color', 'group_collapsed', 'condition_type', 'condition_x',
            'condition_y', 'condition_color', 'loop_count'
        ]
        
        for field in fields:
            value = getattr(self, field, None)
            if value is not None and hasattr(action, field):
                setattr(action, field, deepcopy(value))
        
        # Ensure action_type is set
        action.action_type = self.action_type


class ActionPresetManager:
    """Manages action presets storage and retrieval."""
    
    DEFAULT_PRESETS = [
        ActionPreset(
            name="Quick Key Press",
            description="Brief key press with minimal delay",
            action_type="key",
            duration=0.05,
            random_delay=0.01,
            category="Key Actions",
            icon="key"
        ),
        ActionPreset(
            name="Hold Key",
            description="Hold key down for a duration",
            action_type="key",
            duration=0.5,
            hold_mode=True,
            category="Key Actions",
            icon="key"
        ),
        ActionPreset(
            name="Smart Image Search",
            description="Wait up to 5 seconds for image with retry",
            action_type="image",
            similarity=0.9,
            wait_timeout=5.0,
            retry_attempts=3,
            retry_delay=0.5,
            on_not_found="stop",
            category="Image Actions",
            icon="image"
        ),
        ActionPreset(
            name="Quick Image Check",
            description="Single-shot image check with no wait",
            action_type="image",
            similarity=0.95,
            wait_timeout=0.0,
            on_not_found="skip",
            category="Image Actions",
            icon="image"
        ),
        ActionPreset(
            name="Human-like Click",
            description="Randomized click within target area",
            action_type="click",
            click_button="left",
            click_rand_radius=10,
            duration=0.1,
            random_delay=0.05,
            category="Click Actions",
            icon="click"
        ),
        ActionPreset(
            name="Right Click",
            description="Right mouse button click",
            action_type="click",
            click_button="right",
            duration=0.1,
            category="Click Actions",
            icon="click"
        ),
        ActionPreset(
            name="Short Pause",
            description="Brief 0.5 second delay",
            action_type="pause",
            duration=0.5,
            category="Timing",
            icon="pause"
        ),
        ActionPreset(
            name="Medium Pause",
            description="1 second delay",
            action_type="pause",
            duration=1.0,
            category="Timing",
            icon="pause"
        ),
        ActionPreset(
            name="Long Pause",
            description="5 second delay",
            action_type="pause",
            duration=5.0,
            category="Timing",
            icon="pause"
        ),
        ActionPreset(
            name="Blue Folder",
            description="Grouped actions with blue accent",
            action_type="group",
            group_color="#3b82f6",
            group_collapsed=False,
            category="Groups",
            icon="group"
        ),
        ActionPreset(
            name="Red Recovery",
            description="Recovery action group (red)",
            action_type="group",
            group_color="#ef4444",
            group_collapsed=True,
            category="Groups",
            icon="group"
        ),
        ActionPreset(
            name="Loop 2x",
            description="Repeat block 2 times",
            action_type="loop",
            loop_count=2,
            category="Loops",
            icon="loop"
        ),
        ActionPreset(
            name="Loop 5x",
            description="Repeat block 5 times",
            action_type="loop",
            loop_count=5,
            category="Loops",
            icon="loop"
        ),
        ActionPreset(
            name="Pixel Color Check",
            description="Check pixel color at coordinates",
            action_type="condition",
            condition_type="pixel_color",
            category="Conditions",
            icon="condition"
        ),
    ]
    
    def __init__(self, base_dir: str = None):
        """Initialize preset manager.
        
        Args:
            base_dir: Directory to store presets (default: ~/.macroforge)
        """
        if base_dir is None:
            base_dir = os.path.expanduser("~/.macroforge")
        
        self.presets_dir = os.path.join(base_dir, "presets")
        self.presets_file = os.path.join(self.presets_dir, "action_presets.json")
        
        self._presets: Dict[str, ActionPreset] = {}
        self._ensure_dir()
        self._load_presets()
    
    def _ensure_dir(self):
        """Ensure presets directory exists."""
        os.makedirs(self.presets_dir, exist_ok=True)
    
    def _load_presets(self):
        """Load presets from file or initialize defaults."""
        if os.path.exists(self.presets_file):
            try:
                with open(self.presets_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for preset_data in data.get('presets', []):
                    preset = ActionPreset.from_dict(preset_data)
                    self._presets[preset.name] = preset
                
                logger.info(f"Loaded {len(self._presets)} presets")
            except Exception as e:
                logger.warning(f"Failed to load presets: {e}")
                self._load_defaults()
        else:
            self._load_defaults()
    
    def _load_defaults(self):
        """Load default presets."""
        for preset in self.DEFAULT_PRESETS:
            self._presets[preset.name] = preset
        self._save_presets()
        logger.info(f"Initialized {len(self._presets)} default presets")
    
    def _save_presets(self):
        """Save presets to file."""
        try:
            data = {
                'presets': [p.to_dict() for p in self._presets.values()]
            }
            with open(self.presets_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save presets: {e}")
    
    def get_preset(self, name: str) -> Optional[ActionPreset]:
        """Get a preset by name."""
        return self._presets.get(name)
    
    def get_all_presets(self) -> List[ActionPreset]:
        """Get all presets."""
        return list(self._presets.values())
    
    def get_presets_by_category(self, category: str) -> List[ActionPreset]:
        """Get presets filtered by category."""
        return [p for p in self._presets.values() if p.category == category]
    
    def get_presets_by_type(self, action_type: str) -> List[ActionPreset]:
        """Get presets filtered by action type."""
        return [p for p in self._presets.values() if p.action_type == action_type]
    
    def get_categories(self) -> List[str]:
        """Get list of all categories."""
        return sorted(set(p.category for p in self._presets.values()))
    
    def add_preset(self, preset: ActionPreset) -> bool:
        """Add or update a preset."""
        try:
            self._presets[preset.name] = preset
            self._save_presets()
            logger.info(f"Saved preset: {preset.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to add preset: {e}")
            return False
    
    def delete_preset(self, name: str) -> bool:
        """Delete a preset."""
        if name in self._presets:
            del self._presets[name]
            self._save_presets()
            logger.info(f"Deleted preset: {name}")
            return True
        return False
    
    def duplicate_preset(self, name: str, new_name: str) -> Optional[ActionPreset]:
        """Duplicate an existing preset."""
        preset = self._presets.get(name)
        if not preset:
            return None
        
        new_preset = ActionPreset.from_dict(preset.to_dict())
        new_preset.name = new_name
        self.add_preset(new_preset)
        return new_preset
    
    def create_from_action(self, name: str, description: str, 
                          action, category: str = "Custom") -> ActionPreset:
        """Create a preset from an existing action."""
        preset = ActionPreset(
            name=name,
            description=description,
            action_type=getattr(action, 'action_type', 'key'),
            category=category
        )
        
        # Copy all applicable fields from action
        for field in ActionPreset.__dataclass_fields__:
            if field in ('name', 'description', 'action_type', 'tags', 'category', 'icon'):
                continue
            if hasattr(action, field):
                setattr(preset, field, deepcopy(getattr(action, field)))
        
        self.add_preset(preset)
        return preset
    
    def search_presets(self, query: str) -> List[ActionPreset]:
        """Search presets by name, description, or tags."""
        query = query.lower()
        results = []
        
        for preset in self._presets.values():
            if (query in preset.name.lower() or
                query in preset.description.lower() or
                any(query in tag.lower() for tag in preset.tags)):
                results.append(preset)
        
        return results


# Global instance for convenience
_preset_manager: Optional[ActionPresetManager] = None


def get_preset_manager() -> ActionPresetManager:
    """Get or create the global preset manager."""
    global _preset_manager
    if _preset_manager is None:
        _preset_manager = ActionPresetManager()
    return _preset_manager
