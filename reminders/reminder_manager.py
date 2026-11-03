"""
VERONIKA AI - Reminder Manager
Manages reminder lifecycle with periodic checking.
"""
import logging
import threading
import time
from typing import Optional, Callable, List

from memory.memory_manager import MemoryManager

logger = logging.getLogger(__name__)


class ReminderManager:
    """Periodically checks for due reminders and triggers notifications."""

    def __init__(self, memory_manager: MemoryManager):
        self.memory = memory_manager
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._on_reminder: Optional[Callable] = None
        self._check_interval = 30  # seconds

    def start(self, on_reminder: Callable[[dict], None]):
        """Start the reminder checking loop."""
        if self._running:
            return
        self._on_reminder = on_reminder
        self._running = True
        self._thread = threading.Thread(target=self._check_loop, daemon=True)
        self._thread.start()
        logger.info("Reminder manager started")

    def _check_loop(self):
        """Periodically check for due reminders."""
        while self._running:
            try:
                due = self.memory.get_due_reminders()
                for reminder in due:
                    if self._on_reminder:
                        self._on_reminder(reminder)
                    self.memory.reminders.mark_notified(reminder["id"])
            except Exception as e:
                logger.error("Reminder check error: %s", e)

            # Wait in small increments so we can stop quickly
            for _ in range(self._check_interval * 2):
                if not self._running:
                    break
                time.sleep(0.5)

    def stop(self):
        """Stop the reminder checking loop."""
        self._running = False
        logger.info("Reminder manager stopped")

    def create_reminder(self, title: str, due_at: str, description: str = "") -> int:
        """Create a new reminder."""
        return self.memory.create_reminder(title, due_at, description)

    def get_pending(self) -> List[dict]:
        """Get all pending reminders."""
        return self.memory.get_pending_reminders()

    def complete(self, reminder_id: int):
        """Mark a reminder as completed."""
        self.memory.complete_reminder(reminder_id)
