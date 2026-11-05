"""
VERONIKA AI - AI Provider Base Interface
Defines the common interface for all AI providers.
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, AsyncGenerator, Generator
from enum import Enum

logger = logging.getLogger(__name__)


class ProviderStatus(Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    NO_API_KEY = "no_api_key"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"


@dataclass
class AIMessage:
    """A single message in a conversation."""
    role: str  # 'system', 'user', 'assistant'
    content: str
    image_data: Optional[bytes] = None  # For vision capabilities
    image_mime: Optional[str] = None


@dataclass
class AIResponse:
    """Response from an AI provider."""
    content: str
    model: str = ""
    finish_reason: str = ""
    usage: Dict[str, int] = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def is_error(self) -> bool:
        return self.error is not None


@dataclass
class ModelConfig:
    """Configuration for an AI model."""
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048
    stream: bool = True


VERONIKA_SYSTEM_PROMPT = """You are VERONIKA AI, a premium desktop personal AI assistant.

Personality: Intelligent, calm, professional, conversational, helpful, and context-aware.
You are transparent about errors and limitations — never claim an operation succeeded unless verified.

You support English, Hindi, and Hinglish. Respond in the user's preferred language.

You can assist with:
- General conversation and questions
- Windows automation (launching apps, opening folders/websites, creating files)
- File operations (reading, summarizing, explaining code)
- Screen analysis (when screenshots are provided)
- Reminders and task management
- Calculations and web searches

When the user requests an action, respond with a structured command in JSON format like:
{"action": "action_name", "args": {"key": "value"}}

Available actions:
- launch_app: {"name": "app_name"}
- open_folder: {"path": "folder_path"}
- open_website: {"url": "https://..."}
- open_settings: {"page": "settings_page"}
- create_file: {"path": "file_path", "content": "text content"}
- search_files: {"directory": "path", "pattern": "*.txt"}
- take_screenshot: {}
- create_reminder: {"title": "reminder title", "due_at": "ISO datetime"}
- open_terminal: {"directory": "working_dir"}
- browser_search: {"query": "search query"}
- calculate: {"expression": "math expression"}
- save_note: {"title": "note title", "content": "note content"}
- start_workflow: {"workflow": "workflow_name"}

For regular conversation, just respond naturally without any JSON.
When you cannot determine the correct action, explain what you need from the user.
Never execute destructive operations without confirmation.
"""


class AIProviderBase(ABC):
    """Abstract base class for AI provider implementations."""

    # Cost classification for the free-first policy: "free" | "local" | "paid"
    cost_tier: str = "paid"

    def capabilities(self) -> Dict[str, Any]:
        """Declare provider capabilities for capability-aware routing."""
        return {
            "streaming": False,
            "tools": False,
            "vision": self.supports_vision(),
            "context_limit": None,
        }

    @abstractmethod
    def get_name(self) -> str:
        """Return the provider name."""
        ...

    @abstractmethod
    def get_status(self) -> ProviderStatus:
        """Check if the provider is available and configured."""
        ...

    @abstractmethod
    def send_message(
        self,
        messages: List[AIMessage],
        config: Optional[ModelConfig] = None,
    ) -> AIResponse:
        """Send a message and get a response (synchronous)."""
        ...

    @abstractmethod
    def send_message_stream(
        self,
        messages: List[AIMessage],
        config: Optional[ModelConfig] = None,
    ) -> Generator[str, None, None]:
        """Send a message and stream the response (generator)."""
        ...

    @abstractmethod
    def get_available_models(self) -> List[str]:
        """Return list of available model names."""
        ...

    @abstractmethod
    def supports_vision(self) -> bool:
        """Whether this provider supports image/vision input."""
        ...

    def cancel(self):
        """Cancel an ongoing request. Override if supported."""
        pass
