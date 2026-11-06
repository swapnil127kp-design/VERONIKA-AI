# RESOURCE INTEGRATION MAP — VERONIKA

> Phase 0 deliverable. Every row is grounded in an actual audit with file:line evidence.
> Last updated: 2026-11-06. **Status: ULTRON ✓, VERONIKA ✓, Part 7 ✓, MYRAA △ (partial — new owner-supplied resource, deep audit pending).**

## 1. Source Projects

| # | Project | Path | License | Reuse stance |
|---|---|---|---|---|
| A | VERONIKA (existing, partially built) | `C:\Users\Swapnil\OneDrive\Desktop\claude code\VERONIKA` | MIT (author: Swapnil Kumar) | Primary codebase — extend, don't rewrite |
| B | JARVIS Part 7 (YouTube playlist source) | `C:\Users\Swapnil\OneDrive\Desktop\claude code\jarvis\Playlist-main\Playlist-main\Part 7` | **TAMCL v1.0** (Tech GPTx / Rehaan, © 2026) — reuse/sale permitted **with preserved attribution**; media-shoutout clause only triggers if VERONIKA media references this codebase | ⚠️ **Pattern reference + asset salvage with attribution** — see headline finding below |
| C | ULTRON 3D UI | `C:\Users\Swapnil\OneDrive\Desktop\claude code\ultron` | **MIT © 2026 Swapnil Kumar** (`LICENSE`, 1,070 B) | Full reuse permitted |
| D | MYRAA V2 (desktop assistant + native Android port) | `C:\Users\Swapnil\OneDrive\Desktop\claude code\MYRAA MOBILE\mayra android` (`MYRAA PC_` folder is currently EMPTY) | `LICENSE` present, contents not yet verified | Pending deep audit — Android-native provider networking, Keystore auth, STT+TTS, PWA/HUD; see §5 |

## 2. ULTRON UI — verified findings (audit complete)

### 2.1 Framework facts
- Next.js **16.2.10** App Router + React 19.2.7 + **three.js 0.185.1** (`package.json:11-17`).
- **Raw three.js — no react-three-fiber, no drei, no framer-motion, no zustand** (repo-wide grep: zero matches).
- 5 source files, ~1,400 LOC total: `lib/orbScene.ts` (858 LOC), `lib/handTracker.ts` (271), `components/JarvisOrb.tsx` (176), `app/layout.tsx` (25), `app/page.tsx` (5).
- **No lights, no textures** — all additive `LineBasicMaterial`/`PointsMaterial`/`SpriteMaterial`; procedural canvas textures only.
- Postprocessing: `EffectComposer` → `UnrealBloomPass` (strength 1.8) → custom GLSL chromatic-aberration + amber grade pass (`orbScene.ts:39-86`).

### 2.2 Integration map — ULTRON rows

| Requirement | Source | Existing component | Target module | Action | Evidence |
|---|---|---|---|---|---|
| 3D Orb | ULTRON | `lib/orbScene.ts` → `createOrbScene(container): OrbSceneApi` | `ui/assets/ultron` (Next.js app embedded in desktop shell) | **Reuse as-is** + extend API with `setEnergy/setColors/setMode` (<50 LOC) | `orbScene.ts:8-17, 23, 850-857`; dispose at `:829-848` |
| HUD chrome | ULTRON | `components/JarvisOrb.tsx:108-174` + `app/globals.css` | Same | **Adapt** — extend `MODE_LABEL` map, add chat/state/task panels | `JarvisOrb.tsx:9-13` |
| Keyboard/mouse input | ULTRON | keydown handler + `OrbitControls` | Same | **Reuse as-is** | `JarvisOrb.tsx:81-104`; `orbScene.ts:89-95` |
| Gesture control | ULTRON | `lib/handTracker.ts` (MediaPipe `@mediapipe/tasks-vision 0.10.35`, pinch → spin/zoom) | `vision/` + HUD | **Adapt** — bundle wasm/model locally or disable; `G` toggle already isolates it | `handTracker.ts:7-10, 96-104`; toggle `JarvisOrb.tsx:96-98` |
| App shell / page | ULTRON | `app/layout.tsx`, `app/page.tsx`, `next.config.ts` | embedded UI | **Reuse as-is** + add `output: "export"` for QWebEngineView | `next.config.ts:3-5` (currently empty) |
| Theme colors | ULTRON | Hardcoded **amber** constants `C_BRIGHT 0xffaa30 …` + CSS `#ffaa30` | Persona theming | **Adapt** — replace constants via `setColors`; NOTE: palette is amber, **not** cyan/red | `orbScene.ts:98-102`; `globals.css:77,98` |
| Audio reactivity | — | **Does not exist** (no AnalyserNode/FFT anywhere) | `ui/ultron_bridge.py` | **Build new** | verified negative grep |
| WebSocket bridge | — | **Does not exist** (zero HTTP/WS calls in frontend) | `ui/ultron_bridge.py` | **Build new** — contract below | verified negative grep |

### 2.3 Backend→UI event contract (the seam to build)

Nothing in the frontend consumes backend events yet. Minimal contract to implement:

| Event | Payload | Drives |
|---|---|---|
| `orb.rotate` | `{dx, dy}` | `OrbSceneApi.rotateBy` (`orbScene.ts:660-673`) |
| `orb.zoom` | `{factor}` | `zoomBy` (`:675-684`) |
| `orb.reset` | `{}` | `resetView` (`:686-691`) |
| `assistant.state` | `{mode: "idle"\|"listening"\|"thinking"\|"speaking"\|..., energy?}` | surge block `:728-745`, `bloom.strength` `:806`, `MODE_LABEL` |
| `assistant.text` | `{lines: string[]}` | text sprites `:412-521` |
| `assistant.color` | `{bright, mid, dim, hot}` | constants `:98-102` (materials are per-`lineMat` → swap is easy) |

### 2.4 Known risks / gaps (verified)
1. **No static-export config** — must add `output: "export"` to `next.config.ts:3` before QWebEngineView embedding (app is 100% client-rendered, so export is safe).
2. **MediaPipe CDN dependency** (`cdn.jsdelivr.net` wasm + `storage.googleapis.com` model, `handTracker.ts:7-10`) — breaks offline unless bundled locally.
3. **Perf debt**: ~1,700 individual sprite draw calls (1,200 text sprites at `:484-489`), 250 debris meshes, 2,000-point dust; RAF runs unconditionally (`:701-815`) — no visibility pause, no reduced-motion mode. Needs a performance profile for modest laptops.
4. No tests, no lint, no CI (`package.json:6-10` has only dev/build/start).
5. `docs/screenshot.png` (3.16 MB) is repo bloat — harmless.

## 3. VERONIKA existing codebase — verified findings (audit complete)

Full audit: 66 source/config/test files inspected, all claims file:line-cited. Git repo, zero TODO/FIXME, MIT © 2026 Swapnil Kumar.

### 3.1 Integration map — VERONIKA rows

| Requirement | Existing component | Action | Evidence |
|---|---|---|---|
| Provider abstraction + routing | `ai/provider_base.py` + `ai/provider_manager.py` (TaskRouter `:53-89`, fallback `:681-736`) | **Reuse as-is**; port fake streaming → real token streaming | streaming is simulated (`:644-660`: blocking call + word-split + `sleep(0.01)`) |
| MCP client | `mcp/mcp_client.py` (stdio `:121-267`, HTTP `:274-506`, manager `:401-`) | **Reuse as-is**; extract config loader into the registry module README promises | `load_servers_from_config` `:389-398`; `mcp_server_registry.py` does NOT exist (README.md:88 drift) |
| ReAct agent loop | `mcp/rea_bridge.py:206-350` | **Reuse** — generalize action-source injection | think→act→observe, iteration caps |
| Swarm multi-agent | `ai/swarm_coordinator.py:94-164` | **Reuse** — ThreadPoolExecutor fan-out/fan-in | dependency-free |
| Action bus + permissions | `automation/action_registry.py` (30+ actions) + `permissions.py` | **Reuse pattern**; re-audit exec actions (§3.3) | dynamic `mcp__*` namespacing |
| Memory schema | `memory/database.py:50-126` (WAL, 6 tables) + `repositories.py` | **Reuse as-is** — schema is the rebuild's data contract | conversations, memories, reminders, preferences, entities, personas |
| Self-upgrade | `app/self_upgrade.py` (backup→validate→run→rollback) | **Reuse** | 323 LOC |
| TTS + ULTRON DSP | `voice/text_to_speech.py` (edge-tts → SAPI5 → pydub DSP → 5-tier playback) | **Reuse**; declare `numpy`/`simpleaudio` in requirements | 385 LOC |
| STT | `voice/speech_recognition.py` (Google Web Speech API) | **Adapt** — privacy gating required (audio leaves machine) | §3.3-9 |
| Microphone | `voice/microphone.py` — **device listing only, no recording** | **Complete/rewrite** — `_is_recording` never True (`:16,66`) | voice chain ~60% wired |
| Wake word | `voice/wake_word.py` (Porcupine, demo keyword) | **Adapt** — keyring key never written (`:59`); env fallback `:62` | partial |
| 3D orb (current) | `ui/assets/orb.html` — single-file Three.js 0.160.0 via unpkg + WS client to `:8766` | **Replace** with ULTRON Next.js app (§2) — there is NO Next.js app in ui/assets, only this HTML | `orb.html:104-116`, MediaPipe 0.10.14 `:408-429` |
| Orb bridge | `ui/ultron_bridge.py` — hand-rolled RFC6455 WS (:8766) + HTTP (:3000), events state/mode/color/audio/greeting | **Replace** with maintained WS lib; align events with §2.3 contract | 676 LOC stdlib |
| Persona/entity system | `ai/persona_manager.py` (278) + `ai/entity_manager.py` (442) | **Salvage concepts, rewrite** — entangled with bridge | modes: veronika/friday/ultron + overlays |
| Chat UI | `ui/chat_panel.py` — plain QLabel bubbles | **Improve** — no markdown/code rendering | 169 LOC |
| Settings UI | `ui/settings_window.py:156` — provider combo only `["openai","google"]` | **Improve** — expose all 5 providers | manager supports openai/google/groq/openrouter/omniroute |
| Exam predictor | `ai/exam_predictor.py` (310) | **Reuse** — self-contained | actions `predict_exam`, `add_past_question` |
| Workflow engine | `automation/workflow_engine.py` | **Fix** — `self._step_timeout` assigned `:104`, never read (dead config) | hung step blocks workflow |
| Sync server | `server/sync_server.py` (FastAPI :8765, WS /ws/chat + /ws/live) | **Reuse + harden** | see §3.3-1/2 |

### 3.2 Test baseline — VERIFIED 2026-11-04

**`pytest tests -q` → 205 passed in 11.58s** (README claim confirmed). Coverage is backend-only across 14 files; `conftest.py` has no fixtures; no UI/voice/server tests despite `pytest-qt`/`pytest-asyncio` declared. Git tree clean except untracked `docs/`.

### 3.4 Provider endpoint baseline — VERIFIED 2026-11-04

**OmniRoute `http://127.0.0.1:20128/v1` → OFFLINE** (connection refused at audit time). Consequence for Phase 2: OmniRoute adapter must be built against the OpenAI-compatible interface with a health-check + graceful "endpoint offline" state; model identifiers (`kr/qwen3-coder-next`, etc.) remain unverified until the service is running. Never assume these models exist.

### 3.3 Security hazards (ranked, file:line)

1. **Arbitrary PowerShell/Python exec reachable from agent loop** — `coding_engine.py:83-90,126-133`; `run_shell` lacks directory permission check. Critical without user-confirmation gate.
2. **Master sync token printed to console** (`sync_server.py:589`) + LAN URL advertised (`:587,594-601`) over unencrypted HTTP/WS.
3. **Empty-token acceptance risk** — `auth.py:112-115` + default `""` (`config.py:99`): `hmac.compare_digest("","")` passes.
4. **Plaintext token fallback in settings.json** — `auth.py:51-53`, `:58-59`.
5. **Gemini API key in URL query** — `provider_manager.py:566` → move to `x-goog-api-key` header.
6. **CDN-pinned JS in desktop app** — `orb.html:104-116` (unpkg), `:408-429` (jsdelivr) — offline failure + supply-chain surface.
7. **File search ignores VCS ignores** — `file_actions.py` can enumerate `.env`-adjacent files.
8. Positive: keys kept out of config via keyring-first (`config.py:269-289`); extend env_map (`:284-287`) to all providers.

## 4. JARVIS Part 7 — verified findings (audit complete)

### ⚠️ HEADLINE FINDING — read before planning Android work
**The entire Kotlin application source is MISSING from all 7 parts.** Every part contains exactly 1 `.kt` file (`JarvisApp.kt`, which imports 12+ nonexistent classes) and 9 completely empty package dirs (`audio, automation, background, data, network, security, ui, util, vision` — verified twice via independent methods). File counts grow (Part 1=39 → Part 7=218) but only resources grow: layouts, drawables, HTML/JS assets, ML model binaries, gradle configs. **Nothing in this project can compile.** The Android companion must be built as a NEW project using salvaged assets + documented patterns — not by porting code.

### 4.1 What IS salvageable (218 files in Part 7, all verified)

| Requirement | Existing component | Target module | Action | Evidence |
|---|---|---|---|---|
| Offline STT model | Vosk 0.3.x US-English model binaries (~71 MB: `am\final.mdl` 16MB, `graph\Gr.fst` 24MB, `graph\HCLr.fst` 22MB, ivector) | `voice/speech_to_text.py` (desktop: `vosk` pip pkg accepts same models) + Android assets | **Adapt** — binaries complete; wiring must be rebuilt | `Part 7\app\src\main\assets\model-en-us\` |
| Voice biometrics (owner gate) | Kaldi x-vector speaker model (`final.ext.raw` 14.9MB + transform/mean/mfcc) + full enrollment UX spec (3 samples, cosine threshold 0.50, Strict/Balanced/Relaxed) | `security/voice_auth` + Android enrollment | **Adapt** — model reusable, matching code rebuild | `assets\model-spk\`; `activity_voice_enrollment.xml:143-376` |
| 3D orb (mobile) | Self-contained `orb.html` + bundled `three.min.js` (603KB) with `applyTheme`/`setOrbState`/`setExternalAudio` APIs | Android companion WebView | **Reuse** (with TAMCL attribution) | `orb.html:184,248,262` |
| HUD "Arc Core" | Full-screen HUD with clean `JarvisBridge` JS contract (onOrbClicked/onMicClicked/onPowerClicked/onScreenShareClicked/onHistoryClicked/onSettingsClicked) | Android companion | **Reuse/Adapt** | `hud\index.html:816-856` |
| Liquid-Glass theme system | 29 theme tokens + glow drawables (dark/light/red/sunset) | Android UI | **Reuse** — pure XML, drop-in | `res\values\attrs.xml:4-29` |
| Layouts (20) | home/chat/memory/persona/permission/enrollment screens | Android UI | **Adapt** — remove hardcoded "Rehaan" (`fragment_home.xml:81`) | `res\layout\` |
| 17 overlay avatars + picker | SVG avatar toys + gallery | Android UI | **Adapt** — all fetch React from esm.sh at runtime; must vendor for offline | `assets\overlay-toys\gallery.html:26-33` |
| Two-tier voice design | Architecture doc: cheap on-device wake standby → open Live only after wake; 16kHz PCM @20ms; 2-min silence → standby; foreground service types for Android 14+ | `voice/` + Android services | **Pattern-only** (doc is excellent, code absent) | `docs\architecture\voice-architecture-research.md:5-25` |
| Command catalog | WhatsApp/YouTube/phone-hardware/memory command list | `automation/` | **Pattern-only** | `activity_hands_free.xml:447-528` |
| Permission onboarding UX | Per-permission rationale screen + GRANT ALL | Android UI | **Adapt** | `activity_permission.xml:136-437` |
| Settings payload pattern | Single settings payload (userName, persona, voice, permissions) | Identity model | **Pattern-only** — store name, never hardcode | `settings.html:956-970` |
| Kotlin logic (ALL) | `JarvisApp.kt` references 12+ missing classes; CommandExecutor, memory DAOs, Gemini client, accessibility service — all gone | — | **Rebuild** (fatal gap) | `JarvisApp.kt:4-22` |

### 4.2 License compliance requirements (TAMCL v1.0, `ROOT\LICENSE`)
1. Preserve copyright + permission notice in any copied/forked portion (`:35-38`).
2. Do NOT remove "Tech GPTx" attribution from copied code/manifests/UI credits/docs.
3. Media shoutout clause triggers only if VERONIKA-related media references this codebase (`:11-30`).
4. Record: any salvaged asset (orb.html, three.min.js, Vosk models are third-party Alpha Cephei © 2020 / David Snyder — check their own licenses separately before shipping).

### 4.3 Broken/absent items verified
- No compilable source in any part; `activity_main.xml:271` references nonexistent `CurvedDockLineView`.
- Model radio labels ("gemini-3.8-live", "gemini-3.1-flash") don't match real Google model IDs (`activity_api_connection.xml:270-304`).
- Weather widget has no provider/key/code anywhere — UI shell only.
- "Embedded release API key" claim is false advertising — no key exists (good).
- Voice-videos docs reference 3 mp4s that don't exist; no audio assets at all.

## 5. MYRAA V2 — new owner-supplied resource (top-level audit 2026-11-06, deep audit pending)

Supplied by the owner 2026-11-06 alongside an empty `MYRAA PC_` folder and build artifacts (`MYRAA-Mobile-1.0.0-rc.5-private.apk`, instrumentation logs, `SHA256.json`). Top-level findings — verified only to the depth listed:

1. **Identity:** MYRAA is a separate desktop AI assistant with a modular real-time 3D anime (PMX/MMD) character system — Electron/React/Three.js on Windows, with a documented **native Android companion** that runs provider networking, Keystore-based auth, speech recognition and TTS **standalone** (no Windows PC required). Source: `README.md:1-17`.
2. **Architecture split (relevant to VERONIKA cross-device work):** Android uses the same PMX character runtime with native lifecycle, provider networking, Keystore credential storage, STT/TTS — this is the most relevant existing implementation VERONIKA has for the Android companion requirement that Part 7 cannot provide (Part 7 Kotlin source is missing, §4 headline finding).
3. **Structure:** `agent/`, `android/`, `electron/`, `voice/`, `memory/`, `cognition/`, `companion/`, `settings/`, `permissions/`, `presence/`, `native/`, TypeScript servers (`server.ts`, `server_memory.ts`, `server_screenVision.ts`) + Vite builds (`vite.mobile.config.ts`) — 52 top-level entries.
4. **Docs bundle:** `MYRAA-V2-PROGRESS.md`, `MYRAA-V2-TEST-REPORT.md`, `MYRAA-V2-RELEASE-CHECKLIST.md`, `docs/GOOGLE-KEY-TROUBLESHOOTING.md`, `docs/V2-BUILD.md`, `docs/V2-MODELS.md` — useful as a pattern reference for VERONIKA's own continuity/testing ledger system.
5. **Build artifacts present but NOT executed:** RC5 APK + `android-actions-*.log` — never install/run resource binaries; APK analysis (if requested) belongs to the REA/packaging track.
6. **Reuse stance:** *pending* until (a) `LICENSE` and `THIRD-PARTY-NOTICES.md` are read, (b) `android/` networking/Keystore/STT modules are inspected, (c) PMX character runtime (third-party MMD ecosystem — redistribution rights explicitly limited per `README.md:17`) is separated from provider/voice/memory code that can be adapted.
7. **Action:** schedule MYRAA deep audit (Android modules first, license second) in the next planning pass; update this map only after file-level inspection. Do not copy anything from MYRAA until license compliance is verified.

## 6. Resource extraction rules (standing)

1. Never execute unknown scripts from resource folders.
2. Record origin of every reused component in this file.
3. If a license does not permit direct reuse → learn the pattern, implement independently.
4. Verify claimed features by reading the actual source before recording them here.
