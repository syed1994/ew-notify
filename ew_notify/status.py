"""Human-readable system + market status for iPhone/Mac alerts."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from ew_notify import ctx, project_root
from ew_notify.flags import (
    coach_active,
    cursor_loop_active,
    kite_active,
    kite_last_ltp,
)
from ew_notify.market import (
    is_market_session,
    list_instruments,
    load_json,
    load_portfolios,
    load_scans,
    load_watcher_config,
    now_ist,
)

SERVICE_LABELS = {
    "watcher": ("Market watcher", "NIFTY scan every 5 min → Excel"),
    "agent_watch": ("Agent watch", "15 min log + hourly coach trigger"),
    "phone_listener": ("Phone listener", "iPhone commands: status · start · stop"),
}


def _launchctl_status(ctl_script: Path) -> dict[str, bool]:
    if not ctl_script.exists():
        return {}
    result = subprocess.run(
        ["/bin/bash", str(ctl_script), "status"],
        capture_output=True,
        text=True,
        check=False,
    )
    flags: dict[str, bool] = {}
    for line in (result.stdout or "").splitlines():
        if "=" not in line:
            continue
        key, val = line.strip().split("=", 1)
        flags[key] = val == "running"
    return flags


def _market_block(scans: dict[str, Any], cfg: dict[str, Any], root: Path) -> list[str]:
    now = now_ist(cfg)
    in_session, session_reason = is_market_session(cfg, now)
    lines: list[str] = ["Market"]

    if not scans:
        scans = {"NIFTY": load_json(root / "state" / "latest-scan.json")}

    any_open = any(s.get("market_open") for s in scans.values() if isinstance(s, dict))
    if any_open or in_session:
        if any_open:
            lines.append("  OPEN  ·  9:15–15:30 IST")
        else:
            lines.append(f"  Between scans  ·  {session_reason}")
        for instrument_id, scan in scans.items():
            if not isinstance(scan, dict):
                continue
            label = scan.get("label") or instrument_id
            contract = scan.get("contract_label") or scan.get("contract")
            if scan.get("ltp") is not None:
                head = f"  {label}  {scan['ltp']}"
                if contract:
                    head += f"  ·  {contract}"
                lines.append(head)
                lines.append(
                    f"  15m  {scan.get('bias', '—')}  ·  {scan.get('wave_count', '—')}"
                )
                if scan.get("skip_reason"):
                    lines.append(f"  skip  {scan['skip_reason']}")
    else:
        first = next(iter(scans.values()), {}) if scans else {}
        reason = (first.get("skip_reason") if isinstance(first, dict) else None) or session_reason
        lines.append(f"  CLOSED  ·  {str(reason).replace('_', ' ')}")
        for instrument_id, scan in scans.items():
            if not isinstance(scan, dict):
                continue
            label = scan.get("label") or instrument_id
            ltp = scan.get("ltp")
            if ltp is None and kite_active(root) and instrument_id == "NIFTY":
                ltp = kite_last_ltp(root)
            if ltp is not None:
                lines.append(f"  Last {label}  {ltp}")

    return lines


def _positions_block(scans: dict[str, Any], root: Path, *, title: str = "Paper") -> list[str]:
    lines: list[str] = [title]
    portfolios = load_portfolios(root)

    if not scans:
        pf = load_json(root / "state" / "paper-portfolio.json")
        scans = {"NIFTY": {"portfolio": {
            "daily_pnl_inr": pf.get("daily_pnl_inr", 0),
            "trades_today": pf.get("trades_today", 0),
            "open_position": pf.get("position"),
        }}}

    for instrument_id in list_instruments(root):
        scan = scans.get(instrument_id, {}) if isinstance(scans, dict) else {}
        if not isinstance(scan, dict):
            scan = {}
        portfolio = scan.get("portfolio") or {}
        if not portfolio:
            pf = portfolios.get(instrument_id, {})
            portfolio = {
                "daily_pnl_inr": pf.get("daily_pnl_inr", 0),
                "trades_today": pf.get("trades_today", 0),
                "open_position": pf.get("position"),
            }

        pos = portfolio.get("open_position")
        pnl = float(portfolio.get("daily_pnl_inr", 0) or 0)
        trades = int(portfolio.get("trades_today", 0) or 0)
        if pos:
            lines.append(f"  {instrument_id}  {pos['direction'].upper()}")
            lines.append(
                f"  entry {pos['entry']}  ·  SL {pos['stop']}  ·  TGT {pos['target']}"
            )
        else:
            lines.append(f"  {instrument_id}  flat")
        lines.append(f"  P&L today ₹{pnl:.0f}  ·  Trades {trades}/2")
        if scan.get("alert"):
            lines.append(f"  ⚠ {scan['alert']}")
    return lines


def _upstox_services_block(upstox_root: Path) -> list[str]:
    lines: list[str] = []
    ctl = upstox_root / "scripts" / "watcher_ctl_upstox.sh"
    running: list[str] = []
    stopped: list[str] = []

    if not ctl.exists():
        stopped.append("✗ Upstox watcher ctl missing")
    else:
        flags = _launchctl_status(ctl)
        labels = {
            "upstox_watcher": ("Upstox watcher", "5 min scan → sandbox orders"),
            "upstox_agent_watch": ("Upstox agent watch", "15 min log"),
        }
        for key, (name, detail) in labels.items():
            if flags.get(key):
                running.append(f"✓ {name} — {detail}")
            else:
                stopped.append(f"✗ {name} — {detail}")

    if cursor_loop_active(upstox_root):
        running.append("✓ Cursor AI loop — /loop 1h in Upstox chat")
    else:
        stopped.append("✗ Cursor AI loop — start loop in Upstox chat")

    if kite_active(upstox_root) or kite_active(Path.home() / "Projects" / "ew-paper-trading"):
        root_for_ltp = upstox_root if kite_active(upstox_root) else Path.home() / "Projects" / "ew-paper-trading"
        ltp = kite_last_ltp(root_for_ltp)
        detail = f"verified · NIFTY {ltp}" if ltp else "verified"
        running.append(f"✓ Kite live price — {detail}")
    else:
        stopped.append("✗ Kite live price — login in Cursor MCP")

    ux_cfg = load_json(upstox_root / "config" / "upstox.json")
    token_ok = bool(ux_cfg.get("enabled") and ux_cfg.get("access_token"))
    if token_ok:
        running.append(
            f"✓ Upstox token — sandbox={ux_cfg.get('sandbox', True)}"
        )
    else:
        stopped.append("✗ Upstox token — missing/disabled")

    notify = load_json(upstox_root / "config" / "notifications.json")
    topic = notify.get("alerts_topic") or "ew-sk-upstox-trade-alert"
    if notify.get("enabled"):
        running.append(f"✓ Trade ENTRY alerts → {topic}")
    else:
        stopped.append(f"✗ Trade ENTRY alerts off ({topic})")

    lines.append("Services · running")
    lines.extend(f"  {x}" for x in (running if running else ["(nothing)"]))
    lines.append("")
    lines.append("Services · stopped")
    lines.extend(f"  {x}" for x in (stopped if stopped else ["(none)"]))
    return lines


def _paper_services_block(paper_root: Path) -> list[str]:
    ctl = paper_root / "scripts" / "watcher_ctl.sh"
    flags = _launchctl_status(ctl)
    running: list[str] = []
    stopped: list[str] = []

    for key, (name, detail) in SERVICE_LABELS.items():
        if flags.get(key):
            running.append(f"✓ {name} — {detail}")
        else:
            stopped.append(f"✗ {name} — {detail}")

    if coach_active(paper_root):
        running.append("✓ Hourly coach — market-hour summary to iPhone")
    else:
        stopped.append("✗ Hourly coach — send start session to enable")

    if cursor_loop_active(paper_root):
        running.append("✓ Cursor AI loop — /loop 1h active in Market Watch chat")
    else:
        stopped.append("✗ Cursor AI loop — send /loop 1h in Market Watch chat")

    if kite_active(paper_root):
        ltp = kite_last_ltp(paper_root)
        detail = f"verified in Cursor · NIFTY {ltp}" if ltp else "verified in Cursor"
        running.append(f"✓ Kite live price — {detail}")
    else:
        stopped.append("✗ Kite live price — login in Cursor MCP (log kite)")

    lines = ["Services · running"]
    lines.extend(f"  {x}" for x in (running if running else ["(nothing)"]))
    lines.append("")
    lines.append("Services · stopped")
    lines.extend(f"  {x}" for x in (stopped if stopped else ["(none)"]))
    return lines


def build_status_message() -> str:
    """Profile-scoped status: paper-only or upstox-only (no dual mix)."""
    from ew_notify import profile as active_profile

    c = ctx()
    paper_root = Path(c["paper_root"])
    upstox_root = Path(c.get("upstox_root") or (Path.home() / "Projects" / "ew-paper-trading-upstox"))

    if active_profile() == "upstox":
        root = upstox_root
        cfg = load_watcher_config(root)
        scans = load_scans(root)
        if not scans:
            scan = load_json(root / "state" / "latest-scan.json")
            scans = {scan.get("instrument", "NIFTY"): scan} if scan else {
                "NIFTY": {"market_open": False, "skip_reason": "no_scan_yet"}
            }
        parts = ["Upstox sandbox status", ""]
        parts.extend(_market_block(scans, cfg, root))
        parts.append("")
        parts.extend(_positions_block(scans, root, title="Paper"))
        parts.append("")
        parts.extend(_upstox_services_block(root))
        return "\n".join(parts)

    # paper profile — paper only
    cfg = load_watcher_config(paper_root)
    scans = load_scans(paper_root)
    if not scans:
        scan = load_json(paper_root / "state" / "latest-scan.json")
        scans = {scan.get("instrument", "NIFTY"): scan} if scan else {
            "NIFTY": {"market_open": False, "skip_reason": "no_scan_yet"}
        }

    parts = ["Paper trading status", ""]
    parts.extend(_market_block(scans, cfg, paper_root))
    parts.append("")
    parts.extend(_positions_block(scans, paper_root, title="Paper"))
    parts.append("")
    parts.extend(_paper_services_block(paper_root))
    return "\n".join(parts)


def launchctl_service_flags() -> dict[str, bool]:
    """Watcher flags for the active profile."""
    from ew_notify import profile as active_profile

    c = ctx()
    if active_profile() == "upstox":
        upstox_root = Path(c.get("upstox_root") or (Path.home() / "Projects" / "ew-paper-trading-upstox"))
        return _launchctl_status(upstox_root / "scripts" / "watcher_ctl_upstox.sh")
    paper_root = Path(c["paper_root"])
    return _launchctl_status(paper_root / "scripts" / "watcher_ctl.sh")
