# Visual Memory — Backend

Backend for **Visual Memory**: it turns live camera feeds into searchable semantic
memories you can talk to. This repo is backend-owned; the frontend is a separate app
(see `docs/FRONTEND_PLAN.md`).

## Architecture (locked)

| Layer | Technology |
|---|---|
| Visual model | **Qwen3.8-27B** via Groq, model `qwen/qwen3.8-27b` |
| Chat / agent | **GPT-OSS 20B** via Groq, model `openai/gpt-oss-20b` |
| Embeddings | **Qwen3-Embedding-0.6B**, client-side (Transformers.js + ONNX + WebGPU) |
| Local gate | OpenCV frame difference (no second AI model) |
| Database | Supabase: Auth, PostgreSQL, pgvector, Storage |
| Backend | Python 3.12, FastAPI, Pydantic, OpenCV, asyncio, WebSockets |

No Ollama. No local VLM. No Firestore. No Redis/Celery/Kafka/Qdrant/Pinecone.

## Data flow

```
Browser getUserMedia -> sampled JPEG frames -> WS /ws/cameras/{camera_id}
  -> OpenCV gate (160x120 gray, frame diff, threshold, persistence, cooldown)
  -> rolling buffer -> payload (main + context + change-region crop)
  -> Groq qwen/qwen3.8-27b -> validated scene/objects/events JSON
  -> scene-state delta -> memory + evidence (Supabase Storage)
  -> browser embeds memory text (Qwen3-Embedding-0.6B) -> POST /api/memories/{id}/embedding
Chat: POST /api/chat -> gpt-oss-20b tool loop -> retrieval -> answer + evidence
```

## 1. Prerequisites

- Python 3.12+ (3.11 works; 3.13 tested)
- A Supabase project (Auth + Postgres + Storage)
- A Groq API key

## 2. Python setup

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate
pip install -r backend/requirements.txt
```

## 3. Environment variables

```bash
copy .env.example .env      # Windows
cp .env.example .env        # macOS/Linux
```

Fill in `.env`. Never expose `GROQ_API_KEY` or `SUPABASE_SERVICE_ROLE_KEY` to the
frontend.

## 4. Supabase project setup

1. Create a project at https://supabase.com.
2. Project Settings -> API: copy `Project URL`, `anon` key, `service_role` key.
3. Project Settings -> API -> JWT Settings: copy the JWT secret (for `SUPABASE_JWT_SECRET`).
4. Database -> Connection string: copy into `DATABASE_URL`.
5. Storage: the migration creates a private `evidence` bucket.

## 5. Run migrations

Run the SQL against your Supabase database (SQL editor, or a Postgres client):

```bash
# Option A: Supabase dashboard -> SQL Editor -> paste supabase/migrations/0001_init.sql -> Run
# Option B: psql
psql "$DATABASE_URL" -f supabase/migrations/0001_init.sql
```

This enables `pgvector`, creates all tables/indexes, enables RLS (own-rows policies),
and creates the private evidence bucket.

## 6. Groq configuration

Set `GROQ_API_KEY`, and (optionally) `GROQ_VLM_MODEL` / `GROQ_CHAT_MODEL`. Defaults
are already the locked models. Reasoning is disabled for the VLM
(`reasoning_effort="none"`).

## 7. Running FastAPI

```bash
make run
# or
uvicorn backend.app.main:app --reload --port 8000
```

- Health: `GET /api/health`
- OpenAPI: `http://127.0.0.1:8000/docs`

## 8. WebSocket usage

```
ws://127.0.0.1:8000/ws/cameras/{camera_id}?token=<supabase_jwt>
```

CLIENT -> SERVER

```json
{"type": "camera_connected"}
{"type": "frame", "data": "<base64 jpeg>", "ts": 1730000000000}
{"type": "stop"}
```

SERVER -> CLIENT

```json
{"type": "connection_state", "state": "connected|disconnected|error"}
{"type": "processing", "state": "idle|analyzing"}
{"type": "change_detected", "score": 0.031}
{"type": "memory_created", "memory_id": "...", "summary": "...", "events": [...]}
{"type": "error", "message": "..."}
```

Frames are never streamed back; the browser keeps its own preview.

## 9. Testing with mock VLM

The entire suite runs offline — no Groq key, no camera, no Supabase, no GPU:

```bash
pytest -q
```

This uses `MOCK_MODE` mock providers (`MockVisionProvider`, `MockChatProvider`) and an
in-memory SQLite database. It covers auth, user isolation, the gate, the rolling
buffer, VLM JSON validation, memory creation + delta, object history, hybrid retrieval,
embedding-update authorization, GPT-OSS tool execution, evidence authorization, and a
mocked end-to-end pipeline.

To run the live server in mock mode:

```bash
MOCK_MODE=true uvicorn backend.app.main:app --port 8000
```

## 10. Current limitations

- RTSP/IP/ONVIF cameras are a placeholder (`RTSPCameraSource`) — not implemented.
- No server-side embedding model (correct by design: embeddings are client-side).
- Evidence storage falls back to a local directory when Supabase is not configured.
- Single process (in-memory camera registry); no horizontal scaling yet.
- `GET /api/evidence/{id}` redirects to a signed URL (or returns metadata offline).

## 11. Future RTSP adapter

`backend/app/cameras/rtsp.py` / `RTSPCameraSource` is intentionally stubbed. Implement
`start()` / `stop()` there and register it in `build_camera_source`; the rest of the
pipeline (gate, buffer, VLM, memory) is source-agnostic.

## Repository layout

```
backend/app/
  api/         health, cameras, memories, objects, events, chat, evidence, ws
  core/        config, security (JWT), logging
  db/          models, repositories, session
  cameras/     base, browser, manager, rtsp (stub)
  perception/  gate, buffer, pipeline, image_utils
  providers/   vision, groq_qwen38, chat, groq_gptoss, mock
  memory/      schemas, service (delta), normalization, serialize
  retrieval/   service, hybrid
  agent/       service, tools, prompts
  evidence/    service
  workers/     camera_worker, embedding
supabase/migrations/
docs/FRONTEND_PLAN.md
```