"""
VERONIKA AI - Chat Panel
Conversation interface with message history and input.
"""
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel,
    QLineEdit, QFrame, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QKeyEvent

from ui.components import ChatBubble, CyberButton, Colors

logger = logging.getLogger(__name__)


class ChatInput(QLineEdit):
    """Styled chat input with enter-to-send."""

    submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Type a message or command...")
        self.setMinimumHeight(44)
        self.setStyleSheet(f"""
            QLineEdit {{
                background-color: rgba(22, 22, 32, 220);
                color: {Colors.TEXT_PRIMARY.name()};
                border: 1px solid rgba(50, 55, 70, 150);
                border-radius: 10px;
                padding: 10px 16px;
                font-size: 14px;
                font-family: 'Segoe UI', sans-serif;
            }}
            QLineEdit:focus {{
                border: 1px solid rgba(0, 200, 240, 120);
                background-color: rgba(22, 22, 32, 250);
            }}
            QLineEdit::placeholder {{
                color: rgba(80, 90, 110, 180);
            }}
        """)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            text = self.text().strip()
            if text:
                self.submitted.emit(text)
                self.clear()
        else:
            super().keyPressEvent(event)


class ChatPanel(QWidget):
    """Main chat conversation panel."""

    message_sent = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scroll area for messages
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: rgba(18, 18, 24, 200);
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 200, 240, 60);
                border-radius: 3px;
                min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

        self._messages_widget = QWidget()
        self._messages_layout = QVBoxLayout(self._messages_widget)
        self._messages_layout.setContentsMargins(12, 12, 12, 12)
        self._messages_layout.setSpacing(8)
        self._messages_layout.addStretch()

        self._scroll.setWidget(self._messages_widget)
        layout.addWidget(self._scroll, 1)

        # Input area
        input_container = QWidget()
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(12, 8, 12, 12)
        input_layout.setSpacing(8)

        self._input = ChatInput()
        self._input.submitted.connect(self._on_submit)

        self._send_btn = CyberButton("Send")
        self._send_btn.setFixedWidth(70)
        self._send_btn.clicked.connect(lambda: self._on_submit(self._input.text().strip()))

        input_layout.addWidget(self._input, 1)
        input_layout.addWidget(self._send_btn)

        layout.addWidget(input_container)

    def _on_submit(self, text: str):
        if text:
            self._input.clear()
            self.message_sent.emit(text)

    def add_user_message(self, text: str):
        """Add a user message bubble."""
        bubble = ChatBubble(text, is_user=True)
        self._messages_layout.insertWidget(self._messages_layout.count() - 1, bubble)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def add_assistant_message(self, text: str):
        """Add an assistant message bubble."""
        bubble = ChatBubble(text, is_user=False)
        self._messages_layout.insertWidget(self._messages_layout.count() - 1, bubble)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def update_last_assistant_message(self, text: str):
        """Update the last assistant message (for streaming)."""
        count = self._messages_layout.count()
        for i in range(count - 2, -1, -1):
            widget = self._messages_layout.itemAt(i).widget()
            if isinstance(widget, ChatBubble):
                # Find the QLabel with the message
                for child in widget.findChildren(QLabel):
                    if child.wordWrap():
                        child.setText(text)
                        QTimer.singleShot(50, self._scroll_to_bottom)
                        return
        # If no existing bubble, create new one
        self.add_assistant_message(text)

    def clear_messages(self):
        """Clear all chat messages."""
        while self._messages_layout.count() > 1:
            item = self._messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _scroll_to_bottom(self):
        vbar = self._scroll.verticalScrollBar()
        vbar.setValue(vbar.maximum())

    def set_input_enabled(self, enabled: bool):
        self._input.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)

    def focus_input(self):
        self._input.setFocus()
