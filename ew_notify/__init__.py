"""Shared ntfy / Mac notifications for EW trading stacks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_CONTEXT: dict[str, Any] = {
    "configured": False,
    "project_root": None,
    "profile": "paper",
    "notify_path": None,
    "paper_root": None,
    "upstox_root": None,
}

DEFAULT_TOPICS = {
    "paper": {
        "alerts_topic": "ew-sk-paper-alerts",
        "commands_topic": "ew-sk-paper-cmd",
    },
    # Equity book (legacy profile name: upstox)
    "equity": {
        "alerts_topic": "ew-sk-equity-trade-alert",
        "commands_topic": None,
    },
    "upstox": {
        "alerts_topic": "ew-sk-equity-trade-alert",
        "commands_topic": None,
    },
    "breakout": {
        "alerts_topic": "breakout-swing-sk-alerts",
        "commands_topic": None,
    },
    "timeproof": {
        "alerts_topic": "timeproof-sk-alerts",
        "commands_topic": None,
    },
}


def configure(
    project_root: Path | str,
    *,
    profile: str = "paper",
    notify_path: Path | str | None = None,
    paper_root: Path | str | None = None,
    upstox_root: Path | str | None = None,
    **_ignored: Any,
) -> None:
    """Bind this process to a trading project + alert profile."""
    root = Path(project_root).resolve()
    home = Path.home()
    _CONTEXT["configured"] = True
    _CONTEXT["project_root"] = root
    _CONTEXT["profile"] = (profile or "paper").lower().strip()
    _CONTEXT["notify_path"] = Path(notify_path) if notify_path else root / "config" / "notifications.json"
    _CONTEXT["paper_root"] = Path(paper_root).resolve() if paper_root else home / "Projects" / "ew-paper-trading"
    _CONTEXT["upstox_root"] = (
        Path(upstox_root).resolve() if upstox_root else home / "Projects" / "ew-paper-trading-equity"
    )


def ctx() -> dict[str, Any]:
    if not _CONTEXT["configured"]:
        raise RuntimeError("ew_notify.configure(project_root, profile=...) was not called")
    return _CONTEXT


def project_root() -> Path:
    return Path(ctx()["project_root"])


def profile() -> str:
    return str(ctx()["profile"])


def is_equity_profile(name: str | None = None) -> bool:
    """True for equity book (profile equity or legacy upstox)."""
    p = (name or profile()).lower().strip()
    return p in ("equity", "upstox")


def state_dir(root: Path | None = None) -> Path:
    return (root or project_root()) / "state"


def notify_path() -> Path:
    return Path(ctx()["notify_path"])
