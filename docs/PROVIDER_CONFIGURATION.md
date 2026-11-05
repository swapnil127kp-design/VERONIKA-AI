# VERONIKA — PROVIDER CONFIGURATION

> Phase 2 deliverable · 2026-11-04 · Describes the multi-provider AI engine, routing, and the free-first policy.

## 1. Registered providers

| Provider | Key | Endpoint | Cost tier | Streaming | Vision | Model discovery |
|---|---|---|---|---|---|---|
| `openai` | OPENAI_API_KEY (keyring/env) | api.openai.com (SDK) | **paid** | ✅ SDK | ✅ (model-dependent) | hardcoded list |
| `google` | GOOGLE_API_KEY | generativelanguage.googleapis.com | **free** (free tier; paid beyond quota) | ✅ SDK + native REST SSE | ✅ | hardcoded list |
| `groq` | GROQ_API_KEY | api.groq.com/openai/v1 | **free** (free tier) | ✅ SSE | ❌ | ✅ live `/models` + fallback |
| `openrouter` | OPENROUTER_API_KEY | openrouter.ai/api/v1 | **free** (default `:free` model; paid models exist) | ✅ SSE | ❌ | ✅ live `/models` + fallback |
| `omniroute` | none (local) | `http://127.0.0.1:20128/v1` (configurable) | **local** | ✅ SSE | ❌ | ✅ live `/models` + fallback |
| `ollama` | none (local) | `http://127.0.0.1:11434/v1` (configurable) | **local** | ✅ SSE | ❌ | ✅ live `/models` + fallback |

Health checks: OpenAI-compatible providers probe `GET /models` with a 30s TTL cache. Providers without keys report `NO_API_KEY` without network calls.

## 2. Verification status (honest, 2026-11-04)

| Provider | Verified live? | Notes |
|---|---|---|
| omniroute | ❌ **OFFLINE** at audit time (connection refused) | Model IDs (`kr/qwen3-coder-next`, `agentrouter/deepseek-v4-flash`, `glm-5.3`) are owner-supplied **candidates, unverified**. Live `/models` discovery takes precedence once the gateway runs. |
| groq | ❌ no API key configured | Model list is candidate-only until a key is set; live discovery will supersede it. |
| openrouter | ❌ no API key configured | Same as above. |
| google | ⚠️ SDK now installed; no key configured | **`google-generativeai` package is deprecated (EOL)** — Google recommends `google.genai`. The native REST SSE path built in Phase 2 is the future-proof route; SDK migration is a Phase 4+ consideration. |
| openai | ❌ no API key configured | SDK-backed. |
| ollama | ❌ not running | Optional local provider; not in default routing chains. |

No provider has been verified end-to-end with real credentials yet. All streaming/discovery logic is verified via mocked-transport unit tests (`tests/test_providers.py`).

## 3. Free-first policy (directive §4.5)

- Every provider declares `cost_tier`: `free` | `local` | `paid`.
- Config `ai.free_only` (env `AI_FREE_ONLY`, default `false`): when enabled, **paid providers are never selected silently** — routing skips them and the error message tells the owner to disable free-only mode.
- Classification is static per provider for now; per-model pricing (OpenRouter `:free` suffixes, etc.) is refined in Phase 4 (Model Scout).

## 4. Routing

- `TaskRouter` classifies messages (GENERAL/CHAT/CODE/VOICE/VISION) via keyword heuristics + image presence.
- Per-task chains in `DEFAULT_ROUTING`; per-task model overrides in `DEFAULT_TASK_MODELS`.
- **Capability-aware**: VISION tasks skip providers without vision support.
- Fallback: first available provider in the chain wins; errors cascade down the chain.
- `_last_routed` reports which provider/model answered and its cost tier (`get_last_routing()`).

## 5. Usage reporting

`ProviderManager.get_usage_summary()` returns per-session totals: `requests`, `prompt_tokens`, `completion_tokens` per provider (non-stream requests include token counts where the API provides them; streams count requests).

## 6. Adding a new provider

1. Subclass `OpenAICompatibleProvider` (for OpenAI-protocol endpoints): set `name`, `provider_key`, `base_url`, `default_model`, `cost_tier`, `fallback_models`.
2. Add the provider key to `config.get_api_key` env_map (`app/config.py`) if it needs a key.
3. Register it in `ProviderManager.__init__` and (optionally) add to `DEFAULT_ROUTING`.
4. Add a connection test in `tests/test_providers.py`.

No core changes required — adapters are self-contained (directive §4.1.G).
