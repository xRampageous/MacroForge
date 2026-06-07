"""Action presets dialog for MacroForge.

Provides UI for browsing, managing, and applying action presets.
"""

from typing import Optional, List, Callable

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QComboBox, QScrollArea, QFrame, QMessageBox, QMenu,
    QInputDialog, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from ui.theme import COLORS
from action_presets import ActionPreset, ActionPresetManager
from debugger import logger


class PresetCard(QFrame):
    """Visual card for displaying a preset."""
    
    clicked = pyqtSignal(object)  # Preset
    apply_clicked = pyqtSignal(object)  # Preset
    
    def __init__(self, preset: ActionPreset, parent=None):
        super().__init__(parent)
        self.preset = preset
        self._setup_ui()
    
    def _setup_ui(self):
        self.setFixedSize(200, 120)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        
        # Title
        title = QLabel(self.preset.name)
        title.setStyleSheet(f"color: {COLORS['text']}; font-weight: 700; font-size: 13px;")
        layout.addWidget(title)
        
        # Description
        desc = QLabel(self.preset.description[:50] + "..." if len(self.preset.description) > 50 else self.preset.description)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        layout.addWidget(desc)
        
        layout.addStretch()
        
        # Type badge
        type_badge = QLabel(self.preset.action_type.upper())
        type_badge.setStyleSheet(f"""
            background-color: {COLORS['accent']};
            color: {COLORS['bg']};
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 600;
        """)
        layout.addWidget(type_badge)
    
    def enterEvent(self, event):
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_hover']};
                border: 2px solid {COLORS['accent']};
                border-radius: 8px;
            }}
        """)
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """)
        super().leaveEvent(event)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.preset)
        super().mousePressEvent(event)


class PresetDialog(QDialog):
    """Dialog for browsing and managing action presets."""
    
    preset_selected = pyqtSignal(object)  # ActionPreset
    
    def __init__(self, preset_manager: ActionPresetManager, parent=None):
        super().__init__(parent)
        self._preset_mgr = preset_manager
        self._selected_preset: Optional[ActionPreset] = None
        self._category_filter = "All"
        self._search_text = ""
        
        self.setWindowTitle("Action Presets")
        self.setMinimumSize(800, 600)
        self._setup_ui()
        self._load_presets()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Header
        header = QLabel("Action Presets")
        header.setStyleSheet(f"color: {COLORS['text']}; font-size: 20px; font-weight: 700;")
        layout.addWidget(header)
        
        subtitle = QLabel("Choose from predefined action templates or create your own")
        subtitle.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        layout.addWidget(subtitle)
        
        # Search and filter bar
        filter_layout = QHBoxLayout()
        
        # Search
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search presets...")
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px 12px;
                color: {COLORS['text']};
            }}
        """)
        self._search_input.textChanged.connect(self._on_search_changed)
        filter_layout.addWidget(self._search_input, stretch=1)
        
        # Category filter
        self._category_combo = QComboBox()
        self._category_combo.addItem("All Categories")
        self._category_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 12px;
                color: {COLORS['text']};
            }}
        """)
        self._category_combo.currentTextChanged.connect(self._on_category_changed)
        filter_layout.addWidget(self._category_combo)
        
        # Add button
        add_btn = QPushButton("+ New Preset")
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: {COLORS['bg']};
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {COLORS['accent_hover']}; }}
        """)
        add_btn.clicked.connect(self._on_add_preset)
        filter_layout.addWidget(add_btn)
        
        layout.addLayout(filter_layout)
        
        # Presets grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self._grid_widget = QFrame()
        self._grid_layout = QGridLayout(self._grid_widget)
        self._grid_layout.setSpacing(16)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        
        scroll.setWidget(self._grid_widget)
        layout.addWidget(scroll, stretch=1)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['bg_card']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px 20px;
            }}
            QPushButton:hover {{ background-color: {COLORS['bg_hover']}; }}
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        self._apply_btn = QPushButton("Apply Preset")
        self._apply_btn.setEnabled(False)
        self._apply_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: {COLORS['bg']};
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {COLORS['accent_hover']}; }}
            QPushButton:disabled {{ background-color: {COLORS['border']}; }}
        """)
        self._apply_btn.clicked.connect(self._on_apply)
        button_layout.addWidget(self._apply_btn)
        
        layout.addLayout(button_layout)
    
    def _load_presets(self):
        """Load presets into the grid."""
        # Clear existing
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Get categories for filter
        categories = set()
        presets = self._preset_mgr.get_all_presets()
        
        for preset in presets:
            categories.add(preset.category)
        
        # Update category combo
        current = self._category_combo.currentText()
        self._category_combo.clear()
        self._category_combo.addItem("All Categories")
        for cat in sorted(categories):
            self._category_combo.addItem(cat)
        
        if current in [self._category_combo.itemText(i) for i in range(self._category_combo.count())]:
            self._category_combo.setCurrentText(current)
        
        # Filter presets
        filtered = []
        for preset in presets:
            # Category filter
            if self._category_filter != "All" and preset.category != self._category_filter:
                continue
            
            # Search filter
            if self._search_text:
                search_lower = self._search_text.lower()
                if (search_lower not in preset.name.lower() and 
                    search_lower not in preset.description.lower() and
                    search_lower not in preset.action_type.lower()):
                    continue
            
            filtered.append(preset)
        
        # Add to grid (4 columns)
        for i, preset in enumerate(filtered):
            card = PresetCard(preset)
            card.clicked.connect(self._on_preset_clicked)
            self._grid_layout.addWidget(card, i // 4, i % 4)
        
        # Add stretch to bottom
        self._grid_layout.setRowStretch(self._grid_layout.rowCount(), 1)
    
    def _on_preset_clicked(self, preset: ActionPreset):
        """Handle preset card click."""
        self._selected_preset = preset
        self._apply_btn.setEnabled(True)
        self._apply_btn.setText(f"Apply '{preset.name}'")
    
    def _on_apply(self):
        """Apply selected preset."""
        if self._selected_preset:
            self.preset_selected.emit(self._selected_preset)
            self.accept()
    
    def _on_search_changed(self, text: str):
        """Handle search text change."""
        self._search_text = text
        self._load_presets()
    
    def _on_category_changed(self, category: str):
        """Handle category filter change."""
        self._category_filter = category if category != "All Categories" else "All"
        self._load_presets()
    
    def _on_add_preset(self):
        """Add new preset from current action."""
        # This would integrate with main window to create preset from selection
        QMessageBox.information(
            self,
            "Create Preset",
            "Select an action in the timeline and use the right-click menu to save as preset."
        )
    
    def get_selected_preset(self) -> Optional[ActionPreset]:
        """Get the selected preset."""
        return self._selected_preset
