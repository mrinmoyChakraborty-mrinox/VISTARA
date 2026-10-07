# Visual Memory — Project Plan

## 1. Vision

> **Visual Memory turns live camera feeds into searchable memories you can talk to.**

Traditional cameras are excellent at recording, but poor at helping people remember. Finding a useful event often means watching footage manually or knowing the approximate date and time first.

Visual Memory creates a semantic memory layer above live camera feeds. It continuously observes authorized camera sources, converts meaningful visual observations into structured memories, and lets users retrieve those memories through natural-language chat.

The user experience is intentionally simple:

```text
Connect camera → Start Memory → camera observes → memory is created → ask a question → retrieve evidence
```

## 2. Problem

Users may have hours of footage but still struggle to answer simple questions such as:

- Where did I last see my backpack?
- When did the phone move?
- What changed while I was away?
- What was on the desk before I left?
- Which camera last saw the object?
- What happened after the package was placed on the table?

The problem is not lack of video. The problem is lack of **searchable semantic memory**.

Traditional workflow:

```text
Hours of footage
      ↓
Manual scrubbing
      ↓
Guess timestamp
      ↓
Inspect frames
      ↓
Find event
```

Visual Memory:

```text
Live camera
      ↓
Visual understanding
      ↓
Semantic memory
      ↓
Natural-language query
      ↓
Relevant event + evidence
```

## 3. Product Goals

### Primary goals

1. Accept a live camera feed from a browser/webcam for the MVP.
2. Keep visual processing efficient so the VLM is not called for every frame.
3. Extract three levels of perception:
   - Overall scene perception
   - Granular object/state perception
   - Event/delta perception
4. Store semantic memories with timestamps, camera IDs and evidence references.
5. Allow a conversational agent to search and reason over those memories.
6. Return the relevant frame/evidence for a retrieved memory.
7. Keep each user's cameras and memories isolated.
8. Use open-weight AI as an important part of the core system.

### Secondary goals

- Support multiple cameras per account.
- Support phone-as-camera through a browser.
- Add semantic/vector retrieval.
- Provide object history and event timelines.
- Make the architecture provider-agnostic.

## 4. Non-Goals for the Hack Day

Do not attempt to build the complete production platform during the event.

```text
❌ Full CCTV/NVR ecosystem
❌ Perfect object tracking
❌ Unlimited video retention
❌ Continuous VLM inference
❌ Full raw-video RAG
❌ Complex distributed infrastructure
❌ Native mobile application
❌ Facial recognition
❌ Identity tracking of people
❌ Perfect action recognition
❌ Hours-long video understanding
```

The hackathon target is a reliable single-camera end-to-end demo.

## 5. Core Product Loop

```text
Camera
  ↓
Local lightweight CV gate
  ↓
Meaningful change?
  ├── No → continue monitoring
  └── Yes
        ↓
  Rolling frame context
        ↓
  Open-weight VLM
        ↓
  Scene + objects + events
        ↓
  Semantic memory
        ↓
  Metadata + optional embeddings
        ↓
  Retrieval tools
        ↓
  GPT-OSS 20B
        ↓
  Answer + evidence
```

## 6. AI Division of Responsibilities

### Local CV gate — Gatekeeper

Use OpenCV for cheap frame-change detection and optional SSIM/perceptual comparison.

Its job is only to answer:

> **Should the expensive visual model wake up?**

It does not need to identify the object or understand the event.

### Qwen3-VL-2B-Instruct — Eyes

The VLM converts selected visual context into structured perception:

1. **Overall scene** — broad context, scene type, activity, environment.
2. **Granular state** — objects, locations, status and relationships.
3. **Events/delta** — meaningful changes relative to the previous state.

### GPT-OSS 20B — Brain / Chat

GPT-OSS 20B should not receive the entire camera history.

It should:

```text
Understand question
      ↓
Choose retrieval tool
      ↓
Retrieve relevant memories
      ↓
Reason over retrieved context
      ↓
Answer naturally
```

### Embedding model — Semantic index

Use Qwen3-Embedding-0.6B or another small open embedding model to make semantic memories searchable beyond exact keywords.

## 7. Memory Model

Every meaningful observation should be represented roughly as:

```json
{
  "user_id": "user_123",
  "camera_id": "cam_01",
  "timestamp": "2026-10-07T20:14:32",
  "scene": {
    "type": "work desk",
    "summary": "A person is working at a desk with electronics components.",
    "activity": "computer/electronics work"
  },
  "objects": [
    {
      "id": "obj_01",
      "name": "ESP32",
      "location": "center of desk",
      "status": "visible"
    }
  ],
  "events": [
    {
      "type": "object_moved",
      "object": "ESP32",
      "from": "center of desk",
      "to": "beside laptop"
    }
  ],
  "evidence": {
    "frame": "frame_184.jpg"
  }
}
```

## 8. Hierarchical Memory Strategy

Do not treat every frame as a separate permanent memory.

```text
User
 └── Camera
      └── Time range
           ├── Overall scene state
           ├── Object states
           ├── Events
           └── Evidence
```

This supports different query types efficiently:

| Query | Best memory layer |
|---|---|
| What was happening around 8 PM? | Scene perception |
| Where was my phone? | Object state/history |
| What changed? | Events/deltas |
| Show me when it happened | Evidence |

## 9. Retrieval Strategy

Use hybrid retrieval rather than pure vector search:

```text
Semantic similarity
      +
Object filter
      +
Camera filter
      +
Time/date filter
      +
Event type filter
```

Example:

> “Where was my backpack yesterday evening?”

can become:

```text
object = backpack
camera = any authorized camera
date = yesterday
time >= 17:00
sort = latest
semantic similarity = high
```

## 10. Agent Tools

GPT-OSS 20B should have a small, explicit tool surface.

### `search_memory`

Find memories by natural language and optional filters.

### `get_object_history`

Return chronological observations for an object.

### `get_events`

Return events within a time range, optionally scoped by camera or object.

### `get_scene`

Return overall scene perceptions around a requested timestamp/range.

### `get_evidence`

Return the original frame or short clip associated with a memory.

## 11. Camera Strategy

### MVP

Support browser camera input:

```text
Webcam / external USB camera
        ↓
Browser getUserMedia / WebRTC
        ↓
Backend
```

Also support a phone acting as a camera through a browser where practical.

### Future

```text
RTSP
ONVIF
IP cameras
NVR streams
Dedicated mobile app
```

Only cameras the user owns or is authorized to access should be connected.

## 12. Inference Strategy

The project should prefer local or open-weight inference but remain provider-flexible.

### VLM

- Primary architecture: Qwen3-VL family.
- Local execution is preferred for reliability and privacy.
- Cloud inference may be used for faster demos when available.

### GLLM

- Locked: **GPT-OSS 20B**.
- Primary cloud route: Groq when available.
- Architecture should allow another provider to be swapped later.

### Why event-driven inference matters

The camera can run continuously while expensive inference is conditional on meaningful scene changes.

```text
30 FPS camera
      ↓
local sampling / change detection
      ↓
most frames discarded
      ↓
selected moments
      ↓
VLM
```

## 13. Rolling Context Buffer

Maintain a tiny local frame buffer.

When a meaningful change is detected, collect:

```text
2–3 seconds before
+
trigger moment
+
~1 second after
```

Then send only the contextual burst to the VLM.

This avoids feeding the complete video history to the model while preserving temporal context.

## 14. Demo Strategy

The demo should prove the complete product loop rather than breadth.

### Recommended scene

Use a controlled workspace with 3–4 distinctive objects:

```text
ESP32
Phone
Notebook
Bottle
```

### Demonstration

1. Start camera.
2. Let initial scene perception appear.
3. Move ESP32.
4. Move phone.
5. Let the system create semantic events.
6. Open chat.
7. Ask: “Where was the ESP32 before I moved it?”
8. Ask: “What changed in the last minute?”
9. Ask: “Show me when I moved the ESP32.”
10. Display the evidence frame.

### Video target

Keep the final demo video comfortably below the 3-minute maximum, ideally around 2:15–2:40.

## 15. Success Criteria

The MVP is successful when all of these work in one run:

```text
✅ Camera connects
✅ Live preview works
✅ Local gate reduces redundant inference
✅ VLM produces structured scene/object/event data
✅ Memories are persisted
✅ Chat reaches memory tools
✅ GPT-OSS 20B answers from retrieved memories
✅ Evidence frame can be opened
✅ User/camera/memory IDs stay isolated
```

## 16. Post-Hackathon Direction

Potential upgrades:

- Multiple simultaneous cameras.
- RTSP/ONVIF integration.
- Stronger object identity tracking.
- Persistent object identity across cameras.
- Memory consolidation and deduplication.
- Better temporal reasoning.
- Configurable retention policies.
- Local-only privacy mode.
- Short evidence clips instead of single frames.
- More sophisticated semantic indexes.

## 17. Final Positioning

### One-line pitch

> **Visual Memory turns live camera feeds into searchable memories you can talk to.**

### Problem

> Cameras record everything, but finding something useful often requires manually watching footage or knowing when the event happened.

### Solution

> Visual Memory continuously converts meaningful visual observations into structured memories and lets users retrieve them conversationally.

### Technical differentiator

> **Semantic compression before retrieval:** the system does not RAG over raw video; it transforms video into scene state, object state, events and evidence first.

### AI differentiator

> **The VLM creates the memory; GPT-OSS 20B reasons over the memory.**
