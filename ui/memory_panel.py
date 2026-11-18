"""
VERONIKA AI - Memory Panel
UI component for viewing, searching, and managing categorized memories.
"""
import logging
from datetime import datetime
from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QLabel, QFrame, QScrollArea, QMessageBox,
    QDialog, QTextEdit,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QColor

from ui.components import Colors, CyberButton

logger = logging.getLogger(__name__)


class MemoryDetailDialog(QDialog):
    """Dialog for viewing/editing memory details."""

    def __init__(self, memory_item: dict, parent=None):
        super().__init__(parent)
        self.memory_item = memory_item
        self.setWindowTitle("Memory Details")
        self.setMinimumSize(500, 400)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Colors.BG_DARK.name()};
                color: {Colors.TEXT_PRIMARY.name()};
            }}
            QLabel {{
                color: {Colors.TEXT_PRIMARY.name()};
            }}
            QTextEdit {{
                background-color: rgba(22, 22, 32, 200);
                color: {Colors.TEXT_PRIMARY.name()};
                border: 1px solid rgba(50, 55, 70, 100);
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Header with ID and timestamp
        header_layout = QHBoxLayout()
        id_label = QLabel(f"ID: {self.memory_item.get('id', 'N/A')}")
        id_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        timestamp = self.memory_item.get("timestamp", "N/A")
        time_label = QLabel(f"Created: {timestamp}")
        time_label.setFont(QFont("Segoe UI", 9))
        time_label.setStyleSheet("color: rgba(100, 150, 200, 180);")
        header_layout.addWidget(id_label)
        header_layout.addStretch()
        header_layout.addWidget(time_label)
        layout.addLayout(header_layout)

        # Relevance score
        score = self.memory_item.get("relevance_score", 0.0)
        score_label = QLabel(f"Relevance Score: {score:.2f}")
        score_label.setStyleSheet(f"color: {'#00c8f0' if score > 0.7 else '#90ee90' if score > 0.5 else '#ffb347'};")
        layout.addWidget(score_label)

        # Content
        content_label = QLabel("Content:")
        content_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(content_label)

        content_text = QTextEdit()
        content_text.setText(self.memory_item.get("content", ""))
        content_text.setReadOnly(True)
        layout.addWidget(content_text, 1)

        # Metadata
        metadata_label = QLabel("Metadata:")
        metadata_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(metadata_label)

        metadata_text = QTextEdit()
        import json
        metadata = self.memory_item.get("metadata_json", "{}")
        try:
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
            metadata_str = json.dumps(metadata, indent=2)
        except:
            metadata_str = str(metadata)
        metadata_text.setText(metadata_str)
        metadata_text.setReadOnly(True)
        metadata_text.setMaximumHeight(120)
        layout.addWidget(metadata_text)

        # Close button
        close_btn = CyberButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


class MemoryListWidget(QWidget):
    """Widget for displaying a list of memories with search."""

    memory_selected = Signal(dict)
    memory_deleted = Signal(int, str)  # memory_id, category

    def __init__(self, memory_manager, category: str, parent=None):
        super().__init__(parent)
        self.memory_manager = memory_manager
        self.category = category
        self._setup_ui()
        self.load_memories()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Search bar
        search_layout = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(f"Search {self.category}...")
        self._search_input.setMinimumHeight(36)
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: rgba(22, 22, 32, 200);
                color: {Colors.TEXT_PRIMARY.name()};
                border: 1px solid rgba(50, 55, 70, 100);
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border: 1px solid rgba(0, 200, 240, 120);
            }}
        """)
        self._search_input.textChanged.connect(self._on_search)
        search_layout.addWidget(self._search_input)

        search_btn = CyberButton("Search")
        search_btn.clicked.connect(self._on_search)
        search_layout.addWidget(search_btn)

        layout.addLayout(search_layout)

        # Memory list
        self._list = QListWidget()
        self._list.setStyleSheet(f"""
            QListWidget {{
                background-color: rgba(18, 18, 24, 200);
                border: 1px solid rgba(50, 55, 70, 100);
                border-radius: 6px;
                color: {Colors.TEXT_PRIMARY.name()};
            }}
            QListWidget::item:selected {{
                background-color: rgba(0, 200, 240, 60);
            }}
            QListWidget::item:hover {{
                background-color: rgba(0, 200, 240, 30);
            }}
            QScrollBar:vertical {{
                background: rgba(18, 18, 24, 100);
                width: 6px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(0, 200, 240, 50);
                border-radius: 3px;
                min-height: 20px;
            }}
        """)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._list, 1)

        # Action buttons
        btn_layout = QHBoxLayout()

        view_btn = CyberButton("View Details")
        view_btn.clicked.connect(self._on_view_details)
        btn_layout.addWidget(view_btn)

        delete_btn = CyberButton("Delete")
        delete_btn.setStyleSheet(delete_btn.styleSheet() + "background-color: rgba(255, 80, 80, 25);")
        delete_btn.clicked.connect(self._on_delete)
        btn_layout.addWidget(delete_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def load_memories(self):
        """Load all memories from the current category."""
        self._list.clear()
        memories = self.memory_manager.get_all_by_category(self.category, limit=100)

        for memory in memories:
            content_preview = memory.get("content", "")[:80]
            timestamp = memory.get("timestamp", "")[:10]
            score = memory.get("relevance_score", 0.0)

            item_text = f"{content_preview}... [Score: {score:.2f}, {timestamp}]"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, memory)
            self._list.addItem(item)

    def _on_search(self):
        """Search memories by query."""
        query = self._search_input.text().strip()
        if not query:
            self.load_memories()
            return

        self._list.clear()
        results = self.memory_manager.search_memory(self.category, query, limit=50)

        for memory in results:
            content_preview = memory.get("content", "")[:80]
            timestamp = memory.get("timestamp", "")[:10]
            score = memory.get("relevance_score", 0.0)

            item_text = f"{content_preview}... [Score: {score:.2f}, {timestamp}]"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, memory)
            self._list.addItem(item)

    def _on_view_details(self):
        """View details of selected memory."""
        current_item = self._list.currentItem()
        if not current_item:
            QMessageBox.information(self, "Info", "Please select a memory first.")
            return

        memory = current_item.data(Qt.ItemDataRole.UserRole)
        dialog = MemoryDetailDialog(memory, self)
        dialog.exec()

    def _on_item_double_clicked(self, item: QListWidgetItem):
        """Double-click to view details."""
        memory = item.data(Qt.ItemDataRole.UserRole)
        dialog = MemoryDetailDialog(memory, self)
        dialog.exec()

    def _on_delete(self):
        """Delete selected memory."""
        current_item = self._list.currentItem()
        if not current_item:
            QMessageBox.information(self, "Info", "Please select a memory first.")
            return

        reply = QMessageBox.question(
            self, "Delete Memory",
            "Are you sure you want to delete this memory?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            memory = current_item.data(Qt.ItemDataRole.UserRole)
            memory_id = memory.get("id")
            self.memory_manager.delete_memory(memory_id, self.category)
            self.memory_deleted.emit(memory_id, self.category)
            self.load_memories()


class MemoryPanel(QWidget):
    """Main memory management UI with tabs for different memory categories."""

    def __init__(self, memory_manager, parent=None):
        super().__init__(parent)
        self.memory_manager = memory_manager
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title
        title = QLabel("Memory Engine")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY.name()};")
        layout.addWidget(title)

        # Global search for all categories
        search_layout = QHBoxLayout()
        search_label = QLabel("Search All:")
        search_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()};")
        self._global_search = QLineEdit()
        self._global_search.setPlaceholderText("Search across all memories...")
        self._global_search.setMaximumHeight(36)
        self._global_search.setStyleSheet(f"""
            QLineEdit {{
                background-color: rgba(22, 22, 32, 200);
                color: {Colors.TEXT_PRIMARY.name()};
                border: 1px solid rgba(50, 55, 70, 100);
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border: 1px solid rgba(0, 200, 240, 120);
            }}
        """)
        self._global_search.textChanged.connect(self._on_global_search)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self._global_search, 1)
        layout.addLayout(search_layout)

        # Tab widget for different memory categories
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget {{
                background-color: transparent;
            }}
            QTabBar {{
                background-color: rgba(18, 18, 24, 200);
                color: {Colors.TEXT_SECONDARY.name()};
            }}
            QTabBar::tab {{
                background-color: rgba(30, 30, 40, 150);
                color: {Colors.TEXT_SECONDARY.name()};
                padding: 8px 16px;
                border-radius: 4px;
                margin-right: 4px;
            }}
            QTabBar::tab:selected {{
                background-color: rgba(0, 200, 240, 40);
                color: {Colors.TEXT_PRIMARY.name()};
            }}
            QTabBar::tab:hover {{
                background-color: rgba(0, 200, 240, 30);
            }}
            QTabWidget::pane {{
                border: 1px solid rgba(50, 55, 70, 100);
                border-radius: 6px;
            }}
        """)

        # Create tabs for each category
        categories = [
            ("All", "all"),
            ("Profile", "user_profile"),
            ("Projects", "projects"),
            ("Tasks", "tasks"),
            ("Preferences", "preferences"),
            ("Session", "session"),
        ]

        self._list_widgets = {}
        for display_name, category in categories:
            if category == "all":
                # Special "All" tab that shows global search results
                all_widget = QWidget()
                all_layout = QVBoxLayout(all_widget)

                results_label = QLabel("Search Results:")
                results_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()};")
                all_layout.addWidget(results_label)

                self._results_list = QListWidget()
                self._results_list.setStyleSheet(f"""
                    QListWidget {{
                        background-color: rgba(18, 18, 24, 200);
                        border: 1px solid rgba(50, 55, 70, 100);
                        border-radius: 6px;
                        color: {Colors.TEXT_PRIMARY.name()};
                    }}
                    QListWidget::item:selected {{
                        background-color: rgba(0, 200, 240, 60);
                    }}
                """)
                self._results_list.itemDoubleClicked.connect(self._on_result_clicked)
                all_layout.addWidget(self._results_list)

                self._tabs.addTab(all_widget, display_name)
            else:
                list_widget = MemoryListWidget(self.memory_manager, category)
                list_widget.memory_deleted.connect(self._on_memory_deleted)
                self._list_widgets[category] = list_widget
                self._tabs.addTab(list_widget, display_name)

        layout.addWidget(self._tabs, 1)

    def _on_global_search(self):
        """Search across all memory categories."""
        query = self._global_search.text().strip()
        if not query:
            self._results_list.clear()
            return

        results = self.memory_manager.get_relevant_context(query, limit=50)
        self._results_list.clear()

        for result in results:
            category = result.get("category_name", "unknown")
            content_preview = result.get("content", "")[:70]
            score = result.get("relevance_score", 0.0)

            item_text = f"[{category}] {content_preview}... (Score: {score:.2f})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, result)
            self._results_list.addItem(item)

    def _on_result_clicked(self, item: QListWidgetItem):
        """View details of a search result."""
        result = item.data(Qt.ItemDataRole.UserRole)
        dialog = MemoryDetailDialog(result, self)
        dialog.exec()

    def _on_memory_deleted(self, memory_id: int, category: str):
        """Handle memory deletion from category tabs."""
        logger.info("Memory #%d deleted from %s", memory_id, category)

    def refresh_all(self):
        """Refresh all memory lists."""
        for list_widget in self._list_widgets.values():
            list_widget.load_memories()

    def add_memory_from_ui(self, category: str, content: str, metadata: dict = None):
        """Add a new memory from UI (called from other panels)."""
        if category == "user_profile":
            self.memory_manager.user_profile.add(content, metadata)
        elif category == "projects":
            self.memory_manager.projects.add(content, metadata)
        elif category == "tasks":
            self.memory_manager.tasks.add(content, metadata)
        elif category == "preferences":
            self.memory_manager.preference_memories.add(content, metadata)
        elif category == "session":
            self.memory_manager.session.add(content, metadata)

        self.refresh_all()
