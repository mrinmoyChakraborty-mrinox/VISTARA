"""Phase 2 diagnostics — secret-free configuration status.

Run:  python scripts/doctor.py         (config only)
      python scripts/doctor.py --ping  (also checks provider reachability)

NEVER prints env values. Only reports configured/missing and reachable/unreachable.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.core.config import settings

REQUIRED_SUPABASE = ["SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY"]
OPTIONAL_SUPABASE = ["SUPABASE_JWT_SECRET", "DATABASE_URL", "SUPABASE_EVIDENCE_BUCKET"]
REQUIRED_GROQ = ["GROQ_API_KEY"]


def _flag(name: str, value: str) -> str:
    return f"{name}: {'configured' if value else 'MISSING'}"


def report() -> int:
    print("== Visual Memory — configuration doctor ==")
    for name in REQUIRED_SUPABASE:
        print("  " + _flag(name, getattr(settings, name.lower(), "")))
    for name in OPTIONAL_SUPABASE:
        print("  " + _flag(name, getattr(settings, name.lower(), "")))
    for name in REQUIRED_GROQ:
        print("  " + _flag(name, settings.groq_api_key))
    print("  GROQ_VLM_MODEL:", settings.groq_vlm_model)
    print("  GROQ_CHAT_MODEL:", settings.groq_chat_model)
    print("  GROQ_VLM_REASONING_EFFORT:", settings.groq_vlm_reasoning_effort)
    print("  MOCK_MODE:", settings.mock_mode)

    missing = [n for n in REQUIRED_SUPABASE if not getattr(settings, n.lower(), "")]
    if not settings.database_url:
        missing.append("DATABASE_URL")
    if missing:
        print("\nBLOCKER: real Supabase not configured; missing: " + ", ".join(missing))
        print(
            "  -> Real DB/Auth/Storage/RLS verification cannot run until these are set in .env."
        )
        return 1
    print("\nSupabase configuration present (values not shown).")
    return 0


def ping() -> None:
    print("\n== provider reachability (no secrets printed) ==")
    if settings.groq_api_key:
        try:
            from groq import Groq

            models = Groq(api_key=settings.groq_api_key).models.list()
            ids = sorted(m.id for m in models.data)
            vlm_ok = settings.groq_vlm_model in ids
            chat_ok = settings.groq_chat_model in ids
            print(f"  Groq: reachable ({len(ids)} models)")
            print(
                f"  VLM {settings.groq_vlm_model}: {'available' if vlm_ok else 'NOT in catalog'}"
            )
            print(
                f"  CHAT {settings.groq_chat_model}: {'available' if chat_ok else 'NOT in catalog'}"
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  Groq: unreachable ({type(exc).__name__})")
    else:
        print("  Groq: not configured")

    if settings.database_url and not settings.database_url.startswith("sqlite"):
        try:
            from sqlalchemy import create_engine, text

            from backend.app.db.session import _normalize_url

            eng = create_engine(_normalize_url(settings.database_url))
            with eng.connect() as conn:
                conn.execute(text("select 1"))
            print("  Postgres: reachable")
        except Exception as exc:  # noqa: BLE001
            print(f"  Postgres: unreachable ({type(exc).__name__})")
    else:
        print("  Postgres: not configured (DATABASE_URL is sqlite/unset)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ping", action="store_true", help="check provider reachability")
    args = ap.parse_args()
    code = report()
    if args.ping:
        ping()
    raise SystemExit(code)
