# VERONIKA — DEVELOPMENT ROADMAP

> Phase 0 deliverable · 2026-11-04 · Sequenced per the Master Directive (§23), grounded in audit findings.

**Status legend:** ✅ done · 🔄 in progress · ⬜ pending · ⛔ blocked (documented blocker)

## Phase 0 — Complete Source Code Audit ✅
- [x] ULTRON UI audited (5 files, ~1,400 LOC, MIT) — full reuse permitted; integration contract defined.
- [x] VERONIKA audited (66 files) — 205 tests verified passing (11.58s); 12 hazards catalogued.
- [x] Part 7 audited (218 files) — **Kotlin source missing entirely**; assets/models/layouts salvageable under TAMCL attribution.
- [x] Deliverables: RESOURCE_INTEGRATION_MAP.md, ARCHITECTURE.md, this roadmap, FEATURE_STATUS.md, SECURITY.md.

## Phase 1 — Core Foundation ✅ (2026-11-04)
Completed:
1. `requirements.txt`: `numpy` declared; `simpleaudio` documented as optional (no cp313 wheel — needs MSVC Build Tools; TTS degrades gracefully without it).
2. Config: `get_api_key` env_map extended to all 5 providers (openai, google, groq, openrouter, omniroute).
3. **H-3 fixed**: `verify_master_token` rejects when no master token is configured (`server/auth.py`).
4. **H-1 fixed**: master token never persisted in plaintext config; legacy tokens migrated to keyring + scrubbed; keyring-only persistence (session-only fallback with warning).
5. **H-2 fixed**: master token no longer printed to console; Settings → General → Phone Sync now provides Show Token / Rotate Token.
6. **H-5 fixed**: Gemini API key moved from URL query to `x-goog-api-key` header.
7. README drift fixed (mcp registry file, multi-provider naming, structure tree, test timing).
**Accept:** ✅ 216 tests pass (205 baseline + 11 new security tests in `tests/test_security.py`).

## Phase 2 — AI Provider System ✅ (2026-11-04)
Completed:
1. **Real token streaming everywhere** — audit's fake streaming was only in `GoogleProvider`; replaced with SDK streaming + native REST SSE (`streamGenerateContent?alt=sse`). OpenAI-compatible providers already had real SSE.
2. **Live model discovery** — all OpenAI-compatible providers fetch `GET /models` (300s cache) with hardcoded fallback candidates; health probes cached 30s.
3. **OmniRoute adapter** — health-checked (verified OFFLINE 2026-11-04; model IDs remain unverified candidates until it runs).
4. **Ollama adapter added** (optional local, not in default chains); Groq + OpenRouter wired with discovery.
5. **Free-first policy** — `cost_tier` on every provider (`free`/`local`/`paid`); `ai.free_only` / `AI_FREE_ONLY` config; paid providers never silently selected when enabled.
6. **Capability-aware routing** — VISION tasks skip non-vision providers; `capabilities()` declared on all providers.
7. **Usage reporting** — `get_usage_summary()` per-provider requests/tokens.
8. Findings: `google-generativeai` SDK was missing from the venv (installed now) and is **deprecated EOL** — REST SSE path is the future-proof route.
**Accept:** ✅ 237 tests pass (216 + 21 new provider tests in `tests/test_providers.py`, all network mocked). Docs: `docs/PROVIDER_CONFIGURATION.md`.

## Phase 3 — Personality Engine ✅ (2026-11-04)
Completed:
1. **Companion replaces Girlfriend** — new non-romantic `companion` mode (prompt explicitly forbids flirting/romantic pet names/relationship framing); `girlfriend` kept as deprecated alias everywhere (set_mode, config migration, overlay setter, legacy bridge).
2. **ULTRON de-toxified** — "kamine" and all demeaning terms removed from prompts + greetings; sarcastic "Stark/Boss/Swapnil" address retained; protective-guardian role intact.
3. **Varied greetings** — every persona AND entity now has a 5-greeting pool; `get_wake_greeting()` / `wake_greeting` property pick randomly (canonical first entry preserved for legacy consumers).
4. **Startup greeting toggle** — `persona.startup_greeting` config (default true); UI welcome message gated; mic is never activated by a greeting.
5. **Per-persona capabilities + shortcuts** — `capabilities: List[str]`, `shortcuts: Dict[str,str]` metadata on every persona; exposed via `get_available_modes()`.
6. Mode-switch contract enforced: `set_mode()` writes ONLY `persona.mode` (verified by test capturing every config write).
**Accept:** ✅ 269 tests pass (237 + 32 new persona/entity tests). Voice profiles verified: FRIDAY=Aria, Companion=Ava +10Hz, ULTRON=Christopher −40Hz + `ultron` DSP.
FRIDAY (default, cyan #00D2FF) · Supportive Companion (pink #FF007F, non-romantic per directive §6.2) · ULTRON (crimson #FF1A1A, sarcastic + original robotic DSP voice).
Mode switch changes voice/prompt/theme/greeting only. Greeting toggle (no silent mic activation). Rebuild entity/persona entanglement cleanly.

## Phase 4 — Model Scout ✅ (2026-11-04)
Completed:
1. `ai/model_scout.py` — read-only live catalogue scout: OpenRouter public `/models` (455 models, pricing/modality/tools metadata), Gemini `/models` (46 models, key from keyring), Groq (honest `no_key`), local gateways (honest `offline`).
2. Free-first recommendation report with verification date + exact source endpoint per entry (no invented links).
3. CLI command `scout` in `main.py`; **never writes config** (approval-before-activation enforced + tested).
4. `docs/MODEL_SCOUT.md` with live-verified data (18 free OpenRouter models incl. 1M-context vision+tools; Gemini 2.5 Flash/Pro free tier).
**Accept:** ✅ 280 tests pass (269 + 11 scout tests, network mocked; live scan run manually 2026-11-04).

## Phase 5 — Voice Engine ⬜
1. **Complete `microphone.py` recording pipeline** (currently device-listing only — biggest voice gap).
2. STT: local Vosk option using Part 7's bundled US-English model binaries (`voice/` desktop via `vosk` pip) + privacy-gated cloud STT; Hindi/Hinglish support evaluation.
3. TTS per-persona profiles; speech interruption (barge-in); optional wake word (fix dead keyring path `wake_word.py:59`); visible mic status + stop control.

## Phase 6 — Three.js UI Integration ⬜
1. Vendor ULTRON Next.js app into `ui/assets/ultron`; add `output: "export"`; embed via QWebEngineView (serve `out/` over local HTTP, not file://).
2. Extend `OrbSceneApi` with `setEnergy/setColors/setMode` (<50 LOC per audit).
3. Replace hand-rolled `ultron_bridge.py` WS with maintained lib; implement §2.3 event contract.
4. State machine wiring (orb reacts to real mic/AI/task states); persona themes; audio-reactivity (FFT amplitude only, no raw audio).
5. Performance: visibility-pause, reduced-motion, sprite-budget tuning (~1,700 draw calls today).
**Accept:** orb state changes verifiably driven by backend events; works offline (no CDN).

## Phase 7 — Memory Engine ⬜
Add categories: user profile / project / task / preference / session memory on top of existing 6-table schema; relevant-context retrieval + summarization (no full-history stuffing); memory search/edit/delete UI; project registration with real paths; "what were we working on" queries.

## Phase 8 — Coding & Automation ⬜
Terminal manager + python runner (streaming stdout/stderr, timeouts, cancel); git manager (status/diff/commit/pull/push w/ approval); coding agent with **self-correction loop** (error → diagnose → patch → re-test, retry limit, checkpoints); task orchestrator (INSPECT→…→REPORT with UI progress + cancellation); L1/L2/L3 permission enforcement (SECURITY.md).

## Phase 9 — Backend & Auth ⬜
FastAPI hardening; user accounts + device registration; full REST surface per directive §15.1; WSS for networked mode (0.0.0.0 only behind explicit opt-in + protections); audit logs; extended DB schema.

## Phase 10 — Android Companion ⬜ **(NEW BUILD — Part 7 has no source)**
New Kotlin project reusing: orb.html + three.min.js, HUD bridge contract, Liquid-Glass theme tokens, layouts (de-branded), Vosk model binaries, x-vector biometrics model. Implement: login/device auth, shared memory client, text+voice chat, notifications/reminders, remote PC task requests (risk-gated), offline queue. Attribution per TAMCL.

## Phase 11 — Cross-Device Integration ⬜
PC↔phone sync verification (conversation continuity, memory consistency, task history); offline queue + retry without duplicates; conflict resolution; device revocation.

## Phase 12 — Vision & Gesture ⬜
Vision agent (screenshot/image analysis with permission + no-auto-upload); OCR only when needed; MediaPipe gestures with locally bundled wasm/model (CDN dependency eliminated), camera-active indicator, manual disable.

## Phase 13 — Advanced Multi-Agent Workflows ⬜
Coordinator-driven decomposition, minimum-useful agent selection, independent reviewer passes, parallel execution where useful, progress monitoring, usage limits, recovery.

## Phase 14 — Final Hardening ⬜
Integration + security testing, performance profiling, installer/verification, recovery testing, full docs set (SETUP, API_REFERENCE, ANDROID_SETUP, PROVIDER_CONFIGURATION).

## Standing rules (from directive §26)
Inspect before changing · no silent paid usage · no fake UI/progress · verify before claiming · incremental changes · update docs with every feature change · keep 205-test baseline green.
