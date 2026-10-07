# Visual Memory — Hack Day Task Board

## How to Use This File

This task plan is optimized for a **very short hackathon build window**. Work in priority order. Do not start stretch work while a higher-priority task is still broken.

Priority levels:

- **P0 — Must work:** project cannot ship without it.
- **P1 — Strongly recommended:** materially improves the demo.
- **P2 — Stretch:** only after the MVP is stable.
- **P3 — Post-hackathon:** do not touch during the event.

---

# P0 — Core MVP

## 1. Repository Bootstrap

**Owner:** Backend / shared

- [ ] Create public GitHub repository.
- [ ] Add open-source license.
- [ ] Create frontend and backend structure.
- [ ] Add `.env.example`.
- [ ] Add initial README.
- [ ] Add setup/run commands.

**Done when:** A clean clone can install dependencies and start both apps.

---

## 2. Camera Input

**Owner:** Frontend

- [ ] Implement browser camera permission flow.
- [ ] Display live camera preview.
- [ ] Create camera ID.
- [ ] Start/stop memory session.
- [ ] Send frames to backend or processing pipeline.

**Done when:** A webcam appears reliably in the app.

---

## 3. Local CV Gate

**Owner:** Backend / CV

- [ ] Sample frames at low FPS.
- [ ] Resize frames before comparison.
- [ ] Implement basic frame difference.
- [ ] Add change threshold.
- [ ] Add cooldown.
- [ ] Confirm static scene does not trigger repeated inference.

**Done when:** The system can distinguish “mostly unchanged” from “something changed.”

---

## 4. Rolling Frame Buffer

**Owner:** Backend / CV

- [ ] Create fixed-size deque.
- [ ] Keep a few seconds of recent frames.
- [ ] Capture post-trigger frames.
- [ ] Select 3–5 representative frames for VLM.

**Done when:** A detected event produces a small contextual burst rather than one isolated frame.

---

## 5. Qwen3-VL Integration

**Owner:** AI

- [ ] Choose working inference path.
- [ ] Send one test image.
- [ ] Write the perception prompt.
- [ ] Force structured JSON.
- [ ] Validate with Pydantic.
- [ ] Handle malformed responses.
- [ ] Measure response latency.

**Done when:** A camera moment reliably produces scene, objects and events JSON.

---

## 6. Overall Scene Perception

**Owner:** AI

- [ ] Define scene schema.
- [ ] Capture `scene_type`.
- [ ] Capture `summary`.
- [ ] Capture `activity`.
- [ ] Store scene state.

**Done when:** A broad question such as “What was happening?” has usable scene context.

---

## 7. Granular Object Perception

**Owner:** AI

- [ ] Define object schema.
- [ ] Capture object names.
- [ ] Capture locations.
- [ ] Capture status.
- [ ] Add simple alias normalization.

**Done when:** Demo objects have consistent names and locations.

---

## 8. Event / Delta Extraction

**Owner:** AI + Backend

- [ ] Define event types.
- [ ] Compare new state against previous state.
- [ ] Store movement events.
- [ ] Store appearance/disappearance events.
- [ ] Avoid duplicate events.

**Done when:** Moving the ESP32 creates one useful event instead of many repeated records.

---

## 9. SQLite Memory Layer

**Owner:** Backend

- [ ] Create database.
- [ ] Create users table.
- [ ] Create cameras table.
- [ ] Create memories table.
- [ ] Create objects table.
- [ ] Create observations table.
- [ ] Create events table.
- [ ] Create evidence table.
- [ ] Add timestamp indexes.

**Done when:** Memories survive process restart.

---

## 10. Evidence Storage

**Owner:** Backend

- [ ] Save representative event frames.
- [ ] Generate deterministic evidence paths.
- [ ] Store evidence reference with memory.
- [ ] Add secure evidence retrieval.

**Done when:** Every demo event can open its associated image.

---

# P0 — Chat + Retrieval

## 11. Memory Retrieval Service

**Owner:** Backend

- [ ] Implement `search_memory()`.
- [ ] Implement `get_object_history()`.
- [ ] Implement `get_events()`.
- [ ] Implement `get_scene()`.
- [ ] Implement `get_evidence()`.

**Done when:** Each tool can be called independently from a test function/API request.

---

## 12. GPT-OSS 20B Integration

**Owner:** AI / Backend

- [ ] Configure GPT-OSS 20B provider.
- [ ] Define system prompt.
- [ ] Register memory tools.
- [ ] Parse tool calls.
- [ ] Execute tool calls server-side.
- [ ] Feed tool results back to model.
- [ ] Return final answer.

**Done when:**

```text
“Where was the ESP32 before I moved it?”
```

produces a correct historical answer from stored memory.

---

## 13. Chat UI

**Owner:** Frontend

- [ ] Message list.
- [ ] Input box.
- [ ] Send state.
- [ ] Loading state.
- [ ] Render answer.
- [ ] Render evidence action.
- [ ] Handle tool/retrieval errors gracefully.

**Done when:** The full chat interaction works without developer tools.

---

# P0 — End-to-End Integration

## 14. Full Live Memory Loop

**Owner:** Full team

- [ ] Connect camera.
- [ ] Start memory.
- [ ] Detect initial scene.
- [ ] Move ESP32.
- [ ] Capture event.
- [ ] Move phone.
- [ ] Capture event.
- [ ] Verify timeline updates.
- [ ] Query through chat.
- [ ] Open evidence.

**Done when:** The complete demo works twice in a row.

---

# P1 — Make the Demo Look Like a Product

## 15. Dashboard

**Owner:** Frontend

- [ ] Camera card.
- [ ] Live status.
- [ ] Current scene summary.
- [ ] Recent event timeline.
- [ ] Quick chat entry point.

---

## 16. Object History UI

**Owner:** Frontend

- [ ] Click object.
- [ ] Show first seen.
- [ ] Show last seen.
- [ ] Show location changes.
- [ ] Show associated evidence.

Target display:

```text
ESP32
10:41 — center of desk
10:43 — beside laptop
10:47 — right side
```

---

## 17. Evidence Viewer

**Owner:** Frontend

- [ ] Evidence thumbnail.
- [ ] Open full image.
- [ ] Show camera.
- [ ] Show timestamp.
- [ ] Show event description.

---

## 18. Memory Status UX

**Owner:** Frontend

Useful states:

```text
● Memory active
◐ Analyzing event
● Memory saved
○ Waiting for change
```

This helps judges understand what the system is doing.

---

## 19. Demo Hardening

**Owner:** Full team

- [ ] Fix camera permission edge cases.
- [ ] Fix duplicate events.
- [ ] Fix VLM JSON failures.
- [ ] Add network/API timeout handling.
- [ ] Add graceful cloud-provider failure state.
- [ ] Keep local fallback available if already working.
- [ ] Test with exact demo objects.

---

# P1 — Semantic Retrieval

## 20. Embedding Pipeline

**Owner:** AI / Backend

Only start after keyword/metadata retrieval works.

- [ ] Add Qwen3-Embedding-0.6B.
- [ ] Generate memory embeddings.
- [ ] Store/retrieve embeddings.
- [ ] Add semantic search.
- [ ] Combine semantic + metadata filters.

**Demo query:**

> “Where did I put that little development board?”

should find an ESP32 memory.

---

# P2 — Multi-Camera

## 21. Camera Management

- [ ] Multiple cameras per user.
- [ ] Camera names.
- [ ] Camera status.
- [ ] Start/stop independently.
- [ ] Camera-specific timelines.

## 22. Cross-Camera Retrieval

- [ ] Search all authorized cameras.
- [ ] Return camera name in answer.
- [ ] Return evidence from correct camera.

Example:

> “Your backpack was last seen on the living-room camera at 7:14 PM.”

---

# P2 — Phone as Camera

## 23. Mobile Browser Camera

- [ ] Mobile camera page.
- [ ] Session token.
- [ ] Stream to backend.
- [ ] Pair camera with user account.
- [ ] Show connection status on desktop.

---

# P2 — Evidence Clips

## 24. Short Event Clip Storage

- [ ] Keep a few seconds before event.
- [ ] Keep a few seconds after event.
- [ ] Store short event clip.
- [ ] Add clip playback.

This is preferable to attempting to make the entire historical video searchable.

---

# P3 — Post-Hackathon Research

These tasks are intentionally **not part of the hackathon MVP**.

## 25. Better Object Identity

- [ ] Object re-identification.
- [ ] Persistent object IDs across time.
- [ ] Cross-camera object identity.

## 26. Memory Consolidation

- [ ] Merge repeated observations.
- [ ] Maintain stable object state.
- [ ] Create higher-level summaries.
- [ ] Compress old memories.

## 27. Production Camera Support

- [ ] RTSP.
- [ ] ONVIF.
- [ ] NVR.
- [ ] IP camera discovery.

## 28. Production Data Infrastructure

- [ ] PostgreSQL.
- [ ] pgvector.
- [ ] Object storage.
- [ ] Background workers.
- [ ] Retention policies.

## 29. Advanced Temporal Reasoning

- [ ] Event chains.
- [ ] “What happened after X?” reasoning.
- [ ] Scene transition graphs.
- [ ] Long-horizon summaries.

---

# Suggested Team Split

For a two-person team:

## Person A — Perception / Backend / AI

Primary ownership:

```text
Camera ingestion
OpenCV gate
Rolling buffer
Qwen3-VL
Memory schema
SQLite
Retrieval tools
GPT-OSS 20B integration
```

## Person B — Frontend / Product / Demo

Primary ownership:

```text
React app
Camera UI
Dashboard
Timeline
Chat UI
Evidence viewer
Object history
Visual polish
Demo flow
```

Both should help with final integration and demo recording.

---

# Recommended Hack-Day Order

Follow this exact dependency chain.

```text
1. Webcam
   ↓
2. One VLM request
   ↓
3. Structured JSON
   ↓
4. Save memory
   ↓
5. OpenCV gate
   ↓
6. Event detection
   ↓
7. Retrieval tools
   ↓
8. GPT-OSS 20B chat
   ↓
9. Evidence viewer
   ↓
10. UI polish
   ↓
11. Demo video
```

Do not reverse this order.

Do not spend the first hour polishing UI before a single memory can be created and retrieved.

---

# Final Ship Checklist

## Product

- [ ] User can start memory.
- [ ] User can see the camera live.
- [ ] System creates memories automatically.
- [ ] User can chat with memory.
- [ ] System returns historical facts.
- [ ] User can open visual evidence.

## AI

- [ ] Open-weight VLM is used for visual semantics.
- [ ] GPT-OSS 20B is used for conversational reasoning.
- [ ] AI outputs are validated before persistence.
- [ ] No claim of certainty when only visual inference exists.

## Engineering

- [ ] Local CV gate limits expensive inference.
- [ ] Raw video is not blindly embedded into RAG.
- [ ] Semantic memories are indexed.
- [ ] User isolation is enforced.
- [ ] Evidence access is protected.

## Hackathon

- [ ] Public GitHub repository.
- [ ] Open-source license.
- [ ] README with architecture and setup.
- [ ] Repeatable live demo.
- [ ] Demo video <= 3 minutes.
- [ ] No unfinished feature is required for the demo.

---

# The One Rule

> **Ship the loop, not the platform.**

The winning MVP is not the one with the most camera integrations or the biggest database.

It is the one where a judge can watch an object move, ask a natural-language question about its past, and immediately see the correct remembered event and evidence.
