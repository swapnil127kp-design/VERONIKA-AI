"""
VERONIKA AI - Chat Panel
Conversation interface with message history and input.
"""
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel,
    QLineEdit, QFrame, QSizePolicy, QProgressBar,
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
    """Main chat conversation panel with voice controls."""

    message_sent = Signal(str)
    voice_button_clicked = Signal()  # Emitted when mic button clicked
    voice_cancel_clicked = Signal()  # Emitted when cancel button clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_recording = False
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
        input_layout = QVBoxLayout(input_container)
        input_layout.setContentsMargins(12, 8, 12, 12)
        input_layout.setSpacing(6)

        # Text input row
        text_row = QWidget()
        text_layout = QHBoxLayout(text_row)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(8)

        self._input = ChatInput()
        self._input.submitted.connect(self._on_submit)

        self._send_btn = CyberButton("Send")
        self._send_btn.setFixedWidth(70)
        self._send_btn.clicked.connect(lambda: self._on_submit(self._input.text().strip()))

        text_layout.addWidget(self._input, 1)
        text_layout.addWidget(self._send_btn)

        # Voice controls row
        voice_row = QWidget()
        voice_layout = QHBoxLayout(voice_row)
        voice_layout.setContentsMargins(0, 0, 0, 0)
        voice_layout.setSpacing(8)

        # Microphone button
        self._mic_btn = CyberButton("🎤 Voice")
        self._mic_btn.setFixedWidth(100)
        self._mic_btn.clicked.connect(self._on_mic_clicked)

        # Recording indicator and status
        self._recording_label = QLabel("")
        self._recording_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_SECONDARY.name()};
                font-size: 13px;
                padding: 0 8px;
            }}
        """)
        self._recording_label.hide()

        # Level meter (shows RMS during recording)
        self._level_meter = QProgressBar()
        self._level_meter.setRange(0, 100)
        self._level_meter.setValue(0)
        self._level_meter.setTextVisible(False)
        self._level_meter.setFixedHeight(6)
        self._level_meter.setStyleSheet(f"""
            QProgressBar {{
                background-color: rgba(22, 22, 32, 180);
                border: 1px solid rgba(50, 55, 70, 100);
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {Colors.CYAN.name()},
                    stop:0.5 {Colors.GREEN.name()},
                    stop:1 {Colors.ORANGE.name()});
                border-radius: 2px;
            }}
        """)
        self._level_meter.hide()

        # Cancel button (shown during recording)
        self._cancel_btn = CyberButton("Cancel")
        self._cancel_btn.setFixedWidth(80)
        self._cancel_btn.clicked.connect(self._on_cancel_clicked)
        self._cancel_btn.hide()

        voice_layout.addWidget(self._mic_btn)
        voice_layout.addWidget(self._recording_label)
        voice_layout.addWidget(self._level_meter, 1)
        voice_layout.addWidget(self._cancel_btn)
        voice_layout.addStretch()

        input_layout.addWidget(text_row)
        input_layout.addWidget(voice_row)

        layout.addWidget(input_container)

    def _on_submit(self, text: str):
        if text:
            self._input.clear()
            self.message_sent.emit(text)

    def _on_mic_clicked(self):
        """Handle microphone button click."""
        self.voice_button_clicked.emit()

    def _on_cancel_clicked(self):
        """Handle cancel button click during recording."""
        self.voice_cancel_clicked.emit()

    def set_recording_state(self, is_recording: bool, status_text: str = ""):
        """Update UI to show recording state."""
        self._is_recording = is_recording

        if is_recording:
            self._mic_btn.setText("⏺ Recording")
            self._mic_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba(255, 70, 80, 200);
                    color: white;
                    border: 1px solid rgba(255, 100, 100, 150);
                    border-radius: 8px;
                    padding: 8px 12px;
                    font-size: 13px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: rgba(255, 90, 100, 220);
                }}
            """)
            self._recording_label.setText(status_text or "Listening...")
            self._recording_label.show()
            self._level_meter.show()
            self._cancel_btn.show()
            self._input.setEnabled(False)
            self._send_btn.setEnabled(False)
        else:
            self._mic_btn.setText("🎤 Voice")
            self._mic_btn.setStyleSheet("")  # Reset to default CyberButton style
            self._recording_label.hide()
            self._level_meter.hide()
            self._level_meter.setValue(0)
            self._cancel_btn.hide()
            self._input.setEnabled(True)
            self._send_btn.setEnabled(True)

    def update_recording_level(self, level: float):
        """Update the level meter during recording (0.0 to 1.0)."""
        if self._is_recording:
            self._level_meter.setValue(int(level * 100))

    def update_recording_status(self, status: str):
        """Update the status label during recording/transcription."""
        self._recording_label.setText(status)

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
        """Clear all messages."""
        count = self._messages_layout.count()
        for i in range(count - 1, -1, -1):
            item = self._messages_layout.itemAt(i)
            if item.widget() and not isinstance(item, type(self._messages_layout.itemAt(count - 1))):
                item.widget().deleteLater()

    def _scroll_to_bottom(self):
        """Scroll to the bottom of the message area."""
        scrollbar = self._scroll.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
