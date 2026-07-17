"""Load per-repo notifications.json (separate topics per profile)."""

from __future__ import annotations

import json
from typing import Any

from ew_notify import DEFAULT_TOPICS, notify_path, profile


def load_notify_config() -> dict[str, Any]:
    path = notify_path()
    if not path.exists():
        # Fall back to defaults for the active profile
        defaults = dict(DEFAULT_TOPICS.get(profile(), DEFAULT_TOPICS["paper"]))
        defaults["enabled"] = False
        defaults["server"] = "https://ntfy.sh"
        defaults["profile"] = profile()
        return defaults

    with path.open() as f:
        cfg = json.load(f)

    # Fill topic defaults if missing
    defaults = DEFAULT_TOPICS.get(str(cfg.get("profile") or profile()), DEFAULT_TOPICS["paper"])
    if not cfg.get("alerts_topic"):
        cfg["alerts_topic"] = defaults.get("alerts_topic")
    if "commands_topic" not in cfg:
        cfg["commands_topic"] = defaults.get("commands_topic")
    cfg.setdefault("server", "https://ntfy.sh")
    cfg.setdefault("profile", profile())
    return cfg
