"""
VERONIKA AI - SQLite Database Manager
Handles all persistent storage operations.
"""
import sqlite3
import logging
import threading
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from app.config import DATABASE_PATH

logger = logging.getLogger(__name__)


class Database:
    """Thread-safe SQLite database manager."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DATABASE_PATH
        self._local = threading.local()
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create a thread-local database connection."""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                str(self.db_path), check_same_thread=False
            )
            self._local.connection.row_factory = sqlite3.Row
            self._local.connection.execute("PRAGMA journal_mode=WAL")
            self._local.connection.execute("PRAGMA foreign_keys=ON")
        return self._local.connection

    @contextmanager
    def get_cursor(self):
        """Context manager for database cursor with auto-commit/rollback."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()

    def _init_schema(self):
        """Initialize database schema."""
        with self.get_cursor() as cursor:
            # Conversations
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT DEFAULT 'New Conversation',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Messages
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                )
            """)

            # Memory / Notes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL DEFAULT 'general',
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_memories_key
                ON memories(category, key)
            """)

            # Reminders
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    due_at TIMESTAMP NOT NULL,
                    is_completed INTEGER DEFAULT 0,
                    is_notified INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Automation history
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS automation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_type TEXT NOT NULL,
                    action_args TEXT DEFAULT '{}',
                    result TEXT DEFAULT '',
                    success INTEGER DEFAULT 1,
                    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # User preferences (approved by user)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

        logger.info("Database schema initialized at %s", self.db_path)

    def close(self):
        """Close the thread-local connection."""
        if hasattr(self._local, "connection") and self._local.connection:
            self._local.connection.close()
            self._local.connection = None


# Singleton database instance
db = Database()
