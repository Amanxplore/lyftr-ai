# Lyftr AI — Full-Stack LLM Chatbot with Automatic Key Failover & Response Caching

A production-ready full-stack LLM gateway and multi-turn chatbot built with **React (Vite + TypeScript)**, **Python + FastAPI**, **LiteLLM**, and **SQLite**.

---

## 1. Live URLs

- **Frontend URL**: `<deploy-to-vercel-netlify-or-render-and-paste-url>`
- **Backend URL**: `<deploy-to-render-railway-or-fly-and-paste-url>`
- **Demo Video**: `<paste-2-to-3-minute-demo-video-url>`

> Note: Ensure `ENABLE_FAILURE_SIMULATION=true` and `ALLOWED_ORIGINS=<your-frontend-url>` are set on the deployed backend, and `VITE_API_URL=<your-backend-url>` is set when building the deployed frontend.

---

## 2. Run locally: with Docker and without

### Prerequisites

- Copy `.env.example` to `.env` and populate at least 2 API keys in `LLM_API_KEYS`:

```bash
cp .env.example .env
```

### Option A: With Docker (Recommended)

Start the entire stack (backend on `http://localhost:8000`, frontend on `http://localhost:3000`) with a single command:

```bash
make up
```

To tail logs or stop the stack:

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
export LLM_MODEL="gemini/gemini-2.0-flash"
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
cd backend
.venv/bin/pytest -v
```

---

## 3. Design decisions: key fallback, caching, SQLite session storage

### Automatic Key Failover (`failover_service.py` & `llm_service.py`)

- `LLM_API_KEYS` is parsed into an ordered pool (`key_1`, `key_2`, ...), optionally paired with per-key models via `LLM_MODELS` (or a shared `LLM_MODEL`).
- On each `POST /chat` request, the gateway iterates through the pool in order. Any retryable provider failure — HTTP `429` rate limits, quota errors, `5xx` upstream errors, timeouts, connection errors, or invalid/revoked key errors — increments `fallback_attempts` and immediately fails over to the next key without exposing stack traces or partial failures to the caller.
- If every configured key fails, the API returns HTTP `503` with `{"detail": "all providers unavailable"}` and **writes nothing** to SQLite.
- When `ENABLE_FAILURE_SIMULATION=true`, the `X-Simulate-Failure` header (`key_1=429`, `key_1=500`, `*=429`, etc.) injects deterministic LiteLLM exceptions per key for that single request. Requests with active failure simulation bypass the cache read path (`no-cache`) so failover behavior can always be demonstrated cleanly on demand.

### Response Caching (`cache_service.py`)

- LiteLLM's built-in cache (`litellm.Cache`, configurable as in-memory `local` or `disk`) is initialized at application startup.
- The cache key covers the LiteLLM `model` and the full conversation message list (`[system_prompt, ...history, new_user_message]`). Therefore:
  - Sending the same first message across two different sessions produces `LLM_CACHE` on the second request.
  - Sending a different message, different history, or a different `system_prompt` misses the cache and triggers `LIVE_INFERENCE`.
- Cache hits inspect `response._hidden_params["cache_hit"]`, return the identical cached `reply` and stored per-request token counts, set `key_id` to `null` and `fallback_attempts` to `0`, and resolve in a fraction of a live API call.

### SQLite Session Storage (`database/connection.py` & `repository.py`)

- Session state and message history are persisted solely in SQLite (`sqlite3` with WAL mode and `busy_timeout=5000`), with schema auto-created on startup:
  - `messages (id, session_id, role, content, metadata, created_at)` indexed by `(session_id, id)`
  - `sessions (session_id, system_prompt, created_at, updated_at)` so per-session system prompt overrides persist across turns without ever leaking system prompts into `GET /sessions/{session_id}/messages`.
- User and assistant messages are written together inside a single transaction **only after** LiteLLM returns a valid response, ensuring failed `422` or `503` requests never pollute session history.

---

## 4. Verification: how to see failover, cache hits and per-message token usage

### 1. Health Check

```bash
curl -s http://localhost:8000/health | jq
# {"status":"ok","keys_configured":2,"cache_enabled":true}
```

### 2. Live Inference & Per-Message Token Usage

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo-1","message":"What is the capital of France?"}' | jq
```

Expect `"resolution_source": "LIVE_INFERENCE"`, `"key_id": "key_1"`, `"fallback_attempts": 0`, and per-request `input_tokens` / `output_tokens`.

### 3. Cache Hit Across Sessions

Send the exact same first message in a new session (`demo-2`):

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo-2","message":"What is the capital of France?"}' | jq
```

Expect `"resolution_source": "LLM_CACHE"`, `"key_id": null`, `"fallback_attempts": 0`, identical `reply`, and significantly lower `latency_ms`.

### 4. Automatic Failover with `X-Simulate-Failure`

```bash
# Key 1 returns 429 -> automatic failover to key_2
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: key_1=429" \
  -d '{"session_id":"demo-failover","message":"Say hello in one word."}' | jq

# All keys fail -> clean 503 and nothing added to history
curl -i -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: *=429" \
  -d '{"session_id":"demo-fail-all","message":"Say hello"}'
```

### 5. Multi-Turn History Endpoint

```bash
curl -s http://localhost:8000/sessions/demo-1/messages | jq
```

Returns oldest-first `user` and `assistant` messages without the system prompt.

---

## 5. Setup Used: your editor and AI tools

- **Editor / IDE**: VS Code / Antigravity IDE
- **AI Tools**: Gemini-powered coding assistant for architecture planning, test scaffolding, and contract verification.

---

## 6. Bonus features (if any): what you added beyond the requirements and why

- **Interactive Failover Test Hook Selector in the UI**: Allows selecting `key_1=429`, `key_1=500`, or `*=429` directly from the gateway sidebar to demonstrate `X-Simulate-Failure` live in the browser without needing external curl commands.
- **Per-Key Multi-Model Support (`LLM_MODELS`)**: Supports pairing different keys with different LiteLLM providers/models (e.g., Gemini primary + Groq/OpenAI fallback) in addition to multiple keys on a single model.
- **SQLite History Reload Button**: Allows querying `GET /sessions/{session_id}/messages` directly from the UI sidebar to visually verify persistence in SQLite.
- **Structured JSON Logging Middleware**: Logs every request method, path, status code, and latency without ever logging API keys or secrets.
