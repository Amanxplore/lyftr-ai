# Lyftr AI — Full-Stack LLM Chatbot with Automatic Key Failover & Response Caching

A production-ready full-stack LLM gateway and multi-turn chatbot built with **React (Vite + TypeScript)**, **Python + FastAPI**, **LiteLLM**, and **SQLite**.

---

## 1. Live URLs

- **GitHub Repository**: https://github.com/Amanxplore/lyftr-ai
- **Frontend URL (Cloudflare Pages)**: https://lyftr-ai.pages.dev
- **Backend URL (Railway)**: https://lyftr-backend-production-3c06b20e.up.railway.app
- **Backend Health Endpoint**: https://lyftr-backend-production-3c06b20e.up.railway.app/health
- **Demo Video**: `<paste-2-to-3-minute-demo-video-url>`

---

## 2. Run locally: with Docker and without

### Prerequisites

Copy `.env.example` to `.env` and populate at least 2 API keys in `LLM_API_KEYS`:

```bash
cp .env.example .env
```

### Option A: With Docker (Recommended)

Start the entire stack (backend on `http://localhost:8000`, frontend on `http://localhost:3000`) with a single command:

```bash
make up
```

To tail logs or stop the stack without deleting the persistent SQLite volume:

```bash
make logs
make down
```

SQLite data is persisted across container restarts via the `lyftr_data` Docker named volume mounted at `/data` (`DATABASE_URL=sqlite:////data/app.db`).

### Option B: Without Docker (Local Development)

#### 1. Backend (FastAPI + LiteLLM + SQLite)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export LLM_API_KEYS="your-key-1,your-key-2"
export LLM_MODEL="gemini/gemini-3.5-flash"
export LLM_MODELS="gemini/gemini-3.5-flash,groq/qwen/qwen3.8-27b"
export DATABASE_URL="sqlite:///./data/app.db"
export ENABLE_FAILURE_SIMULATION="true"
export ALLOWED_ORIGINS="http://localhost:3000,http://127.0.0.1:3000"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. Frontend (React + Vite + TypeScript)

```bash
cd frontend
npm install
export VITE_API_URL="http://localhost:8000"
npm run dev -- --port 3000
```

#### 3. Run Backend Test Suite

```bash
make test
```

### Production Environment Variables (Names Only)

- **Railway Backend**: `LLM_API_KEYS`, `LLM_MODEL`, `LLM_MODELS`, `DATABASE_URL`, `ALLOWED_ORIGINS`, `ENABLE_FAILURE_SIMULATION`, `CACHE_ENABLED`, `CACHE_TYPE`, `PORT`, `RAILWAY_RUN_UID`
- **Cloudflare Pages Frontend (build-time)**: `VITE_API_URL`

---

## 3. Design decisions: key fallback, caching, SQLite session storage

### Automatic Key Failover (`failover_service.py` & `llm_service.py`)

- `LLM_API_KEYS` is parsed into an ordered pool (`key_1`, `key_2`, ...), paired with per-key LiteLLM models via `LLM_MODELS` (`gemini/gemini-3.5-flash` primary, `groq/qwen/qwen3.8-27b` fallback) or a shared `LLM_MODEL`.
- On each `POST /chat` request, the gateway iterates through the pool in order. Any retryable provider failure — HTTP `429` rate limits, quota errors, `5xx` upstream errors, timeouts, connection errors, or invalid/revoked key errors — increments `fallback_attempts` and immediately fails over to the next key without exposing stack traces or partial failures.
- If every configured key fails, the API returns HTTP `503` with `{"detail": "all providers unavailable"}` and writes nothing to SQLite.
- When `ENABLE_FAILURE_SIMULATION=true`, the `X-Simulate-Failure` header (`key_1=429`, `key_1=500`, `key_1=429,key_2=500`, `*=429`) injects deterministic LiteLLM exceptions per key for that request only and bypasses cache reads so failover is always testable on demand.

### Response Caching (`cache_service.py`)

- LiteLLM's built-in in-memory cache (`litellm.enable_cache(type="local")`) is initialized at startup.
- The cache key covers the LiteLLM `model` and the full conversation message list (`[system_prompt, ...history, new_user_message]`). Identical first messages across different sessions hit `LLM_CACHE`, while different prompts, histories, or system prompts miss and run `LIVE_INFERENCE`.
- Cache hits inspect `response._hidden_params["cache_hit"]`, return the identical cached `reply` and stored per-request token counts, set `key_id` to `null` and `fallback_attempts` to `0`, and resolve in tens of milliseconds instead of multi-second provider round trips.

### SQLite Session Storage (`database/connection.py` & `repository.py`)

- Session state and message history are persisted solely in SQLite (`sqlite3` with WAL mode and `busy_timeout=5000`), backed in production by a `500 MB` Railway volume mounted at `/data` (`sqlite:////data/app.db`).
- Schema is created automatically on startup (`messages` + `sessions` tables). User and assistant turns are committed atomically only after a successful completion, ensuring `422` or `503` errors never pollute history.

### Free-Tier Hosting Limitations

- **Railway**: Deployed on the trial/free tier with a `500 MB` persistent `/data` volume (free plan includes `$1/month` non-rollover usage credit after trial and sleeps after inactivity; wakes automatically on incoming requests).
- **Cloudflare Pages**: Static Vite SPA hosting with unmetered static bandwidth and `/* /index.html 200` SPA fallback via `_redirects`.
- **LLM Quotas**: Google Gemini & Groq free tiers enforce RPM/TPM/RPD limits; high traffic or large prompts can trigger `429` rate limits (automatically mitigated across providers by key failover).

---

## 4. Verification: how to see failover, cache hits and per-message token usage

### Automated Local Backend Tests

- `cd backend && .venv/bin/pytest -v`: **17 passed, 0 failed, 0 skipped**.
- `cd frontend && npm run build`: **Passed** (`tsc -b && vite build`).

### Live Production Verification (Observed Results)

1. **Frontend Reachability**: `GET https://lyftr-ai.pages.dev` -> `HTTP 200` (no auth required, bundle configured with `https://lyftr-backend-production-3c06b20e.up.railway.app`).
2. **Health & CORS**: `GET https://lyftr-backend-production-3c06b20e.up.railway.app/health` with `Origin: https://lyftr-ai.pages.dev` -> `200 {"status":"ok","keys_configured":2,"cache_enabled":true}` and `access-control-allow-origin: https://lyftr-ai.pages.dev`.
3. **Live Inference & Multi-Turn Memory**:
   - Turn 1 (`prod-a-1795590166`): `LIVE_INFERENCE`, `key_1`, `gemini/gemini-3.5-flash`, `input_tokens: 39`, `output_tokens: 105`, `latency_ms: 27641`.
   - Turn 2 (`prod-a-1795590166`): Recalled the secret code word from Turn 1 (`input_tokens: 49`, `output_tokens: 131`).
4. **Cache Hit Across Sessions**:
   - Identical first message in new session `prod-b-1795590166` -> `LLM_CACHE`, `key_id: null`, `fallback_attempts: 0`, identical `reply` and `39/105` tokens, `latency_ms: 48` (vs `27641 ms` live).
5. **Failover (`X-Simulate-Failure`)**:
   - `X-Simulate-Failure: key_1=429` -> `200`, `key_id: "key_2"`, `model: "groq/qwen/qwen3.8-27b"`, `fallback_attempts: 1`, `latency_ms: 327`.
   - `X-Simulate-Failure: *=429` -> `503 {"detail": "all providers unavailable"}`, confirmed `404` on `/sessions/{id}/messages` (not persisted).
6. **Validation & Persistence Across Restart**:
   - Whitespace message -> `422` JSON `{"detail": ...}`, not persisted.
   - Restarted Railway `lyftr-backend` container via `railway restart --yes`; after `/health` returned `200`, `GET /sessions/prod-a-1795590166/messages` returned all 4 persisted turns from `/data/app.db`.

### Quick Verification Commands

```bash
# 1. Health check
curl -s https://lyftr-backend-production-3c06b20e.up.railway.app/health

# 2. Live chat + cache check (run twice with two different session_ids)
curl -s -X POST https://lyftr-backend-production-3c06b20e.up.railway.app/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo-1","message":"What is the capital of France?"}'

# 3. Failover test hook (key_1=429 -> key_2)
curl -s -X POST https://lyftr-backend-production-3c06b20e.up.railway.app/chat \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: key_1=429" \
  -d '{"session_id":"demo-failover","message":"Say hello in one word."}'

# 4. All providers down -> 503
curl -i -s -X POST https://lyftr-backend-production-3c06b20e.up.railway.app/chat \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: *=429" \
  -d '{"session_id":"demo-fail-all","message":"Say hello"}'

# 5. Session history
curl -s https://lyftr-backend-production-3c06b20e.up.railway.app/sessions/demo-1/messages
```

---

## 5. Setup Used: your editor and AI tools

- **Editor / IDE**: VS Code / Antigravity IDE
- **AI Tools**: Gemini-powered coding assistant for architecture planning, test scaffolding, deployment automation, and contract verification.

---

## 6. Bonus features (if any): what you added beyond the requirements and why

- **Interactive Failover Test Hook Selector in the UI**: Allows selecting `key_1=429`, `key_1=500`, or `*=429` directly from the gateway sidebar to demonstrate `X-Simulate-Failure` live in the browser without needing external curl commands.
- **Per-Key Multi-Model Support (`LLM_MODELS`)**: Supports pairing different keys with different LiteLLM providers/models (Gemini primary + Groq fallback) in addition to multiple keys on a single model.
- **SQLite History Reload Button & Retry Action**: Allows querying `GET /sessions/{session_id}/messages` directly from the UI sidebar to verify SQLite persistence, and retrying failed `503` requests from error bubbles.
- **Structured JSON Logging Middleware**: Logs every request method, path, status code, and latency without ever logging API keys or secrets.
