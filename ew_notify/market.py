"""Lightweight market-session helpers (no trading_common dependency)."""

from __future__ import annotations

import json
from datetime import datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from ew_notify import project_root


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open() as f:
        return json.load(f)


def load_watcher_config(root: Path | None = None) -> dict[str, Any]:
    root = root or project_root()
    path = root / "config" / "watcher.json"
    return load_json(path)


def now_ist(cfg: dict[str, Any] | None = None) -> datetime:
    tz = (cfg or {}).get("timezone") or "Asia/Kolkata"
    return datetime.now(ZoneInfo(tz))


def is_market_session(cfg: dict[str, Any], now: datetime) -> tuple[bool, str]:
    if now.weekday() >= 5:
        return False, "weekend"
    open_t = time(9, 15)
    close_t = time(15, 30)
    t = now.time()
    if t < open_t or t > close_t:
        return False, "outside_market_hours"
    return True, "open"


def list_instruments(root: Path | None = None) -> list[str]:
    root = root or project_root()
    data = load_json(root / "config" / "instruments.json")
    enabled = data.get("enabled")
    if enabled:
        return list(enabled)
    return list(data.get("definitions", {}).keys()) or ["NIFTY"]


def load_portfolios(root: Path | None = None) -> dict[str, Any]:
    root = root or project_root()
    data = load_json(root / "state" / "portfolios.json")
    if data:
        return data
    # legacy single file
    pf = load_json(root / "state" / "paper-portfolio.json")
    return {"NIFTY": pf} if pf else {}


def load_scans(root: Path | None = None) -> dict[str, Any]:
    root = root or project_root()
    scans = load_json(root / "state" / "latest-scans.json")
    if scans:
        return scans
    scan = load_json(root / "state" / "latest-scan.json")
    if scan:
        return {scan.get("instrument", "NIFTY"): scan}
    return {}
