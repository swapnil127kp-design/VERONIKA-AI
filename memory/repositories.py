"""
VERONIKA AI - Data Repositories
Provides typed access to database tables.
"""
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from memory.database import Database, db

logger = logging.getLogger(__name__)


class ConversationRepository:
    """Manages conversation and message records."""

    def __init__(self, database: Database = None):
        self.db = database or db

    def create_conversation(self, title: str = "New Conversation") -> int:
        with self.db.get_cursor() as c:
            c.execute(
                "INSERT INTO conversations (title) VALUES (?)", (title,)
            )
            return c.lastrowid

    def get_conversations(self, limit: int = 50) -> List[dict]:
        with self.db.get_cursor() as c:
            c.execute(
                "SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in c.fetchall()]

    def delete_conversation(self, conversation_id: int):
        with self.db.get_cursor() as c:
            c.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))

    def add_message(self, conversation_id: int, role: str, content: str) -> int:
        with self.db.get_cursor() as c:
            c.execute(
                "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
                (conversation_id, role, content),
            )
            c.execute(
                "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (conversation_id,),
            )
            return c.lastrowid

    def get_messages(
        self, conversation_id: int, limit: int = 100
    ) -> List[dict]:
        with self.db.get_cursor() as c:
            c.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC LIMIT ?",
                (conversation_id, limit),
            )
            return [dict(row) for row in c.fetchall()]

    def search_messages(self, query: str, limit: int = 20) -> List[dict]:
        with self.db.get_cursor() as c:
            c.execute(
                "SELECT * FROM messages WHERE content LIKE ? ORDER BY created_at DESC LIMIT ?",
                (f"%{query}%", limit),
            )
            return [dict(row) for row in c.fetchall()]

    def clear_all(self):
        with self.db.get_cursor() as c:
            c.execute("DELETE FROM messages")
            c.execute("DELETE FROM conversations")


class MemoryRepository:
    """Manages key-value memory entries."""

    def __init__(self, database: Database = None):
        self.db = database or db

    def save(self, category: str, key: str, value: str):
        with self.db.get_cursor() as c:
            c.execute(
                """INSERT INTO memories (category, key, value)
                   VALUES (?, ?, ?)
                   ON CONFLICT(category, key) DO UPDATE
                   SET value = excluded.value, updated_at = CURRENT_TIMESTAMP""",
                (category, key, value),
            )

    def get(self, category: str, key: str) -> Optional[str]:
        with self.db.get_cursor() as c:
            c.execute(
                "SELECT value FROM memories WHERE category = ? AND key = ?",
                (category, key),
            )
            row = c.fetchone()
            return row["value"] if row else None

    def get_all(self, category: Optional[str] = None) -> List[dict]:
        with self.db.get_cursor() as c:
            if category:
                c.execute(
                    "SELECT * FROM memories WHERE category = ? ORDER BY updated_at DESC",
                    (category,),
                )
            else:
                c.execute("SELECT * FROM memories ORDER BY updated_at DESC")
            return [dict(row) for row in c.fetchall()]

    def search(self, query: str) -> List[dict]:
        with self.db.get_cursor() as c:
            c.execute(
                "SELECT * FROM memories WHERE key LIKE ? OR value LIKE ? ORDER BY updated_at DESC",
                (f"%{query}%", f"%{query}%"),
            )
            return [dict(row) for row in c.fetchall()]

    def delete(self, memory_id: int):
        with self.db.get_cursor() as c:
            c.execute("DELETE FROM memories WHERE id = ?", (memory_id,))

    def clear_all(self):
        with self.db.get_cursor() as c:
            c.execute("DELETE FROM memories")


class ReminderRepository:
    """Manages reminder records."""

    def __init__(self, database: Database = None):
        self.db = database or db

    def create(self, title: str, due_at: str, description: str = "") -> int:
        with self.db.get_cursor() as c:
            c.execute(
                "INSERT INTO reminders (title, description, due_at) VALUES (?, ?, ?)",
                (title, description, due_at),
            )
            return c.lastrowid

    def get_pending(self) -> List[dict]:
        with self.db.get_cursor() as c:
            c.execute(
                "SELECT * FROM reminders WHERE is_completed = 0 ORDER BY due_at ASC"
            )
            return [dict(row) for row in c.fetchall()]

    def get_due(self) -> List[dict]:
        now = datetime.now().isoformat()
        with self.db.get_cursor() as c:
            c.execute(
                "SELECT * FROM reminders WHERE is_completed = 0 AND is_notified = 0 AND due_at <= ? ORDER BY due_at ASC",
                (now,),
            )
            return [dict(row) for row in c.fetchall()]

    def mark_completed(self, reminder_id: int):
        with self.db.get_cursor() as c:
            c.execute(
                "UPDATE reminders SET is_completed = 1 WHERE id = ?", (reminder_id,)
            )

    def mark_notified(self, reminder_id: int):
        with self.db.get_cursor() as c:
            c.execute(
                "UPDATE reminders SET is_notified = 1 WHERE id = ?", (reminder_id,)
            )

    def delete(self, reminder_id: int):
        with self.db.get_cursor() as c:
            c.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))

    def get_all(self) -> List[dict]:
        with self.db.get_cursor() as c:
            c.execute("SELECT * FROM reminders ORDER BY due_at DESC")
            return [dict(row) for row in c.fetchall()]


class AutomationHistoryRepository:
    """Records executed automation actions."""

    def __init__(self, database: Database = None):
        self.db = database or db

    def record(self, action_type: str, action_args: dict, result: str, success: bool):
        with self.db.get_cursor() as c:
            c.execute(
                "INSERT INTO automation_history (action_type, action_args, result, success) VALUES (?, ?, ?, ?)",
                (action_type, json.dumps(action_args), result, int(success)),
            )

    def get_recent(self, limit: int = 50) -> List[dict]:
        with self.db.get_cursor() as c:
            c.execute(
                "SELECT * FROM automation_history ORDER BY executed_at DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in c.fetchall()]

    def clear_all(self):
        with self.db.get_cursor() as c:
            c.execute("DELETE FROM automation_history")


class PreferenceRepository:
    """Manages user-approved preferences."""

    def __init__(self, database: Database = None):
        self.db = database or db

    def set(self, key: str, value: str):
        with self.db.get_cursor() as c:
            c.execute(
                """INSERT INTO preferences (key, value)
                   VALUES (?, ?)
                   ON CONFLICT(key) DO UPDATE
                   SET value = excluded.value, updated_at = CURRENT_TIMESTAMP""",
                (key, value),
            )

    def get(self, key: str, default: str = "") -> str:
        with self.db.get_cursor() as c:
            c.execute("SELECT value FROM preferences WHERE key = ?", (key,))
            row = c.fetchone()
            return row["value"] if row else default

    def get_all(self) -> Dict[str, str]:
        with self.db.get_cursor() as c:
            c.execute("SELECT key, value FROM preferences")
            return {row["key"]: row["value"] for row in c.fetchall()}
