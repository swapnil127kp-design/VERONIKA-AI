# VERONIKA — FEATURE STATUS

> Phase 0 deliverable · 2026-11-04 · Verified against actual source. Legend: ✅ Implemented · ⚠️ Partial · ❌ Missing · 🎯 Planned (directive requirement, not yet built).

## Existing VERONIKA features

| Feature | Status | Evidence / gap |
|---|---|---|
| Multi-provider LLM (openai, google, groq, openrouter, omniroute, ollama) | ✅ | 6 providers registered; env_map covers all; live `/models` discovery + health caching |
| Task-based model routing | ✅ | `provider_manager.py` TaskRouter; vision tasks now capability-filtered |
| Provider fallback chain | ✅ | `provider_manager.py`; free-only policy enforced in both send paths |
| Token streaming | ✅ | **Real streaming everywhere** (Phase 2): OpenAI-compatible SSE + Gemini SDK/REST SSE; fake split removed |
| Gemini REST fallback | ✅ | `:640-642` + now streaming-capable; SDK itself is deprecated EOL (see PROVIDER_CONFIGURATION.md) |
| Free-first policy | ✅ | `cost_tier` classification + `ai.free_only` guard |
| Usage reporting | ✅ | `get_usage_summary()` per-provider totals |
| MCP client (stdio + HTTP) | ✅ | `mcp_client.py:121-267, 274-506` |
| MCP registry module | ❌ | Doesn't exist; README.md:88 drift; loader lives at `:389-398` |
| ReAct agent loop (REA) | ✅ | `rea_bridge.py:206-350` |
| Swarm parallel agents | ✅ | `swarm_coordinator.py:94-164` |
| SQLite memory (WAL, 6 tables) | ✅ | `database.py:50-126` |
| Memory sync export | ✅ | `memory_manager.export_data` → `sync_server.py:175` |
| Sync server (FastAPI :8765, WS chat/live) | ✅ | `sync_server.py`; hardening required (SECURITY.md H-1..H-3) |
| HMAC sync auth | ✅ | `auth.py:85, 112-115`; empty-token risk (H-3) |
| Action registry (30+ actions) | ✅ | `action_registry.py` |
| Permission path gating | ✅ | `permissions.py`; `run_shell` lacks dir check (H-4) |
| Shell / Python execution | ✅ (risky) | `coding_engine.py:83-90, 126-133` |
| Workflow engine | ⚠️ | Step-timeout dead config (`workflow_engine.py:104`) |
| Self-upgrade backup/rollback | ✅ | `self_upgrade.py` (323 LOC) |
| TTS (edge-tts + SAPI5 + ULTRON DSP) | ✅ | `text_to_speech.py` (385 LOC) |
| STT (Google Web API) | ⚠️ | Works; privacy gating needed (H-9) |
| Microphone recording | ❌ | `microphone.py` lists devices only; no record path |
| Wake word | ⚠️ | Porcupine demo keyword; keyring key never written (`wake_word.py:59`) |
| Screen capture | ✅ | `screenshot_capture.py` (mss) |
| 3D orb UI | ⚠️ | Single-file `orb.html`, CDN-pinned (H-8); ULTRON app to replace it |
| Orb bridge WS | ✅ | `ultron_bridge.py` (:8766/:3000); hand-rolled — replace |
| Chat markdown/code rendering | ❌ | Plain QLabel bubbles (`chat_panel.py`) |
| Exam predictor | ✅ | `exam_predictor.py` (310 LOC) |
| Persona/entity modes | ✅ | veronika/friday/ultron + overlays (`entity_manager.py`) — companion overlay non-romantic, girlfriend alias supported |
| Personality Engine (3 personas) | ✅ | **Phase 3 done**: Companion (non-romantic) replaces Girlfriend (deprecated alias), ULTRON de-toxified (no "kamine"), 5-greeting pools + randomization, startup-greeting toggle, capabilities/shortcuts metadata; mode switch writes only `persona.mode` |
| Test suite | ✅ | **269 passed, ~10s** (verified 2026-11-04; 205 baseline + 11 security + 21 provider + 32 persona/entity tests); backend-only, no UI/voice/server tests |

## ULTRON UI features (reference project)

| Feature | Status | Notes |
|---|---|---|
| 3D holographic orb (raw three.js, bloom + chromatic GLSL) | ✅ (in source repo) | Reuse as-is + add setters |
| Orb programmatic control | ⚠️ | Camera-only API today; state/color setters to add |
| Gesture control (MediaPipe pinch) | ✅ (in source repo) | CDN-dependent; bundle locally for offline |
| Audio reactivity | ❌ | Not implemented anywhere yet |
| Backend event bridge | ❌ | No WS/HTTP calls exist; contract defined (MAP §2.3) |
| Chat/task panels | ❌ | Not present; to be built on HUD |

## Part 7 features (Android reference)

| Feature | Status | Notes |
|---|---|---|
| Compilable Kotlin app | ❌ | Source missing from all parts; only `JarvisApp.kt` (imports 12+ missing classes) |
| Offline STT model (Vosk) | ✅ (binaries) | ~71 MB, reusable; wiring rebuild |
| Voice biometrics model (x-vector) | ✅ (binaries + UX spec) | Matching code rebuild |
| 3D orb + HUD (mobile) | ✅ (assets) | Reusable with TAMCL attribution |
| Liquid-Glass theme system | ✅ (XML) | Drop-in |
| 17 overlay avatars | ✅ (assets) | Need esm.sh vendoring |
| Gemini Live transport | 🎯 pattern only | Docs describe; no code |
| Command executor | 🎯 pattern only | Catalog documented; code absent |

## Directive features not yet started (🎯 planned, roadmap phases)

Cross-device account+memory sync (Ph9-11) · Android companion (Ph10) · Model Scout live discovery (Ph4) · Self-correction coding loop (Ph8) · Task orchestrator with progress UI (Ph8) · Project memory (Ph7) · Permission levels L1/L2/L3 (Ph8-9) · Vision agent analysis (Ph12) · Gesture→action mapping (Ph12) · Notifications center (Ph9) · Audit logs (Ph9) · Multi-agent coordinator+reviewer (Ph13).
