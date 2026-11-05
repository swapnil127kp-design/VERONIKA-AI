# VERONIKA — MODEL SCOUT REPORT

> Phase 4 deliverable · **Live-verified: 2026-11-04** · Read-only scout: `ai/model_scout.py` · CLI: `python main.py` → `scout`

## 1. Method (honest, reproducible)

- Data below was fetched **live** from the official endpoints on 2026-11-04 — no invented links, no guessed model IDs.
- OpenRouter's catalogue is public (`https://openrouter.ai/api/v1/models`) — no key needed.
- Gemini's catalogue was fetched with the owner's configured key (`x-goog-api-key` header).
- Groq was **not checked** (no key configured) — reported honestly as `no_key`.
- Local gateways (OmniRoute `127.0.0.1:20128`, Ollama `127.0.0.1:11434`) were probed and were **offline** at scan time.
- Re-run anytime: `python main.py` → type `scout`. The scout is **read-only** (verified by test `test_scout_never_writes_config`).

## 2. Provider status at scan time (2026-11-04)

| Provider | Status | Models seen | Notes |
|---|---|---|---|
| openrouter | ✅ ok | 455 (18 free) | Public catalogue; pricing metadata per model |
| google | ✅ ok | 46 | Key configured (keyring); free tier with daily quotas |
| groq | ⚠️ no_key | — | `GROQ_API_KEY` not configured |
| omniroute | ⚠️ offline | — | Connection refused (same as Phase 0/2 audits) |
| ollama | ⚠️ offline | — | Not running |

## 3. Verified free models — OpenRouter (top by context, 2026-11-04)

| Model | Context | Vision | Tools |
|---|---|---|---|
| `stealth/crouton-alpha` | 1,048,576 | ✅ | ✅ |
| `thinkingmachines/inkling-small:free` | 1,048,576 | ✅ | ✅ |
| `thinkingmachines/inkling:free` | 1,048,576 | ✅ | ✅ |
| `google/lyria-3-pro-preview` | 1,048,576 | ✅ | ❌ |
| `nvidia/nemotron-3.5-super-vl:free` | 1,000,000 | ✅ | ✅ |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | 1,000,000 | ❌ | ✅ |
| `dots-studio/dots-3-note-preview:free` | 512,000 | ✅ | ✅ |
| `google/gemma-4-31b-it:free` | 262,144 | ✅ | ✅ |
| `cohere/north-mini-code:free` | 256,000 | ❌ | ✅ |
| `openrouter/free` | 200,000 | ✅ | ✅ |
| `liquid/lfm-2.5-2.6b:free` | 65,536 | ❌ | ✅ |

*(18 free models total; table shows the strongest candidates. Full list via `scout`.)*

## 4. Verified free models — Google Gemini (2026-11-04)

46 models support `generateContent`. Highlights:

| Model | Input token limit | Notes |
|---|---|---|
| `gemini-2.5-flash` | 1,048,576 | Fast free-tier workhorse — **recommended default for chat** |
| `gemini-2.5-pro` | 1,048,576 | Free tier with daily quota; strongest Gemini reasoning |
| `gemini-flash-latest` / `gemini-pro-latest` | 1,048,576 | Aliases that track the newest release |
| `gemini-2.5-flash-lite` | 1,048,576 | Cheapest/fastest tier |

Vision variants (image input) were detected among the 46; the scout reports per-model vision flags.

## 5. Recommendations (free-first policy)

1. **Default chat/voice:** `google/gemini-2.5-flash` (already the configured `google_model` default) — verified live, 1M context, free tier.
2. **Coding tasks:** `cohere/north-mini-code:free` or `stealth/crouton-alpha` (tools + huge context) via OpenRouter when a key is configured.
3. **Vision tasks:** any OpenRouter free model with `VIS=Y` above, or Gemini vision variants.
4. **Local-first:** bring OmniRoute online or start Ollama — both are `local` tier and always free.
5. **Paid providers (`openai`)** remain gated behind `ai.free_only=false` + owner approval.

## 6. Approval-before-activation (directive rule)

The scout **never** changes configuration. To activate a scouted model:

1. Owner picks a model from this report (or a fresh `scout` run).
2. Owner sets it explicitly: Settings → AI, or `config ai.google_model <id>` / env (`OPENROUTER_MODEL`, etc.).
3. Connection test: `python main.py` → `test <provider>` (Phase 2 harness) or just chat.

## 7. Caveats

- Free tiers change without notice (models get deprecated, quotas move). Re-run `scout` before relying on any entry.
- OpenRouter `:free` variants are rate-limited per day; the catalogue does not expose current quota numbers.
- Model IDs from local gateways remain unverified until those gateways are running.
