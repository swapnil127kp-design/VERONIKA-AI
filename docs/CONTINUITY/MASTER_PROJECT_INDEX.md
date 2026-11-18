# VERONIKA MASTER PROJECT INDEX

**Owner:** Swapnil Kumar · **Project:** VERONIKA AI (`C:\Users\Swapnil\OneDrive\Desktop\claude code\VERONIKA`)
**Created:** 2026-11-06 (Continuity Engine rollout) · **Maintain:** update on every meaningful change.

## What VERONIKA is

Personal multi-agent, multi-model, cross-device AI ecosystem (Windows desktop native + Android companion):

- PySide6 desktop app (`main.py` → `ui/main_window.py`), MIT licensed
- Multi-provider AI (`ai/provider_manager.py`: openai, google, groq, openrouter, omniroute, ollama) + task routing
- Persona system (`ai/persona_manager.py`, `ai/entity_manager.py`) — FRIDAY / Companion / ULTRON
- MCP client (`mcp/mcp_client.py`) + ReAct loop (`mcp/rea_bridge.py`)
- Voice stack (`voice/`): mic capture, Vosk offline STT (en-US + hi-IN), Google cloud STT, Edge/SAPI5 TTS, wake word, barge-in
- Windows automation (`automation/`) with permission gates (`automation/permissions.py`)
- SQLite memory (`memory/`) + reminders
- FastAPI sync server (`server/sync_server.py`) + HMAC auth (`server/auth.py`)
- ULTRON 3D orb bridge (`ui/ultron_bridge.py`, WebSocket)
- Vision (`vision/screenshot_capture.py`)

## Master specification sources

| Source | Where |
|---|---|
| Full master directive chain (original + REA + Neural Galaxy + Continuity + Execution) | Owner notepad: `C:\Users\Swapnil\OneDrive\Desktop\veronika ai master promte.txt` |
| Neural Galaxy spec (project-local copy) | `docs/NEURAL_GALAXY_MASTER_SPEC.md` |
| REA addendum audit | `docs/REA_CAPABILITIES_AUDIT.md`, `docs/REA_INTEGRATION_PLAN.md` |
| Video feature audit (3 Jarvis/HOLO videos) | `docs/VIDEO_REFERENCE_AUDIT.md` |
| Master requirements index | `docs/MASTER_REQUIREMENTS_INDEX.md` (verify exists; create if missing) |

## Reference resources (read-only, originating outside VERONIKA)

| ID | Resource | Path | Status |
|---|---|---|---|
| A | Existing VERONIKA codebase | this repo | Primary, extend-don't-rewrite |
| B | JARVIS Part 7 (Android; Kotlin source missing) | `...\claude code\jarvis\Playlist-main\Playlist-main\Part 7` | Audited; model binaries salvageable; license §map |
| C | ULTRON 3D UI (Next.js + three.js) | `...\claude code\ultron` | Audited; MIT; primary UI source |
| D | MYRAA V2 (`mayra android`) | `...\claude code\MYRAA MOBILE\mayra android` | Deep-audited 2026-11-06; MIT source; asset-bound restrictions; `MYRAA PC_` folder EMPTY |

## Documentation index (docs/)

Phase/audit reports: ARCHITECTURE.md · CURRENT_STATUS.md · DEVELOPMENT_ROADMAP.md · FEATURE_COVERAGE_MATRIX.md · FEATURE_STATUS.md · MODEL_SCOUT.md · PHASE_0_AUDIT_COMPLETE.md · PHASE_5_VOICE_ENGINE.md · PHASE_5_DAY_1_COMPLETE.md · PROVIDER_CONFIGURATION.md · REA_CAPABILITIES_AUDIT.md · REA_INTEGRATION_PLAN.md · RESOURCE_INTEGRATION_MAP.md · SECURITY.md · VIDEO_REFERENCE_AUDIT.md · NEURAL_GALAXY_MASTER_SPEC.md

## How to resume (for any future session/AI)

1. Read `docs/CONTINUITY/CURRENT_DEVELOPMENT_STATUS.md` + `NEXT_ACTIONS.md`.
2. Read `.veronika/last_checkpoint.json`, `current_task.json`, `project_state.json`.
3. `git status` + `git log --oneline -10`; run `pytest tests -q` (expect baseline recorded in `TESTING_STATUS.md`).
4. Reconcile docs vs code, then continue the next untested/pending task. **Never restart the project from zero.**

## Continuity rules (binding, from the owner's Ultimate directive)

- Zero-feature-loss: never silently drop a requirement; track every feature in `COMPLETE_FEATURE_COVERAGE.md` + `docs/FEATURE_COVERAGE_MATRIX.md`.
- Checkpoint after every important task; record real test results only.
- Free-first; never silently activate paid APIs; record paid dependencies honestly.
- Owner controls git commit/push decisions; never auto-reset uncommitted work.
