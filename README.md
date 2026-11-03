# VERONIKA AI — Autonomous Desktop Agent & Orchestrator

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![Framework: PySide6](https://img.shields.io/badge/GUI-PySide6%20%28Qt%206%29-41CD52.svg?logo=qt&logoColor=white)](https://pypi.org/project/PySide6/)
[![Protocol: Model Context Protocol](https://img.shields.io/badge/Protocol-MCP-orange.svg)](https://modelcontextprotocol.io)
[![Tests: 205 Passed](https://img.shields.io/badge/Tests-205%20Passed-brightgreen.svg)](tests/)
[![Author: Swapnil Kumar](https://img.shields.io/badge/Author-Swapnil%20Kumar-blueviolet.svg)](#-author--maintainer)

An open-source, production-grade autonomous desktop AI assistant and multi-agent orchestrator built with **PySide6 (Qt 6)**. VERONIKA combines multi-provider LLM intelligence (**OpenAI GPT-4o**, **Google Gemini**) with full **Model Context Protocol (MCP)** tool integration, multi-agent swarm execution, real-time voice and vision, persistent SQLite memory, and deep Windows automation.

---

## 🌟 Key Highlights & Architecture

```
                                  ┌───────────────────────────┐
                                  │   Swapnil Kumar (User)    │
                                  └─────────────┬─────────────┘
                                                │ (Voice / Hotkeys / UI)
                                                ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   VERONIKA CORE RUNTIME                                     │
├───────────────────────────────┬─────────────────────────────┬───────────────────────────────┤
│       AI Intelligence         │      Desktop Automation     │       Perception & UI         │
│  • Dual Provider (OpenAI/Gem) │  • Windows Action Engine    │  • PySide6 Glassmorphic UI    │
│  • Dynamic Model Routing      │  • Multi-step Workflows     │  • 3D Holographic Orb Bridge  │
│  • MCP Client & Tools         │  • Sandboxed Permissions    │  • Real-time Audio STT/TTS    │
│  • Autonomous Agent Swarms    │  • Phone Sync Server        │  • Screen Vision (Pillow/mss) │
│  • Memory & Knowledge Graph   │  • Self-Upgrade System      │  • Windows Credential Sec     │
└───────────────────────────────┴─────────────────────────────┴───────────────────────────────┘
```

---

## ✨ Features

| Category | Description |
|---|---|
| 🤖 **Dual AI Providers** | Hot-swappable backends for **OpenAI** (GPT-4o / Codex) and **Google Gemini** with intelligent routing |
| 🔌 **Model Context Protocol (MCP)** | Standardized tool integration allowing dynamic execution of external developer servers |
| 🐝 **Autonomous Swarm Coordinator** | Multi-worker parallel reasoning engine for executing complex development and automation tasks |
| 🎭 **Multi-Entity Persona System** | Switch dynamically between *VERONIKA* (Commander), *FRIDAY* (Tactical), and *ULTRON* (Guardian) |
| 🎙 **Real-time Voice I/O** | Push-to-talk speech-to-text with multi-engine TTS (Edge-TTS & Windows SAPI5) and DSP pitch shifting |
| 👁 **Vision & Screen Analysis** | Low-latency screenshot capture with automated AI visual reasoning |
| 🌐 **3D Holographic Orb Bridge** | Embedded WebSocket server bridging system states to a 3D Three.js holographic particle orb |
| ⚡ **Windows Automation Engine** | Sandboxed execution for app launching, file manipulation, browser navigation, and custom workflows |
| 💾 **Persistent SQLite Memory** | Local session logging, contextual memory retrieval, notes, and timed reminder scheduling |
| 🔒 **Enterprise-Grade Security** | Sensitive API credentials managed via **Windows Credential Manager** (`keyring`); dangerous paths blacklisted |

---

## 📁 Project Structure

```
VERONIKA/
├── main.py                     # Primary runtime entry point
├── requirements.txt            # Dependency manifest
├── .env.example                # Sample environment configuration
├── LICENSE                     # MIT Open Source License
├── CONTRIBUTING.md             # Community contribution guide
│
├── ai/                         # Intelligence & Persona Subsystems
│   ├── entity_manager.py       # Independent sentient character engine
│   ├── model_scout.py          # Real-time free/high-speed model discovery
│   ├── persona_manager.py      # Voice profiles and prompt styling
│   ├── provider_base.py        # Abstract AI client interface
│   ├── provider_manager.py     # OpenAI, Gemini & Dynamic Router
│   └── swarm_coordinator.py    # Multi-agent worker orchestration
│
├── app/                        # Application Infrastructure
│   ├── config.py               # Settings loader & AppData directory manager
│   ├── logging_config.py       # Structured logging system
│   └── self_upgrade.py         # Automated update and health engine
│
├── automation/                 # Windows OS Automation
│   ├── action_registry.py      # Central execution dispatcher
│   ├── application_launcher.py # Safe executable & store app launcher
│   ├── browser_actions.py      # URL routing and settings navigation
│   ├── coding_engine.py        # Autonomous code generation & diffing
│   ├── file_actions.py         # Sandboxed filesystem operations
│   ├── github_scout.py         # Autonomous GitHub repository scout
│   ├── permissions.py          # Path validation and security guards
│   └── workflow_engine.py      # Sequenced workflow executor
│
├── mcp/                        # Model Context Protocol
│   ├── mcp_client.py           # Standardized MCP client
│   └── mcp_server_registry.py  # External tool configuration
│
├── memory/                     # Local Storage & Knowledge
│   ├── database.py             # SQLite connection & schema migrations
│   ├── memory_manager.py       # Conversational memory API
│   └── repositories.py         # Typed repository data access
│
├── server/                     # Communication & Sync
│   ├── auth.py                 # HMAC token authentication
│   └── sync_server.py          # FastAPI cross-device synchronization
│
├── ui/                         # PySide6 Presentation Layer
│   ├── assets/                 # Holographic UI assets & web templates
│   ├── chat_panel.py           # Message stream renderer
│   ├── components.py           # Animated visual widgets & custom controls
│   ├── main_window.py          # Orchestration window
│   ├── settings_window.py      # Multi-tab preference manager
│   ├── system_tray.py          # System tray integration
│   └── ultron_bridge.py        # WebSocket bridge for 3D orb HUD
│
├── vision/                     # Vision Processing
│   └── screenshot_capture.py   # Multi-monitor screenshot capture
│
├── voice/                      # Audio & Speech
│   ├── microphone.py           # Audio device lifecycle manager
│   ├── speech_recognition.py   # Speech-to-text pipeline
│   ├── text_to_speech.py       # Edge-TTS & SAPI5 synthesizer
│   └── wake_word.py            # Wake-word detection engine
│
└── tests/                      # Automated Test Suite (205 tests)
    ├── conftest.py
    ├── test_ai.py
    ├── test_automation.py
    ├── test_config.py
    ├── test_entity.py
    ├── test_mcp.py
    ├── test_swarm.py
    └── ...
```

---

## 🚀 Getting Started

### 1. Prerequisites

* **Windows 10 / 11** (64-bit)
* **Python 3.11+** installed
* Git

### 2. Installation

Clone the repository and create an isolated virtual environment:

```bash
git clone https://github.com/swapnil127kp-design/VERONIKA-AI.git
cd VERONIKA-AI

python -m venv .venv
.\.venv\Scripts\activate

pip install -r requirements.txt
```

### 3. Configuration

Duplicate `.env.example` to `.env`:

```bash
copy .env.example .env
```

Add your API credentials:
```env
AI_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key_here
# Optional: Google Gemini key
GEMINI_API_KEY=your_gemini_api_key_here
```

*(Note: In production, API keys can also be managed securely in Windows Credential Manager directly via the in-app Settings interface.)*

### 4. Running the Assistant

```bash
python main.py
```

---

## 🧪 Testing

The repository includes a comprehensive test suite covering AI providers, automation sandbox security, memory databases, and MCP integrations:

```bash
pytest tests/ -v
```

All 205 tests pass cleanly in under 10 seconds.

---

## ⌨️ Shortcuts & Controls

* `Ctrl + N`: Start a fresh conversation
* `Ctrl + ,`: Open application settings
* `Ctrl + Shift + V`: Trigger push-to-talk voice input
* `Ctrl + Shift + S`: Capture screen area and request instant AI multimodal analysis

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Please check the [CONTRIBUTING.md](CONTRIBUTING.md) guide before opening pull requests.

---

## 👨‍💻 Author & Maintainer

* **Swapnil Kumar** — Lead Maintainer & Core Architect

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for complete details.
