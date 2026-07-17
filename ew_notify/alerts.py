"""Trade / session / coach alert message bodies (paper trading only)."""

from __future__ import annotations

from ew_notify.flags import coach_active, cursor_loop_active, kite_active


def build_trade_entry_alert(
    direction: str,
    entry: float,
    stop: float,
    target: float,
    bias: str,
    wave_count: str,
    *,
    execution: str = "paper",
) -> str:
    is_sandbox = execution in ("upstox_sandbox", "sandbox", "upstox")
    kind = "SANDBOX" if is_sandbox else "PAPER"
    money = (
        "Upstox sandbox order (no live money)"
        if is_sandbox
        else "paper trade (not real money)"
    )
    where = (
        "Excel + journal upstox_order_id"
        if is_sandbox
        else "Excel Trades sheet"
    )
    return "\n".join([
        f"{kind} ENTRY  ·  {direction.upper()}",
        "",
        f"  entry {entry}  ·  SL {stop}  ·  TGT {target}",
        f"  15m   {bias}  ·  {wave_count}",
        "",
        f"✓ Watcher placed {money}",
        f"→ Check {where} · honor stop/target",
    ])


def build_trade_exit_alert(
    reason: str,
    pnl: float,
    direction: str,
    *,
    execution: str = "paper",
) -> str:
    is_sandbox = execution in ("upstox_sandbox", "sandbox", "upstox")
    kind = "SANDBOX" if is_sandbox else "PAPER"
    outcome = "WIN" if pnl > 0 else "LOSS" if pnl < 0 else "FLAT"
    close_line = (
        "✓ Position closed · opposite Upstox sandbox order"
        if is_sandbox
        else "✓ Position closed in paper portfolio"
    )
    return "\n".join([
        f"{kind} EXIT  ·  {outcome}  ·  {direction.upper()}",
        "",
        f"  reason  {reason.replace('_', ' ')}",
        f"  P&L     ₹{pnl:.0f}",
        "",
        close_line,
        "→ Flat until next setup",
    ])


def build_square_off_alert(pnl: float, *, execution: str = "paper") -> str:
    is_sandbox = execution in ("upstox_sandbox", "sandbox", "upstox")
    where = "Sandbox" if is_sandbox else "Paper"
    return "\n".join([
        "SQUARE-OFF  15:15 IST",
        "",
        f"  {where} position closed",
        f"  day P&L  ₹{pnl:.0f}",
        "",
        "✓ Watcher flat for rest of day unless new signal",
    ])


def build_start_message(watcher_result: str) -> str:
    from ew_notify.market import is_market_session, load_watcher_config, now_ist

    cfg = load_watcher_config()
    now = now_ist(cfg)
    in_session, reason = is_market_session(cfg, now)

    if in_session:
        market_line = "OPEN now — scans and coach active"
    else:
        market_line = f"CLOSED ({reason.replace('_', ' ')}) — scans resume 9:15 IST Mon–Fri"

    loop_hint = (
        "✓ Cursor AI loop already running"
        if cursor_loop_active()
        else "✗ Cursor AI loop — open Market Watch chat → /loop 1h"
    )

    return "\n".join([
        "Session started",
        "",
        "Services · running",
        "  ✓ Market watcher — 5 min NIFTY scan → Excel",
        "  ✓ Agent watch — 15 min log on Mac",
        "  ✓ Hourly coach — summary to this phone (market hours)",
        "  ✓ Phone commands — status · start · stop",
        "",
        "Still need",
        f"  {loop_hint}",
        (
            "  ✓ Kite MCP — verified in Cursor"
            if kite_active()
            else "  ✗ Kite MCP — login in Cursor for live NIFTY verify"
        ),
        "",
        f"Market  {market_line}",
        f"  (watchers: {watcher_result})",
    ])


def build_stop_message(watcher_result: str) -> str:
    return "\n".join([
        "Session stopped",
        "",
        "Services · stopped",
        "  ✗ Market watcher — no more 5 min scans",
        "  ✗ Agent watch — no more 15 min logs",
        "  ✗ Hourly coach — no more phone summaries",
        "",
        "Still running",
        "  ✓ Phone listener — send start session to resume",
        "",
        "Reminder",
        "  If Cursor AI loop was on, send: stop the market loop",
        "",
        f"  ({watcher_result})",
    ])


def build_coach_message(
    summary: str,
    recommendation: str,
    *,
    service_flags: dict[str, bool] | None = None,
) -> str:
    flags = service_flags or {}
    coach_line = "ON" if coach_active() else "OFF"
    loop_line = "ON" if cursor_loop_active() else "OFF"
    labels = {
        "watcher": "Market watcher",
        "agent_watch": "Agent watch",
        "phone_listener": "Phone listener",
    }
    svc_lines = [
        f"  {'✓' if flags.get(k) else '✗'} {name}"
        for k, name in labels.items()
    ]
    return "\n".join([
        "Coach · hourly",
        f"  Coach {coach_line}  ·  Cursor loop {loop_line}",
        "",
        "Systems",
        *svc_lines,
        "",
        summary.strip(),
        "",
        f"→ {recommendation}",
    ])
