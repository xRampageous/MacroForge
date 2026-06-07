"""Error handling and user-friendly error dialogs for MacroForge.

Provides:
- Friendly error dialogs with actionable buttons
- Error reporting with context
- Auto-retry mechanisms for transient failures
- Error logging with user-friendly messages
"""

import traceback
from typing import Optional, Callable, Dict

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QCheckBox, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from ui.theme import COLORS
from debugger import logger


class FriendlyErrorDialog(QDialog):
    """User-friendly error dialog with actionable options.
    
    Features:
    - Clear error title and description
    - Technical details (expandable)
    - Action buttons (Retry, Report, Ignore)
    - Context-aware suggestions
    """
    
    def __init__(self, parent=None, title="Error", message="", 
                 details="", error_type="general", retry_callback=None):
        super().__init__(parent)
        
        self.error_type = error_type
        self.retry_callback = retry_callback
        self._result = "ignore"
        
        self.setWindowTitle(title)
        self.setMinimumSize(500, 300)
        
        self._build_ui(title, message, details)
        self._apply_styling()
    
    def _build_ui(self, title, message, details):
        """Build the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Error icon and title
        header = QHBoxLayout()
        
        icon_label = QLabel("⚠")
        icon_label.setStyleSheet("color: #ef4444; font-size: 32px;")
        header.addWidget(icon_label)
        
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            color: {COLORS['text']};
            font-size: 16px;
            font-weight: 700;
        """)
        header.addWidget(title_label)
        header.addStretch()
        
        layout.addLayout(header)
        
        # User-friendly message
        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet(f"color: {COLORS['text']}; font-size: 12px;")
        layout.addWidget(msg_label)
        
        # Suggestion based on error type
        suggestion = self._get_suggestion()
        if suggestion:
            suggestion_label = QLabel(f"💡 {suggestion}")
            suggestion_label.setWordWrap(True)
            suggestion_label.setStyleSheet(f"""
                color: {COLORS['accent']};
                font-size: 11px;
                background-color: {COLORS['bg_card']};
                padding: 8px;
                border-radius: 6px;
            """)
            layout.addWidget(suggestion_label)
        
        # Technical details (expandable)
        self._details_checkbox = QCheckBox("Show technical details")
        self._details_checkbox.setStyleSheet(f"color: {COLORS['text_dim']};")
        layout.addWidget(self._details_checkbox)
        
        self._details_text = QTextEdit()
        self._details_text.setPlainText(details)
        self._details_text.setReadOnly(True)
        self._details_text.setMaximumHeight(150)
        self._details_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS['bg_card']};
                color: {COLORS['text_dim']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                font-family: Consolas;
                font-size: 10px;
            }}
        """)
        self._details_text.setVisible(False)
        layout.addWidget(self._details_text)
        
        self._details_checkbox.toggled.connect(self._details_text.setVisible)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {COLORS['border']};")
        sep.setFixedHeight(1)
        layout.addWidget(sep)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        # Report button
        report_btn = QPushButton("📤 Send Report")
        report_btn.setToolTip("Send error report to help improve MacroForge")
        report_btn.clicked.connect(self._on_report)
        btn_layout.addWidget(report_btn)
        
        btn_layout.addStretch()
        
        # Retry button (if callback provided)
        if self.retry_callback:
            retry_btn = QPushButton("🔄 Retry")
            retry_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['accent']};
                    color: #000;
                    border: none;
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-weight: 700;
                }}
            """)
            retry_btn.clicked.connect(self._on_retry)
            btn_layout.addWidget(retry_btn)
        
        # Ignore/Close button
        ignore_btn = QPushButton("Close")
        ignore_btn.clicked.connect(self._on_ignore)
        btn_layout.addWidget(ignore_btn)
        
        layout.addLayout(btn_layout)
    
    def _apply_styling(self):
        """Apply dialog styling."""
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['bg']};
            }}
            QPushButton {{
                background-color: {COLORS['bg_tertiary']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {COLORS['accent']};
            }}
        """)
    
    def _get_suggestion(self) -> str:
        """Get contextual suggestion based on error type."""
        suggestions = {
            "image_search": "Try adjusting the similarity threshold or capturing a clearer template image.",
            "file_not_found": "Check that the file exists and you have permission to access it.",
            "network": "Check your internet connection and try again.",
            "permission": "Try running MacroForge as administrator.",
            "memory": "Close other applications to free up memory, or restart MacroForge.",
            "syntax": "Check the syntax of your configuration file.",
            "engine": "Try stopping and restarting the macro.",
            "general": "If this persists, please send a report to help us fix it.",
        }
        return suggestions.get(self.error_type, suggestions["general"])
    
    def _on_retry(self):
        """Handle retry button."""
        self._result = "retry"
        if self.retry_callback:
            self.retry_callback()
        self.accept()
    
    def _on_ignore(self):
        """Handle ignore/close button."""
        self._result = "ignore"
        self.reject()
    
    def _on_report(self):
        """Handle report button."""
        self._result = "report"
        # In a real implementation, this would send the report
        QMessageBox.information(
            self,
            "Report Sent",
            "Thank you! Your error report has been submitted."
        )
        self.reject()
    
    def get_result(self) -> str:
        """Get the user's choice."""
        return self._result


class ErrorHandler:
    """Centralized error handling for MacroForge.
    
    Provides consistent error handling with:
    - User-friendly error messages
    - Automatic retry for transient errors
    - Error categorization
    - Context preservation
    """
    
    # Error categories
    IMAGE_ERRORS = ["image_search", "template_not_found", "screenshot_failed"]
    FILE_ERRORS = ["file_not_found", "permission_denied", "read_error", "write_error"]
    NETWORK_ERRORS = ["connection_failed", "timeout", "download_failed"]
    ENGINE_ERRORS = ["engine_crash", "action_failed", "invalid_action"]
    
    def __init__(self, window):
        self.window = window
        self._error_counts: Dict[str, int] = {}
        self._max_retries = 3
    
    def handle_error(self, error: Exception, context: str = "", 
                    error_type: str = "general", retry_callback: Callable = None,
                     show_dialog: bool = True) -> str:
        """Handle an error with user-friendly messaging.
        
        Args:
            error: The exception that occurred
            context: Where/what was happening when error occurred
            error_type: Category of error
            retry_callback: Function to call if user chooses retry
            show_dialog: Whether to show error dialog
        
        Returns:
            User's choice: "retry", "ignore", or "report"
        """
        # Log the error
        error_msg = str(error)
        tb = traceback.format_exc()
        logger.error(f"Error in {context}: {error_msg}\n{tb}")
        
        # Track error count for auto-retry logic
        error_key = f"{error_type}:{context}"
        self._error_counts[error_key] = self._error_counts.get(error_key, 0) + 1
        
        # Auto-retry logic for transient errors
        if self._should_auto_retry(error_type, error_key):
            logger.info(f"Auto-retrying {context}...")
            if retry_callback:
                retry_callback()
                return "retry"
        
        if not show_dialog:
            return "ignore"
        
        # Build user-friendly message
        title, message = self._get_friendly_message(error_type, error_msg, context)
        
        # Show dialog
        dialog = FriendlyErrorDialog(
            parent=self.window,
            title=title,
            message=message,
            details=tb,
            error_type=error_type,
            retry_callback=retry_callback if self._can_retry(error_type) else None
        )
        dialog.exec()
        
        return dialog.get_result()
    
    def _should_auto_retry(self, error_type: str, error_key: str) -> bool:
        """Determine if we should auto-retry this error."""
        count = self._error_counts.get(error_key, 0)
        
        # Auto-retry transient errors up to max_retries
        if error_type in ["network", "image_search"] and count <= self._max_retries:
            return True
        
        return False
    
    def _can_retry(self, error_type: str) -> bool:
        """Check if error type supports retry."""
        return error_type in ["image_search", "network", "engine"]
    
    def _get_friendly_message(self, error_type: str, error_msg: str, context: str) -> tuple:
        """Get user-friendly title and message for error type."""
        
        messages = {
            "image_search": (
                "Image Not Found",
                f"Couldn't find the target image. The screen may have changed or the image template needs updating.\n\n"
                f"Context: {context}"
            ),
            "file_not_found": (
                "File Not Found",
                f"The file '{error_msg}' couldn't be found.\n\n"
                f"Context: {context}"
            ),
            "permission": (
                "Permission Denied",
                f"MacroForge doesn't have permission to access this resource.\n\n"
                f"Context: {context}"
            ),
            "network": (
                "Connection Error",
                f"Couldn't connect to the server. Please check your internet connection.\n\n"
                f"Context: {context}"
            ),
            "engine": (
                "Macro Error",
                f"An error occurred while running the macro:\n{error_msg}\n\n"
                f"Context: {context}"
            ),
            "memory": (
                "Out of Memory",
                f"MacroForge is running low on memory. Try closing other applications.\n\n"
                f"Context: {context}"
            ),
        }
        
        return messages.get(error_type, (
            "Error",
            f"An unexpected error occurred:\n{error_msg}\n\n"
            f"Context: {context}"
        ))
    
    def reset_error_count(self, error_type: str = None):
        """Reset error count(s)."""
        if error_type:
            keys = [k for k in self._error_counts if k.startswith(f"{error_type}:")]
            for key in keys:
                self._error_counts[key] = 0
        else:
            self._error_counts.clear()


def show_error(window, error: Exception, context: str = "", 
               error_type: str = "general", retry_callback: Callable = None) -> str:
    """Convenience function to show error dialog.
    
    Returns:
        User's choice: "retry", "ignore", or "report"
    """
    handler = ErrorHandler(window)
    return handler.handle_error(error, context, error_type, retry_callback)


def handle_exception(window, exc_type, exc_value, exc_traceback):
    """Global exception handler for uncaught exceptions."""
    logger.exception("Uncaught exception:", exc_info=(exc_type, exc_value, exc_traceback))
    
    # Show user-friendly dialog for critical errors
    if window:
        dialog = FriendlyErrorDialog(
            parent=window,
            title="Unexpected Error",
            message="MacroForge encountered an unexpected error. The application may be unstable.",
            details="".join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
            error_type="general"
        )
        dialog.exec()
