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
    ltp = data.get("spot_ltp", data.get("ltp"))
    return float(ltp) if ltp is not None else None


def kite_session_info(root: Path | None = None) -> dict[str, Any]:
    """Full kite-session.json payload when connected within TTL."""
    if not kite_active(root):
        return {}
    return _load_json(state_dir(root) / "kite-session.json")


def kite_status_lines(root: Path | None = None) -> tuple[bool, str]:
    """Return (active, one-line detail for phone status)."""
    info = kite_session_info(root)
    if not info:
        return False, "run kite_login.py then kite_ctl.py verify"

    source = str(info.get("source") or "")
    spot = info.get("spot_ltp", info.get("ltp"))
    fut = info.get("fut_ltp")
    fut_sym = info.get("fut_symbol") or ""

    if source in ("kite_connect", "upstox", "upstox_candle", "upstox_quote"):
        label = "Kite Connect" if source.startswith("kite") else source.replace("_", " ")
        bits = [f"✓ {label}"]
        if spot is not None:
            bits.append(f"spot {spot}")
        if fut is not None:
            short = str(fut_sym).split(":")[-1] if fut_sym else "FUT"
            bits.append(f"{short} {fut}")
        return True, " · ".join(bits)

    # Legacy Cursor MCP verify (spot may be index or a single equity LTP)
    if spot is not None:
        detail = f"✓ Kite MCP · LTP {spot}"
    else:
        detail = "✓ Kite MCP · verified"
    return True, detail


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
