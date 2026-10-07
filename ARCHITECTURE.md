# Visual Memory — Final Architecture

> **A searchable, conversational memory layer for live camera feeds.**
>
> **The camera sees it. Qwen3.8 understands it. Visual Memory stores it. GPT-OSS finds it.**

---

## 1. Critical Architecture Correction

The **primary visual model is NOT Ollama / Qwen3-VL-2B**.

The locked visual model is:

```text
Qwen3.8-27B
```

running through:

```text
Groq
model ID: qwen/qwen3.8-27b
```

Groq currently lists Qwen3.8-27B as a multimodal vision model with tool use and reasoning capabilities. Groq's current model catalog also lists GPT-OSS 20B separately for reasoning/function calling. citeturn683371search4turn683371search2

The locked conversational model is:

```text
GPT-OSS 20B
```

through:

```text
Groq
model ID: openai/gpt-oss-20b
```

The embedding model remains:

```text
Qwen3-Embedding-0.6B
```

running client-side in the browser with Transformers.js/WebGPU.

Therefore the core AI stack is:

```text
Qwen3.8-27B   → Visual perception / semantic memory creation
Qwen3-Embedding-0.6B → Client-side semantic indexing/search
GPT-OSS 20B  → Conversational reasoning / memory agent
```

There is **no Ollama dependency in the primary architecture**.

---

# 2. Product Definition

Visual Memory turns live camera feeds into a searchable semantic memory.

A user can connect:

- browser webcam
- external camera accessible to the browser
- phone camera through a mobile browser
- future authorized IP/CCTV/RTSP cameras
- multiple cameras under one account

Instead of manually watching hours of footage or needing to remember an exact timestamp, the system turns meaningful observations into semantic memories.

Example:

> **"Where did I last see my backpack?"**

The system retrieves:

> "Your backpack was last observed beside the sofa on Camera 2 at 7:14 PM."

The user can then ask:

> **"Show me."**

The application retrieves the associated visual evidence.

---

# 3. Fundamental Principle

Visual Memory is **not raw-video RAG**.

The system performs:

```text
RAW LIVE FEED
      ↓
LOCAL CHANGE GATE
      ↓
MEANINGFUL MOMENT
      ↓
QWEN3.8-27B VLM
      ↓
SEMANTIC MEMORY
      ↓
CLIENT-SIDE EMBEDDING
      ↓
SUPABASE + PGVECTOR
      ↓
HYBRID RETRIEVAL
      ↓
GPT-OSS 20B
      ↓
ANSWER + EVIDENCE
```

The key optimization is:

> **Semantic compression first, retrieval second.**

The application does not try to embed or send every frame of the live feed.

---

# 4. Locked Technology Stack

## Frontend

```text
Next.js
TypeScript
App Router
Tailwind CSS
shadcn/ui
Lucide
Web APIs / getUserMedia()
WebSockets
Web Worker
Transformers.js
WebGPU
```

Responsibilities:

- authentication UI
- camera connection UI
- local camera preview
- local frame sampling
- local change detection
- client-side embedding
- chat UI
- memory timeline
- evidence viewer

---

## Backend

```text
Python 3.12
FastAPI
Pydantic
OpenCV
FFmpeg
asyncio
WebSockets
```

Responsibilities:

- authenticated API
- camera session management
- receiving selected frames
- VLM orchestration
- semantic memory creation
- embedding coordination
- retrieval
- GPT-OSS agent/tool execution
- evidence management

---

# 5. AI Stack

## 5.1 Visual Model — Qwen3.8-27B

```text
Model: qwen/qwen3.8-27b
Provider: Groq
Role: visual perception
```

Qwen3.8-27B is the primary visual model in the system. Groq currently lists it under Vision and Function Calling / Tool Use, and its model catalog describes it as a multimodal model. citeturn683371search4turn683371search2

Its job is to interpret a small set of contextual frames and produce structured semantic information:

```text
1. Overall scene perception
2. Granular object/state perception
3. Event/change perception
4. Confidence
```

It is **not** the user-facing chat model.

---

## 5.2 Embedding Model — Qwen3-Embedding-0.6B

```text
Model: Qwen3-Embedding-0.6B
Runtime: Transformers.js
Execution: browser WebGPU
Role: semantic memory indexing + query embedding
```

The embedding model runs client-side.

It does not process images.

It processes semantic text generated from the VLM and user search queries.

---

## 5.3 Conversational Model — GPT-OSS 20B

```text
Model: openai/gpt-oss-20b
Provider: Groq
Role: conversational reasoning + tool use
```

GPT-OSS 20B receives the user's question and uses explicit memory tools rather than receiving the complete camera feed. Groq currently supports tool use for GPT-OSS 20B. citeturn683371search3turn683371search4

---

# 6. Responsibility Separation

```text
                        VISUAL MEMORY
                              │
            ┌─────────────────┼─────────────────┐
            │                 │                 │
            ▼                 ▼                 ▼
        PERCEPTION          INDEXING        REASONING
            │                 │                 │
      Qwen3.8-27B       Qwen3-Embedding       GPT-OSS 20B
        👁 EYES          🧭 MEMORY INDEX       🧠 BRAIN
            │                 │                 │
            ▼                 ▼                 ▼
    scene/object/event       vectors        tools + answer
```

### Qwen3.8-27B

> What did the camera see?

### Qwen3-Embedding-0.6B

> How do we find this memory later when the user describes it differently?

### GPT-OSS 20B

> What exactly is the user asking, which memory tools are needed, and how should the retrieved evidence be explained?

---

# 7. Complete Architecture

```text
                           USER ACCOUNT
                                │
                   ┌────────────┴────────────┐
                   │                         │
              CAMERA MANAGER                CHAT
                   │                         │
          ┌────────┼─────────┐               │
          ▼        ▼         ▼               ▼
      WebCam     Phone    IP/CCTV*      GPT-OSS 20B
          │        │         │               │
          └────────┼─────────┘               │
                   ▼                         │
             Camera Session                  │
                   │                         │
                   ▼                         │
          Browser Local Preview              │
                   │                         │
                   ▼                         │
          Local Frame Sampling               │
                   │                         │
                   ▼                         │
           LOCAL CHANGE GATE                 │
                   │                         │
             meaningful?                     │
              /          \                   │
            NO            YES                │
            │              │                 │
         discard      Rolling Buffer          │
                           │                  │
                           ▼                  │
                      Context Frames          │
                           │                  │
                           ▼                  │
                     Groq Qwen3.8-27B        │
                           │                  │
              ┌────────────┼────────────┐     │
              ▼            ▼            ▼     │
            Scene        Objects       Events │
              │            │            │     │
              └────────────┼────────────┘     │
                           ▼                  │
                    Semantic Memory            │
                           │                  │
             ┌─────────────┼─────────────┐    │
             ▼             ▼             ▼    │
          Metadata       Evidence     Semantic Text
             │             │             │
             │             ▼             │
             │        Supabase Storage    │
             │                           │
             │                     Browser Worker
             │                           │
             │                  Qwen3-Embedding-0.6B
             │                           │
             │                      WebGPU/local
             │                           │
             │                           ▼
             │                      vector(1024)
             │                           │
             └──────────────┬────────────┘
                            ▼
                    Supabase Postgres
                         + pgvector
                            │
                            ▼
                     HYBRID RETRIEVAL
                            │
                            └──────────────► GPT-OSS 20B
                                                │
                                 ┌──────────────┼──────────────┐
                                 ▼              ▼              ▼
                           Search Memory   Object History  Evidence
                                 │              │              │
                                 └──────────────┼──────────────┘
                                                ▼
                                          Final Answer
                                                │
                                                ▼
                                         Evidence Viewer
```

`*` IP/CCTV/RTSP support is a future adapter unless already implemented.

---

# 8. Browser-Side Camera Processing

The browser should keep the camera preview local.

```text
Camera
  ↓
getUserMedia()
  ↓
<video>
  ↓
Frame sampling
  ↓
Local change gate
```

The browser does not need to send every frame to the backend.

This reduces:

- bandwidth
- inference requests
- backend load
- unnecessary processing

---

# 9. Local Perception Gate

The gate is deliberately simple.

It answers:

> **"Should I send this moment to Qwen3.8-27B?"**

Initial techniques:

```text
frame resize
+
grayscale
+
frame difference
+
persistence check
+
optional SSIM
+
cooldown
```

Example:

```text
Camera → 30 FPS
       ↓
Local sampling → 2–5 FPS
       ↓
Scene unchanged
       ↓
No Groq call
```

When meaningful movement occurs:

```text
Scene changed
       ↓
rolling buffer
       ↓
context capture
       ↓
Qwen3.8-27B
```

The expensive model is therefore **event-driven, not frame-driven**.

---

# 10. Rolling Context

Keep a tiny rolling buffer locally.

Example:

```text
T-3
T-2
T-1
TRIGGER
T+1
T+2
```

When the local gate fires, the system uses this contextual set.

The goal is to allow the VLM to distinguish:

```text
"ESP32 is on the right"
```

from:

```text
"ESP32 moved from the center to the right."
```

without processing an entire video segment.

---

# 11. Event Cooldown

Avoid repeated inference for one physical action.

```text
ESP32 moves
   ↓
multiple changed frames
   ↓
ONE semantic event
   ↓
cooldown
   ↓
monitoring resumes
```

Example configuration:

```env
COOLDOWN_SECONDS=8
```

The value is configurable.

---

# 12. Qwen3.8-27B VLM Output

The VLM should return structured JSON.

Example:

```json
{
  "scene": {
    "type": "work desk",
    "summary": "A person is working at a desk with a laptop, phone, notebook and ESP32.",
    "activity": "Computer and electronics work.",
    "environment": "Indoor workspace."
  },

  "objects": [
    {
      "temporary_id": "obj_01",
      "name": "ESP32",
      "location": "center of desk",
      "status": "visible",
      "attributes": {
        "color": "green"
      }
    }
  ],

  "events": [
    {
      "type": "object_moved",
      "object_name": "ESP32",
      "from_location": "center of desk",
      "to_location": "beside laptop",
      "description": "ESP32 moved beside the laptop.",
      "confidence": 0.91
    }
  ]
}
```

Validate this with Pydantic before persistence.

---

# 13. Three Layers of Visual Memory

## 13.1 Overall Perception

Stores the broad state of the scene.

Example:

```text
Scene: Home workspace
Summary: Person working at desk with electronics.
Activity: Computer/electronics work
```

Useful for:

```text
"What was happening around 8 PM?"
"What did the workspace look like before I left?"
```

---

## 13.2 Granular Perception

Stores:

```text
objects
locations
states
relationships
attributes
```

Useful for:

```text
"Where was my phone?"
"What was beside the ESP32?"
```

---

## 13.3 Event / Delta Perception

Stores meaningful changes:

```text
OBJECT_APPEARED
OBJECT_DISAPPEARED
OBJECT_MOVED
OBJECT_PICKED_UP
OBJECT_PLACED
OBJECT_OPENED
OBJECT_CLOSED
SCENE_CHANGED
ACTIVITY_CHANGED
```

MVP priority:

```text
OBJECT_APPEARED
OBJECT_DISAPPEARED
OBJECT_MOVED
SCENE_CHANGED
```

---

# 14. Semantic Memory Record

A memory is not just a frame.

It contains:

```text
user_id
camera_id
timestamp

scene
objects
events
confidence

evidence_id
embedding
created_at
```

Conceptually:

```text
USER
 └── CAMERA
      └── TIMELINE
           ├── SCENE
           ├── OBJECT STATES
           ├── EVENTS
           └── EVIDENCE
```

---

# 15. Memory Creation and Embedding Flow

The memory should **not wait for embedding generation**.

```text
Camera
  ↓
Gate
  ↓
Qwen3.8-27B
  ↓
Semantic JSON
  │
  ├──────────────→ Save semantic memory
  │                     │
  │                     └→ timeline updates immediately
  │
  └──────────────→ Semantic text
                         │
                         ▼
              Browser Embedding Worker
                         │
                  Qwen3-Embedding-0.6B
                         │
                       WebGPU
                         │
                         ▼
                    vector(1024)
                         │
                         ▼
                  Supabase pgvector
```

Therefore:

> **VLM latency is on the hot path. Embedding latency is background work.**

---

# 16. Why Embeddings Are Needed

Embeddings make semantic retrieval possible when the user's wording differs from the VLM's wording.

Stored memory:

```text
"ESP32 moved from center of desk to beside laptop."
```

User:

```text
"Where did I put that little development board?"
```

Exact keyword matching may not connect these.

The embedding model represents meaning numerically:

```text
memory text
    ↓
Qwen3-Embedding-0.6B
    ↓
vector
```

The user query is embedded in the same way.

```text
query
 ↓
Qwen3-Embedding-0.6B
 ↓
query vector
```

pgvector can then locate semantically similar memories.

Important:

> **The embedding is an index, not the memory itself.**

PostgreSQL remains the source of truth.

---

# 17. Client-Side Embedding Architecture

The browser uses a Web Worker:

```text
BROWSER
│
├── Main Thread
│   ├── UI
│   ├── camera preview
│   └── chat
│
└── Web Worker
    └── Qwen3-Embedding-0.6B
            ↓
          WebGPU
            ↓
       1024-dimensional vector
```

The model is downloaded on first use and cached by the browser/site storage where supported.

The application should gracefully handle browsers without WebGPU by falling back to metadata retrieval or an optional server-side embedding adapter.

---

# 18. Hybrid Retrieval

Never use vector search alone.

Use:

```text
semantic similarity
+
object filters
+
event filters
+
camera filters
+
time filters
+
recency
```

Examples:

### Exact temporal query

> "What happened between 8:00 and 8:10?"

Use timestamp filtering.

### Exact object event

> "When did the ESP32 move?"

Use object + event metadata.

### Fuzzy query

> "Where did I put that tiny board?"

Use vector search.

### Mixed query

> "Where was my backpack yesterday evening?"

Use:

```text
user_id
+
semantic object match
+
date/time filter
+
latest timestamp
```

---

# 19. GPT-OSS 20B Agent

GPT-OSS 20B is the conversational reasoning layer.

It receives:

```text
user question
+
small set of retrieved memories
```

It does not receive the full camera footage.

The agent determines:

```text
What is the user asking?
        ↓
Which memory tool should I call?
        ↓
What memories are relevant?
        ↓
What can I reliably conclude?
        ↓
How should I answer?
```

---

# 20. Agent Tools

Create:

```text
search_memory()
get_object_history()
get_last_seen()
get_events()
get_scene()
get_memory()
get_evidence()
```

Example:

```text
USER:
"Where was the ESP32 before I moved it?"

             ↓

GPT-OSS 20B

             ↓

get_object_history("ESP32")

             ↓

Retrieval

             ↓

10:41 → center of desk
10:46 → beside laptop

             ↓

GPT-OSS 20B

             ↓

"It was in the center of the desk before you moved it."
```

---

# 21. Evidence Retrieval

When the user says:

> "Show me."

GPT-OSS can call:

```text
get_evidence(memory_id)
```

Then:

```text
memory
 ↓
evidence record
 ↓
protected storage
 ↓
authorized access
 ↓
frontend evidence viewer
```

This grounds the answer in the original visual evidence.

---

# 22. Multi-Camera Memory

Every memory is scoped to:

```text
user_id
camera_id
timestamp
```

Example:

```text
USER
├── Camera 1 → Workspace
├── Camera 2 → Living Room
├── Camera 3 → Bedroom
└── Camera 4 → Shop
```

User asks:

> "Which camera saw my backpack last?"

The retrieval layer searches only the current user's authorized cameras.

Result:

```text
Camera: Living Room
Time: 19:14:52
Object: black backpack
Location: beside sofa
```

---

# 23. Supabase Data Architecture

Use Supabase rather than Firestore for the core memory platform.

## Supabase Auth

Handles:

```text
signup
login
sessions
identity
```

## PostgreSQL

Stores:

```text
profiles
cameras
camera_sessions
memories
memory_objects
memory_events
object_history
evidence
chat_conversations
chat_messages
```

## pgvector

Stores semantic vectors:

```text
memory_id
embedding vector(1024)
```

## Supabase Storage

Stores:

```text
event frames
short evidence clips
```

---

# 24. Database Schema

## `profiles`

```text
id
display_name
created_at
```

## `cameras`

```text
id
user_id
name
type
status
config
created_at
updated_at
```

## `camera_sessions`

```text
id
user_id
camera_id
started_at
ended_at
status
```

## `memories`

```text
id
user_id
camera_id
timestamp

scene_type
scene_summary
activity
environment

embedding vector(1024)

confidence
created_at
```

## `memory_objects`

```text
id
user_id
memory_id
name
normalized_name
location
status
attributes
```

## `memory_events`

```text
id
user_id
memory_id
camera_id
timestamp

event_type
object_name
from_location
to_location
description
confidence
```

## `object_history`

```text
id
user_id
object_key
camera_id
memory_id
timestamp
location
status
```

## `evidence`

```text
id
user_id
camera_id
memory_id
timestamp
storage_path
mime_type
```

## `chat_conversations`

```text
id
user_id
title
created_at
updated_at
```

## `chat_messages`

```text
id
conversation_id
user_id
role
content
tool_calls
created_at
```

---

# 25. User Isolation

Every user-owned record contains:

```text
user_id
```

Backend identity must come from the verified authenticated session.

Never trust:

```text
client-provided user_id
```

Use Row Level Security.

Conceptually:

```text
User A
 ├── Cameras
 ├── Memories
 ├── Objects
 ├── Events
 ├── Evidence
 └── Chats

User B
 ├── Cameras
 ├── Memories
 ├── Objects
 ├── Events
 ├── Evidence
 └── Chats
```

No user should be able to query another user's visual memory.

---

# 26. Evidence Storage

Raw video is not the primary semantic database.

Store evidence separately.

MVP:

```text
event frame JPEG
```

Optional:

```text
short event clip
```

Storage example:

```text
/user_id/camera_id/events/memory_id/frame.jpg
```

or:

```text
/user_id/camera_id/events/memory_id/event.mp4
```

Evidence retrieval must be authorization checked.

---

# 27. Realtime Architecture

Use WebSockets for:

```text
camera connection state
processing state
VLM status
new memory events
errors
```

Suggested endpoint:

```text
/ws/cameras/{camera_id}
```

The browser keeps its own live preview.

The backend should not unnecessarily send the same raw video back to the browser.

---

# 28. API Surface

```text
GET    /api/health

GET    /api/cameras
POST   /api/cameras
DELETE /api/cameras/{id}

POST   /api/cameras/{id}/start
POST   /api/cameras/{id}/stop

GET    /api/memories
GET    /api/memories/{id}

GET    /api/objects/{name}/history
GET    /api/events

POST   /api/chat

GET    /api/evidence/{id}
```

All protected endpoints enforce user ownership.

---

# 29. Provider Abstractions

Do not scatter model/provider-specific code throughout the application.

Use:

```python
class VisionProvider:
    async def analyze(self, frames, previous_state=None):
        ...

class ChatProvider:
    async def chat(self, messages, tools=None):
        ...

class EmbeddingProvider:
    async def embed(self, texts):
        ...
```

Implement:

```text
VisionProvider
  └── GroqQwen38VisionProvider

ChatProvider
  └── GroqGPTOSS20Provider

EmbeddingProvider
  └── BrowserQwenEmbeddingProvider
```

This preserves the ability to add alternate inference providers later.

---

# 30. Environment Variables

```env
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=

GROQ_API_KEY=
GROQ_VLM_MODEL=qwen/qwen3.8-27b
GROQ_CHAT_MODEL=openai/gpt-oss-20b

EMBEDDING_MODEL=Qwen3-Embedding-0.6B

FRAME_SAMPLE_FPS=2
CHANGE_THRESHOLD=
BUFFER_SECONDS=3
POST_EVENT_SECONDS=2
COOLDOWN_SECONDS=8
```

Never expose:

```text
GROQ_API_KEY
SUPABASE_SERVICE_ROLE_KEY
```

to the browser.

---

# 31. Inference Cost Strategy

The visual model is the expensive/limited component.

Therefore:

```text
Camera
 ↓
LOCAL CV GATE
 ↓
NO CHANGE
 → no Groq request

CHANGE
 ↓
small contextual frame set
 ↓
Qwen3.8-27B
 ↓
semantic memory
```

The system should never create a cloud request simply because a new camera frame arrived.

The number of VLM requests should be approximately proportional to **meaningful events**, not frame count or total video duration.

---

# 32. Failure Modes

## VLM unavailable

```text
Camera remains connected
↓
local gate continues
↓
semantic processing pauses/retries
```

## Groq unavailable

```text
Existing memories remain searchable
↓
chat/VLM functionality shows degraded state
```

## WebGPU unavailable

```text
metadata retrieval remains available
↓
optional server-side embedding fallback
```

## Object disappears behind another object

Use:

```text
"last observed"
```

rather than claiming:

```text
"definitely removed"
```

---

# 33. Privacy

The system deals with camera footage and therefore must be privacy-conscious.

Principles:

```text
Authorized cameras only
       ↓
Per-user isolation
       ↓
Protected evidence
       ↓
Clear local/cloud processing status
       ↓
Configurable retention
```

MVP intentionally excludes:

```text
facial recognition
person identity tracking
```

The system should distinguish between visual observation and inference.

---

# 34. MVP

The hackathon vertical slice is:

```text
ONE BROWSER CAMERA
       ↓
LIVE PREVIEW
       ↓
LOCAL CV GATE
       ↓
ROLLING BUFFER
       ↓
GROQ QWEN3.8-27B
       ↓
SCENE + OBJECTS + EVENTS
       ↓
SUPABASE MEMORY
       ↓
CLIENT-SIDE EMBEDDING
       ↓
PGVECTOR
       ↓
GPT-OSS 20B
       ↓
TOOL-BASED RETRIEVAL
       ↓
ANSWER
       ↓
EVIDENCE FRAME
```

Controlled demo objects:

```text
ESP32
Phone
Notebook
Bottle
```

This is intentional.

The goal is one highly reliable end-to-end experience.

---

# 35. Three-Minute Demo Story

```text
0:00
Camera starts
        ↓
"Visual Memory is now watching."

0:15
Desk scene is semantically understood.

0:30
Move ESP32.

0:35
Event:
"ESP32 moved."

0:45
Move phone.

0:50
Event:
"Phone moved beside notebook."

1:00
Open chat.

1:05
"Where was the ESP32 before I moved it?"

1:10
GPT-OSS calls object history.

1:15
Answer:
"It was in the center of the desk."

1:25
"Show me."

1:30
Evidence frame appears.

1:40
"What changed in the last minute?"

1:45
AI returns multiple events.

2:00
Show semantic memory timeline.

2:15
Show architecture.

2:35
Explain:
"We don't RAG over raw video.
We semantically compress it first."

2:50
Final product statement.
```

Target final video length:

```text
~2:30–2:50
```

Keep it below the 3-minute requirement.

---

# 36. What Is Explicitly Not Part of the MVP

```text
❌ Ollama dependency
❌ Qwen3-VL-2B
❌ Raw-video RAG
❌ Full video embeddings
❌ Continuous VLM inference
❌ Full CCTV/NVR platform
❌ Native mobile app
❌ Perfect object re-identification
❌ Facial recognition
❌ Person identity tracking
❌ Redis/Celery/Kafka
❌ Separate vector database
❌ Complex multi-agent system
❌ Long-term autonomous memory consolidation
❌ Perfect action recognition
```

The VLM is **Qwen3.8-27B via Groq**.

The conversational model is **GPT-OSS 20B via Groq**.

The embedding model is **Qwen3-Embedding-0.6B client-side**.

---

# 37. Long-Term Architecture

```text
                         VISUAL MEMORY
                              │
             ┌────────────────┴─────────────────┐
             │                                  │
       Camera Gateway                     Local Gateway
             │                                  │
      RTSP / ONVIF / IP                  Browser / Phone
             │                                  │
             └────────────────┬─────────────────┘
                              │
                       Semantic Memory
                              │
             ┌────────────────┼────────────────┐
             ▼                ▼                ▼
        Scene Memory      Object Graph      Event Graph
             │                │                │
             └────────────────┼────────────────┘
                              ▼
                       Hybrid Retrieval
                              │
                              ▼
                         Agent / Chat
                              │
                              ▼
                    Evidence + Insights
```

Future:

- RTSP/IP/ONVIF
- stronger object identity resolution
- local VLM fallback
- native mobile capture
- memory consolidation
- cross-camera object trajectories
- configurable retention
- richer evidence clips
- alerts
- automated summaries

---

# 38. Final Architecture Decision Table

| Layer | Technology | Role |
|---|---|---|
| Frontend | Next.js + TypeScript | Product UI |
| Camera capture | `getUserMedia()` | Browser/phone camera |
| Local gate | OpenCV + frame diff + optional SSIM | Decide when VLM should run |
| Context buffer | Browser/backend memory buffer | Temporal context around events |
| Visual AI | **Qwen3.8-27B via Groq** | Scene/object/event semantics |
| Semantic memory | PostgreSQL | Source of truth |
| Embeddings | **Qwen3-Embedding-0.6B** | Semantic indexing/search |
| Embedding runtime | Transformers.js + WebGPU | Client-side embeddings |
| Vector search | pgvector | Similarity retrieval |
| Chat/agent | **GPT-OSS 20B via Groq** | Tool use + reasoning |
| Auth | Supabase Auth | User identity |
| Evidence | Supabase Storage | Frames/clips |
| API | FastAPI | Backend orchestration |
| Realtime | WebSockets | Camera/processing state |
| Media | FFmpeg | Future RTSP/IP processing |
| Deployment | Vercel + FastAPI host + Supabase + Groq | Infrastructure |

---

# 39. Final Mental Model

```text
┌────────────────────────────────────────────────────┐
│ 1. SEE                                             │
│ Camera → Local CV Gate → Qwen3.8-27B             │
├────────────────────────────────────────────────────┤
│ 2. REMEMBER                                        │
│ Scene + Objects + Events + Evidence               │
├────────────────────────────────────────────────────┤
│ 3. INDEX                                           │
│ Browser Qwen3 Embeddings → pgvector               │
├────────────────────────────────────────────────────┤
│ 4. RETRIEVE                                        │
│ Metadata + Temporal + Semantic Search             │
├────────────────────────────────────────────────────┤
│ 5. REASON                                          │
│ GPT-OSS 20B + Memory Tools                        │
├────────────────────────────────────────────────────┤
│ 6. PROVE                                           │
│ Timestamp + Camera + Original Visual Evidence     │
└────────────────────────────────────────────────────┘
```

## Final Product Loop

```text
THE CAMERA SAW IT
        ↓
QWEN3.8 UNDERSTOOD IT
        ↓
THE MEMORY STORED IT
        ↓
THE EMBEDDING INDEXED IT
        ↓
THE RETRIEVER FOUND IT
        ↓
GPT-OSS REASONED OVER IT
        ↓
THE USER GOT THE ANSWER
        ↓
THE SYSTEM SHOWED THE EVIDENCE
```

> # Visual Memory
>
> **Live visual world → semantic memory → conversational recall.**
