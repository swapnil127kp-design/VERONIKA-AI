"""
VERONIKA AI - Settings Window
Comprehensive settings interface for all configurable options.
"""
import logging
from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QCheckBox, QSpinBox, QPushButton, QTabWidget,
    QScrollArea, QFrame, QGroupBox, QMessageBox, QFileDialog,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from app.config import config, APP_VERSION, APP_NAME
from ui.components import Colors, CyberButton

logger = logging.getLogger(__name__)


class SettingsWindow(QDialog):
    """Full settings dialog with tabs."""

    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} - Settings")
        self.setMinimumSize(600, 550)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Colors.BG_DARK.name()};
            }}
            QLabel {{
                color: {Colors.TEXT_PRIMARY.name()};
                font-size: 13px;
            }}
            QGroupBox {{
                color: {Colors.CYAN.name()};
                font-size: 13px;
                font-weight: 600;
                border: 1px solid {Colors.BORDER.name()};
                border-radius: 8px;
                margin-top: 16px;
                padding-top: 20px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }}
            QComboBox, QSpinBox, QLineEdit {{
                background: {Colors.BG_INPUT.name()};
                color: {Colors.TEXT_PRIMARY.name()};
                border: 1px solid {Colors.BORDER.name()};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
                min-height: 28px;
            }}
            QComboBox:focus, QSpinBox:focus, QLineEdit:focus {{
                border: 1px solid {Colors.CYAN_DIM.name()};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QCheckBox {{
                color: {Colors.TEXT_PRIMARY.name()};
                font-size: 13px;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid {Colors.BORDER.name()};
                background: {Colors.BG_INPUT.name()};
            }}
            QCheckBox::indicator:checked {{
                background: {Colors.CYAN_DIM.name()};
                border-color: {Colors.CYAN.name()};
            }}
            QTabWidget::pane {{
                border: 1px solid {Colors.BORDER.name()};
                border-radius: 8px;
                background: {Colors.BG_CARD.name()};
            }}
            QTabBar::tab {{
                background: {Colors.BG_DARK.name()};
                color: {Colors.TEXT_SECONDARY.name()};
                padding: 8px 16px;
                border: none;
                border-bottom: 2px solid transparent;
                font-size: 12px;
                font-weight: 600;
            }}
            QTabBar::tab:selected {{
                color: {Colors.CYAN.name()};
                border-bottom: 2px solid {Colors.CYAN.name()};
            }}
            QTabBar::tab:hover {{
                color: {Colors.TEXT_PRIMARY.name()};
            }}
        """)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        # Title
        title = QLabel(f"⚙  {APP_NAME} Settings")
        title.setStyleSheet(f"""
            font-size: 18px;
            font-weight: 700;
            color: {Colors.CYAN.name()};
            padding-bottom: 8px;
        """)
        layout.addWidget(title)

        # Tabs
        tabs = QTabWidget()
        tabs.addTab(self._create_ai_tab(), "AI Provider")
        tabs.addTab(self._create_voice_tab(), "Voice")
        tabs.addTab(self._create_general_tab(), "General")
        tabs.addTab(self._create_automation_tab(), "Automation")
        tabs.addTab(self._create_about_tab(), "About")
        layout.addWidget(tabs, 1)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        save_btn = CyberButton("Save Settings")
        save_btn.clicked.connect(self._save_settings)

        cancel_btn = CyberButton("Cancel", Colors.TEXT_SECONDARY)
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def _create_ai_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # Provider selection
        group = QGroupBox("AI Provider Configuration")
        g_layout = QVBoxLayout(group)

        row = QHBoxLayout()
        row.addWidget(QLabel("Provider:"))
        self._provider_combo = QComboBox()
        self._provider_combo.addItems(["openai", "google"])
        self._provider_combo.setCurrentText(config.get("ai", "provider", "openai"))
        self._provider_combo.currentTextChanged.connect(self._on_provider_changed)
        row.addWidget(self._provider_combo, 1)
        g_layout.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Model:"))
        self._model_input = QLineEdit()
        current_provider = config.get("ai", "provider", "openai")
        self._model_input.setText(config.get("ai", f"{current_provider}_model", ""))
        self._model_input.setPlaceholderText("e.g., gpt-4o or gemini-1.5-pro")
        row2.addWidget(self._model_input, 1)
        g_layout.addLayout(row2)

        # API Key
        key_group = QGroupBox("API Key")
        k_layout = QVBoxLayout(key_group)

        note = QLabel(
            "⚠ API keys are stored in your system's credential manager (Windows Credential Locker). "
            "Storing API keys on a personal computer carries inherent risk. Ensure your system is secured."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {Colors.ORANGE.name()}; font-size: 11px;")
        k_layout.addWidget(note)

        key_row = QHBoxLayout()
        key_row.addWidget(QLabel("API Key:"))
        self._api_key_input = QLineEdit()
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_input.setPlaceholderText("Enter your API key")
        key_row.addWidget(self._api_key_input, 1)

        save_key_btn = CyberButton("Store Key", Colors.GREEN)
        save_key_btn.setFixedWidth(100)
        save_key_btn.clicked.connect(self._save_api_key)
        key_row.addWidget(save_key_btn)
        k_layout.addLayout(key_row)

        # Temperature / Max tokens
        params_row = QHBoxLayout()
        params_row.addWidget(QLabel("Temperature:"))
        self._temp_spin = QSpinBox()
        self._temp_spin.setRange(0, 20)
        self._temp_spin.setValue(int(config.get("ai", "temperature", 0.7) * 10))
        params_row.addWidget(self._temp_spin)
        params_row.addWidget(QLabel("Max Tokens:"))
        self._tokens_spin = QSpinBox()
        self._tokens_spin.setRange(100, 8192)
        self._tokens_spin.setSingleStep(256)
        self._tokens_spin.setValue(config.get("ai", "max_tokens", 2048))
        params_row.addWidget(self._tokens_spin)

        self._stream_check = QCheckBox("Stream responses")
        self._stream_check.setChecked(config.get("ai", "stream_responses", True))

        layout.addWidget(group)
        layout.addWidget(key_group)
        layout.addLayout(params_row)
        layout.addWidget(self._stream_check)
        layout.addStretch()
        return widget

    def _create_voice_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("Speech Settings")
        g_layout = QVBoxLayout(group)

        self._tts_check = QCheckBox("Enable Text-to-Speech")
        self._tts_check.setChecked(config.get("voice", "tts_enabled", True))
        g_layout.addWidget(self._tts_check)

        row = QHBoxLayout()
        row.addWidget(QLabel("Speech Speed:"))
        self._speed_spin = QSpinBox()
        self._speed_spin.setRange(50, 400)
        self._speed_spin.setSingleStep(10)
        self._speed_spin.setValue(config.get("voice", "tts_speed", 150))
        self._speed_spin.setSuffix(" wpm")
        row.addWidget(self._speed_spin)
        g_layout.addLayout(row)

        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel("Recognition Language:"))
        self._stt_lang_combo = QComboBox()
        self._stt_lang_combo.addItems(["en-US", "en-IN", "hi-IN"])
        self._stt_lang_combo.setCurrentText(config.get("voice", "stt_language", "en-US"))
        lang_row.addWidget(self._stt_lang_combo)
        g_layout.addLayout(lang_row)

        engine_row = QHBoxLayout()
        engine_row.addWidget(QLabel("STT Engine:"))
        self._stt_engine_combo = QComboBox()
        self._stt_engine_combo.addItem("Google (cloud) — free; audio leaves device", "google_free")
        self._stt_engine_combo.addItem("Vosk (local) — 100% offline, private", "vosk_local")
        idx = self._stt_engine_combo.findData(
            config.get("voice", "stt_engine", "google_free")
        )
        self._stt_engine_combo.setCurrentIndex(max(0, idx))
        engine_row.addWidget(self._stt_engine_combo, 1)
        g_layout.addLayout(engine_row)

        privacy_note = QLabel(
            "🔒 Privacy: the Google engine sends your speech audio to Google's "
            "free web API for recognition. The Vosk engine runs entirely on "
            "this PC (model: voice/models/) and never uploads audio."
        )
        privacy_note.setWordWrap(True)
        privacy_note.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()}; font-size: 11px;")
        g_layout.addWidget(privacy_note)

        self._barge_in_check = QCheckBox(
            "Allow voice interruption (barge-in) while VERONIKA speaks"
        )
        self._barge_in_check.setChecked(config.get("voice", "barge_in_enabled", False))
        g_layout.addWidget(self._barge_in_check)

        barge_note = QLabel(
            "Barge-in keeps the microphone metering active during speech and "
            "interrupts VERONIKA when it detects sustained voice above the "
            "threshold. On loud speakers VERONIKA may hear herself — the "
            "⏹ Stop button in the chat view always works."
        )
        barge_note.setWordWrap(True)
        barge_note.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()}; font-size: 11px;")
        g_layout.addWidget(barge_note)

        wake_group = QGroupBox("Wake Word")
        w_layout = QVBoxLayout(wake_group)

        self._wake_check = QCheckBox("Enable 'Hey Veronika' wake word")
        self._wake_check.setChecked(config.get("wake_word", "enabled", False))
        w_layout.addWidget(self._wake_check)

        wake_note = QLabel(
            "Wake word detection requires either:\n"
            "• Picovoice Porcupine (with access key from picovoice.ai), or\n"
            "• Falls back to periodic speech recognition (uses microphone)"
        )
        wake_note.setWordWrap(True)
        wake_note.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()}; font-size: 11px;")
        w_layout.addWidget(wake_note)

        layout.addWidget(group)
        layout.addWidget(wake_group)
        layout.addStretch()
        return widget

    def _create_general_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("General Settings")
        g_layout = QVBoxLayout(group)

        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel("Preferred Language:"))
        self._lang_combo = QComboBox()
        self._lang_combo.addItems(["en", "hi", "hinglish"])
        self._lang_combo.setCurrentText(config.get("general", "language", "en"))
        lang_row.addWidget(self._lang_combo)
        g_layout.addLayout(lang_row)

        self._startup_check = QCheckBox("Start with Windows (opt-in)")
        self._startup_check.setChecked(config.get("general", "startup_with_windows", False))
        g_layout.addWidget(self._startup_check)

        self._float_check = QCheckBox("Enable floating assistant window")
        self._float_check.setChecked(config.get("ui", "floating_window", False))
        g_layout.addWidget(self._float_check)

        self._screenshot_check = QCheckBox("Confirm before sending screenshots to AI")
        self._screenshot_check.setChecked(config.get("general", "screenshot_confirm", True))
        g_layout.addWidget(self._screenshot_check)

        mem_group = QGroupBox("Memory")
        m_layout = QVBoxLayout(mem_group)

        self._auto_save_check = QCheckBox("Auto-save conversation history")
        self._auto_save_check.setChecked(config.get("memory", "auto_save_conversations", True))
        m_layout.addWidget(self._auto_save_check)

        sync_group = QGroupBox("Phone Sync")
        s_layout = QVBoxLayout(sync_group)

        sync_note = QLabel(
            "The sync token pairs the Android app with this PC. It is stored in "
            "Windows Credential Manager and is never printed to the console."
        )
        sync_note.setWordWrap(True)
        sync_note.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()}; font-size: 11px;")
        s_layout.addWidget(sync_note)

        sync_row = QHBoxLayout()
        reveal_btn = CyberButton("Show Token")
        reveal_btn.clicked.connect(self._show_sync_token)
        rotate_btn = CyberButton("Rotate Token", Colors.ORANGE)
        rotate_btn.clicked.connect(self._rotate_sync_token)
        sync_row.addWidget(reveal_btn)
        sync_row.addWidget(rotate_btn)
        s_layout.addLayout(sync_row)

        layout.addWidget(group)
        layout.addWidget(mem_group)
        layout.addWidget(sync_group)
        layout.addStretch()
        return widget

    def _create_automation_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("Automation Settings")
        g_layout = QVBoxLayout(group)

        self._confirm_destructive = QCheckBox("Confirm before destructive actions")
        self._confirm_destructive.setChecked(config.get("automation", "confirm_destructive", True))
        g_layout.addWidget(self._confirm_destructive)

        timeout_row = QHBoxLayout()
        timeout_row.addWidget(QLabel("Step Timeout:"))
        self._timeout_spin = QSpinBox()
        self._timeout_spin.setRange(5, 120)
        self._timeout_spin.setValue(config.get("automation", "step_timeout_seconds", 30))
        self._timeout_spin.setSuffix(" sec")
        timeout_row.addWidget(self._timeout_spin)
        g_layout.addLayout(timeout_row)

        max_row = QHBoxLayout()
        max_row.addWidget(QLabel("Max Workflow Steps:"))
        self._max_steps_spin = QSpinBox()
        self._max_steps_spin.setRange(1, 50)
        self._max_steps_spin.setValue(config.get("automation", "max_workflow_steps", 20))
        max_row.addWidget(self._max_steps_spin)
        g_layout.addLayout(max_row)

        layout.addWidget(group)
        layout.addStretch()
        return widget

    def _create_about_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        about = QLabel(f"""
            <div style="text-align: center; padding: 20px;">
                <h2 style="color: {Colors.CYAN.name()};">{APP_NAME}</h2>
                <p style="color: {Colors.TEXT_SECONDARY.name()};">Version {APP_VERSION}</p>
                <p style="color: {Colors.TEXT_SECONDARY.name()};">
                    A premium AI desktop assistant for Windows.
                </p>
                <br/>
                <p style="color: {Colors.TEXT_DIM.name()}; font-size: 11px;">
                    PC counterpart of the VERONIKA AI Android application.
                </p>
            </div>
        """)
        about.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(about)
        layout.addStretch()
        return widget

    def _on_provider_changed(self, provider: str):
        default_model = "gemini-1.5-pro" if provider == "google" else "gpt-4o"
        self._model_input.setText(config.get("ai", f"{provider}_model", default_model))
        self._model_input.setPlaceholderText(f"e.g., {default_model}")

    def _save_api_key(self):
        key = self._api_key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "API Key", "Please enter an API key.")
            return

        provider = self._provider_combo.currentText()
        config.set_api_key(provider, key)
        self._api_key_input.clear()
        QMessageBox.information(
            self, "API Key Saved",
            f"API key for {provider} has been securely stored.\n\n"
            "Note: Keys are stored in Windows Credential Manager."
        )

    def _show_sync_token(self):
        """Reveal the sync master token without printing it to any log."""
        try:
            from server.auth import SyncAuth
            token = SyncAuth().master_token
        except Exception as e:
            QMessageBox.warning(self, "Phone Sync", f"Could not load sync token: {e}")
            return
        QMessageBox.information(
            self, "Phone Sync Token",
            f"Your sync master token:\n\n{token}\n\n"
            "Enter this in the Android app's API & Connection screen. "
            "Keep it private — anyone with this token can connect to your PC.",
        )

    def _rotate_sync_token(self):
        """Invalidate the current sync token and issue a new one."""
        confirm = QMessageBox.question(
            self, "Rotate Sync Token",
            "Invalidate the current sync token and issue a new one?\n\n"
            "All paired devices will need to re-authenticate with the new token.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            from server.auth import SyncAuth
            token = SyncAuth().rotate_token()
        except Exception as e:
            QMessageBox.warning(self, "Phone Sync", f"Could not rotate token: {e}")
            return
        QMessageBox.information(
            self, "Phone Sync",
            f"New sync token:\n\n{token}\n\n"
            "Enter it in the Android app to re-pair.",
        )

    def _save_settings(self):
        # AI
        config.set("ai", "provider", self._provider_combo.currentText())
        provider = self._provider_combo.currentText()
        config.set("ai", f"{provider}_model", self._model_input.text().strip())
        config.set("ai", "temperature", self._temp_spin.value() / 10.0)
        config.set("ai", "max_tokens", self._tokens_spin.value())
        config.set("ai", "stream_responses", self._stream_check.isChecked())

        # Voice
        config.set("voice", "tts_enabled", self._tts_check.isChecked())
        config.set("voice", "tts_speed", self._speed_spin.value())
        config.set("voice", "stt_language", self._stt_lang_combo.currentText())
        engine_data = self._stt_engine_combo.currentData()
        if engine_data:
            config.set("voice", "stt_engine", engine_data)
        config.set("voice", "barge_in_enabled", self._barge_in_check.isChecked())

        # Wake word
        config.set("wake_word", "enabled", self._wake_check.isChecked())

        # General
        config.set("general", "language", self._lang_combo.currentText())
        config.set("general", "startup_with_windows", self._startup_check.isChecked())
        config.set("general", "screenshot_confirm", self._screenshot_check.isChecked())
        config.set("ui", "floating_window", self._float_check.isChecked())

        # Memory
        config.set("memory", "auto_save_conversations", self._auto_save_check.isChecked())

        # Automation
        config.set("automation", "confirm_destructive", self._confirm_destructive.isChecked())
        config.set("automation", "step_timeout_seconds", self._timeout_spin.value())
        config.set("automation", "max_workflow_steps", self._max_steps_spin.value())

        config.save()
        self.settings_changed.emit()
        self.accept()
