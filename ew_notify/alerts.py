"""Trade / session / coach alert message bodies."""

from __future__ import annotations

from typing import Any

from ew_notify.flags import coach_active, cursor_loop_active, kite_active, kite_status_lines


def unrealized_pnl_inr(
    position: dict[str, Any] | None,
    ltp: Any,
    lot_size: int = 1,
) -> float | None:
    """Mark-to-market INR vs entry. None if the position or LTP cannot be used."""
    if not position or ltp is None:
        return None
    try:
        entry = float(position["entry"])
        mark = float(ltp)
        qty = int(position.get("qty") or 0)
        direction = str(position.get("direction") or "")
        lot = int(lot_size or 1)
    except (TypeError, ValueError, KeyError):
        return None
    if qty <= 0 or lot <= 0 or direction not in ("long", "short"):
        return None
    sign = 1 if direction == "long" else -1
    return (mark - entry) * sign * qty * lot


def unrealized_r(position: dict[str, Any] | None, ltp: Any) -> float | None:
    """Current R vs initial stop."""
    if not position or ltp is None:
        return None
    try:
        entry = float(position["entry"])
        mark = float(ltp)
        stop0 = float(position.get("initial_stop") or position.get("stop"))
        direction = str(position.get("direction") or "")
    except (TypeError, ValueError, KeyError):
        return None
    risk = abs(entry - stop0)
    if risk <= 0 or direction not in ("long", "short"):
        return None
    if direction == "long":
        return (mark - entry) / risk
    return (entry - mark) / risk


def format_running_pnl(
    position: dict[str, Any] | None,
    ltp: Any,
    lot_size: int = 1,
    *,
    include_qty: bool = True,
) -> str:
    """Compact iPhone fragment, e.g. `run ₹+480 (0.09R) · qty 400`."""
    pnl = unrealized_pnl_inr(position, ltp, lot_size)
    if pnl is None:
        return ""
    r = unrealized_r(position, ltp)
    if abs(pnl) < 0.5:
        text = "run ₹0"
    else:
        text = f"run ₹{pnl:+.0f}"
    if r is not None:
        text = f"{text} ({r:.2f}R)"
    if include_qty:
        try:
            qty = int((position or {}).get("qty") or 0)
        except (TypeError, ValueError):
            qty = 0
        if qty:
            text = f"{text} · qty {qty}"
    return text


def _exec_kind(execution: str) -> str:
    return "SANDBOX" if execution in ("upstox_sandbox", "sandbox", "upstox") else "PAPER"


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


def build_open_pnl_alert(
    direction: str,
    entry: float,
    stop: float,
    target: float | None,
    ltp: float,
    pnl: float,
    *,
    qty: int | None = None,
    r_multiple: float | None = None,
    execution: str = "paper",
    instrument: str | None = None,
) -> str:
    kind = _exec_kind(execution)
    name = (instrument or "").upper() or "—"
    if abs(pnl) < 0.5:
        run = "run  ₹0"
    else:
        run = f"run  ₹{pnl:+.0f}"
    if r_multiple is not None:
        run += f"  ({r_multiple:.2f}R)"
    try:
        qty_n = int(qty or 0)
    except (TypeError, ValueError):
        qty_n = 0
    if qty_n:
        run += f"  ·  qty {qty_n}"
    tgt = "—" if target is None else target
    return "\n".join([
        f"{kind} OPEN  ·  {name}  ·  {direction.upper()}",
        "",
        f"  LTP {ltp}  ·  entry {entry}",
        f"  {run}",
        f"  SL {stop}  ·  TGT {tgt}",
        "",
        "✓ Paper position still open",
        "→ Honor stop/target",
    ])


def build_open_pnl_book_alert(rows: list[dict[str, Any]]) -> str:
    """Combined running-P&L body when more than one name is open."""
    if not rows:
        return "PAPER OPEN  ·  flat"
    if len(rows) == 1:
        row = rows[0]
        return build_open_pnl_alert(
            direction=str(row.get("direction") or ""),
            entry=float(row["entry"]),
            stop=float(row["stop"]),
            target=row.get("target"),
            ltp=float(row["ltp"]),
            pnl=float(row["pnl"]),
            qty=row.get("qty"),
            r_multiple=row.get("r_multiple"),
            execution=str(row.get("execution") or "paper"),
            instrument=str(row.get("instrument") or ""),
        )
    book = 0.0
    lines = ["PAPER OPEN", ""]
    for row in rows:
        name = str(row.get("instrument") or "—").upper()
        direction = str(row.get("direction") or "").upper()
        pnl = float(row.get("pnl") or 0)
        book += pnl
        r = row.get("r_multiple")
        try:
            qty_n = int(row.get("qty") or 0)
        except (TypeError, ValueError):
            qty_n = 0
        if abs(pnl) < 0.5:
            run = "run ₹0"
        else:
            run = f"run ₹{pnl:+.0f}"
        if r is not None:
            run += f" ({float(r):.2f}R)"
        if qty_n:
            run += f" · qty {qty_n}"
        lines.append(
            f"  {name}  {direction} @ {row.get('entry')}  ·  LTP {row.get('ltp')}"
        )
        lines.append(f"  {run}")
    if abs(book) < 0.5:
        book_txt = "₹0"
    else:
        book_txt = f"₹{book:+.0f}"
    lines.extend(["", f"  book run  {book_txt}", "", "→ Honor stop/target"])
    return "\n".join(lines)


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
