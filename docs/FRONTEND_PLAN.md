# Visual Memory — Frontend Plan

Implementation-ready plan for the browser client of **Visual Memory**. This document is
frontend-only: it does not change, extend, or redesign any backend contract. Every REST
endpoint, WebSocket message, and TypeScript interface below is **frozen** and must be
consumed exactly as specified.

Stack: **Next.js (App Router) + TypeScript + Tailwind CSS + shadcn/ui + Lucide**,
**Web APIs (`getUserMedia`)**, **WebSockets**, **Web Worker**, **Transformers.js + ONNX +
WebGPU**.

---

## 1. Scope and Ground Rules

- The frontend is the browser client only. It talks to a Python FastAPI backend over REST
  and WebSockets.
- The client never sends `user_id`. Identity is derived server-side from the bearer token.
- The client never computes embeddings on the main thread. All embeddings happen in a Web
  Worker.
- The client never sends every camera frame. Only sampled, gated, downscaled JPEG frames
  are sent over the WebSocket.
- No raw video is uploaded or downloaded for the MVP. Evidence is a single authorized JPEG
  fetched by ID.

### 1.1 Frontend responsibilities

| Responsibility | Where it lives |
|---|---|
| Auth UI + session handling | Supabase JS client, `AuthProvider` |
| Camera connect + live preview | `/cameras`, `useCamera` |
| Frame sampling (~2 FPS) + downscale | `frameSampler` worker/module |
| Local change gate | `changeGate` module |
| WebSocket transport to backend | `useCameraSocket` |
| Client-side embedding | `embedding.worker.ts` |
| Memory timeline + detail | `/memory`, `/objects/[name]` |
| Evidence viewer | `EvidenceViewer` |
| Chat UI + tool surfacing | `/chat`, `ChatProvider` |
| Global status + processing state | `StatusBar` |

---

## 2. Frozen Backend Contracts

These are reproduced exactly as frozen. The frontend must conform to them; it must not
propose alternatives.

### 2.1 Authentication

- Supabase Auth via the **JS client** (`@supabase/supabase-js`).
- The client attaches `Authorization: Bearer <supabase_access_token>` to every protected
  backend REST request and passes the JWT in the WebSocket query string.
- The backend derives `user_id` server-side. The client never sends `user_id`.
- `GET /api/health` is public; all other REST routes require the bearer token.

### 2.2 REST endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/health` | Public | Backend liveness/readiness |
| GET | `/api/cameras` | Bearer | List the current user's cameras |
| POST | `/api/cameras` | Bearer | Create a camera record |
| DELETE | `/api/cameras/{id}` | Bearer | Delete a camera |
| POST | `/api/cameras/{id}/start` | Bearer | Start a camera session |
| POST | `/api/cameras/{id}/stop` | Bearer | Stop a camera session |
| GET | `/api/memories` | Bearer | List/search memories |
| GET | `/api/memories/{id}` | Bearer | One memory with objects/events/evidence |
| POST | `/api/memories/{id}/embedding` | Bearer | Upload a client-computed vector |
| GET | `/api/objects/{name}/history` | Bearer | Chronological history for an object |
| GET | `/api/events` | Bearer | List events (filterable) |
| GET | `/api/evidence/{id}` | Bearer | Returns authorized/signed image |
| POST | `/api/chat` | Bearer | Ask the agent a question |

`POST /api/chat` request body:

```json
{ "conversation_id": "optional-string", "message": "required-string" }
```

`POST /api/chat` response:

```json
{
  "conversation_id": "string",
  "answer": "string",
  "evidence": [],
  "tool_calls": []
}
```

> Note on `GET /api/evidence/{id}`: it returns an authorized/signed image. The client must
> fetch it with the bearer token via `fetch()` and render the response as a blob URL; it
> must not use a bare `<img src>` against a protected route unless the backend returns a
> signed URL in `Evidence.url`.

### 2.3 WebSocket endpoint

```
/ws/cameras/{camera_id}?token=<jwt>
```

Client to server messages:

| Message | Shape |
|---|---|
| camera_connected | `{ "type": "camera_connected" }` |
| frame | `{ "type": "frame", "data": "<base64 jpeg>", "ts": <ms> }` |
| stop | `{ "type": "stop" }` |

Server to client messages:

| Message | Shape |
|---|---|
| connection_state | `{ "type": "connection_state", "state": "connected\|disconnected\|error" }` |
| processing | `{ "type": "processing", "state": "idle\|analyzing" }` |
| change_detected | `{ "type": "change_detected", "score": <number> }` |
| memory_created | `{ "type": "memory_created", "memory": <Memory> }` |
| error | `{ "type": "error", "message": <string> }` |

### 2.4 Agent tools the chat surfaces

`search_memory`, `get_object_history`, `get_last_seen`, `get_events`, `get_scene`,
`get_memory`, `get_evidence`.

The UI renders these from `ChatMessage.tool_calls` / the chat response `tool_calls`. The UI
does not invoke tools directly; it only displays them and links their results to evidence.

---

## 3. Environment Variables and Secrets

Frontend (browser-exposed; all prefixed `NEXT_PUBLIC_`):

```env
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_BACKEND_URL=
NEXT_PUBLIC_WS_URL=
```

**Never expose to the browser:**

```
GROQ_API_KEY
SUPABASE_SERVICE_ROLE_KEY
```

These are server-only secrets. They must never appear in any `NEXT_PUBLIC_*` variable, any
client bundle, any log, or any commit. All Groq inference and all privileged Supabase
access happen behind the FastAPI backend. The browser holds only the Supabase anon key and
the user's access token.

| Variable | Used for |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase JS client init (auth only) |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase JS client init (auth only) |
| `NEXT_PUBLIC_BACKEND_URL` | Base URL for all REST calls |
| `NEXT_PUBLIC_WS_URL` | Base URL for WebSocket (`ws://` or `wss://`) |

---

## 4. TypeScript Domain Types (verbatim)

These interfaces are frozen. Document them exactly as written; do not rename fields.

```ts
type CameraStatus = "idle" | "active" | "disconnected" | "error";
interface Camera { id: string; user_id: string; name: string; source_type: "browser" | "rtsp"; status: CameraStatus; config: Record<string, unknown>; created_at: string; updated_at: string; last_seen_at: string | null; }
type CameraSessionStatus = "started" | "stopped" | "error";
interface CameraSession { id: string; camera_id: string; user_id: string; started_at: string; ended_at: string | null; status: CameraSessionStatus; }
interface Scene { type: string; summary: string; activity: string; environment: string; }
interface MemoryObject { id: string; memory_id: string; name: string; normalized_name: string; location: string; status: string; attributes: Record<string, unknown>; }
interface MemoryEvent { id: string; memory_id: string; camera_id: string; timestamp: string; event_type: string; object_name: string; from_location: string; to_location: string; description: string; confidence: number; }
interface Evidence { id: string; memory_id: string; camera_id: string; timestamp: string; storage_path: string; mime_type: string; url?: string; }
interface Memory { id: string; camera_id: string; timestamp: string; scene: Scene; objects: MemoryObject[]; events: MemoryEvent[]; confidence: number; evidence_id: string | null; created_at: string; }
interface ChatMessage { id: string; conversation_id: string; role: "user" | "assistant" | "tool"; content: string; tool_calls: ToolResult[] | null; created_at: string; }
interface ToolResult { tool: string; args: Record<string, unknown>; result: unknown; }
```

Place these in `src/types/domain.ts`. Do not add required fields.

### 4.1 Client-only helper types

These are frontend-internal, not backend contracts.

```ts
type WsConnectionState = "connecting" | "connected" | "disconnected" | "error";
type ProcessingState = "idle" | "analyzing";
type LocalGateState = "idle" | "buffering" | "triggered" | "cooldown";

interface LocalChangeResult { changed: boolean; score: number; }
type WebGpuSupport = "webgpu" | "wasm" | "unsupported";
```

---

## 5. Application Architecture

### 5.1 Route structure (App Router)

```
src/app/
  layout.tsx                 root layout (fonts, ThemeProvider, AuthProvider, Toaster)
  page.tsx                   /            marketing/landing
  (auth)/
    login/page.tsx           /login
    signup/page.tsx          /signup
  (app)/
    layout.tsx               authenticated shell (sidebar, topbar, StatusBar)
    dashboard/page.tsx       /dashboard
    cameras/page.tsx         /cameras
    memory/page.tsx          /memory
    objects/[name]/page.tsx  /objects/[name]   Object History
    chat/page.tsx            /chat
    settings/page.tsx        /settings
  api/                       (no backend routes; optional auth callback only)
```

A route group `(app)` guards all authenticated pages: if there is no Supabase session,
redirect to `/login` and preserve the intended path.

### 5.2 Providers and shared state

| Provider | Responsibility |
|---|---|
| `AuthProvider` | Supabase session, user, `accessToken`, `signIn`, `signUp`, `signOut`, `onAuthStateChange` |
| `ApiProvider` (hook-based) | Authenticated `fetch` wrapper that injects the bearer token |
| `CameraProvider` | Active camera, WebSocket lifecycle, live processing state, latest `Memory` |
| `ChatProvider` | Conversations, messages, streaming/loading, tool call log |
| `ThemeProvider` | shadcn theme (light/dark) |
| `Toaster` | shadcn toast notifications |

### 5.3 Suggested source layout

```
src/
  app/                (routes above)
  components/
    ui/               shadcn primitives
    layout/           AppSidebar, Topbar, StatusBar, ProcessingIndicator
    camera/           CameraPreview, CameraCard, ChangeScoreGauge, FrameStats
    memory/           MemoryTimeline, MemoryCard, MemoryDetail, ObjectChip
    chat/             ChatPanel, MessageBubble, ToolCallList, EvidenceStrip
    evidence/         EvidenceViewer, EvidenceThumbnail
    objects/          ObjectTimeline, LocationChangeList, LastObservedCard
  lib/
    supabaseClient.ts
    apiClient.ts
    wsClient.ts
    embeddingClient.ts
    frameSampler.ts
    changeGate.ts
    format.ts         (time, duration, confidence formatting)
  workers/
    embedding.worker.ts
    frameSampler.worker.ts
  hooks/
    useAuth.ts useCameras.ts useCameraSocket.ts useMemories.ts
    useObjectHistory.ts useEvents.ts useChat.ts useEmbedding.ts useLocalGate.ts
  types/
    domain.ts         (verbatim interfaces)
    ws.ts
```

---

## 6. Authentication Flow

1. `AuthProvider` initializes `createClient(NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY)`.
2. On mount it calls `supabase.auth.getSession()` and subscribes to `onAuthStateChange`.
3. The access token is stored in memory and mirrored from the session. It is attached as
   `Authorization: Bearer <token>` on every protected request.
4. `/login` and `/signup` use `signInWithPassword` and `signUp`.
5. `signOut()` clears the session and redirects to `/`.
6. The `(app)` layout redirects unauthenticated users to `/login?next=<path>`.
7. The WebSocket URL appends `?token=<jwt>`. If the token rotates, reconnect the socket.
8. On backend `401`, attempt `supabase.auth.refreshSession()` once, then retry; if it still
   fails, sign out and redirect to `/login`.

The client never calls Supabase database or storage APIs directly for memories, cameras,
evidence, or chat. Supabase JS is used for **auth only**.

---

## 7. API Client Conventions

`src/lib/apiClient.ts` exposes typed wrappers around `fetch`:

```ts
async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = await getAccessToken();
  const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) throw await toApiError(res);
  return res.json() as Promise<T>;
}
```

Rules:

- Every protected call goes through `apiFetch`. Never hand-roll headers in a component.
- Query parameters are built with `URLSearchParams`; never send `user_id`.
- Evidence images use a dedicated `fetchEvidenceBlob(id)` helper (see §11.6).
- Errors normalize to `{ status, code?, message }` for consistent UI handling.

### 7.1 Endpoint usage map

| Client function | Endpoint | Used by |
|---|---|---|
| `getHealth()` | `GET /api/health` | `StatusBar`, `/settings` |
| `listCameras()` | `GET /api/cameras` | `/cameras`, `/dashboard`, `/settings` |
| `createCamera(body)` | `POST /api/cameras` | `/cameras` |
| `deleteCamera(id)` | `DELETE /api/cameras/{id}` | `/cameras`, `/settings` |
| `startCamera(id)` | `POST /api/cameras/{id}/start` | `/cameras` |
| `stopCamera(id)` | `POST /api/cameras/{id}/stop` | `/cameras` |
| `listMemories(params)` | `GET /api/memories` | `/memory`, `/dashboard` |
| `getMemory(id)` | `GET /api/memories/{id}` | `/memory` detail, `/chat` evidence |
| `postEmbedding(id, vector)` | `POST /api/memories/{id}/embedding` | embedding worker result |
| `getObjectHistory(name, params)` | `GET /api/objects/{name}/history` | `/objects/[name]`, `/memory` object view |
| `listEvents(params)` | `GET /api/events` | `/memory`, `/dashboard` |
| `fetchEvidence(id)` | `GET /api/evidence/{id}` | `EvidenceViewer` |
| `postChat(body)` | `POST /api/chat` | `/chat` |

Because the exact query parameters of `GET /api/memories` and `GET /api/events` are not
part of the frozen surface, the frontend must treat them as optional filters and remain
functional when only `GET` with no params is supported. Filtering must also be possible
client-side over the returned list for the MVP.

---

## 8. WebSocket Client Contract

`src/hooks/useCameraSocket.ts` owns exactly one socket per active camera.

Lifecycle:

1. Caller supplies `cameraId`.
2. Build URL: `${NEXT_PUBLIC_WS_URL}/ws/cameras/${cameraId}?token=${jwt}`.
3. On `open`, send `{ type: "camera_connected" }`.
4. Send `{ type: "frame", data, ts }` for each gated, sampled frame.
5. On stop, send `{ type: "stop" }` then close.
6. Reconnect with exponential backoff (1s, 2s, 4s, capped 15s), max 5 attempts, when the
   socket closes unexpectedly and the camera is still meant to be active.

Server message handling:

| Incoming `type` | UI effect |
|---|---|
| `connection_state` | Update `WsConnectionState`; show badge in `StatusBar` |
| `processing` | Toggle `ProcessingIndicator` (`idle` / `analyzing`) |
| `change_detected` | Update `ChangeScoreGauge` with `score` |
| `memory_created` | Prepend `memory` to timeline; toast "Memory created"; invalidate memories query |
| `error` | Toast error; set camera card error state; keep socket open unless fatal |

Base64 frames are encoded with `canvas.toDataURL("image/jpeg", quality)` and stripped of the
data URL prefix before sending (`data.split(",")[1]`).

---

## 9. Camera Capture, Frame Sampling, and Local Gate

### 9.1 Frame sampling strategy

- Target sampling rate: **~2 FPS** (one frame every ~500 ms). Configurable in `/settings`.
- Capture source: `<video>` fed by `getUserMedia({ video: true, audio: false })`.
- Downscale so the **maximum side is ~1024 px**, preserving aspect ratio, before encoding.
- Encode as **JPEG base64** (`image/jpeg`, quality ~0.7).
- Do not send a frame when the local gate decides nothing changed.
- Never send more than the configured FPS regardless of camera frame rate.

```ts
// lib/frameSampler.ts (conceptual)
function sample(video: HTMLVideoElement, maxSide = 1024): string {
  const scale = Math.min(1, maxSide / Math.max(video.videoWidth, video.videoHeight));
  const w = Math.round(video.videoWidth * scale);
  const h = Math.round(video.videoHeight * scale);
  const canvas = new OffscreenCanvas(w, h);
  const ctx = canvas.getContext("2d")!;
  ctx.drawImage(video, 0, 0, w, h);
  return canvas.convertToBlob({ type: "image/jpeg", quality: 0.7 })
    .then(blobToBase64);
}
```

### 9.2 Local change gate

The gate decides whether a sampled frame is worth sending. It runs in the browser
(optionally in `frameSampler.worker.ts`), never on the backend.

Pipeline: downscale to a small grayscale thumbnail, compare against the previous thumbnail
(mean absolute difference), apply a persistence check over consecutive samples, then a
cooldown.

State machine:

```
idle -> buffering (change rising) -> triggered (change confirmed) -> cooldown (fixed window) -> idle
```

| Parameter | Default | Meaning |
|---|---|---|
| `sampleFps` | 2 | Sampling rate |
| `changeThreshold` | configurable | Minimum normalized diff to count as change |
| `persistenceFrames` | 2 | Consecutive changed samples before trigger |
| `cooldownSeconds` | 8 | Suppress re-trigger after an event |

The gate mirrors the backend's own gate conceptually but is not authoritative: the backend
runs its own OpenCV change gate. Sending a frame that the backend's gate rejects is
harmless; the client gate exists to reduce bandwidth and unnecessary uploads.

> Important: the backend remains the source of truth for gate decisions. The client gate is
> a bandwidth optimization. Do not assume client and server thresholds match.

### 9.3 Camera states

Use `CameraStatus` exactly: `idle`, `active`, `disconnected`, `error`. Map:

| Camera UX state | `CameraStatus` |
|---|---|
| Created, not started | `idle` |
| Streaming locally, socket connected | `active` |
| Socket closed unexpectedly | `disconnected` |
| Permission denied / backend error | `error` |

The raw `Camera.status` comes from the backend. The client overlays live socket state
without writing back a conflicting status.

---

## 10. Client-Side Embedding Worker

### 10.1 Model and runtime

| Property | Value |
|---|---|
| Model | **Qwen3-Embedding-0.6B** |
| Runtime | **Transformers.js** (`@huggingface/transformers`) |
| Backend | **ONNX Runtime Web** |
| Acceleration | **WebGPU** when available, **WASM** fallback |
| Output dimension | **1024** |
| Execution | **Web Worker** (never the main thread) |

### 10.2 Worker protocol

`src/workers/embedding.worker.ts` receives:

```ts
type EmbedRequest = { id: string; type: "embed"; text: string; memoryId: string };
type EmbedResponse =
  | { id: string; type: "result"; memoryId: string; vector: number[]; dims: number }
  | { id: string; type: "progress"; progress: number; file: string }
  | { id: string; type: "error"; memoryId?: string; message: string }
  | { id: string; type: "capability"; support: WebGpuSupport };
```

### 10.3 Lifecycle and fallback

1. On `embedding.worker.ts` init, detect capability:
   `navigator.gpu` present and `requestAdapter()` succeeds -> `webgpu`; else `wasm`; else
   `unsupported`.
2. Load the model once (`pipeline("feature-extraction", "Qwen/Qwen3-Embedding-0.6B", { device })`).
   Report `progress` events so the UI can show first-load progress.
3. WebGPU failure at runtime (adapter lost, OOM) -> transparently re-init with WASM and
   report a `capability` downgrade. The UI shows "Embedding running on CPU (WebGPU
   unavailable)".
4. If `unsupported` (no WASM worker path), skip client embedding and degrade to metadata
   retrieval. Never block memory creation or chat on embeddings.

### 10.4 Producing and uploading a vector

- Source text: a semantic string composed from the memory, e.g.
  `${scene.summary} | ${objects.map(o => `${o.name} at ${o.location}`).join("; ")} | ${events.map(e => e.description).join("; ")}`.
- The worker embeds the text to a 1024-dim vector.
- The main thread reads `memory_created.memory.id` and calls
  `POST /api/memories/{id}/embedding` with the vector through `apiFetch`.
- Embedding upload is **background work**. Memory display must not wait for it. Show a
  subtle "Indexing" pill on the memory card that clears when the POST resolves.

Suggested upload body (frontend proposes, backend owns the final schema):

```json
{ "embedding": [/* 1024 numbers */], "dims": 1024 }
```

If the backend rejects the body shape, this is the only place the frontend adapts; memory
creation and chat still work without embeddings.

---

## 11. Pages

All authenticated pages render inside the `(app)` shell with a persistent `StatusBar`
showing: backend health, WebSocket connection state, and global processing state.

### 11.1 `/` — Landing

- **Purpose:** Explain the product in one screen; route to login/signup; if authenticated,
  offer "Open dashboard".
- **Main components:** `Hero`, `HowItWorks` (See -> Remember -> Index -> Retrieve -> Reason
  -> Prove), `LocalVsCloudExplainer` (§13), `FeatureGrid`, `CTAButtons`, `Footer`.
- **Data needed:** none from the backend. Optionally `GET /api/health` for a live badge.
- **API endpoints:** `GET /api/health` (optional).
- **WebSocket events:** none.
- **Loading states:** health badge skeleton.
- **Empty states:** n/a.
- **Error states:** health badge shows "Backend unreachable" without blocking the page.
- **User actions:** Log in, Create account, Open dashboard.
- **Relationships:** links to `/login`, `/signup`, `/dashboard`.

### 11.2 `/login` — Log in

- **Purpose:** Authenticate via Supabase.
- **Main components:** `LoginForm` (email, password), `OAuthButtons` (optional), `FormError`.
- **Data needed:** none from backend.
- **API endpoints:** none (Supabase Auth only).
- **WebSocket events:** none.
- **Loading states:** submit button spinner, disable form during request.
- **Empty states:** n/a.
- **Error states:** invalid credentials, unconfirmed email, network error; inline form alert.
- **User actions:** submit credentials, go to signup, reset password (optional link).
- **Relationships:** on success redirect to `/dashboard` (or `?next=`); links to `/signup`.

### 11.3 `/signup` — Sign up

- **Purpose:** Create a Supabase account.
- **Main components:** `SignupForm` (email, password, confirm), `EmailConfirmationNotice`.
- **Data needed:** none from backend.
- **API endpoints:** none (Supabase Auth only).
- **WebSocket events:** none.
- **Loading states:** submit spinner; post-signup "check your email" state.
- **Empty states:** n/a.
- **Error states:** weak password, email exists, rate limit; inline alert.
- **User actions:** submit signup, go to login.
- **Relationships:** success -> confirmation message then `/login` or `/dashboard` if
  confirmation is disabled.

### 11.4 `/dashboard` — Overview

- **Purpose:** At-a-glance summary and entry point to monitoring and memory.
- **Main components:** `CameraSummary` (count by status), `RecentMemories` (last ~5),
  `RecentEvents` (last ~5), `ProcessingIndicator`, `QuickAsk` (input that routes to
  `/chat` with a prefilled question), `StatusBar`.
- **Data needed:** cameras, recent memories, recent events.
- **API endpoints:** `GET /api/cameras`, `GET /api/memories`, `GET /api/events`.
- **WebSocket events:** `memory_created` to live-prepend new memories; `processing` for the
  indicator. If a camera is active in another tab, the dashboard may not hold the socket;
  in that case it refreshes on focus.
- **Loading states:** skeleton cards for each panel.
- **Empty states:** "No cameras yet" -> CTA to `/cameras`; "No memories yet" -> CTA to
  start a camera; "No events yet".
- **Error states:** per-panel error with retry; global banner if health fails.
- **User actions:** open camera, open memory, open event, ask a question, go to chat.
- **Relationships:** links to `/cameras`, `/memory`, `/chat`, `/objects/[name]`.

### 11.5 `/cameras` — Camera management and live monitoring

- **Purpose:** Create cameras, start/stop sessions, connect the browser webcam, watch live
  preview, and see live memories appear.
- **Main components:** `CameraList`, `CameraCard`, `NewCameraDialog`, `CameraPreview`
  (`<video>` + overlay), `FrameStats` (FPS sent, KB/frame), `ChangeScoreGauge`,
  `ProcessingIndicator`, `LiveMemoryFeed`, `PermissionPrompt`.
- **Data needed:** cameras list; live `Memory` objects from the socket.
- **API endpoints:** `GET /api/cameras`, `POST /api/cameras`,
  `POST /api/cameras/{id}/start`, `POST /api/cameras/{id}/stop`,
  `DELETE /api/cameras/{id}`.
- **WebSocket events:** connect to `/ws/cameras/{id}?token=<jwt>`; send `camera_connected`,
  `frame`, `stop`; receive `connection_state`, `processing`, `change_detected`,
  `memory_created`, `error`.
- **Loading states:** camera list skeleton; start/stop button spinners; "Requesting camera
  permission..." state.
- **Empty states:** no cameras -> `NewCameraDialog`; camera exists but not started ->
  "Start monitoring"; permission denied -> instructions to re-enable.
- **Error states:** `getUserMedia` denied/unavailable; start/stop failure; WebSocket
  `error`; reconnect backoff banner.
- **User actions:** add camera (`name`, `source_type`), delete camera (confirm), start/stop,
  toggle preview, switch active camera, stop all.
- **Relationships:** newly created memories link to `/memory`; camera rows link to
  `/objects/[name]` for observed objects; `StatusBar` reflects socket state.

Creation payload: `{ "name": string, "source_type": "browser" }`. `config` may carry
client-side hints (e.g. `deviceId`, `facingMode`) but the backend owns the stored shape.

### 11.6 `/memory` — Memory timeline and object history sub-view

- **Purpose:** Browse, filter, inspect semantic memories and their evidence; host the
  Object History sub-view.
- **Main components:** `MemoryTimeline` (virtualized list), `MemoryCard` (scene summary,
  object chips, event badges, timestamp, camera, confidence, evidence thumbnail),
  `MemoryDetailDrawer`, `MemoryFilters` (camera, date range, event type, object, text),
  `EvidenceViewer`, `ObjectHistoryPanel` (sub-view, §12), `IndexingPill`.
- **Data needed:** memories (paginated), events, object history when a sub-view is open,
  evidence blob per memory.
- **API endpoints:** `GET /api/memories`, `GET /api/memories/{id}`,
  `GET /api/objects/{name}/history`, `GET /api/events`, `GET /api/evidence/{id}`.
- **WebSocket events:** `memory_created` to live-insert when a monitored camera is active.
- **Loading states:** timeline skeleton; detail drawer skeleton; evidence spinner
  (blurred placeholder).
- **Empty states:** "No memories yet" with CTA to `/cameras`; filter yields no results ->
  "No memories match these filters" with clear-filters action.
- **Error states:** list fetch error with retry; evidence 403/404 -> "Evidence unavailable"
  placeholder; embedding upload failure -> keep memory, show retry pill.
- **User actions:** scroll/paginate, filter, open detail, view evidence full-screen,
  open object history, copy memory ID, ask about this memory (routes to `/chat`).
- **Relationships:** detail -> `/objects/[name]`; "Ask about this" -> `/chat` with context;
  camera label links to `/cameras`.

Evidence fetching: `fetchEvidence(id)` with bearer token -> `response.blob()` ->
`URL.createObjectURL(blob)`. Revoke object URLs on unmount. If `Evidence.url` is present,
it may be a signed URL and can be used directly.

### 11.7 `/chat` — Conversational retrieval

- **Purpose:** Ask natural-language questions; receive grounded answers plus evidence and
  the diagnostic tool-call trail.
- **Main components:** `ChatPanel`, `MessageList`, `MessageBubble` (user/assistant/tool),
  `Composer` (multiline, Enter to send, Shift+Enter newline), `ToolCallList`,
  `EvidenceStrip`, `SuggestedQuestions`, `ConversationSidebar` (if conversations are
  server-persisted), `TypingIndicator`.
- **Data needed:** messages for the active conversation; `conversation_id`.
- **API endpoints:** `POST /api/chat`; `GET /api/memories/{id}` and
  `GET /api/evidence/{id}` to render evidence returned in the response.
- **WebSocket events:** none required. `/chat` is REST-driven.
- **Loading states:** send disabled + `TypingIndicator` while awaiting the response;
  evidence thumbnails load progressively after the answer.
- **Empty states:** no conversation -> `SuggestedQuestions` ("Where did I last see my
  backpack?", "What changed in the last hour?", "Show me the ESP32").
- **Error states:** chat request failure with retry (resend the last user message);
  evidence fetch failure degrades to text-only answer.
- **User actions:** send message, start new conversation, open suggested question, click
  evidence to open `EvidenceViewer`, expand a tool call to see `args`/`result`, retry.
- **Relationships:** evidence opens the same viewer as `/memory`; a memory referenced by a
  tool result links to `/memory`.

Rendering contract for a chat turn:

1. Optimistically append the user message.
2. Call `POST /api/chat` with `{ conversation_id?, message }`.
3. On response, store `conversation_id`, append assistant message with `content` and
   `tool_calls`, and set `evidence` for the turn.
4. Render `tool_calls` as a collapsible `ToolCallList` grouped by `tool`. Known tools:
   `search_memory`, `get_object_history`, `get_last_seen`, `get_events`, `get_scene`,
   `get_memory`, `get_evidence`.
5. Evidence items become thumbnails that open `EvidenceViewer`.

The assistant answer must be presented as "last observed" style information when the
backend returns it that way. The UI must never rephrase an answer into a claim of certain
absence. Treat the answer text as authoritative and display it verbatim.

### 11.8 `/settings` — Account and processing settings

- **Purpose:** Account info, camera management shortcuts, processing/capture settings,
  embedding/WebGPU status, privacy and data controls, backend health.
- **Main components:** `AccountSection` (email, sign out), `CamerasSection` (list, delete),
  `CaptureSettings` (sample FPS target, downscale max side, JPEG quality), `GateSettings`
  (client threshold, cooldown display), `EmbeddingStatus` (capability, model cache state,
  re-download), `PrivacySection` (local vs cloud explainer, §13), `HealthSection`
  (backend health, WS URL, build info).
- **Data needed:** user (Supabase), cameras, embedding capability, health.
- **API endpoints:** `GET /api/health`, `GET /api/cameras`, `DELETE /api/cameras/{id}`.
- **WebSocket events:** none (may show last known connection state read-only).
- **Loading states:** health check spinner; capability detection pending.
- **Empty states:** no cameras -> link to `/cameras`; embedding unsupported -> explanatory
  fallback message.
- **Error states:** health unreachable banner; camera delete failure toast.
- **User actions:** sign out, delete camera, adjust capture settings (persisted in
  `localStorage`), force re-download embedding model, test camera, test backend.
- **Relationships:** sign out -> `/`; camera management duplicates `/cameras` actions but
  routes there for creation; explainer reused from `/`.

Capture/gate settings live client-side (`localStorage`) and are not sent to the backend
unless a future contract adds them. They must not require backend changes.

---

## 12. Object History

Object History answers "Where did this object go over time, and where was it last?" It is
reachable two ways and uses the same components:

- Sub-view inside `/memory` (an `ObjectHistoryPanel` that opens when an object chip is
  selected).
- Dedicated route `/objects/[name]` (deep-linkable; `name` is the URL-encoded object name,
  matched against `MemoryObject.normalized_name` or `name`).

### 12.1 Purpose

Show a chronological timeline of observations for one object across all of the user's
authorized cameras, highlighting camera, location changes, and the last observed state.

### 12.2 Main components

| Component | Responsibility |
|---|---|
| `ObjectHeader` | Object display name, normalized key, total observations, cameras seen on |
| `ObjectTimeline` | Vertical timeline of observations, newest first (toggle to oldest first) |
| `LocationChangeList` | Only entries where `location` differs from the previous entry |
| `CameraBadge` | Camera name/ID for each observation |
| `LastObservedCard` | The single most recent observation, prominently displayed |
| `ObjectEvidenceStrip` | Evidence thumbnails for each observation's memory |
| `ObjectSearchEmpty` | Empty/unknown-object state |
| `AskAboutObject` | Routes to `/chat` with a prefilled question |

### 12.3 Data needed

`GET /api/objects/{name}/history` returns the object's observations. The frontend maps each
entry to the fields it needs and tolerates the backend's exact envelope shape by normalizing
to:

```ts
interface ObjectObservation {
  memory_id: string;
  camera_id: string;
  timestamp: string;
  location: string;
  status: string;
  attributes: Record<string, unknown>;
}
```

Derived values:

- **Object timeline:** all observations sorted by `timestamp` desc.
- **Camera:** distinct `camera_id` values, resolved to names via `GET /api/cameras`.
- **Location changes:** observation where `location !== previous.location` (in
  chronological order).
- **Last observed:** the observation with the maximum `timestamp`. Wording must be
  "last observed", never "definitely removed" or "not present".

If the backend returns memories instead of a flat observation list, the client flattens
`memory.objects` filtered by the object name, preserving the same derived values.

### 12.4 API endpoints

- `GET /api/objects/{name}/history` (primary)
- `GET /api/cameras` (resolve camera names)
- `GET /api/memories/{id}` (optional, to hydrate detail on click)
- `GET /api/evidence/{id}` (thumbnails)

### 12.5 WebSocket events

- `memory_created`: if the new memory contains an object matching the current page's name,
  live-prepend the observation.

### 12.6 Loading, empty, error states

- **Loading:** timeline skeleton rows; `LastObservedCard` skeleton.
- **Empty:** object has never been observed -> "No observations for this object yet." with a
  link to `/cameras`. Unknown/never-seen object -> same with the queried name shown.
- **Error:** history fetch failure -> retry; camera-name resolution failure -> fall back to
  showing raw `camera_id`; evidence failure -> placeholder thumbnail.

### 12.7 Important user actions

- Open an observation -> `/memory` detail drawer for that `memory_id`.
- Open the evidence for an observation in `EvidenceViewer`.
- Filter the timeline by camera.
- Toggle chronological direction.
- Ask about the object -> `/chat` prefilled with e.g. "Where did I last see the {name}?".
- Copy a shareable `/objects/{name}` link.

### 12.8 Relationships

- Reached from `/memory` object chips and from `/dashboard` recent-event object names.
- Each observation links back to `/memory`; each evidence item uses the shared
  `EvidenceViewer`; "Ask about object" links to `/chat`.

---

## 13. Local vs Cloud AI (Product UI Copy)

Display this explainer on `/` (dedicated section) and `/settings` (Privacy section), and
summarize it as a compact `ProcessingBadge` on `/cameras`.

| Stage | Where it runs | What leaves the device |
|---|---|---|
| Camera capture + local change gate | **Your browser** | Nothing. Frames stay local until the gate triggers. |
| Frame upload | Browser -> backend | Only gated, downscaled JPEG frames (~2 FPS max). |
| Visual understanding (VLM) | **Groq cloud** (Qwen3.8-27B) | The selected context frames. |
| Memory storage | Backend / database | Structured scene/object/event JSON, not raw video. |
| Embeddings | **Client-side** (Qwen3-Embedding-0.6B in a Web Worker) | The 1024-dim vector only, never the frames. |
| Chat reasoning | **Groq cloud** (GPT-OSS 20B) | Your question plus retrieved memory text. |
| Evidence | Authorized storage | A single authorized JPEG on request. |

Suggested UI copy:

> **Where your video goes.** The live camera preview and the change detection that decides
> when something interesting happens run entirely in your browser. Only a small number of
> downscaled frames are sent when a change is detected. Visual understanding and chat run in
> the cloud. Your memory text is turned into a search vector locally, in a Web Worker, and
> only the vector is uploaded. Evidence frames are stored and returned only to you.

Never expose Groq keys or service-role keys to the browser (see §3).

---

## 14. Shared UI Patterns

### 14.1 Loading states

- Use skeletons that match the final layout's size to avoid layout shift.
- Per-button spinners for mutations (start/stop/delete/send).
- Long-running indicators for first embedding-model download (progress bar from worker
  `progress` events).

### 14.2 Empty states

Every list has a purposeful empty state with a primary action:

| List | Empty copy | Action |
|---|---|---|
| Cameras | "No cameras yet." | Add camera |
| Memories | "No memories yet." | Start a camera |
| Events | "No events yet." | Start a camera |
| Chat | Suggested questions | Send a suggestion |
| Object history | "No observations for this object yet." | Open cameras |

### 14.3 Error states

- Network/API errors: inline panel with retry; toasts for transient failures.
- WebSocket: non-blocking banner with reconnect status.
- Auth: on 401 -> refresh once -> sign out + redirect.
- Evidence 403/404: neutral placeholder, never a broken image.
- VLM/Groq degraded (surfaced via backend `error` or chat failure): banner "Visual
  understanding is temporarily unavailable. Existing memories remain searchable."

### 14.4 Status vocabulary

Use consistent wording: `idle`, `connecting`, `connected`, `disconnected`, `error`,
`analyzing`, `cooldown`. Avoid invented statuses.

---

## 15. Cross-Page Relationships

```
/            -> /login, /signup, /dashboard
/login       <-> /signup
/dashboard   -> /cameras, /memory, /chat, /objects/[name]
/cameras     -> /memory (new memories), /objects/[name]
/memory      -> /objects/[name], /chat, /cameras
/objects/[name] -> /memory, /chat
/chat        -> /memory (tool results), EvidenceViewer (shared), /objects/[name]
/settings    -> /cameras, /, sign out
```

Shared across pages: `StatusBar` (health + WS + processing), `EvidenceViewer`,
`MemoryDetailDrawer`, `CameraBadge`, `ObjectChip`, `ToolCallList`.

---

## 16. Implementation Order

1. Project scaffold: Next.js + TypeScript + Tailwind + shadcn/ui; env validation.
2. `types/domain.ts` (verbatim interfaces) + `lib/apiClient.ts` + `lib/supabaseClient.ts`.
3. `AuthProvider`, `(auth)` pages, `(app)` guard, `StatusBar`.
4. `/cameras`: camera CRUD, `getUserMedia`, preview, `useCameraSocket`, frame sampling,
   local gate, live memory feed.
5. `/memory`: timeline, filters, detail drawer, `EvidenceViewer`.
6. `/objects/[name]`: Object History timeline, location changes, last observed.
7. `/chat`: composer, message list, tool-call surfacing, evidence strip.
8. Embedding Web Worker: capability detection, WebGPU/WASM fallback, background POST to
   `/api/memories/{id}/embedding`.
9. `/dashboard` and `/settings`; local vs cloud explainer.
10. Loading/empty/error polish, responsiveness, accessibility, acceptance checklist (§17).

---

## 17. Acceptance Checklist

- Auth: unauthenticated users cannot reach `(app)` routes; token attached to every protected
  call; 401 refresh-and-retry works.
- Camera: browser preview works; frames are sampled ~2 FPS, downscaled (max side ~1024),
  JPEG base64; `camera_connected`, `frame`, `stop` are the only client messages sent.
- WebSocket: all five server message types are handled; reconnect backoff works; stop sends
  `stop` before closing.
- Memory: `memory_created` live-inserts; evidence renders as an authorized blob; filters
  and empty states work.
- Object History: timeline, camera, location changes, and last observed all derive from
  `GET /api/objects/{name}/history`; wording is always "last observed".
- Chat: `POST /api/chat` contract honored; `tool_calls` surfaced; evidence from the
  response rendered; answer displayed verbatim.
- Embeddings: run in the worker; WebGPU with WASM fallback; 1024-dim vector POSTed to
  `/api/memories/{id}/embedding`; memory/chat never blocked on embedding.
- Secrets: only `NEXT_PUBLIC_*` variables reach the browser; `GROQ_API_KEY` and
  `SUPABASE_SERVICE_ROLE_KEY` appear nowhere in the client.
- No backend contracts changed; no `user_id` ever sent by the client.
