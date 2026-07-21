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
    kite_status_lines,
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
    "ws_trigger": ("Kite WS ticks", "live FUT ticks → paper breakout"),
}

# Equity book (ew-paper-trading-upstox) — launchd labels still *upstox*, ctl keys are equity_*
EQUITY_SERVICE_LABELS = {
    "equity_watcher": ("Equity watcher", "3 min EQ scan → Excel / paper"),
    "equity_agent_watch": ("Equity agent watch", "15 min log + coach"),
    "kite_ws": ("Kite WS ticks", "live EQ LTP → SL/target exits"),
}


def _short_name(instrument_id: str, scan: dict[str, Any] | None = None) -> str:
    """Compact label for phone (HDFCBANK → HDFC)."""
    aliases = {
        "RELIANCE": "RELI",
        "HDFCBANK": "HDFC",
        "ICICIBANK": "ICICI",
        "INFY": "INFY",
        "SBIN": "SBIN",
        "NIFTY": "NIFTY",
        "BANKNIFTY": "BN",
    }
    return aliases.get(instrument_id, (scan or {}).get("label") or instrument_id)


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
        scans = load_scans(root) or {"—": load_json(root / "state" / "latest-scan.json")}

    any_open = any(s.get("market_open") for s in scans.values() if isinstance(s, dict))
    multi = len([k for k, s in scans.items() if isinstance(s, dict)]) > 1

    if any_open or in_session:
        if any_open:
            lines.append("  OPEN  ·  9:15–15:30 IST")
        else:
            lines.append(f"  Between scans  ·  {session_reason}")

        if multi:
            # One compact LTP row for equities book
            bits: list[str] = []
            for instrument_id, scan in scans.items():
                if not isinstance(scan, dict) or scan.get("ltp") is None:
                    continue
                bits.append(f"{_short_name(instrument_id, scan)} {scan['ltp']}")
            if bits:
                lines.append("  " + " · ".join(bits))
            # Only expand bias for names with open interest or an alert
            for instrument_id, scan in scans.items():
                if not isinstance(scan, dict):
                    continue
                pos = (scan.get("portfolio") or {}).get("open_position")
                if not pos and not scan.get("alert"):
                    continue
                lines.append(
                    f"  {_short_name(instrument_id, scan)}  15m {scan.get('bias', '—')}"
                    f"  ·  {scan.get('wave_count', '—')}"
                )
                if scan.get("skip_reason") and pos:
                    lines.append(f"    skip  {scan['skip_reason']}")
        else:
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
        if multi:
            bits = []
            for instrument_id, scan in scans.items():
                if not isinstance(scan, dict):
                    continue
                ltp = scan.get("ltp")
                if ltp is not None:
                    bits.append(f"{_short_name(instrument_id, scan)} {ltp}")
            if bits:
                lines.append("  Last  " + " · ".join(bits))
        else:
            for instrument_id, scan in scans.items():
                if not isinstance(scan, dict):
                    continue
                label = scan.get("label") or instrument_id
                ltp = scan.get("ltp")
                if ltp is None and kite_active(root) and instrument_id in ("NIFTY", "RELIANCE"):
                    ltp = kite_last_ltp(root)
                if ltp is not None:
                    lines.append(f"  Last {label}  {ltp}")

    return lines


def _positions_block(scans: dict[str, Any], root: Path, *, title: str = "Paper") -> list[str]:
    lines: list[str] = [title]
    portfolios = load_portfolios(root)
    instruments = list_instruments(root) or list(portfolios.keys()) or list(scans.keys())

    day_pnl = 0.0
    day_trades = 0
    open_lines: list[str] = []
    flat_names: list[str] = []

    for instrument_id in instruments:
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
        day_pnl += pnl
        day_trades += trades
        short = _short_name(instrument_id, scan)

        if pos:
            open_lines.append(
                f"  {short}  {pos['direction'].upper()} @ {pos['entry']}"
            )
            open_lines.append(
                f"    SL {pos['stop']}  ·  TGT {pos['target']}"
            )
            if scan.get("alert"):
                open_lines.append(f"    ⚠ {scan['alert']}")
        else:
            flat_names.append(short)

    if open_lines:
        lines.extend(open_lines)
        if flat_names:
            lines.append(f"  Flat  {', '.join(flat_names)}")
    else:
        lines.append("  Flat all")

    lines.append(f"  Day P&L ₹{day_pnl:.0f}  ·  Trades {day_trades}")
    return lines


def _equity_services_block(equity_root: Path) -> list[str]:
    """Services for Nifty-50 equity paper book (Kite candles + WS ticks)."""
    lines: list[str] = []
    ctl = equity_root / "scripts" / "watcher_ctl_upstox.sh"
    flags = _launchctl_status(ctl) if ctl.exists() else {}
    running: list[str] = []
    stopped: list[str] = []

    if not ctl.exists():
        stopped.append("✗ Equity watcher ctl missing")
    else:
        for key, (name, detail) in EQUITY_SERVICE_LABELS.items():
            if flags.get(key):
                running.append(f"✓ {name} — {detail}")
            else:
                stopped.append(f"✗ {name} — {detail}")

    if cursor_loop_active(equity_root):
        running.append("✓ Cursor AI loop — /loop 1h in Equity Market Watch chat")
    else:
        stopped.append("✗ Cursor AI loop — start loop in Equity chat")

    if kite_active(equity_root):
        _active, detail = kite_status_lines(equity_root)
        running.append(detail)

    kite_cfg = load_json(equity_root / "config" / "kite.json")
    if kite_cfg.get("enabled") and kite_cfg.get("access_token"):
        running.append("✓ Kite token — candles + WS ticks")
    else:
        stopped.append("✗ Kite token — config/kite.json missing/disabled")

    wcfg = load_watcher_config(equity_root)
    running.append("✓ Feed — Kite REST candles + WS LTP (paper book)")
    if wcfg.get("kite_ws_tick_exits", True):
        if flags.get("kite_ws"):
            running.append("✓ Tick exits — SL/target on every LTP")
        else:
            stopped.append("✗ Tick exits — start kite_ws for live SL/target")

    notify = load_json(equity_root / "config" / "notifications.json")
    topic = notify.get("alerts_topic") or "ew-sk-equity-trade-alert"
    if notify.get("enabled"):
        running.append(f"✓ Trade ENTRY+EXIT alerts → {topic}")
    else:
        stopped.append(f"✗ Trade alerts off ({topic})")

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
        _active, detail = kite_status_lines(paper_root)
        running.append(detail)
    else:
        stopped.append("✗ Kite Connect — morning: kite_login.py then kite_ctl.py verify")

    # Feed mode from watcher config (candles / probe)
    wcfg = load_watcher_config(paper_root)
    if wcfg.get("prefer_kite_candles", True) and wcfg.get("prefer_kite_ltp", True):
        running.append("✓ Feed — Kite Connect candles + LTP (paper book)")
    if wcfg.get("kite_live_entry_probe"):
        running.append("✓ Live entry probe — try Kite order; paper stays truth")

    lines = ["Services · running"]
    lines.extend(f"  {x}" for x in (running if running else ["(nothing)"]))
    lines.append("")
    lines.append("Services · stopped")
    lines.extend(f"  {x}" for x in (stopped if stopped else ["(none)"]))
    return lines


def build_status_for_profile(profile_name: str) -> str:
    """Build status for a profile without permanently changing process profile."""
    c = ctx()
    prev = str(c["profile"])
    name = (profile_name or "paper").lower().strip()
    # Accept legacy "upstox" and preferred "equity"
    if name in ("upstox", "equity"):
        name = "equity"
    c["profile"] = name
    try:
        return build_status_message()
    finally:
        c["profile"] = prev


def build_status_message() -> str:
    """Profile-scoped status: paper (NIFTY FUT) or equity (5 stocks) — no dual mix."""
    from ew_notify import is_equity_profile

    c = ctx()
    paper_root = Path(c["paper_root"])
    equity_root = Path(c.get("upstox_root") or (Path.home() / "Projects" / "ew-paper-trading-upstox"))

    if is_equity_profile():
        root = equity_root
        cfg = load_watcher_config(root)
        scans = load_scans(root)
        if not scans:
            scan = load_json(root / "state" / "latest-scan.json")
            inst = (scan.get("instrument") if isinstance(scan, dict) else None) or "RELIANCE"
            scans = {inst: scan} if scan else {
                "RELIANCE": {"market_open": False, "skip_reason": "no_scan_yet"}
            }
        parts = ["Equity status · RELI · HDFC · ICICI · INFY · SBIN", ""]
        parts.extend(_market_block(scans, cfg, root))
        parts.append("")
        parts.extend(_positions_block(scans, root, title="Paper"))
        parts.append("")
        parts.extend(_equity_services_block(root))
        return "\n".join(parts)

    # paper profile — NIFTY/index FUT book only
    cfg = load_watcher_config(paper_root)
    scans = load_scans(paper_root)
    if not scans:
        scan = load_json(paper_root / "state" / "latest-scan.json")
        inst = (scan.get("instrument") if isinstance(scan, dict) else None) or "NIFTY"
        scans = {inst: scan} if scan else {
            "NIFTY": {"market_open": False, "skip_reason": "no_scan_yet"}
        }

    parts = ["Paper trading status · NIFTY FUT", ""]
    parts.extend(_market_block(scans, cfg, paper_root))
    parts.append("")
    parts.extend(_positions_block(scans, paper_root, title="Paper"))
    parts.append("")
    parts.extend(_paper_services_block(paper_root))
    return "\n".join(parts)


def launchctl_service_flags() -> dict[str, bool]:
    """Watcher flags for the active profile."""
    from ew_notify import is_equity_profile

    c = ctx()
    if is_equity_profile():
        equity_root = Path(c.get("upstox_root") or (Path.home() / "Projects" / "ew-paper-trading-upstox"))
        return _launchctl_status(equity_root / "scripts" / "watcher_ctl_upstox.sh")
    paper_root = Path(c["paper_root"])
    return _launchctl_status(paper_root / "scripts" / "watcher_ctl.sh")
