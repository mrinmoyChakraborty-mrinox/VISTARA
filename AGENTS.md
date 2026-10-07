# AGENTS.md — Visual Memory (backend-owned)

## Scope
- Backend only: Python 3.12, FastAPI, Pydantic, OpenCV, asyncio, WebSockets.
- Do NOT write React code. The frontend is a separate app; its plan lives in `docs/FRONTEND_PLAN.md`.
- Do NOT build anything marked P2/P3 in TASK.md.

## Locked architecture (ARCHITECTURE.md is source of truth for tech)
- Visual model: **Qwen3.8-27B**, Groq, `qwen/qwen3.8-27b`. NOT Qwen3-VL-2B.
- Chat/agent: **GPT-OSS 20B**, Groq, `openai/gpt-oss-20b`.
- Embeddings: **Qwen3-Embedding-0.6B**, CLIENT-SIDE (Transformers.js + ONNX + WebGPU). The
  backend only stores the 1024-dim vector the browser sends.
- Local gate: OpenCV frame difference (+ optional SSIM). No second AI model.
- Database: **Supabase** — Auth, PostgreSQL, pgvector, Storage.
- Forbidden: Ollama, Firestore, Redis, Celery, Kafka, Qdrant, Pinecone, facial recognition.

## Env vars
`SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET,
SUPABASE_EVIDENCE_BUCKET, DATABASE_URL, GROQ_API_KEY, GROQ_VLM_MODEL, GROQ_CHAT_MODEL,
FRAME_SAMPLE_FPS, CHANGE_THRESHOLD, BUFFER_SECONDS, PRE_EVENT_SECONDS, POST_EVENT_SECONDS,
COOLDOWN_SECONDS, PERSISTENCE_FRAMES, USE_SSIM, VLM_*_MAX_SIDE, GROQ_TIMEOUT_SECONDS, MOCK_MODE`.
Never log or ship `GROQ_API_KEY` / `SUPABASE_SERVICE_ROLE_KEY` to the frontend.

## Hard rules
- Work stage-by-stage; stop and show the result after each stage.
- Every DB query takes `user_id` from the authenticated identity, never client input.
- All SQL lives in `backend/app/db/repositories.py`; services call repositories, routes call services.
- Validate all VLM JSON with Pydantic; retry once on malformed output.
- One physical move => exactly one event (scene-state delta + cooldown).
- Agent/retrieval never invent events: "last observed" wording, never claim certain absence.
- Do not add a dependency without saying why (note it in `backend/requirements.txt`).
- Camera ingestion must not block on VLM inference (queue + worker).
- Tests must pass with no Groq key, no camera, no Supabase, no GPU.
- MOCK_MODE=true swaps in offline mock providers.

## Run / test
`make run` (uvicorn on :8000) · `make test` (pytest, offline). Health: `GET /api/health`.