"""
VERONIKA AI - Sidebar
Conversation history, quick actions, and memory panel.
"""
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QPushButton, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont

from ui.components import Colors, CyberButton, GlassCard

logger = logging.getLogger(__name__)


class ConversationItem(QFrame):
    """A single conversation entry in the sidebar."""

    clicked = Signal(int)
    deleted = Signal(int)

    def __init__(self, conv_id: int, title: str, updated_at: str = "", parent=None):
        super().__init__(parent)
        self.conv_id = conv_id
        self._selected = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(52)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 8, 6)
        layout.setSpacing(6)

        info = QVBoxLayout()
        info.setSpacing(2)

        self._title_label = QLabel(title or "New Conversation")
        self._title_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_PRIMARY.name()};
                font-size: 12px;
                font-weight: 600;
            }}
        """)

        time_text = updated_at[:16].replace("T", "  ") if updated_at else ""
        self._time_label = QLabel(time_text)
        self._time_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_DIM.name()};
                font-size: 10px;
            }}
        """)

        info.addWidget(self._title_label)
        info.addWidget(self._time_label)
        layout.addLayout(info, 1)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(22, 22)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Colors.TEXT_DIM.name()};
                border: none;
                font-size: 11px;
                border-radius: 11px;
            }}
            QPushButton:hover {{
                background: rgba(255, 70, 80, 30);
                color: {Colors.RED.name()};
            }}
        """)
        del_btn.clicked.connect(lambda: self.deleted.emit(self.conv_id))
        layout.addWidget(del_btn)

        self._update_style()

    def set_selected(self, selected: bool):
        self._selected = selected
        self._update_style()

    def _update_style(self):
        if self._selected:
            bg = "rgba(0, 200, 240, 15)"
            border = "rgba(0, 200, 240, 50)"
        else:
            bg = "transparent"
            border = "transparent"

        self.setStyleSheet(f"""
            ConversationItem {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            ConversationItem:hover {{
                background: rgba(40, 45, 60, 120);
                border: 1px solid rgba(50, 55, 70, 100);
            }}
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.conv_id)
        super().mousePressEvent(event)


class Sidebar(QWidget):
    """Sidebar with conversation history and quick actions."""

    conversation_selected = Signal(int)
    conversation_deleted = Signal(int)
    new_conversation = Signal()
    open_settings = Signal()
    open_screenshot = Signal()
    toggle_voice = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(260)
        self.setStyleSheet(f"""
            Sidebar {{
                background-color: rgba(20, 20, 28, 240);
                border-right: 1px solid rgba(50, 55, 70, 100);
            }}
        """)
        self._items: dict[int, ConversationItem] = {}
        self._current_id: int | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 14, 10, 10)
        layout.setSpacing(8)

        # Logo / title
        header = QLabel("VERONIKA AI")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet(f"""
            QLabel {{
                color: {Colors.CYAN.name()};
                font-size: 16px;
                font-weight: 800;
                letter-spacing: 3px;
                padding: 6px 0;
            }}
        """)
        layout.addWidget(header)

        # New conversation button
        new_btn = CyberButton("＋  New Chat")
        new_btn.clicked.connect(self.new_conversation.emit)
        layout.addWidget(new_btn)

        # Section label
        section_label = QLabel("CONVERSATIONS")
        section_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_DIM.name()};
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 2px;
                padding-top: 6px;
            }}
        """)
        layout.addWidget(section_label)

        # Scrollable conversation list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 200, 240, 40);
                border-radius: 2px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(2)
        self._list_layout.addStretch()

        scroll.setWidget(self._list_widget)
        layout.addWidget(scroll, 1)

        # Quick actions
        actions_label = QLabel("QUICK ACTIONS")
        actions_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_DIM.name()};
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 2px;
                padding-top: 4px;
            }}
        """)
        layout.addWidget(actions_label)

        btn_row1 = QHBoxLayout()
        btn_row1.setSpacing(6)

        voice_btn = CyberButton("🎙 Voice", Colors.GREEN)
        voice_btn.clicked.connect(self.toggle_voice.emit)
        voice_btn.setFixedHeight(32)
        btn_row1.addWidget(voice_btn)

        screenshot_btn = CyberButton("📸 Screen", Colors.PURPLE)
        screenshot_btn.clicked.connect(self.open_screenshot.emit)
        screenshot_btn.setFixedHeight(32)
        btn_row1.addWidget(screenshot_btn)

        layout.addLayout(btn_row1)

        settings_btn = CyberButton("⚙  Settings", Colors.TEXT_SECONDARY)
        settings_btn.setFixedHeight(32)
        settings_btn.clicked.connect(self.open_settings.emit)
        layout.addWidget(settings_btn)

    def set_conversations(self, conversations: list):
        """Populate the conversation list."""
        # Clear existing items
        self._items.clear()
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for conv in conversations:
            item = ConversationItem(
                conv["id"], conv.get("title", ""), conv.get("updated_at", "")
            )
            item.clicked.connect(self._on_item_clicked)
            item.deleted.connect(self.conversation_deleted.emit)
            self._items[conv["id"]] = item
            self._list_layout.insertWidget(self._list_layout.count() - 1, item)

        if self._current_id and self._current_id in self._items:
            self._items[self._current_id].set_selected(True)

    def _on_item_clicked(self, conv_id: int):
        self.select_conversation(conv_id)
        self.conversation_selected.emit(conv_id)

    def select_conversation(self, conv_id: int):
        """Highlight a conversation in the list."""
        if self._current_id and self._current_id in self._items:
            self._items[self._current_id].set_selected(False)
        self._current_id = conv_id
        if conv_id in self._items:
            self._items[conv_id].set_selected(True)
