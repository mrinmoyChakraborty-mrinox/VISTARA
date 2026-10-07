"""Stage 1 - Prove vision (with resolution sweep + Stage-4 crop shape).

What it does:
  1. Loads ONE image, then 3 frames (real --images or synthetic 1280x720 desk scenes).
  2. Resolution sweep per scene at max-side 512/768/1024/1280, JPEG q=85:
     prints size, payload KB, latency, per-object naming (ESP32/phone/notebook/bottle),
     locations-sensible flag. Recommends the smallest reliable size.
  3. Live Groq VLM call (qwen/qwen3-vl-32b, fallback qwen/qwen3-vl-32b):
     JSON-schema mode (s7 schema), reasoning_effort="none", Pydantic validate,
     retry once on malformed output. Prints latency.
  4. Reports: multi-image support, largest accepted payload, rate-limit headers.
     If multi-image is rejected, tiling fallback stitches frames into one image.
  5. Stage-4 payload shape demo: 1 high-res current + 1-2 low-res context + change-region crop.

Run:
    pip install -r backend/requirements.txt
    $env:GROQ_API_KEY="..."   # PowerShell  |  export GROQ_API_KEY=... (bash)
    python scripts/vlm_smoke_test.py [--images a.jpg b.jpg c.jpg] [--no-live]

Offline (no key / --no-live): encoding sweep + bbox/crop demo still run; VLM columns show SKIP.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from backend.app.config import settings  # noqa: E402
from backend.app.inference.schemas import VLMPerception  # noqa: E402
from backend.app.perception.image_utils import (  # noqa: E402
    change_bbox_from_mask,
    encode_jpeg,
    extract_crop_jpeg,
    map_bbox_to_full,
    prepare_frame_jpeg,
    resize_to_max_side,
    small_gray,
)

CAPTURE_W, CAPTURE_H = 1280, 720  # assumed browser capture
DEMO_OBJECTS = ["ESP32", "phone", "notebook", "bottle"]
SWEEP_DEFAULT = [512, 768, 1024, 1280]

ALIASES = {
    "esp32": "ESP32",
    "esp32 development board": "ESP32",
    "esp32 dev board": "ESP32",
    "development board": "ESP32",
    "small circuit board": "ESP32",
    "circuit board": "ESP32",
    "microcontroller": "ESP32",
    "mobile phone": "phone",
    "smartphone": "phone",
    "cell phone": "phone",
    "notebook": "notebook",
    "notepad": "notebook",
    "bottle": "bottle",
    "water bottle": "bottle",
}


def normalize(name: str) -> str:
    return ALIASES.get(name.strip().lower(), name.strip().lower())


def naming_report(perception: VLMPerception) -> dict[str, bool]:
    seen = {normalize(o.name) for o in perception.objects}
    return {obj: obj.lower() in seen for obj in DEMO_OBJECTS}


def locations_sensible(perception: VLMPerception) -> bool:
    if not perception.objects:
        return False
    return all(len((o.location or "").strip()) >= 3 for o in perception.objects)


# ---------------------------------------------------------------- synthetic scenes
def synthetic_desk(esp32_pos: str = "center", phone_pos: str = "left") -> np.ndarray:
    """Deterministic 1280x720 desk scene. esp32_pos: center|beside-laptop; phone: left|notebook."""
    img = np.full((CAPTURE_H, CAPTURE_W, 3), (52, 42, 34), np.uint8)  # desk
    cv2.rectangle(img, (0, 560), (CAPTURE_W, CAPTURE_H), (38, 30, 24), -1)  # desk edge
    cv2.rectangle(img, (430, 180), (850, 470), (25, 25, 25), -1)  # laptop
    cv2.rectangle(img, (450, 200), (830, 450), (60, 60, 60), -1)  # screen
    # ESP32 green board
    ex = 300 if esp32_pos == "center" else 880
    cv2.rectangle(img, (ex, 480), (ex + 130, 540), (40, 160, 60), -1)
    cv2.putText(
        img, "ESP32", (ex + 15, 518), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2
    )
    # phone
    px = 120 if phone_pos == "left" else 700
    cv2.rectangle(img, (px, 380), (px + 70, 520), (15, 15, 120), -1)
    cv2.putText(
        img, "phone", (px - 5, 560), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
    )
    # notebook
    cv2.rectangle(img, (950, 350), (1150, 540), (200, 200, 210), -1)
    cv2.putText(
        img, "notebook", (955, 575), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
    )
    # bottle
    cv2.rectangle(img, (1120, 180), (1160, 350), (180, 120, 40), -1)
    cv2.putText(
        img, "bottle", (1090, 380), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
    )
    return img


def load_or_synthesize(
    image_args: list[str],
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    if image_args:
        frames = []
        for p in image_args[:3]:
            img = cv2.imread(p)
            if img is None:
                print(f"FATAL: cannot read image {p}")
                sys.exit(1)
            frames.append(img)
        while len(frames) < 3:
            frames.append(frames[-1].copy())
        return [frames[0]], frames[:3]
    single = [synthetic_desk("center", "left")]
    seq = [
        synthetic_desk("center", "left"),
        synthetic_desk("beside-laptop", "left"),
        synthetic_desk("beside-laptop", "notebook"),
    ]
    return single, seq


# ---------------------------------------------------------------- sweep
def sweep_scene(
    name: str,
    frames: list[np.ndarray],
    resolutions: list[int],
    quality: int,
    provider,  # GroqVLMProvider | None (None = offline)
) -> list[dict]:
    rows = []
    for res in resolutions:
        blobs, dims = [], []
        for f in frames:
            blob, w, h = prepare_frame_jpeg(f, res, quality)
            blobs.append(blob)
            dims.append(f"{w}x{h}")
        payload_kb = sum(len(b) for b in blobs) / 1024.0
        row = {
            "scene": name,
            "n_frames": len(frames),
            "max_side": res,
            "dims": dims[0] + (f" x{len(frames)}" if len(frames) > 1 else ""),
            "payload_kb": payload_kb,
            "latency_s": None,
            "naming": {},
            "locations_ok": None,
            "model": "-",
            "notes": "",
        }
        if provider is None:
            row["notes"] = "SKIP (offline)"
            rows.append(row)
            continue
        try:
            t0 = time.perf_counter()
            result = provider.analyze(blobs)
            row["latency_s"] = result.latency_s
            row["model"] = result.model_used + (
                " [fallback]" if result.used_fallback else ""
            )
            if result.used_tiling:
                row["model"] += " [tiled]"
                row["notes"] = "multi-image rejected -> tiled"
            row["naming"] = naming_report(result.perception)
            row["locations_ok"] = locations_sensible(result.perception)
            row["rate_headers"] = result.rate_limit_headers
            row["wall_s"] = time.perf_counter() - t0
        except Exception as e:  # noqa: BLE001
            row["notes"] = f"FAIL: {type(e).__name__}: {str(e)[:160]}"
        rows.append(row)
    return rows


def print_table(rows: list[dict]) -> None:
    hdr = f"{'scene':<10}{'res':>5}  {'size':<16}{'KB':>9}  {'lat(s)':>7}  ESP32 phone note bottle loc  model/notes"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        lat = f"{r['latency_s']:.2f}" if r["latency_s"] is not None else "  SKIP"
        n = r["naming"]

        def mark(k: str) -> str:
            if not n:
                return "-"
            return "Y" if n.get(k, False) else "n"

        loc = "-" if r["locations_ok"] is None else ("Y" if r["locations_ok"] else "n")
        print(
            f"{r['scene']:<10}{r['max_side']:>5}  {r['dims']:<16}{r['payload_kb']:>9.1f}  "
            f"{lat:>7}  {mark('ESP32'):^5} {mark('phone'):^5} {mark('notebook'):^4} {mark('bottle'):^6} {loc:^3}  "
            f"{r['model']} {r['notes']}"
        )


def recommend(rows: list[dict]) -> str:
    """Smallest res where: validated + ESP32 named + >=3/4 named + locations sensible."""
    for r in sorted(rows, key=lambda x: x["max_side"]):
        n = r["naming"]
        if not n or r["locations_ok"] is None:
            continue
        hits = sum(1 for o in DEMO_OBJECTS if n.get(o))
        if (
            n.get("ESP32")
            and hits >= 3
            and r["locations_ok"]
            and not r["notes"].startswith("FAIL")
        ):
            return (
                f"Recommended smallest reliable max-side: {r['max_side']} "
                f"(payload ~{r['payload_kb']:.0f}KB for {r['n_frames']} frame(s), "
                f"latency {r['latency_s']:.2f}s)"
            )
    return "No resolution met the bar (ESP32 + >=3/4 objects + sensible locations) - use 1280."


# ---------------------------------------------------------------- crop demo (Stage-4 shape)
def crop_demo(seq: list[np.ndarray], quality: int, provider) -> None:
    print("\n--- Stage-4 payload shape: main + context + change-region crop ---")
    main_res = settings.vlm_main_max_side
    ctx_res = settings.vlm_context_max_side
    crop_res = settings.vlm_crop_max_side
    print(
        f"env: VLM_MAIN_MAX_SIDE={main_res} VLM_CONTEXT_MAX_SIDE={ctx_res} "
        f"VLM_CROP_MAX_SIDE={crop_res} JPEG q={quality}"
    )
    before, current = seq[0], seq[1]
    ga, gb = small_gray(before), small_gray(current)
    from backend.app.perception.image_utils import frame_change_score as _score

    gate_score = _score(ga, gb)
    fires = gate_score >= settings.change_threshold
    print(
        f"gate score={gate_score:.4f} vs CHANGE_THRESHOLD={settings.change_threshold} "
        f"-> gate would {'FIRE' if fires else 'NOT fire'}"
    )
    # Bbox demo uses threshold 0.0 on purpose: it shows the region that WOULD be
    # cropped whenever the gate fires. (Finding: default 0.12 is far above the
    # ~0.004 score of a small ESP32 move at 160x120 -- Stage 4 will retune it.)
    bbox_small = change_bbox_from_mask(
        ga,
        gb,
        change_threshold=0.0,
        padding_px=8,
    )
    if bbox_small is None:
        print("gate bbox: NO change region found (frames too similar at 160x120).")
        return
    H, W = current.shape[:2]
    bbox_full = map_bbox_to_full(
        bbox_small,
        (ga.shape[1], ga.shape[0]),
        (W, H),
        padding_px=settings.vlm_crop_padding,
    )
    main_blob, mw, mh = prepare_frame_jpeg(current, main_res, quality)
    ctx_blob, cw, ch = prepare_frame_jpeg(before, ctx_res, quality)
    crop_blob, _ = extract_crop_jpeg(current, bbox_full, crop_res, quality)
    print(f"gate bbox small160x120: {bbox_small} -> full{W}x{H}: {bbox_full}")
    print(
        f"main {mw}x{mh} {len(main_blob) / 1024:.1f}KB | "
        f"context {cw}x{ch} {len(ctx_blob) / 1024:.1f}KB | "
        f"crop {len(crop_blob) / 1024:.1f}KB | total {(len(main_blob) + len(ctx_blob) + len(crop_blob)) / 1024:.1f}KB"
    )
    if provider is None:
        print("crop payload built OK (offline, no VLM call).")
        return
    try:
        t0 = time.perf_counter()
        result = provider.analyze([main_blob, ctx_blob, crop_blob])
        print(
            f"crop-shape VLM OK: model={result.model_used} latency={result.latency_s:.2f}s "
            f"(wall {time.perf_counter() - t0:.2f}s) tiled={result.used_tiling}"
        )
        print(
            f"  scene={result.perception.scene.type!r} objs={len(result.perception.objects)} "
            f"events={len(result.perception.events)}"
        )
        print(
            f"  naming={naming_report(result.perception)} locations_ok={locations_sensible(result.perception)}"
        )
    except Exception as e:  # noqa: BLE001
        print(f"crop-shape VLM FAIL: {type(e).__name__}: {str(e)[:200]}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Stage 1 VLM smoke test + resolution sweep"
    )
    ap.add_argument(
        "--images",
        nargs="*",
        default=[],
        help="1-3 image paths (else synthetic 1280x720)",
    )
    ap.add_argument("--resolutions", nargs="*", type=int, default=SWEEP_DEFAULT)
    ap.add_argument("--quality", type=int, default=85)
    ap.add_argument("--no-live", action="store_true", help="skip Groq calls (offline)")
    args = ap.parse_args()

    print("== Visual Memory Stage 1 smoke test ==")
    print(
        f"VLM={settings.vlm_model} fallback={settings.vlm_fallback_model} "
        f"reasoning_effort=none response_format=json_schema(strict) retries=1+fallback"
    )
    single, seq = load_or_synthesize(args.images)
    print(
        f"scenes: single={len(single)} frame(s), sequence={len(seq)} frame(s); "
        f"source={'files' if args.images else 'synthetic 1280x720'}"
    )

    provider = None
    if not args.no_live and settings.groq_api_key:
        from backend.app.inference.groq_vlm import GroqVLMProvider

        provider = GroqVLMProvider(
            api_key=settings.groq_api_key,
            model=settings.vlm_model,
            fallback_model=settings.vlm_fallback_model,
        )
        print("live: Groq client created.")
    elif args.no_live:
        print("live: skipped (--no-live).")
    else:
        print("live: skipped (GROQ_API_KEY not set). Set it in .env to run live calls.")

    all_rows: list[dict] = []
    t_all = time.perf_counter()
    for name, frames in (("single", single), ("sequence", seq)):
        print(f"\n--- sweep: {name} ({len(frames)} frame(s)) ---")
        rows = sweep_scene(name, frames, args.resolutions, args.quality, provider)
        print_table(rows)
        print(recommend(rows))
        all_rows.extend(rows)

    # Reports required by the stage brief.
    live_rows = [r for r in all_rows if r["latency_s"] is not None]
    multi_ok = any(
        r["n_frames"] > 1 and not r["notes"].startswith("FAIL") for r in live_rows
    )
    print("\n--- required reports ---")
    print(
        f"multiple images per request: {'WORKS' if multi_ok else 'NOT PROVEN (offline or failed - tiling fallback available)'}"
    )
    if live_rows:
        biggest = max(live_rows, key=lambda r: r["payload_kb"])
        print(
            f"largest accepted payload (this run): ~{biggest['payload_kb']:.1f}KB "
            f"({biggest['scene']} @ {biggest['max_side']}, {biggest['n_frames']} frame(s))"
        )
        seen_headers: dict = {}
        for r in live_rows:
            seen_headers.update(
                getattr(r, "get", lambda *a, **k: {})("rate_headers", {}) or {}
            )
        if seen_headers:
            print("rate-limit headers observed:")
            for k, v in seen_headers.items():
                print(f"  {k}: {v}")
        else:
            print(
                "rate-limit headers: none captured (provider returned no x-*/ratelimit headers)."
            )
    else:
        print(
            "largest accepted payload: n/a offline (payload KB column still shows encoded sizes)."
        )
        print("rate-limit headers: n/a offline.")

    crop_demo(seq, args.quality, provider)
    print(f"\ntotal wall: {time.perf_counter() - t_all:.1f}s")

    if provider is not None and not live_rows:
        print("\nRESULT: FAIL - live calls attempted but none succeeded.")
        return 1
    print(
        "\nRESULT: OK"
        + (
            " (offline - set GROQ_API_KEY for live proof)"
            if provider is None
            else " (live proof complete)"
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
