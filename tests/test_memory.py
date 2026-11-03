"""
Tests for memory subsystem.
"""
import sqlite3
import tempfile
from pathlib import Path

import pytest

from memory.database import Database
from memory.repositories import (
    ConversationRepository,
    MemoryRepository,
    ReminderRepository,
    AutomationHistoryRepository,
    PreferenceRepository,
)
from memory.memory_manager import MemoryManager


@pytest.fixture
def test_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    db = Database(db_path)
    yield db
    db.close()
    try:
        db_path.unlink()
    except Exception:
        pass


class TestConversationRepository:
    def test_create_and_get(self, test_db):
        repo = ConversationRepository(test_db)
        cid = repo.create_conversation("Test Chat")
        assert cid > 0

        convs = repo.get_conversations()
        assert len(convs) == 1
        assert convs[0]["title"] == "Test Chat"

    def test_add_and_get_messages(self, test_db):
        repo = ConversationRepository(test_db)
        cid = repo.create_conversation("Chat")

        repo.add_message(cid, "user", "Hello")
        repo.add_message(cid, "assistant", "Hi there!")

        msgs = repo.get_messages(cid)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["content"] == "Hi there!"

    def test_delete_conversation(self, test_db):
        repo = ConversationRepository(test_db)
        cid = repo.create_conversation("To Delete")
        repo.add_message(cid, "user", "bye")
        repo.delete_conversation(cid)

        convs = repo.get_conversations()
        assert len(convs) == 0

    def test_search_messages(self, test_db):
        repo = ConversationRepository(test_db)
        cid = repo.create_conversation("Search Test")
        repo.add_message(cid, "user", "Tell me about Python")
        repo.add_message(cid, "assistant", "Python is a programming language")

        results = repo.search_messages("Python")
        assert len(results) == 2

    def test_clear_all(self, test_db):
        repo = ConversationRepository(test_db)
        cid = repo.create_conversation("Clear Test")
        repo.add_message(cid, "user", "test")
        repo.clear_all()

        assert len(repo.get_conversations()) == 0


class TestMemoryRepository:
    def test_save_and_get(self, test_db):
        repo = MemoryRepository(test_db)
        repo.save("notes", "grocery", "milk, eggs, bread")

        value = repo.get("notes", "grocery")
        assert value == "milk, eggs, bread"

    def test_upsert(self, test_db):
        repo = MemoryRepository(test_db)
        repo.save("notes", "key1", "value1")
        repo.save("notes", "key1", "value2")

        assert repo.get("notes", "key1") == "value2"

    def test_get_nonexistent(self, test_db):
        repo = MemoryRepository(test_db)
        assert repo.get("notes", "missing") is None

    def test_search(self, test_db):
        repo = MemoryRepository(test_db)
        repo.save("facts", "capital", "Delhi is the capital of India")
        repo.save("facts", "language", "Hindi is widely spoken")

        results = repo.search("India")
        assert len(results) == 1
        assert results[0]["key"] == "capital"

    def test_delete(self, test_db):
        repo = MemoryRepository(test_db)
        repo.save("notes", "temp", "temporary")
        all_items = repo.get_all("notes")
        assert len(all_items) == 1

        repo.delete(all_items[0]["id"])
        assert len(repo.get_all("notes")) == 0


class TestReminderRepository:
    def test_create_and_get_pending(self, test_db):
        repo = ReminderRepository(test_db)
        rid = repo.create("Buy milk", "2099-12-31T12:00:00")
        assert rid > 0

        pending = repo.get_pending()
        assert len(pending) == 1
        assert pending[0]["title"] == "Buy milk"

    def test_mark_completed(self, test_db):
        repo = ReminderRepository(test_db)
        rid = repo.create("Completed task", "2099-01-01T00:00:00")
        repo.mark_completed(rid)

        pending = repo.get_pending()
        assert len(pending) == 0

    def test_get_due(self, test_db):
        repo = ReminderRepository(test_db)
        # Create one past-due reminder
        repo.create("Past due", "2000-01-01T00:00:00")
        # Create one future reminder
        repo.create("Future", "2099-12-31T23:59:59")

        due = repo.get_due()
        assert len(due) == 1
        assert due[0]["title"] == "Past due"


class TestAutomationHistory:
    def test_record_and_get_recent(self, test_db):
        repo = AutomationHistoryRepository(test_db)
        repo.record("launch_app", {"name": "notepad"}, "Success", True)
        repo.record("open_website", {"url": "google.com"}, "Success", True)

        recent = repo.get_recent(limit=10)
        assert len(recent) == 2

    def test_clear_all(self, test_db):
        repo = AutomationHistoryRepository(test_db)
        repo.record("test", {}, "ok", True)
        repo.clear_all()
        assert len(repo.get_recent()) == 0


class TestPreferenceRepository:
    def test_set_and_get(self, test_db):
        repo = PreferenceRepository(test_db)
        repo.set("theme", "dark")
        assert repo.get("theme") == "dark"

    def test_get_default(self, test_db):
        repo = PreferenceRepository(test_db)
        assert repo.get("missing", "default_val") == "default_val"

    def test_upsert(self, test_db):
        repo = PreferenceRepository(test_db)
        repo.set("key", "v1")
        repo.set("key", "v2")
        assert repo.get("key") == "v2"

    def test_get_all(self, test_db):
        repo = PreferenceRepository(test_db)
        repo.set("a", "1")
        repo.set("b", "2")
        all_prefs = repo.get_all()
        assert all_prefs == {"a": "1", "b": "2"}
