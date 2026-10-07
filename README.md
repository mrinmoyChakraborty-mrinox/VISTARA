# Visual Memory

> **Visual Memory turns live camera feeds into searchable memories you can talk to.**

Backend-owned repo for a one-day hackathon (Best Open-Source AI Project).
A teammate builds the frontend separately — this repo ships an empty
`frontend/` placeholder and a backend API/WS contract they build against.

## Open-weight AI (core to the project)

Both models are **open-weight, served via Groq cloud** (no local models, no GPU required):

| Role | Model | Via |
|---|---|---|
| Vision (VLM) | `qwen/qwen3-vl-32b` (fallback `qwen/qwen3-vl-32b`) | `GROQ_API_KEY` |
| Chat / reasoning + tool calling | `openai/gpt-oss-20b` | `GROQ_API_KEY` |

Provider interfaces (`LLMProvider`, `VLMProvider`) are kept so providers can be
swapped later. Stretch: Qwen3-Embedding-0.6B on CPU (not required for MVP).

## Layout

```text
backend/app/{api,camera,perception,inference,memory,retrieval,agent,storage,models}
frontend/            # empty placeholder (teammate-owned, no React code here)
data/evidence/       # saved evidence JPEGs: data/evidence/user_X/cam_Y/date/mem_Z.jpg
docs/                # spec copies (PLAN/TASK/IMPLEMENTATION/ARCHITECTURE) + API_CONTRACT (Stage 2+)
scripts/             # vlm_smoke_test.py (Stage 1), replay helpers (Stage 7)
tests/               # gate/delta/isolation tests (Stage 4+)
```

## Setup & run

Prerequisites: Python 3.12+.

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

pip install -r backend/requirements.txt
copy .env.example .env        # Windows (use `cp .env.example .env` on macOS/Linux)
# put your key in .env: GROQ_API_KEY=...
make run
# or without make:
# uvicorn backend.app.main:app --reload --port 8000
```

Verify: open `http://127.0.0.1:8000/api/health` and
`http://127.0.0.1:8000/docs` (OpenAPI for the frontend teammate).

## Architecture overview

```text
Browser camera --binary JPEG (~3fps)--> WS /ws/camera/{camera_id}
        --> OpenCV gate (160x120 gray, frame diff, threshold, cooldown)
        --> rolling buffer (3-5 frames) --> Groq VLM (JSON: scene/objects/events)
        --> alias normalization + scene-state delta (exactly one event per move)
        --> SQLite memories + evidence JPEGs
Chat: POST /api/chat --> GPT-OSS 20B tool loop
        (search_memory, get_object_history, get_events, get_scene, get_evidence)
        --> answer + optional evidence reference
```

Rules enforced throughout: `user_id` always comes from the authenticated
identity server-side (never client input); the agent never invents events —
"last observed" wording, never a claim of certain absence.

## Stages

- Stage 0 (current): bootstrap layout, config, health endpoint, one-command run.
- Stage 1: `scripts/vlm_smoke_test.py` proves the VLM JSON contract on Groq.
- Stage 2: WS + REST contract, static-token demo auth, `MOCK_MODE`, `docs/API_CONTRACT.md`.
- Stage 3+: SQLite persistence, perception pipeline, retrieval, chat agent, hardening.

P2/P3 items in TASK.md are explicitly out of scope.
