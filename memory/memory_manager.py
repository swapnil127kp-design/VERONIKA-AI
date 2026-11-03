"""
VERONIKA AI - Memory Manager
High-level interface for managing VERONIKA's persistent memory.
"""
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from memory.repositories import (
    ConversationRepository,
    MemoryRepository,
    ReminderRepository,
    AutomationHistoryRepository,
    PreferenceRepository,
)

logger = logging.getLogger(__name__)


class MemoryManager:
    """Unified memory management for VERONIKA AI."""

    def __init__(self, database=None):
        self.conversations = ConversationRepository(database)
        self.memories = MemoryRepository(database)
        self.reminders = ReminderRepository(database)
        self.automation = AutomationHistoryRepository(database)
        self.preferences = PreferenceRepository(database)

        self._current_conversation_id: Optional[int] = None

    @property
    def current_conversation_id(self) -> Optional[int]:
        return self._current_conversation_id

    def start_new_conversation(self, title: str = "New Conversation") -> int:
        """Start a new conversation and return its ID."""
        self._current_conversation_id = self.conversations.create_conversation(title)
        logger.info("Started new conversation #%d: %s", self._current_conversation_id, title)
        return self._current_conversation_id

    def add_user_message(self, content: str) -> Optional[int]:
        """Add a user message to the current conversation."""
        if not self._current_conversation_id:
            self.start_new_conversation()
        return self.conversations.add_message(
            self._current_conversation_id, "user", content
        )

    def add_assistant_message(self, content: str) -> Optional[int]:
        """Add an assistant message to the current conversation."""
        if not self._current_conversation_id:
            self.start_new_conversation()
        return self.conversations.add_message(
            self._current_conversation_id, "assistant", content
        )

    def get_conversation_history(self, limit: int = 100) -> List[dict]:
        """Get messages for the current conversation."""
        if not self._current_conversation_id:
            return []
        return self.conversations.get_messages(self._current_conversation_id, limit)

    def get_context_messages(self, limit: int = 20) -> List[dict]:
        """Get recent messages formatted for AI context."""
        messages = self.get_conversation_history(limit)
        return [{"role": m["role"], "content": m["content"]} for m in messages]

    def save_memory(self, category: str, key: str, value: str):
        """Save a named memory entry."""
        self.memories.save(category, key, value)
        logger.info("Memory saved: [%s] %s", category, key)

    def recall_memory(self, category: str, key: str) -> Optional[str]:
        """Recall a specific memory."""
        return self.memories.get(category, key)

    def search_memories(self, query: str) -> List[dict]:
        """Search across all memories."""
        return self.memories.search(query)

    def get_all_memories(self, category: Optional[str] = None) -> List[dict]:
        """Get all memory entries."""
        return self.memories.get_all(category)

    def delete_memory(self, memory_id: int):
        """Delete a specific memory entry."""
        self.memories.delete(memory_id)

    def clear_all_memories(self):
        """Clear all memory entries."""
        self.memories.clear_all()
        logger.info("All memories cleared")

    def create_reminder(self, title: str, due_at: str, description: str = "") -> int:
        """Create a new reminder."""
        rid = self.reminders.create(title, due_at, description)
        logger.info("Reminder created: #%d - %s at %s", rid, title, due_at)
        return rid

    def get_due_reminders(self) -> List[dict]:
        """Get reminders that are due."""
        return self.reminders.get_due()

    def get_pending_reminders(self) -> List[dict]:
        """Get all pending reminders."""
        return self.reminders.get_pending()

    def complete_reminder(self, reminder_id: int):
        """Mark a reminder as completed."""
        self.reminders.mark_completed(reminder_id)

    def record_automation(self, action_type: str, args: dict, result: str, success: bool):
        """Record an automation action."""
        self.automation.record(action_type, args, result, success)

    def export_data(self) -> dict:
        """Export all user-owned data."""
        return {
            "exported_at": datetime.now().isoformat(),
            "conversations": self.conversations.get_conversations(limit=1000),
            "memories": self.memories.get_all(),
            "reminders": self.reminders.get_all(),
            "automation_history": self.automation.get_recent(limit=1000),
            "preferences": self.preferences.get_all(),
        }

    def clear_all_data(self):
        """Clear all data from the database. Requires explicit user confirmation."""
        self.conversations.clear_all()
        self.memories.clear_all()
        self.automation.clear_all()
        logger.warning("All data cleared from database")
