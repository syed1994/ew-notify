"""Kite / Cursor-loop session flags stored under a project's state/."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from ew_notify import state_dir

KITE_TTL_HOURS = 12
LOOP_PATTERN = "AGENT_LOOP_TICK_MARKET_WATCH"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _now_ist() -> datetime:
    return datetime.now(ZoneInfo("Asia/Kolkata"))


def kite_active(root: Path | None = None) -> bool:
    path = state_dir(root) / "kite-session.json"
    data = _load_json(path)
    if not data.get("connected"):
        return False
    verified_at = data.get("verified_at", "")
    if not verified_at:
        return False
    try:
        prev = datetime.fromisoformat(verified_at)
        if prev.tzinfo is None:
            prev = prev.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
        hours = (_now_ist() - prev).total_seconds() / 3600
        return hours < KITE_TTL_HOURS
    except ValueError:
        return False


def kite_last_ltp(root: Path | None = None) -> float | None:
    data = _load_json(state_dir(root) / "kite-session.json")
    ltp = data.get("ltp")
    return float(ltp) if ltp is not None else None


def _pgrep_loop() -> bool:
    r = subprocess.run(
        ["pgrep", "-fi", "AGENT_LOOP_TICK_MARKET_WATCH"],
        capture_output=True,
        text=True,
        check=False,
    )
    return r.returncode == 0


def cursor_loop_active(root: Path | None = None) -> bool:
    if _pgrep_loop():
        return True
    data = _load_json(state_dir(root) / "cursor-loop.json")
    return bool(data.get("active"))


def coach_active(root: Path | None = None) -> bool:
    data = _load_json(state_dir(root) / "coach-session.json")
    return bool(data.get("session_active") and data.get("coach_push_to_phone"))
