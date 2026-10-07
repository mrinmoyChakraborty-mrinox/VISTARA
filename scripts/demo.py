"""Local demo control (VISTARA_MODE=local).

Reset or drive the recorded-video demo. Only ever touches LOCAL state
(SQLite file + local evidence dir); refuses to run destructive actions in
live mode so Supabase data can never be wiped from here.

Usage:
    python scripts/demo.py status                    # show mode/db/video state
    python scripts/demo.py reset                     # wipe local DB + evidence
    python scripts/demo.py start [--name N] [--speed S] [--loop]
        # create (or reuse) a video_file camera and start playback via the API
    Backend must be running (default http://127.0.0.1:8000).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.core.config import settings  # noqa: E402

LOCAL_TOKEN = "demo-token"


def _req(base: str, path: str, method: str = "GET", body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{base}{path}",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LOCAL_TOKEN}",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        raw = res.read().decode() or "null"
        return res.status, json.loads(raw)


def _refuse_live(action: str) -> bool:
    if settings.is_live:
        print(f"REFUSED: '{action}' never runs in VISTARA_MODE=live.")
        return True
    return False


def cmd_status(_args) -> int:
    from backend.app.cameras.video import resolve_video_path, video_metadata

    print(f"mode:            {settings.vistara_mode}")
    print(f"database:        {settings.effective_database_url}")
    print(f"evidence dir:    {settings.local_evidence_dir}")
    print(f"groq configured: {settings.groq_configured}")
    try:
        path = resolve_video_path(None)
        meta = video_metadata(path)
        print(f"demo video:      {path}")
        print(
            f"  {meta['width']}x{meta['height']} @ {meta['fps']:.1f}fps, "
            f"{meta['frames']} frames (~{meta['frames'] / max(meta['fps'], 0.01):.1f}s)"
        )
    except ValueError as exc:
        print(f"demo video:      INVALID ({exc})")
        return 1
    return 0


def cmd_reset(_args) -> int:
    if _refuse_live("reset"):
        return 2
    from pathlib import Path

    from backend.app.evidence.service import local_evidence_dir

    db_url = settings.effective_database_url
    removed = []
    if db_url.startswith("sqlite"):
        db_path = Path(db_url.split("sqlite:///", 1)[-1].split("?")[0])
        for suffix in ("", "-journal", "-wal", "-shm"):
            candidate = Path(str(db_path) + suffix) if suffix else db_path
            if candidate.is_file():
                try:
                    candidate.unlink()
                except PermissionError:
                    print(f"LOCKED: {candidate} is open — stop the backend first.")
                    return 3
                removed.append(str(candidate))
    evidence = local_evidence_dir()
    if evidence.is_dir():
        for child in sorted(evidence.iterdir()):
            if child.name == ".gitkeep":
                continue
            if child.is_dir():
                import shutil

                shutil.rmtree(child)
            else:
                child.unlink()
            removed.append(str(child))
    print(f"local demo state reset ({len(removed)} paths removed).")
    for path in removed:
        print(f"  - {path}")
    return 0


def cmd_start(args) -> int:
    if settings.is_live:
        print("NOTE: running against a live-mode backend; using local demo token.")
    base = args.base.rstrip("/")
    try:
        _req(base, "/api/health")
    except Exception as exc:  # noqa: BLE001
        print(f"backend unreachable at {base}: {exc}")
        return 1
    _status, cameras = _req(base, "/api/cameras")
    existing = [c for c in cameras if c.get("name") == args.name]
    if existing:
        camera_id = existing[0]["id"]
        print(f"reusing camera {args.name} ({camera_id})")
    else:
        _status, created = _req(
            base,
            "/api/cameras",
            "POST",
            {
                "name": args.name,
                "source_type": "video_file",
                "config": {
                    "playback_speed": args.speed,
                    "loop": args.loop,
                },
            },
        )
        camera_id = created["id"]
        print(f"created camera {args.name} ({camera_id})")
    _status, started = _req(base, f"/api/cameras/{camera_id}/start", "POST")
    print(f"playback started (status={started.get('status')}).")
    print("Watch memories arrive; ask chat when ready.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Local demo control")
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("reset")
    start = sub.add_parser("start")
    start.add_argument("--name", default="Demo video")
    start.add_argument("--speed", type=float, default=settings.video_playback_speed)
    start.add_argument("--loop", action="store_true")
    args = ap.parse_args()
    if args.cmd == "status":
        return cmd_status(args)
    if args.cmd == "reset":
        return cmd_reset(args)
    return cmd_start(args)


if __name__ == "__main__":
    raise SystemExit(main())
