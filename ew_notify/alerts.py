"""Trade / session / coach alert message bodies."""

from __future__ import annotations

from ew_notify.flags import coach_active, cursor_loop_active, kite_active, kite_status_lines


def build_trade_entry_alert(
    direction: str,
    entry: float,
    stop: float,
    target: float,
    bias: str,
    wave_count: str,
    *,
    execution: str = "paper",
    instrument: str | None = None,
) -> str:
    is_sandbox = execution in ("upstox_sandbox", "sandbox", "upstox")
    kind = "SANDBOX" if is_sandbox else "PAPER"
    money = (
        "Upstox sandbox order (no live money)"
        if is_sandbox
        else "paper trade (not real money)"
    )
    where = (
        "Excel + journal · upstox_order_id"
        if is_sandbox
        else "Excel Trades sheet"
    )
    name = (instrument or "").upper() or "—"
    return "\n".join([
        f"{kind} ENTRY  ·  {name}  ·  {direction.upper()}",
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
    instrument: str | None = None,
) -> str:
    is_sandbox = execution in ("upstox_sandbox", "sandbox", "upstox")
    kind = "SANDBOX" if is_sandbox else "PAPER"
    outcome = "WIN" if pnl > 0 else "LOSS" if pnl < 0 else "FLAT"
    name = (instrument or "").upper() or "—"
    close_line = (
        "✓ Position closed · opposite Upstox sandbox order"
        if is_sandbox
        else "✓ Position closed in paper portfolio"
    )
    return "\n".join([
        f"{kind} EXIT  ·  {name}  ·  {outcome}  ·  {direction.upper()}",
        "",
        f"  reason  {reason.replace('_', ' ')}",
        f"  P&L     ₹{pnl:.0f}",
        "",
        close_line,
        "→ Flat until next setup",
    ])


def build_square_off_alert(
    pnl: float,
    *,
    execution: str = "paper",
    instrument: str | None = None,
) -> str:
    is_sandbox = execution in ("upstox_sandbox", "sandbox", "upstox")
    where = "Sandbox" if is_sandbox else "Paper"
    name = (instrument or "").upper()
    head = f"SQUARE-OFF  15:15 IST  ·  {name}" if name else "SQUARE-OFF  15:15 IST"
    return "\n".join([
        head,
        "",
        f"  {where} position closed",
        f"  day P&L  ₹{pnl:.0f}",
        "",
        "✓ Watcher flat for rest of day unless new signal",
    ])


def build_start_message(watcher_result: str) -> str:
    from ew_notify import is_equity_profile
    from ew_notify.market import is_market_session, load_watcher_config, now_ist

    cfg = load_watcher_config()
    now = now_ist(cfg)
    in_session, reason = is_market_session(cfg, now)
    equity = is_equity_profile()

    if in_session:
        market_line = "OPEN now — scans and coach active"
    else:
        market_line = f"CLOSED ({reason.replace('_', ' ')}) — scans resume 9:15 IST Mon–Fri"

    loop_hint = (
        "✓ Cursor AI loop already running"
        if cursor_loop_active()
        else "✗ Cursor AI loop — open Market Watch chat → /loop 1h"
    )

    if equity:
        watcher_line = "  ✓ Equity watcher — 3 min EQ scan → Excel / paper"
        _on, kite_detail = kite_status_lines()
        kite_line = (
            f"  {kite_detail}"
            if _on
            else "  ✗ Kite Connect — kite_login.py + verify"
        )
        extras = [
            "  ✓ Agent watch — 15 min log on Mac",
            "  ✓ Kite WS ticks — live LTP · SL/target exits",
            "  ✓ Trade ENTRY+EXIT alerts → ew-sk-equity-trade-alert",
        ]
    else:
        watcher_line = "  ✓ Market watcher — 5 min NIFTY scan → Excel"
        _on, kite_detail = kite_status_lines()
        kite_line = (
            f"  {kite_detail}"
            if _on
            else "  ✗ Kite Connect — morning kite_login.py then kite_ctl.py verify"
        )
        extras = [
            "  ✓ Agent watch — 15 min log on Mac",
            "  ✓ Hourly coach — summary to this phone (market hours)",
            "  ✓ Phone commands — status · start · stop",
            "  ✓ Feed — Kite Connect candles / LTP / ticks",
        ]

    return "\n".join([
        "Session started" + (" · Equities" if equity else " · Paper NIFTY"),
        "",
        "Services · running",
        watcher_line,
        *extras,
        "",
        "Still need",
        f"  {loop_hint}",
        kite_line,
        "",
        f"Market  {market_line}",
        f"  (watchers: {watcher_result})",
    ])


def build_stop_message(watcher_result: str) -> str:
    from ew_notify import is_equity_profile

    equity = is_equity_profile()
    scan_lbl = "3 min equity scans" if equity else "5 min NIFTY scans"
    return "\n".join([
        "Session stopped" + (" · Equities" if equity else ""),
        "",
        "Services · stopped",
        f"  ✗ Market watcher — no more {scan_lbl}",
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
    from ew_notify import is_equity_profile

    flags = service_flags or {}
    coach_line = "ON" if coach_active() else "OFF"
    loop_line = "ON" if cursor_loop_active() else "OFF"
    equity = is_equity_profile()
    head = "Coach · Equities" if equity else "Coach · Market Watch"
    labels = {
        "watcher": "Market watcher",
        "agent_watch": "Agent watch",
        "phone_listener": "Phone listener",
        "equity_watcher": "Equity watcher",
        "equity_agent_watch": "Equity agent watch",
        "kite_ws": "Kite WS ticks",
        # legacy keys (pre-rename)
        "upstox_watcher": "Equity watcher",
        "upstox_agent_watch": "Equity agent watch",
    }
    preferred = (
        ("equity_watcher", "equity_agent_watch", "kite_ws")
        if equity
        else ("watcher", "agent_watch", "phone_listener")
    )
    svc_lines = []
    for k in preferred:
        if k in labels:
            svc_lines.append(f"  {'✓' if flags.get(k) else '✗'} {labels[k]}")
    for k, name in labels.items():
        if k not in preferred and k in flags:
            svc_lines.append(f"  {'✓' if flags.get(k) else '✗'} {name}")

    return "\n".join([
        head,
        f"  Coach {coach_line}  ·  Cursor loop {loop_line}",
        "",
        "Systems",
        *(svc_lines or ["  (no service flags)"]),
        "",
        summary.strip(),
        "",
        f"→ {recommendation}",
    ])
