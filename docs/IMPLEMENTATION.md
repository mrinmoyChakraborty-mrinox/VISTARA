# Visual Memory — Implementation Specification

## 1. Objective

Build a hackathon-ready, end-to-end MVP of Visual Memory with one reliable camera path, event-driven visual inference, semantic memory creation, hybrid retrieval, and a GPT-OSS 20B chat agent.

The implementation should prioritize:

1. Reliability of the live demo.
2. Minimum moving parts.
3. Open-weight AI as a core component.
4. Clean boundaries between perception, memory, retrieval and chat.
5. Easy replacement of inference providers.

## 2. Recommended Repository Layout

```text
visual-memory/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── lib/
│   │   └── types/
│   └── package.json
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/
│   │   ├── camera/
│   │   ├── perception/
│   │   ├── inference/
│   │   ├── memory/
│   │   ├── retrieval/
│   │   ├── agent/
│   │   ├── storage/
│   │   └── models/
│   └── requirements.txt
│
├── data/
│   ├── evidence/
│   └── app.db
│
├── docs/
├── .env.example
├── LICENSE
└── README.md
```

## 3. Technology Stack

### Frontend

- React
- Vite
- TypeScript
- Tailwind CSS
- WebRTC/browser camera APIs

### Backend

- Python
- FastAPI
- WebSockets
- OpenCV
- Pydantic
- SQLite

### AI

- **Qwen3-VL-2B-Instruct** for visual perception
- **GPT-OSS 20B** for chat, retrieval planning and reasoning
- **Qwen3-Embedding-0.6B** for semantic memory embeddings

### Optional infrastructure

- Groq for GPT-OSS 20B inference when available
- Local model runtime for VLM fallback
- PostgreSQL + pgvector later
- Object storage later

## 4. Core Runtime Flow

```text
Camera frame
   ↓
Camera manager
   ↓
Local gate
   ↓
Change candidate?
   ├── no → discard
   └── yes
         ↓
    rolling buffer
         ↓
     VLM request
         ↓
    structured JSON
         ↓
 memory normalization
         ↓
     dedup / delta
         ↓
      persistence
         ↓
   embedding/indexing
```

Chat path:

```text
User message
   ↓
GPT-OSS 20B
   ↓
Tool call
   ↓
Retriever
   ↓
Relevant memories
   ↓
GPT-OSS 20B
   ↓
Answer / evidence action
```

## 5. Configuration

Use environment variables so model providers can change without code rewrites.

```env
APP_ENV=development
DATABASE_URL=sqlite:///./data/app.db
EVIDENCE_DIR=./data/evidence

GROQ_API_KEY=
GROQ_GLLM_MODEL=openai/gpt-oss-20b

VLM_PROVIDER=local
VLM_MODEL=Qwen3-VL-2B-Instruct

EMBEDDING_MODEL=Qwen3-Embedding-0.6B

FRAME_SAMPLE_FPS=3
CHANGE_THRESHOLD=0.12
EVENT_COOLDOWN_SECONDS=8
PRE_EVENT_SECONDS=3
POST_EVENT_SECONDS=1
```

Values should be treated as starting points and tuned against the actual camera and model latency.

## 6. Data Model

### `users`

```text
id
email
created_at
```

### `cameras`

```text
id
user_id
name
source_type
source_config
created_at
last_seen_at
status
```

### `memories`

```text
id
user_id
camera_id
timestamp
scene_type
scene_summary
activity
created_at
embedding_ref
```

### `objects`

```text
id
user_id
canonical_name
created_at
last_seen_at
```

### `object_observations`

```text
id
memory_id
object_id
name_as_seen
location
status
confidence
```

### `events`

```text
id
memory_id
user_id
camera_id
timestamp
type
object_id
from_location
to_location
description
confidence
```

### `evidence`

```text
id
memory_id
path
mime_type
created_at
```

## 7. VLM Output Contract

Do not accept free-form captioning as the primary interface.

Require a strict JSON shape.

```json
{
  "scene": {
    "type": "work desk",
    "summary": "Person working at a desk with a laptop and electronics components.",
    "activity": "electronics/computer work",
    "environment": "indoor workspace"
  },
  "objects": [
    {
      "name": "ESP32",
      "location": "center of desk",
      "status": "visible",
      "confidence": 0.86
    }
  ],
  "events": [
    {
      "type": "object_moved",
      "object": "ESP32",
      "from": "center of desk",
      "to": "beside laptop",
      "confidence": 0.82
    }
  ]
}
```

The backend should validate the response with Pydantic before inserting it into memory.

## 8. Perception Gate

Start with a very simple implementation.

### Sampling

Do not process every camera frame through OpenCV at full resolution.

```python
small = cv2.resize(frame, (160, 120))
gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
```

### Basic frame difference

```python
import cv2
import numpy as np


def frame_change_score(a, b):
    diff = cv2.absdiff(a, b)
    return float(np.mean(diff)) / 255.0
```

Use this as a gate, not as the event classifier.

### Optional SSIM

If the simple difference produces too many false positives, add SSIM as a second stage.

### Cooldown

After triggering a VLM analysis:

```python
next_allowed = now + EVENT_COOLDOWN_SECONDS
```

This prevents one physical action from producing repeated VLM calls.

## 9. Rolling Frame Buffer

Maintain a deque of recent frames in memory.

```python
from collections import deque

buffer = deque(maxlen=30)
```

At 5 FPS this is roughly 6 seconds of context.

When the gate fires:

1. Capture the frames already in the buffer.
2. Capture a few frames after the trigger.
3. Select a small representative subset, e.g. 3–5 frames.
4. Send only that subset to the VLM.
5. Save one or more representative frames as evidence.

## 10. Scene-State Delta

Maintain a compact previous semantic state.

Example:

```python
previous_state = {
    "ESP32": "center of desk",
    "phone": "left of laptop",
    "notebook": "right side"
}
```

After new VLM output:

```python
current_state = {
    "ESP32": "beside laptop",
    "phone": "left of laptop",
    "notebook": "right side"
}
```

Generate the delta before writing an event.

```text
ESP32:
center of desk → beside laptop
```

This reduces duplicate semantic memories.

## 11. Memory Normalization

The VLM may call the same object different things.

Examples:

```text
ESP32
ESP development board
development board
small circuit board
```

For the MVP, use a lightweight normalization map for known demo objects.

```python
ALIASES = {
    "esp32 development board": "ESP32",
    "development board": "ESP32",
    "mobile phone": "phone"
}
```

Do not attempt sophisticated identity resolution during the hackathon.

## 12. Memory Persistence

Use SQLite for the MVP.

Recommended SQLAlchemy/SQLModel-style tables:

```text
User
Camera
Memory
Object
ObjectObservation
Event
Evidence
```

Important indexes:

```text
memories(user_id, timestamp)
events(user_id, timestamp)
events(user_id, object_id, timestamp)
memories(camera_id, timestamp)
```

## 13. Retrieval Layer

Implement retrieval as a service rather than placing database queries directly inside the chat code.

### `search_memory()`

Parameters:

```json
{
  "query": "where did I last see my backpack",
  "camera_id": null,
  "start_time": null,
  "end_time": null,
  "limit": 8
}
```

### `get_object_history()`

```json
{
  "object": "ESP32",
  "camera_id": null,
  "start_time": null,
  "end_time": null
}
```

### `get_events()`

```json
{
  "start_time": "...",
  "end_time": "...",
  "event_type": null,
  "object": null,
  "camera_id": null
}
```

### `get_scene()`

```json
{
  "timestamp": "...",
  "camera_id": "..."
}
```

### `get_evidence()`

```json
{
  "memory_id": "mem_123"
}
```

## 14. Hybrid Search

Start with metadata filtering first.

If embeddings are ready, add vector similarity.

```text
candidate set
    ↓
metadata filtering
    ↓
semantic similarity
    ↓
latest / most relevant ranking
```

This is preferable to asking the LLM to inspect every memory.

## 15. GPT-OSS 20B Agent

Use GPT-OSS 20B as a tool-using chat agent.

System prompt responsibilities:

```text
You are the reasoning layer of a visual memory system.
You do not directly observe cameras.
You must use memory tools to retrieve facts.
Do not invent visual events.
Distinguish observed facts from inference.
When evidence is requested, call get_evidence.
```

Agent flow:

```text
User question
    ↓
Decide tool
    ↓
Tool result
    ↓
Answer
```

For multi-step questions:

```text
Question
  ↓
get_object_history
  ↓
get_scene / get_events
  ↓
reason
  ↓
answer
```

## 16. Evidence Handling

Every event that matters should point to evidence.

For MVP, save representative JPEG frames.

```text
data/evidence/
  user_1/
    cam_1/
      2026-10-07/
        mem_001.jpg
        mem_002.jpg
```

Do not store entire continuous video unless required for a future version.

## 17. API Endpoints

### Auth

```text
POST /api/auth/register
POST /api/auth/login
GET  /api/auth/me
```

### Cameras

```text
GET  /api/cameras
POST /api/cameras
DELETE /api/cameras/{camera_id}
POST /api/cameras/{camera_id}/start
POST /api/cameras/{camera_id}/stop
```

### Live state

```text
WS /ws/camera/{camera_id}
GET /api/cameras/{camera_id}/state
```

### Memories

```text
GET /api/memories
GET /api/memories/{memory_id}
GET /api/objects/{object_name}/history
GET /api/events
```

### Chat

```text
POST /api/chat
```

The chat API delegates reasoning to GPT-OSS 20B and executes tool calls server-side.

## 18. Frontend Pages

### Dashboard

Show:

```text
Connected cameras
Memory status
Recent events
Quick chat
```

### Camera page

Show:

```text
Live preview
Current scene summary
Detected objects
Latest event
Memory status
```

### Memory page

Show:

```text
Timeline
Event cards
Evidence thumbnails
Filters
```

### Object history

Show:

```text
Object name
First seen
Last seen
Location timeline
Cameras seen on
Evidence
```

### Chat

Show:

```text
Conversation
Tool activity indicator (optional)
Answer
Evidence cards
```

## 19. Minimum Chat UI

The first version only needs:

```text
┌─────────────────────────────────────┐
│ Visual Memory Chat                  │
├─────────────────────────────────────┤
│ You: Where was my ESP32?            │
│                                     │
│ AI: It was last seen beside the     │
│ laptop at 12:41 PM.                 │
│                                     │
│ [View evidence]                     │
├─────────────────────────────────────┤
│ Ask your visual memory...     [→]   │
└─────────────────────────────────────┘
```

## 20. Multi-User Isolation

Every query must be scoped to the authenticated user.

Never trust `user_id` from the frontend.

Use authenticated session/token identity on the backend:

```python
memory = repo.get_memory(
    memory_id=memory_id,
    user_id=current_user.id,
)
```

Apply the same rule to:

- cameras
- memories
- objects
- events
- evidence files
- chat retrieval

## 21. Privacy Defaults

For the MVP:

- Clearly show camera status.
- Clearly show whether inference is local or cloud.
- Do not expose user evidence URLs publicly.
- Do not implement face recognition.
- Avoid demoing private/confidential content.
- Restrict CCTV support to authorized sources.

## 22. Provider Abstraction

Create an interface instead of hard-coding Groq directly into business logic.

```python
class LLMProvider:
    async def chat(self, messages, tools):
        raise NotImplementedError


class VLMProvider:
    async def analyze(self, frames):
        raise NotImplementedError
```

Then implement:

```text
GroqGPTOSSProvider
LocalGPTOSSProvider (future)
LocalQwenVLMProvider
CloudVLMProvider (future)
```

This allows inference backends to be swapped without rewriting the application.

## 23. Recommended Build Order

### Stage 1 — Prove vision

```text
webcam
 ↓
one image
 ↓
VLM
 ↓
valid JSON
```

Do not proceed until this works.

### Stage 2 — Prove semantic event creation

```text
frame A
 ↓
frame B
 ↓
VLM
 ↓
object/event JSON
```

### Stage 3 — Add local gate

```text
camera
 ↓
OpenCV change gate
 ↓
only trigger when changed
```

### Stage 4 — Persist memory

```text
VLM JSON
 ↓
SQLite
```

### Stage 5 — Retrieval tools

```text
search_memory
get_object_history
get_events
get_scene
get_evidence
```

### Stage 6 — GPT-OSS 20B chat

```text
user
 ↓
GPT-OSS
 ↓
tool
 ↓
memory
 ↓
answer
```

### Stage 7 — UI polish

Only after the complete loop works.

## 24. Demo Reliability Strategy

Use a staged scene.

Recommended objects:

```text
ESP32
phone
notebook
bottle
```

Keep the camera stationary.

Use good lighting.

Avoid visually identical objects.

Perform deliberate, visible movements.

Use a cooldown to avoid duplicate events.

Never depend on a single cloud provider for the only inference path if a local fallback is already available.

## 25. Test Cases

### Test 1 — Static scene

Expected:

```text
camera active
few or zero VLM calls
no duplicate events
```

### Test 2 — Object move

Expected:

```text
ESP32 center → laptop side
one event
one evidence frame
```

### Test 3 — Object disappearance

Expected wording:

```text
ESP32 last observed at...
```

Do not claim definite absence if it may be occluded.

### Test 4 — Chat retrieval

Question:

```text
Where was the ESP32 before I moved it?
```

Expected:

```text
historical location + timestamp
```

### Test 5 — Evidence

Question:

```text
Show me when the ESP32 moved.
```

Expected:

```text
evidence frame opens
```

### Test 6 — User isolation

User A must never retrieve User B's memories.

## 26. Stretch Features

Only attempt after the core demo is stable.

### Stretch A — Semantic embeddings

Add Qwen3-Embedding-0.6B.

### Stretch B — Object history visualization

Show a chronological object timeline.

### Stretch C — Multiple cameras

Add camera selector and cross-camera search.

### Stretch D — Mobile camera

Support phone browser as a camera source.

### Stretch E — Short evidence clips

Store a few seconds around events instead of a single frame.

## 27. Definition of Done

The hackathon MVP is complete when:

```text
[ ] Repository runs from a clean setup
[ ] Camera connects
[ ] Live preview works
[ ] Local gate runs
[ ] VLM returns validated JSON
[ ] Overall scene perception stored
[ ] Object state stored
[ ] Event/delta stored
[ ] Evidence frame stored
[ ] Memory survives process restart
[ ] GPT-OSS 20B chat works
[ ] Chat can call retrieval tools
[ ] Historical query returns correct result
[ ] Evidence button opens correct frame
[ ] User isolation is enforced
[ ] README contains setup instructions
[ ] LICENSE is present
[ ] Demo scenario is repeatable
```
