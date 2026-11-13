"""Push alerts to iPhone via ntfy.sh and show macOS notifications."""

from __future__ import annotations

import logging
import subprocess
import time
import urllib.error
import urllib.request

from ew_notify.config import load_notify_config


def mac_notify(title: str, message: str, *, sound: bool = True) -> None:
    safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
    safe_msg = message.replace("\\", "\\\\").replace('"', '\\"')[:220]
    sound_part = ' sound name "Glass"' if sound else ""
    script = f'display notification "{safe_msg}" with title "{safe_title}"{sound_part}'
    subprocess.run(["osascript", "-e", script], capture_output=True, check=False)


def send_push(
    title: str,
    message: str,
    *,
    topic: str | None = None,
    priority: str = "default",
    tags: str = "chart_with_upwards_trend",
    retries: int = 2,
    markdown: bool = False,
) -> bool:
    cfg = load_notify_config()
    if not cfg.get("enabled"):
        return False

    alerts_topic = topic or cfg.get("alerts_topic")
    server = cfg.get("server", "https://ntfy.sh").rstrip("/")
    if not alerts_topic:
        logging.warning("ntfy alerts_topic not configured")
        return False

    url = f"{server}/{alerts_topic}"
    data = message.encode("utf-8")
    headers = {
        "Title": title[:256],
        "Priority": priority,
        "Tags": tags,
    }
    if markdown:
        headers["Markdown"] = "yes"

    for attempt in range(retries):
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15):
                return True
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt + 1 < retries:
                time.sleep(5 * (attempt + 1))
                continue
            if exc.code == 429:
                logging.warning("ntfy push rate limited")
            else:
                logging.warning("ntfy push failed: HTTP %s", exc.code)
            return False
        except (urllib.error.URLError, OSError) as exc:
            logging.warning("ntfy push failed: %s", exc)
            return False
    return False


def notify_alert(message: str, title: str = "EW Trade", *, markdown: bool = False) -> bool:
    return send_push(title, message, priority="high", tags="rotating_light", markdown=markdown)


def notify_info(message: str, title: str = "Market Watch", *, markdown: bool = False) -> bool:
    return send_push(title, message, priority="default", markdown=markdown)


def notify_both(title: str, message: str, *, mac_title: str | None = None) -> None:
    mac_notify(mac_title or title, message)
    if not send_push(title, message):
        mac_notify("iPhone push delayed", "Rate limited — Mac got your command.", sound=False)
