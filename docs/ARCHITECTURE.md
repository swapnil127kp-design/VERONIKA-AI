# VERONIKA — ARCHITECTURE

> Phase 0 deliverable · 2026-11-04 · Grounded in the actual audited code (see RESOURCE_INTEGRATION_MAP.md for evidence).

## 1. AS-IS Architecture (what exists today, verified)

### 1.1 Boot wiring (`main.py`)
```
config (app/config.py, JSON at %APPDATA%/Veronika AI/config/settings.json)
  → logging (app/logging_config.py, rotating file + console)
  → ProviderManager (ai/provider_manager.py, 5 providers)
  → MemoryManager (memory/memory_manager.py → SQLite WAL)
  → MCPManager (mcp/mcp_client.py, stdio + HTTP transports)
  → ActionRegistry (automation/action_registry.py, 30+ actions + dynamic mcp__* tools)
  → [--sync] SyncServer (server/sync_server.py, FastAPI :8765)
  → GUI (PySide6 MainWindow) or CLI fallback (--cli / missing PySide6)
```

### 1.2 Runtime ports
| Port | Owner | Notes |
|---|---|---|
| 8765 | FastAPI sync server | REST + `WS /ws/chat`, `WS /ws/live`; HMAC token auth |
| 8766 | `ui/ultron_bridge.py` | Hand-rolled RFC6455 WebSocket (orb events) |
| 3000 | `ui/ultron_bridge.py` | HTTP server serving `ui/assets/orb.html` |

### 1.3 Data layer (SQLite WAL, `memory/database.py:50-126`)
Tables: `conversations, memories, reminders, preferences, entities, personas`.
Export via `memory_manager.export_data` (consumed by sync server); import is merge-only (`sync_server.py:183-185`).

### 1.4 Intelligence layer
- 5 providers wired: openai, google, groq, openrouter, omniroute (`provider_manager.py:122-133`).
- TaskRouter classifies code/reasoning/creative → provider (`:53-89`); ordered fallback chain (`:681-736, 845-944`).
- Streaming is **simulated** (blocking call + word-split + 10ms sleeps, `:644-660`).
- REA ReAct loop with tool dispatch + sub-agents (`mcp/rea_bridge.py:206-350`).
- Swarm fan-out/fan-in (`ai/swarm_coordinator.py:94-164`).

### 1.5 UI layer (PySide6)
MainWindow (782 LOC) + sidebar + chat_panel (plain QLabel bubbles) + settings (5 tabs, provider combo limited to openai/google) + system tray + widget kit (`components.py`: AIOrb, GlassCard, CyberButton…). 3D orb = single-file `ui/assets/orb.html` (Three.js 0.160.0 via unpkg CDN, MediaPipe gestures via jsdelivr).

### 1.6 Voice layer (≈60% wired)
TTS complete (edge-tts → SAPI5 → pydub ULTRON DSP → 5-tier playback). STT = Google Web Speech API. **Microphone recording missing** (`microphone.py` lists devices only). Wake word partial (Porcupine, demo keyword, dead keyring lookup).

## 2. TO-BE Architecture (target)

```
┌────────────────────────── Layer 1: Interaction ──────────────────────────┐
│  Text · Voice (STT/TTS) · Gestures (MediaPipe) · Vision (screens/images) │
│  Windows Desktop Client (PySide6 + embedded 3D UI)  ·  Android Companion │
└──────────────────────────────────┬───────────────────────────────────────┘
                                   │
┌────────────────────────── Layer 3: CORE ENGINE ──────────────────────────┐
│  Identity/Account · Persona modes · Context manager · Task router        │
│  Coordinator Agent · Permission gate (L1/L2/L3) · State machine          │
└───────┬──────────────────┬───────────────────────┬───────────────────────┘
        │                  │                       │
┌───────▼──────┐  ┌────────▼────────┐  ┌───────────▼──────────┐
│ Layer 4:     │  │ Layer 5:        │  │ Layer 6:             │
│ AGENTS       │  │ PROVIDERS       │  │ AUTOMATION           │
│ coder, auto, │  │ OmniRoute·Gemini│  │ files·terminal·python│
│ web, vision, │  │ Groq·OpenRouter │  │ git·workflows·self-  │
│ memory, rev. │  │ HF·Ollama       │  │ correction loop      │
└───────┬──────┘  └────────┬────────┘  └───────────┬──────────┘
        └──────────────────┼───────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────────────┐
│ Layer 7: MEMORY & SYNC  (SQLite + FastAPI :8765 + WSS + device registry) │
└──────────────────────────────────┬───────────────────────────────────────┘
┌──────────────────────────────────▼───────────────────────────────────────┐
│ Layer 8: EXTERNAL SERVICES (AI APIs, search, GitHub, MCP servers)        │
└───────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Existing → target mapping (extend, don't rewrite)
| Existing (verified) | Target role | Change required |
|---|---|---|
| `provider_base.py` ABC | Layer 5 contract | Keep; add capability flags (streaming/tools/vision/context) |
| `provider_manager.py` | Layer 5 router | Real streaming; OmniRoute health-check adapter; key→header fix |
| `swarm_coordinator.py` + `rea_bridge.py` | Layer 4 seed | Generalize into `ai/agents/*` with input/output schemas |
| `action_registry.py` + `permissions.py` | Layer 6 bus | Add L1/L2/L3 confirmation gates (SECURITY.md) |
| `database.py` 6 tables | Layer 7 | Add users/devices/projects/tasks/notifications/sync_events/audit_logs |
| `sync_server.py` | Layer 7 | Harden (SECURITY.md), add endpoints per directive §15.1 |
| `ultron_bridge.py` + `orb.html` | UI bridge | Replace with ULTRON Next.js app (`output: "export"`) + maintained WS lib; event contract = RESOURCE_INTEGRATION_MAP §2.3 |
| `text_to_speech.py` DSP chain | Voice engine | Keep; add per-persona voice profiles |
| `microphone.py` | Voice engine | **Complete**: add recording pipeline feeding STT |

### 2.2 New components (no existing code — build new)
- `ai/agents/{coordinator,coder_agent,automation_agent,web_scout_agent,vision_agent,memory_agent,reviewer_agent}.py`
- `ai/task_router.py` (capability-based, not name-based), `ai/context_manager.py`
- `automation/{terminal_manager,python_runner,git_manager,task_orchestrator}.py`
- `memory/{project_memory,sync_manager}.py`
- `security/{secrets_manager,access_control,audit_logger}.py`
- `database/migrations/`
- **Android companion (new Kotlin project)** — Part 7 has NO compilable source (RESOURCE_INTEGRATION_MAP §4); build fresh using salvaged assets (orb.html, HUD, themes, Vosk models) + patterns.

### 2.3 Key contracts
- **Orb event contract**: `assistant.state {mode, energy}`, `assistant.color {bright,mid,dim,hot}`, `assistant.text {lines}`, `orb.rotate/zoom/reset` (RESOURCE_INTEGRATION_MAP §2.3).
- **Assistant state machine**: IDLE · LISTENING · THINKING · SPEAKING · WORKING · WAITING_APPROVAL · SYNCING · ERROR · DISCONNECTED.
- **Persona isolation**: mode switch changes voice/prompt/theme/greeting ONLY — never identity, memory, security, permissions.
- **Free-first policy**: providers classified verified-free / local / paid; paid never selected silently.

## 3. Compatibility & performance constraints
- Windows 10/11, Python 3.11+; PySide6 GUI must stay responsive (async I/O, cancellable tasks).
- 3D UI optional: full experience with effects, degraded mode without (reduced-motion, pausable RAF).
- OmniRoute (127.0.0.1:20128) verified OFFLINE at audit time — adapters need health checks; model IDs unverified until it runs.
- No live SQLite file copying between devices — API-based sync with versioning + conflict handling only.
