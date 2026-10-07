# AGENTS.md — Visual Memory (backend-owned)

## Scope
- Backend only: Python, FastAPI, WebSockets, OpenCV, Pydantic, SQLite (SQLModel/SQLAlchemy).
- Do NOT write React code. `frontend/` stays an empty placeholder (teammate-owned).
- Do NOT build anything marked P2/P3 in TASK.md.

## Source of truth
- Specs: `docs/PLAN.md`, `docs/TASK.md`, `docs/IMPLEMENTATION.md`, `docs/ARCHITECTURE.md`
  (copies of the root specs; root copies are the originals).
- Where specs conflict with the build prompt, the prompt wins. Known conflicts:
  - Cloud-only Groq inference (no local models / Ollama / GPU). Docs mention local VLM first.
  - VLM `qwen/qwen3-vl-32b`, fallback `qwen/qwen3-vl-32b`; chat `openai/gpt-oss-20b`, one `GROQ_API_KEY`.
  - SQLite + local `data/evidence/`, NOT Supabase/Postgres/pgvector/Storage.
  - Seeded demo user + static token header, NOT Supabase Auth / register-login.
  - No browser Transformers.js/WebGPU embeddings; optional CPU Qwen3-Embedding-0.6B stretch only.
  - No Next.js/shadcn/FFmpeg work in this repo.

## Env vars
`GROQ_API_KEY, VLM_MODEL, VLM_FALLBACK_MODEL, LLM_MODEL`
plus gate settings from IMPLEMENTATION.md s5:
`FRAME_SAMPLE_FPS, CHANGE_THRESHOLD, EVENT_COOLDOWN_SECONDS, PRE_EVENT_SECONDS, POST_EVENT_SECONDS`
plus `DATABASE_URL, EVIDENCE_DIR, DEMO_AUTH_TOKEN, MOCK_MODE, APP_ENV`.
See `.env.example`. Keep `LLMProvider` / `VLMProvider` interfaces swappable.

## Hard rules
- Work stage-by-stage, in order; stop + show result after each stage; commit per stage; keep README accurate.
- Never add a dependency without saying why (note it in `backend/requirements.txt` + commit message).
- Every DB query takes `user_id` from the authenticated identity, never from client input.
- Agent/retrieval code never invents events: "last observed" wording, never claim certain absence.
- Validate all VLM JSON with Pydantic; retry once on malformed output (Stage 1+).
- One physical move => exactly one event (scene-state delta + cooldown).

## Layout
`backend/app/{api,camera,perception,inference,memory,retrieval,agent,storage,models}`,
`frontend/` (placeholder), `data/evidence/`, `docs/`, `scripts/`, `tests/`.

## Run
`make run` (or `uvicorn backend.app.main:app --reload --port 8000`).
Health: `GET /api/health`. OpenAPI: `/docs`.
