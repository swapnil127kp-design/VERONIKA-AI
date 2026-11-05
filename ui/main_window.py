"""
VERONIKA AI - Main Window
The primary application window that orchestrates all UI panels,
AI integration, voice, and automation subsystems.
"""
import logging
import threading
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QApplication, QMessageBox, QSplitter, QComboBox,
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QFont, QColor, QKeySequence, QShortcut

from app.config import config, APP_NAME, APP_VERSION
from ai.provider_manager import ProviderManager
from ai.provider_base import ProviderStatus
from ai.persona_manager import PersonaManager
from ai.entity_manager import EntityManager
from memory.memory_manager import MemoryManager
from automation.action_registry import ActionRegistry
from automation.workflow_engine import WorkflowEngine
from reminders.reminder_manager import ReminderManager
from vision.screenshot_capture import ScreenshotCapture
from voice.speech_recognition import SpeechRecognizer
from voice.text_to_speech import TextToSpeech
from voice.wake_word import WakeWordDetector

from ui.components import AIOrb, StateLabel, ConnectionIndicator, Colors
from ui.chat_panel import ChatPanel
from ui.sidebar import Sidebar
from ui.settings_window import SettingsWindow
from ui.system_tray import SystemTrayManager

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """VERONIKA AI main application window."""

    # Thread-safe signals for updating UI from background threads
    _append_assistant_signal = Signal(str)
    _update_streaming_signal = Signal(str)
    _set_state_signal = Signal(str)
    _action_feedback_signal = Signal(str)
    _voice_result_signal = Signal(str)
    _voice_error_signal = Signal(str)
    _reminder_signal = Signal(dict)
    _scout_alert_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(960, 640)
        self.resize(
            config.get("ui", "window_width", 1100),
            config.get("ui", "window_height", 750),
        )

        # ── Core subsystems ──────────────────────────────────
        self.provider_manager = ProviderManager()
        self.memory = MemoryManager()
        try:
            from mcp.mcp_client import build_mcp_manager
            self.mcp_manager = build_mcp_manager(start=True)
        except Exception as e:
            logger.warning("MCP subsystem unavailable: %s", e)
            self.mcp_manager = None
        self.action_registry = ActionRegistry(
            memory_manager=self.memory,
            provider_manager=self.provider_manager,
            mcp_manager=self.mcp_manager,
        )
        self.workflow_engine = WorkflowEngine(self.action_registry)
        self.screenshot = ScreenshotCapture()
        self.speech_recognizer = SpeechRecognizer()
        self.tts = TextToSpeech()
        self.wake_word = WakeWordDetector()
        self.reminder_manager = ReminderManager(self.memory)
        self.tray = SystemTrayManager(self)
        self.persona_manager = PersonaManager.get_instance()
        self.entity_manager = EntityManager.get_instance()

        # 3D orb bridge / phone sync / model scout (started in _start_background_services)
        self.orb_bridge = None
        self.sync_server = None
        self.model_scout = None

        self._streaming_text = ""
        self._is_processing = False

        # ── Connect cross-thread signals ────────────────────
        self._append_assistant_signal.connect(self._on_assistant_message)
        self._update_streaming_signal.connect(self._on_streaming_update)
        self._set_state_signal.connect(self._on_state_change)
        self._action_feedback_signal.connect(self._on_action_feedback)
        self._voice_result_signal.connect(self._on_voice_result)
        self._voice_error_signal.connect(self._on_voice_error)
        self._reminder_signal.connect(self._on_reminder_due)
        self._scout_alert_signal.connect(self._on_scout_alert)

        # ── Build UI ─────────────────────────────────────────
        self._setup_ui()
        self._setup_shortcuts()
        self._setup_tray()

        # ── Initialize state ─────────────────────────────────
        self._update_connection_status()
        self.memory.start_new_conversation()
        self._refresh_sidebar()

        # Start reminder checker
        self.reminder_manager.start(
            lambda r: self._reminder_signal.emit(r)
        )

        # Start wake word if enabled
        if config.get("wake_word", "enabled", False):
            self._start_wake_word()

        # 3D orb bridge, phone sync server, model scout
        self._start_background_services()

        # Apply the persisted persona (orb colors, mode selector, welcome text)
        self._apply_persona_ui(greet=False)

        # Periodic connection check
        self._conn_timer = QTimer(self)
        self._conn_timer.timeout.connect(self._update_connection_status)
        self._conn_timer.start(30_000)

        logger.info("Main window initialized")

    # ═══════════════════════════════════════════════════════════
    # UI Setup
    # ═══════════════════════════════════════════════════════════

    def _setup_ui(self):
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {Colors.BG_DARK.name()};
            }}
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Sidebar ──────────────────────────────────────────
        self.sidebar = Sidebar()
        self.sidebar.new_conversation.connect(self._new_conversation)
        self.sidebar.conversation_selected.connect(self._load_conversation)
        self.sidebar.conversation_deleted.connect(self._delete_conversation)
        self.sidebar.open_settings.connect(self._open_settings)
        self.sidebar.open_screenshot.connect(self._take_screenshot_and_analyze)
        self.sidebar.toggle_voice.connect(self._toggle_voice)
        main_layout.addWidget(self.sidebar)

        # ── Right panel ──────────────────────────────────────
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Top bar
        top_bar = QWidget()
        top_bar.setFixedHeight(50)
        top_bar.setStyleSheet("""
            QWidget {
                background-color: rgba(22, 22, 30, 220);
                border-bottom: 1px solid rgba(50, 55, 70, 100);
            }
        """)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(16, 0, 16, 0)

        # Orb (small version in top bar)
        self.orb = AIOrb(size=36)
        top_layout.addWidget(self.orb)

        self.state_label = StateLabel()
        top_layout.addWidget(self.state_label)

        top_layout.addStretch()

        # Entity selector (VERONIKA / FRIDAY / ULTRON)
        self.mode_selector = QComboBox()
        self.mode_selector.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mode_selector.setMinimumHeight(30)
        self.mode_selector.setToolTip("Active entity (character)")
        for entity in self.entity_manager.get_available_entities():
            self.mode_selector.addItem(entity["display_name"], entity["entity_id"])
        current_idx = self.mode_selector.findData(self.entity_manager.entity_id)
        if current_idx >= 0:
            self.mode_selector.setCurrentIndex(current_idx)
        self.mode_selector.currentIndexChanged.connect(self._on_mode_changed)
        top_layout.addWidget(self.mode_selector)

        # Relationship overlay selector (None / Girlfriend / Partner / Exam Mentor)
        self.overlay_selector = QComboBox()
        self.overlay_selector.setCursor(Qt.CursorShape.PointingHandCursor)
        self.overlay_selector.setMinimumHeight(30)
        self.overlay_selector.setToolTip("Relationship overlay (applied on top of the entity)")
        self.overlay_selector.addItem("Overlay: None", "")
        for ov in self.entity_manager.get_available_overlays():
            self.overlay_selector.addItem(f"Overlay: {ov['display_name']}", ov["overlay_id"])
        ov_idx = self.overlay_selector.findData(self.entity_manager.overlay_id)
        if ov_idx >= 0:
            self.overlay_selector.setCurrentIndex(ov_idx)
        self.overlay_selector.currentIndexChanged.connect(self._on_overlay_changed)
        top_layout.addWidget(self.overlay_selector)

        self.connection_indicator = ConnectionIndicator()
        top_layout.addWidget(self.connection_indicator)

        right_layout.addWidget(top_bar)

        # Chat panel (main area)
        self.chat_panel = ChatPanel()
        self.chat_panel.message_sent.connect(self._on_user_message)
        right_layout.addWidget(self.chat_panel, 1)

        main_layout.addWidget(right_panel, 1)

        # Welcome message — respects the persona.startup_greeting toggle
        # (directive: greeting disableable, and never activates the mic).
        em = self.entity_manager
        help_text = (
            "I can help with conversations, launch apps, open websites, manage files, "
            "take screenshots, set reminders, and much more.\n\n"
            "Type a message or use the 🎙 Voice button to get started! "
            f"(Entity: {em.display_name} — switch entity & overlay via the selectors in the top bar.)"
        )
        if PersonaManager.is_startup_greeting_enabled():
            self.chat_panel.add_assistant_message(f"{em.wake_greeting}\n\n{help_text}")
        else:
            self.chat_panel.add_assistant_message(help_text)

    def _setup_shortcuts(self):
        # Ctrl+N: New conversation
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self._new_conversation)
        # Ctrl+,: Settings
        QShortcut(QKeySequence("Ctrl+,"), self).activated.connect(self._open_settings)
        # Ctrl+Shift+V: Voice input
        QShortcut(QKeySequence("Ctrl+Shift+V"), self).activated.connect(self._toggle_voice)
        # Ctrl+Shift+S: Screenshot
        QShortcut(QKeySequence("Ctrl+Shift+S"), self).activated.connect(
            self._take_screenshot_and_analyze
        )
        # Ctrl+M: Cycle persona mode
        QShortcut(QKeySequence("Ctrl+M"), self).activated.connect(self._cycle_persona)

    def _setup_tray(self):
        self.tray.show_window.connect(self._show_from_tray)
        self.tray.quit_app.connect(self._quit_app)
        self.tray.open_settings.connect(self._open_settings)
        self.tray.new_conversation.connect(self._new_conversation)
        self.tray.toggle_voice.connect(self._toggle_voice)
        self.tray.setup(self)

    # ═══════════════════════════════════════════════════════════
    # Persona / Mode Engine (FRIDAY / Girlfriend / ULTRON)
    # ═══════════════════════════════════════════════════════════

    def _apply_persona_ui(self, greet: bool = False):
        """Push the active entity + overlay into the orb, selectors, and voice."""
        em = self.entity_manager
        accent = QColor(em.orb_color)
        accent2 = QColor(em.accent_color)
        self.orb.set_accent_color(accent, accent2)

        # Keep the entity selector in sync
        idx = self.mode_selector.findData(em.entity_id)
        if idx >= 0 and self.mode_selector.currentIndex() != idx:
            self.mode_selector.blockSignals(True)
            self.mode_selector.setCurrentIndex(idx)
            self.mode_selector.blockSignals(False)

        # Keep the overlay selector in sync
        ov_idx = self.overlay_selector.findData(em.overlay_id)
        if ov_idx >= 0 and self.overlay_selector.currentIndex() != ov_idx:
            self.overlay_selector.blockSignals(True)
            self.overlay_selector.setCurrentIndex(ov_idx)
            self.overlay_selector.blockSignals(False)

        # Keep the legacy PersonaManager aligned (sync server / older consumers)
        self.persona_manager.set_mode(em.legacy_mode_id)

        accent_rgb = f"{accent.red()}, {accent.green()}, {accent.blue()}"
        combo_css = f"""
            QComboBox {{
                background-color: rgba({accent_rgb}, 25);
                color: {em.orb_color};
                border: 1px solid rgba({accent_rgb}, 90);
                border-radius: 8px;
                padding: 4px 14px;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 1px;
                min-width: 100px;
            }}
            QComboBox:hover {{
                background-color: rgba({accent_rgb}, 45);
                border: 1px solid rgba({accent_rgb}, 160);
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                border: none;
                width: 18px;
            }}
            QComboBox QAbstractItemView {{
                background-color: rgb(26, 26, 36);
                color: {em.orb_color};
                selection-background-color: rgba({accent_rgb}, 60);
                selection-color: {em.orb_color};
                border: 1px solid rgba({accent_rgb}, 80);
                outline: none;
            }}
        """
        self.mode_selector.setStyleSheet(combo_css)
        self.overlay_selector.setStyleSheet(combo_css)

        if self.orb_bridge:
            self.orb_bridge.set_entity(em)

        if greet:
            greeting = em.wake_greeting
            self.chat_panel.add_assistant_message(
                f"[Entity → {em.display_name}] {greeting}"
            )
            if config.get("voice", "tts_enabled", True):
                self.tts.speak(
                    greeting,
                    on_started=lambda: self._set_state_signal.emit("speaking"),
                    on_finished=lambda: self._set_state_signal.emit("idle"),
                )

    @Slot(int)
    def _on_mode_changed(self, index: int):
        entity_id = self.mode_selector.itemData(index)
        if not entity_id or entity_id == self.entity_manager.entity_id:
            return
        if self.entity_manager.set_entity(entity_id):
            logger.info("Entity switched to %s", entity_id)
            self._apply_persona_ui(greet=True)

    @Slot(int)
    def _on_overlay_changed(self, index: int):
        overlay_id = self.overlay_selector.itemData(index) or ""
        if overlay_id == self.entity_manager.overlay_id:
            return
        if self.entity_manager.set_overlay(overlay_id):
            logger.info("Relationship overlay switched to %s", overlay_id or "(none)")
            self._apply_persona_ui(greet=True)

    def _cycle_persona(self):
        """Ctrl+M: cycle entities VERONIKA → FRIDAY → ULTRON → VERONIKA."""
        self.entity_manager.next_entity()
        logger.info("Entity cycled to %s", self.entity_manager.entity_id)
        self._apply_persona_ui(greet=True)

    # ═══════════════════════════════════════════════════════════
    # Background services (3D orb bridge, phone sync, model scout)
    # ═══════════════════════════════════════════════════════════

    def _start_background_services(self):
        # 1) 3D holographic orb bridge (browser orb on :3000, WS on :8766)
        if config.get("orb", "enabled", True):
            try:
                from ui.ultron_bridge import UltronBridge
                self.orb_bridge = UltronBridge(
                    http_host=config.get("orb", "http_host", "127.0.0.1"),
                    http_port=int(config.get("orb", "http_port", 3000)),
                    ws_host=config.get("orb", "ws_host", "127.0.0.1"),
                    ws_port=int(config.get("orb", "ws_port", 8766)),
                    enable_audio=bool(config.get("orb", "audio_reactive", True)),
                )
                self.orb_bridge.start()
                if config.get("orb", "open_browser_on_start", False):
                    self.orb_bridge.open_orb()
            except Exception as e:
                logger.warning("Orb bridge failed to start: %s", e)
                self.orb_bridge = None

        # 2) Phone sync server (FastAPI on 0.0.0.0:8765)
        if config.get("sync", "enabled", True):
            try:
                from server.sync_server import SyncServer
                self.sync_server = SyncServer(
                    memory_manager=self.memory,
                    provider_manager=self.provider_manager,
                    action_registry=self.action_registry,
                    persona_manager=self.persona_manager,
                    bridge=self.orb_bridge,
                )
                self.sync_server.start()
            except Exception as e:
                logger.warning("Sync server failed to start: %s", e)
                self.sync_server = None

        # 3) Model scout (free-model discovery alerts)
        if config.get("scout", "enabled", True):
            try:
                from ai.model_scout import ModelScout
                self.model_scout = ModelScout(
                    on_alert=lambda text: self._scout_alert_signal.emit(text),
                    interval_seconds=int(config.get("scout", "interval_seconds", 3600)),
                )
                self.model_scout.start()
            except Exception as e:
                logger.warning("Model scout failed to start: %s", e)
                self.model_scout = None

    @Slot(str)
    def _on_scout_alert(self, message: str):
        self.chat_panel.add_assistant_message(f"🛰 Model Scout:\n{message}")
        self.tray.show_notification("VERONIKA Model Scout", message.split("\n")[0][:120])

    # ═══════════════════════════════════════════════════════════
    # Message Handling
    # ═══════════════════════════════════════════════════════════

    def _on_user_message(self, text: str):
        """Handle a message from the user."""
        if self._is_processing:
            return

        # Barge-in: a new user message interrupts any ongoing speech.
        if self.tts.is_speaking:
            self.tts.stop()

        self._is_processing = True
        self.chat_panel.add_user_message(text)
        self.chat_panel.set_input_enabled(False)
        self._set_state("processing")

        # Save to memory
        self.memory.add_user_message(text)

        # Get context
        context = self.memory.get_context_messages(limit=20)

        # Check streaming preference
        use_stream = config.get("ai", "stream_responses", True)

        def _background_send():
            try:
                if use_stream:
                    self._streaming_text = ""
                    # Add empty bubble for streaming
                    self._append_assistant_signal.emit("")

                    for chunk in self.provider_manager.send_message_stream(
                        text, context_messages=context
                    ):
                        self._streaming_text += chunk
                        self._update_streaming_signal.emit(self._streaming_text)

                    full_response = self._streaming_text
                else:
                    response = self.provider_manager.send_message(
                        text, context_messages=context
                    )
                    if response.is_error:
                        full_response = f"[Error: {response.error}]"
                    else:
                        full_response = response.content
                    self._append_assistant_signal.emit(full_response)

                # Save to memory
                self.memory.add_assistant_message(full_response)

                # Check for actions in the response
                action_data = self.provider_manager.parse_action(full_response)
                if action_data:
                    self._execute_action(action_data)

                # TTS
                if config.get("voice", "tts_enabled", True):
                    # Strip action JSON and code blocks from speech
                    import re
                    speech_text = re.sub(r'```(?:json)?\s*\{.*?\}\s*```', '', full_response, flags=re.DOTALL)
                    speech_text = re.sub(r'\{.*?"action".*?\}', '', speech_text, flags=re.DOTALL).strip()
                    if speech_text:
                        self.tts.speak(
                            speech_text,
                            on_started=lambda: self._set_state_signal.emit("speaking"),
                            on_finished=lambda: self._set_state_signal.emit("idle"),
                        )
                    else:
                        self._set_state_signal.emit("idle")
                else:
                    self._set_state_signal.emit("idle")

            except Exception as e:
                logger.error("Message processing error: %s", e)
                self._append_assistant_signal.emit(f"[Error: {e}]")
                self._set_state_signal.emit("error")
            finally:
                self._is_processing = False

        thread = threading.Thread(target=_background_send, daemon=True)
        thread.start()

    def _execute_action(self, action_data: dict):
        """Execute an action extracted from AI response."""
        action_type = action_data.get("action", "")
        args = action_data.get("args", {})

        self._set_state_signal.emit("executing")
        result = self.action_registry.execute(action_type, args)

        feedback = f"{'✓' if result.success else '✕'} {result.message}"
        self._action_feedback_signal.emit(feedback)
        self._set_state_signal.emit("idle")

    # ═══════════════════════════════════════════════════════════
    # Signal Handlers (UI thread)
    # ═══════════════════════════════════════════════════════════

    @Slot(str)
    def _on_assistant_message(self, text: str):
        self.chat_panel.add_assistant_message(text)
        self.chat_panel.set_input_enabled(True)
        self.chat_panel.focus_input()

    @Slot(str)
    def _on_streaming_update(self, text: str):
        self.chat_panel.update_last_assistant_message(text)
        self.chat_panel.set_input_enabled(True)
        self.chat_panel.focus_input()

    @Slot(str)
    def _on_state_change(self, state: str):
        self._set_state(state)

    @Slot(str)
    def _on_action_feedback(self, message: str):
        self.chat_panel.add_assistant_message(message)

    @Slot(str)
    def _on_voice_result(self, text: str):
        self._set_state("idle")
        if text:
            self.chat_panel._input.setText(text)
            self._on_user_message(text)

    @Slot(str)
    def _on_voice_error(self, error: str):
        self._set_state("error")
        self.chat_panel.add_assistant_message(f"🎙 {error}")
        QTimer.singleShot(2000, lambda: self._set_state("idle"))

    @Slot(dict)
    def _on_reminder_due(self, reminder: dict):
        title = reminder.get("title", "Reminder")
        self.tray.show_notification("VERONIKA Reminder", title)
        self.chat_panel.add_assistant_message(f"⏰ Reminder: **{title}**")

    # ═══════════════════════════════════════════════════════════
    # State Management
    # ═══════════════════════════════════════════════════════════

    def _set_state(self, state: str):
        self.orb.set_state(state)
        self.state_label.set_state(state)
        if self.orb_bridge:
            self.orb_bridge.set_state(state)

    def _update_connection_status(self):
        status = self.provider_manager.get_provider_status()
        provider = self.provider_manager.current_provider
        name = provider.get_name() if provider else "None"
        connected = status == ProviderStatus.AVAILABLE
        self.connection_indicator.set_status(connected, name)

        if not connected:
            self._set_state("disconnected")
        elif not self._is_processing:
            self._set_state("idle")

    # ═══════════════════════════════════════════════════════════
    # Conversations
    # ═══════════════════════════════════════════════════════════

    def _new_conversation(self):
        self.chat_panel.clear_messages()
        cid = self.memory.start_new_conversation()
        self._refresh_sidebar()
        self.sidebar.select_conversation(cid)
        self.chat_panel.add_assistant_message(
            "New conversation started. How can I help you?"
        )
        self.chat_panel.focus_input()

    def _load_conversation(self, conv_id: int):
        self.memory._current_conversation_id = conv_id
        self.chat_panel.clear_messages()

        messages = self.memory.get_conversation_history(limit=100)
        for m in messages:
            if m["role"] == "user":
                self.chat_panel.add_user_message(m["content"])
            elif m["role"] == "assistant":
                self.chat_panel.add_assistant_message(m["content"])

        if not messages:
            self.chat_panel.add_assistant_message("How can I help you?")

        self.sidebar.select_conversation(conv_id)
        self.chat_panel.focus_input()

    def _delete_conversation(self, conv_id: int):
        reply = QMessageBox.question(
            self, "Delete Conversation",
            "Are you sure you want to delete this conversation?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.memory.conversations.delete_conversation(conv_id)
            if self.memory.current_conversation_id == conv_id:
                self._new_conversation()
            self._refresh_sidebar()

    def _refresh_sidebar(self):
        conversations = self.memory.conversations.get_conversations(limit=50)
        self.sidebar.set_conversations(conversations)
        if self.memory.current_conversation_id:
            self.sidebar.select_conversation(self.memory.current_conversation_id)

    # ═══════════════════════════════════════════════════════════
    # Voice
    # ═══════════════════════════════════════════════════════════

    def _toggle_voice(self):
        if self.speech_recognizer.is_listening:
            self.speech_recognizer.cancel()
            self._set_state("idle")
        else:
            self._set_state("listening")
            language = config.get("voice", "stt_language", "en-US")
            self.speech_recognizer.recognize_speech(
                language=language,
                on_result=lambda text: self._voice_result_signal.emit(text),
                on_error=lambda err: self._voice_error_signal.emit(err),
                on_started=lambda: self._set_state_signal.emit("listening"),
                on_stopped=lambda: None,
            )

    def _start_wake_word(self):
        def _on_wake():
            logger.info("Wake word detected — activating voice input")
            self._voice_result_signal.emit("")  # Will show empty, triggers listening
            self._toggle_voice()

        self.wake_word.start(on_wake=_on_wake)

    # ═══════════════════════════════════════════════════════════
    # Screenshot
    # ═══════════════════════════════════════════════════════════

    def _take_screenshot_and_analyze(self):
        """Capture screen and send to AI for analysis."""
        self._set_state("processing")
        self.chat_panel.add_user_message("[Screenshot captured — analyzing...]")

        def _capture():
            try:
                result = self.screenshot.capture_to_bytes()
                if result:
                    image_bytes, mime = result
                    context = self.memory.get_context_messages(limit=10)

                    response = self.provider_manager.send_message(
                        "Please analyze this screenshot and describe what you see. "
                        "Be helpful and context-aware.",
                        context_messages=context,
                        image_data=image_bytes,
                        image_mime=mime,
                    )

                    if response.is_error:
                        self._append_assistant_signal.emit(f"[Error: {response.error}]")
                    else:
                        self._append_assistant_signal.emit(response.content)
                        self.memory.add_assistant_message(response.content)
                else:
                    self._append_assistant_signal.emit(
                        "Failed to capture screenshot. Required packages (mss, Pillow) may not be installed."
                    )
            except Exception as e:
                logger.error("Screenshot analysis error: %s", e)
                self._append_assistant_signal.emit(f"[Error: {e}]")
            finally:
                self._set_state_signal.emit("idle")
                self._is_processing = False

        self._is_processing = True
        thread = threading.Thread(target=_capture, daemon=True)
        thread.start()

    # ═══════════════════════════════════════════════════════════
    # Settings
    # ═══════════════════════════════════════════════════════════

    def _open_settings(self):
        dialog = SettingsWindow(self)
        dialog.settings_changed.connect(self._on_settings_changed)
        dialog.exec()

    def _on_settings_changed(self):
        self._update_connection_status()

        # Re-create provider manager in case provider changed
        self.provider_manager = ProviderManager()
        self._update_connection_status()

        # Update wake word state
        if config.get("wake_word", "enabled", False) and not self.wake_word.is_active:
            self._start_wake_word()
        elif not config.get("wake_word", "enabled", False) and self.wake_word.is_active:
            self.wake_word.stop()

        logger.info("Settings applied")

    # ═══════════════════════════════════════════════════════════
    # Window Management
    # ═══════════════════════════════════════════════════════════

    def _show_from_tray(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _quit_app(self):
        self._cleanup()
        QApplication.instance().quit()

    def closeEvent(self, event):
        """Minimize to tray on close instead of quitting."""
        event.ignore()
        self.hide()
        self.tray.show_notification(
            "VERONIKA AI",
            "Running in background. Double-click tray icon to restore.",
            3000,
        )

    def _cleanup(self):
        """Clean shutdown of all subsystems."""
        logger.info("Shutting down VERONIKA AI...")
        self.reminder_manager.stop()
        self.wake_word.stop()
        self.tts.stop()
        self.speech_recognizer.cancel()
        self.tray.hide()

        if getattr(self.action_registry, "swarm", None):
            try:
                self.action_registry.swarm.shutdown()
            except Exception:
                pass
        if self.mcp_manager:
            try:
                self.mcp_manager.stop()
            except Exception:
                pass
        if self.model_scout:
            try:
                self.model_scout.stop()
            except Exception:
                pass
        if self.sync_server:
            try:
                self.sync_server.stop()
            except Exception:
                pass
        if self.orb_bridge:
            try:
                self.orb_bridge.stop()
            except Exception:
                pass

        # Save window size
        config.set("ui", "window_width", self.width())
        config.set("ui", "window_height", self.height())
        config.save()
