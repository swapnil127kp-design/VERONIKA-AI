# VERONIKA — SECURITY REVIEW & PLAN

> Phase 0 deliverable · 2026-11-04 · Every hazard verified in source with file:line. Feeds Phase 1 (quick wins) and Phase 8-9 (architecture-level controls).
>
> **Status update (Phase 1, 2026-11-04):** H-1 ✅ fixed (keyring-only persistence + legacy migration/scrub) · H-2 ✅ fixed (token hidden from console; Settings → General → Phone Sync exposes Show/Rotate) · H-3 ✅ fixed (empty-configured-token guard) · H-5 ✅ fixed (`x-goog-api-key` header) · H-10 ✅ addressed (numpy declared; simpleaudio documented optional). Remaining: H-4, H-6, H-7, H-8, H-9 (Phases 5-9).

## 1. Verified hazards (current code)

| ID | Severity | Hazard | Location | Fix |
|---|---|---|---|---|
| H-1 | High | Master sync token persisted plaintext in settings.json (keyring fallback) | `app/config.py:99` (default `""`), `server/auth.py:51-53, 58-59` | Keyring-only; refuse to run sync server with empty/missing token |
| H-2 | High | Master token printed to console + LAN URL advertised over unencrypted HTTP/WS | `server/sync_server.py:589, 587, 594-601` | Remove print; token shown once in secure UI; LAN binding behind explicit opt-in; WSS for networked mode |
| H-3 | High | Empty-token acceptance: `hmac.compare_digest("","")` passes if config holds `""` | `auth.py:112-115` + `config.py:99` | Reject empty configured token at startup; constant-time compare with non-empty requirement |
| H-4 | Critical (if agent-triggered) | Arbitrary PowerShell execution reachable from agent loop; `run_shell` has no directory permission check | `automation/coding_engine.py:83-90` (guard gap), `:115-117` | L3 confirmation gate for every exec action (user approval in UI), allowlisted command classes, full audit logging |
| H-5 | Medium | Gemini API key in URL query string (leaks to logs/proxies) | `ai/provider_manager.py:566` | Move to `x-goog-api-key` header |
| H-6 | Medium | `eval()` in calculate action (builtins stripped, char allowlist — acceptable but fragile) | `automation/action_registry.py:392-395` | Replace with AST-walker evaluator |
| H-7 | Medium | CDN-pinned JS loaded into desktop web context (supply chain + offline failure) | `ui/assets/orb.html:104-116` (unpkg), `:408-429` (jsdelivr) | Vendor all frontend deps locally (ULTRON app integration, Phase 6) |
| H-8 | Medium (privacy) | Audio sent to Google free STT endpoint without explicit consent gating | `voice/speech_recognition.py` | Consent prompt + local Vosk default (Phase 5) |
| H-9 | Medium | File search/listing ignores VCS ignores — can enumerate `.env`-adjacent files | `automation/file_actions.py` | Respect .gitignore + secret-file denylist in path policy |
| H-10 | Low | Undeclared optional deps (numpy, simpleaudio) silently degrade TTS playback | `requirements.txt` vs `voice/text_to_speech.py` | Declare in requirements (Phase 1) |

**Positive findings:** API keys kept out of config via keyring-first design (`config.py:269-289`); `.env` properly gitignored (`:1-4`); zero TODO/FIXME/bare-except debt; sync import is merge-only (no destructive replace, `sync_server.py:183-185`).

## 2. Permission model (to implement — directive §16.1)

| Level | Examples | Control |
|---|---|---|
| **L1 — Read-only** | read approved project files, search code, inspect logs/tasks | Allowed by default within approved roots |
| **L2 — Controlled modification** | edit/create project files, change project config | Reviewable diffs + checkpoints; per-directory approval |
| **L3 — High-impact** | delete important files, OS settings, installs, git push, external comms, arbitrary shell/python | Explicit per-action user confirmation, never auto-approved, always audited |

Rules: no personality/mode can bypass permissions; every L2/L3 action is audit-logged; high-impact remote (phone→PC) requests always require on-PC confirmation.

## 3. Emergency controls (to implement — directive §16.2)
Stop current task · disable automation · disconnect remote device · disable microphone · disable webcam · disable network sync · revoke device access. All must be one-click from tray + settings, and effective immediately.

## 4. Secrets policy
- API keys: Windows Credential Manager (keyring) only — never settings.json, never conversation memory, never logs.
- Sync tokens: keyring-only; issued device tokens stored hashed.
- `.env` remains gitignored; `.env.example` carries names only.
- Memory layer must refuse to persist anything matching secret patterns (keys/tokens/passwords).

## 5. Audit logging (to implement — Phase 9)
Append-only `audit_logs` table: timestamp, actor (local/device), action, level, target path/command, result, approval reference. Reviewable in Settings → Privacy.

## 6. Network posture
- Default: sync server binds localhost only.
- LAN access: explicit opt-in + HMAC token + (target) WSS.
- Remote/internet exposure: only via user-configured VPN/tunnel; never bind 0.0.0.0 without explicit consent flow.
