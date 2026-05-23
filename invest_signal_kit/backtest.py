"""Backtest / Signal Replay Lab.

Deterministic event-driven backtesting from a JSON scenario file.
Simulates enter, add, trim, exit, stop, target, time-stop, and
skip/blocked events over price series. Tracks cash, positions, equity
curve, trades, event log, costs, drawdown, turnover, and benchmark
relative performance.

This is research tooling, not financial advice. No live data, no
brokerage integration, no optimization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------

@dataclass
class PricePoint:
    """A single OHLCV bar for one asset on one date."""
    date: str = ""
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0


@dataclass
class SignalEvent:
    """A deterministic signal event in the backtest."""
    date: str = ""
    asset: str = ""
    action: str = ""
    """enter, add, trim, exit, stop, target, time_stop, skip, blocked."""
    quantity: float = 0.0
    """Number of shares. Positive = buy, negative = sell. 0 = use default."""
    price: float = 0.0
    """Override execution price. 0 = use close on event date."""
    reason: str = ""
    """Human-readable reason for this event."""
    confidence: float = 0.0
    """Signal confidence 0-100. Used for gate checks."""
    stop_price: float = 0.0
    """Stop-loss price for this entry."""
    target_price: float = 0.0
    """Target price for this entry."""
    time_stop_days: int = 0
    """Maximum holding period in days."""


@dataclass
class CostConfig:
    """Transaction cost model."""
    commission_per_trade: float = 0.0
    """Fixed commission per trade."""
    slippage_bps: float = 5.0
    """Slippage in basis points of trade value."""


@dataclass
class RiskRules:
    """Risk policy for the backtest."""
    max_position_pct: float = 25.0
    """Maximum single position as % of total equity."""
    max_drawdown_pct: float = 20.0
    """Maximum portfolio drawdown before halting."""
    min_confidence: float = 60.0
    """Minimum signal confidence to enter."""


@dataclass
class BacktestScenario:
    """A complete backtest scenario."""
    initial_capital: float = 100000.0
    price_series: Dict[str, List[PricePoint]] = field(default_factory=dict)
    signal_events: List[SignalEvent] = field(default_factory=list)
    benchmark: List[PricePoint] = field(default_factory=list)
    costs: CostConfig = field(default_factory=CostConfig)
    risk_rules: RiskRules = field(default_factory=RiskRules)


# ---------------------------------------------------------------------------
# Output Data Structures
# ---------------------------------------------------------------------------

@dataclass
class PositionState:
    """Internal state of an open position."""
    asset: str = ""
    shares: float = 0.0
    entry_price: float = 0.0
    entry_date: str = ""
    stop_price: float = 0.0
    target_price: float = 0.0
    time_stop_days: int = 0
    cost_basis: float = 0.0


@dataclass
class TradeRecord:
    """A completed round-trip trade."""
    asset: str = ""
    entry_date: str = ""
    exit_date: str = ""
    entry_price: float = 0.0
    exit_price: float = 0.0
    shares: float = 0.0
    pnl: float = 0.0
    return_pct: float = 0.0
    r_multiple: float = 0.0
    holding_days: int = 0
    exit_reason: str = ""
    total_costs: float = 0.0


@dataclass
class EventLogEntry:
    """A logged event during the backtest."""
    date: str = ""
    asset: str = ""
    action: str = ""
    quantity: float = 0.0
    price: float = 0.0
    value: float = 0.0
    cost: float = 0.0
    cash_after: float = 0.0
    equity_after: float = 0.0
    reason: str = ""
    blocked: bool = False
    block_reason: str = ""


@dataclass
class EquityPoint:
    """A point on the equity curve."""
    date: str = ""
    cash: float = 0.0
    positions_value: float = 0.0
    total_equity: float = 0.0
    drawdown_pct: float = 0.0
    benchmark_value: Optional[float] = None


@dataclass
class BacktestResult:
    """Complete backtest result."""
    # Summary
    initial_capital: float = 0.0
    final_equity: float = 0.0
    total_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0

    # Trade stats
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_trade_return_pct: float = 0.0
    avg_r_multiple: float = 0.0

    # Costs
    total_fees: float = 0.0
    total_slippage: float = 0.0
    total_costs: float = 0.0

    # Benchmark
    benchmark_return_pct: float = 0.0
    alpha_vs_benchmark: float = 0.0

    # Turnover
    total_turnover: float = 0.0

    # Details
    trades: List[TradeRecord] = field(default_factory=list)
    equity_curve: List[EquityPoint] = field(default_factory=list)
    event_log: List[EventLogEntry] = field(default_factory=list)
    blocked_events: List[EventLogEntry] = field(default_factory=list)

    # Config snapshot
    initial_capital_used: float = 0.0
    cost_config: Dict[str, float] = field(default_factory=dict)
    risk_rules: Dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_price_points(data: list) -> List[PricePoint]:
    """Load a list of price points from dicts."""
    points = []
    for d in data:
        points.append(PricePoint(
            date=str(d.get("date", "")),
            open=float(d.get("open", 0)),
            high=float(d.get("high", 0)),
            low=float(d.get("low", 0)),
            close=float(d.get("close", 0)),
            volume=float(d.get("volume", 0)),
        ))
    return points


def load_signal_event(data: dict) -> SignalEvent:
    """Load a SignalEvent from a dict."""
    return SignalEvent(
        date=str(data.get("date", "")),
        asset=str(data.get("asset", "")),
        action=str(data.get("action", "")),
        quantity=float(data.get("quantity", 0)),
        price=float(data.get("price", 0)),
        reason=str(data.get("reason", "")),
        confidence=float(data.get("confidence", 0)),
        stop_price=float(data.get("stop_price", 0)),
        target_price=float(data.get("target_price", 0)),
        time_stop_days=int(data.get("time_stop_days", 0)),
    )


def load_backtest_scenario(data: dict) -> BacktestScenario:
    """Load a BacktestScenario from a dict.

    Expected format:
    {
        "initial_capital": 100000,
        "price_series": {
            "AAPL": [{"date": "2026-01-02", "open": 150, ...}, ...],
            ...
        },
        "signal_events": [
            {"date": "2026-01-02", "asset": "AAPL", "action": "enter", ...},
            ...
        ],
        "benchmark": [{"date": "2026-01-02", "close": 5000, ...}, ...],
        "costs": {"commission_per_trade": 1.0, "slippage_bps": 5},
        "risk_rules": {"max_position_pct": 25, "max_drawdown_pct": 20, "min_confidence": 60}
    }
    """
    initial_capital = float(data.get("initial_capital", 100000))

    price_series: Dict[str, List[PricePoint]] = {}
    for asset, bars in data.get("price_series", {}).items():
        price_series[asset] = load_price_points(bars)

    signal_events = [load_signal_event(e) for e in data.get("signal_events", [])]
    benchmark = load_price_points(data.get("benchmark", []))

    cost_data = data.get("costs", {})
    costs = CostConfig(
        commission_per_trade=float(cost_data.get("commission_per_trade", 0)),
        slippage_bps=float(cost_data.get("slippage_bps", 5)),
    )

    risk_data = data.get("risk_rules", {})
    risk_rules = RiskRules(
        max_position_pct=float(risk_data.get("max_position_pct", 25)),
        max_drawdown_pct=float(risk_data.get("max_drawdown_pct", 20)),
        min_confidence=float(risk_data.get("min_confidence", 60)),
    )

    return BacktestScenario(
        initial_capital=initial_capital,
        price_series=price_series,
        signal_events=signal_events,
        benchmark=benchmark,
        costs=costs,
        risk_rules=risk_rules,
    )


# ---------------------------------------------------------------------------
# Simulation Engine
# ---------------------------------------------------------------------------

def _estimate_cost(value: float, costs: CostConfig) -> Tuple[float, float, float]:
    """Estimate commission, slippage, and total cost."""
    commission = costs.commission_per_trade
    slippage = abs(value) * (costs.slippage_bps / 10000)
    return round(commission, 2), round(slippage, 2), round(commission + slippage, 2)


def _pct(value: float, total: float) -> float:
    """Percentage, safe against division by zero."""
    return (value / total * 100) if total else 0.0


def _dates_union(price_series: Dict[str, List[PricePoint]]) -> List[str]:
    """Get sorted union of all dates across all assets and benchmark."""
    dates = set()
    for bars in price_series.values():
        for bar in bars:
            dates.add(bar.date)
    return sorted(dates)


def _build_close_map(bars: List[PricePoint]) -> Dict[str, float]:
    """Build date -> close price map."""
    return {b.date: b.close for b in bars}


def run_backtest(scenario: BacktestScenario) -> BacktestResult:
    """Run a deterministic backtest simulation.

    Algorithm:
    1. Build chronological date list from all price series.
    2. For each date, update position values, check stops/targets/time-stops.
    3. Process signal events for that date.
    4. Track cash, equity, drawdown, event log.
    5. Close remaining positions at last available price.
    6. Compute summary metrics.
    """
    result = BacktestResult()
    result.initial_capital = scenario.initial_capital
    result.initial_capital_used = scenario.initial_capital
    result.cost_config = {
        "commission_per_trade": scenario.costs.commission_per_trade,
        "slippage_bps": scenario.costs.slippage_bps,
    }
    result.risk_rules = {
        "max_position_pct": scenario.risk_rules.max_position_pct,
        "max_drawdown_pct": scenario.risk_rules.max_drawdown_pct,
        "min_confidence": scenario.risk_rules.min_confidence,
    }

    # Build close price maps per asset
    close_maps: Dict[str, Dict[str, float]] = {}
    for asset, bars in scenario.price_series.items():
        close_maps[asset] = _build_close_map(bars)

    # Benchmark close map
    bench_map = _build_close_map(scenario.benchmark) if scenario.benchmark else {}

    # Get all dates
    all_dates = _dates_union(scenario.price_series)
    if not all_dates:
        result.final_equity = scenario.initial_capital
        return result

    # Index events by date
    events_by_date: Dict[str, List[SignalEvent]] = {}
    for evt in scenario.signal_events:
        events_by_date.setdefault(evt.date, []).append(evt)

    # State
    cash = scenario.initial_capital
    positions: Dict[str, PositionState] = {}
    trades: List[TradeRecord] = []
    event_log: List[EventLogEntry] = []
    blocked_events: List[EventLogEntry] = []
    equity_curve: List[EquityPoint] = []
    peak_equity = scenario.initial_capital
    max_dd = 0.0
    total_fees = 0.0
    total_slippage = 0.0
    total_turnover = 0.0
    halted = False

    # Initial benchmark value
    initial_bench = None
    if scenario.benchmark:
        for d in all_dates:
            if d in bench_map:
                initial_bench = bench_map[d]
                break

    # Asset entry dates for time-stop tracking
    # (already tracked in PositionState.entry_date)

    for date in all_dates:
        # Update position market values (for equity tracking)
        pos_value = 0.0
        for asset, pos in positions.items():
            cm = close_maps.get(asset, {})
            price = cm.get(date, pos.entry_price)
            pos_value += pos.shares * price

        total_equity = cash + pos_value
        if total_equity > peak_equity:
            peak_equity = total_equity
        dd = _pct(peak_equity - total_equity, peak_equity) if peak_equity > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

        # Benchmark value
        bench_val = None
        if initial_bench and date in bench_map:
            bench_val = round(scenario.initial_capital * (bench_map[date] / initial_bench), 2)

        equity_curve.append(EquityPoint(
            date=date,
            cash=round(cash, 2),
            positions_value=round(pos_value, 2),
            total_equity=round(total_equity, 2),
            drawdown_pct=round(dd, 2),
            benchmark_value=bench_val,
        ))

        # Check halt condition
        if halted:
            continue
        if dd >= scenario.risk_rules.max_drawdown_pct:
            halted = True
            event_log.append(EventLogEntry(
                date=date, action="halt", reason=(
                    f"Max drawdown {dd:.1f}% reached limit "
                    f"{scenario.risk_rules.max_drawdown_pct:.1f}%. Trading halted."),
                equity_after=round(total_equity, 2),
            ))

        if halted:
            continue

        # Check stops, targets, and time-stops for open positions
        assets_to_close = []
        for asset, pos in list(positions.items()):
            cm = close_maps.get(asset, {})
            price = cm.get(date)
            if price is None:
                continue

            # Stop loss
            if pos.stop_price > 0 and price <= pos.stop_price:
                assets_to_close.append((asset, price, "stop"))
                continue

            # Target
            if pos.target_price > 0 and price >= pos.target_price:
                assets_to_close.append((asset, price, "target"))
                continue

            # Time stop
            if pos.time_stop_days > 0:
                try:
                    from datetime import datetime as _dt
                    entry_dt = _dt.strptime(pos.entry_date, "%Y-%m-%d")
                    cur_dt = _dt.strptime(date, "%Y-%m-%d")
                    days_held = (cur_dt - entry_dt).days
                    if days_held >= pos.time_stop_days:
                        assets_to_close.append((asset, price, "time_stop"))
                        continue
                except (ValueError, TypeError):
                    pass

        for asset, price, reason_kind in assets_to_close:
            pos = positions[asset]
            trade_value = pos.shares * price
            comm, slip, cost = _estimate_cost(trade_value, scenario.costs)
            cash += trade_value - cost
            total_fees += comm
            total_slippage += slip
            total_turnover += abs(trade_value)

            risk_per_share = abs(pos.entry_price - pos.stop_price) if pos.stop_price > 0 else pos.entry_price
            pnl = (price - pos.entry_price) * pos.shares
            ret_pct = _pct(price - pos.entry_price, pos.entry_price)
            r_mult = pnl / (risk_per_share * abs(pos.shares)) if risk_per_share > 0 and pos.shares != 0 else 0.0

            try:
                from datetime import datetime as _dt
                entry_dt = _dt.strptime(pos.entry_date, "%Y-%m-%d")
                exit_dt = _dt.strptime(date, "%Y-%m-%d")
                holding_days = (exit_dt - entry_dt).days
            except (ValueError, TypeError):
                holding_days = 0

            exit_reason_map = {"stop": "stop_loss", "target": "target_reached", "time_stop": "time_stop"}
            trades.append(TradeRecord(
                asset=asset,
                entry_date=pos.entry_date,
                exit_date=date,
                entry_price=pos.entry_price,
                exit_price=price,
                shares=pos.shares,
                pnl=round(pnl, 2),
                return_pct=round(ret_pct, 2),
                r_multiple=round(r_mult, 2),
                holding_days=holding_days,
                exit_reason=exit_reason_map.get(reason_kind, reason_kind),
                total_costs=round(cost, 2),
            ))

            event_log.append(EventLogEntry(
                date=date, asset=asset, action=reason_kind,
                quantity=-pos.shares, price=price,
                value=round(trade_value, 2), cost=round(cost, 2),
                cash_after=round(cash, 2),
                equity_after=round(cash + sum(
                    close_maps.get(a, {}).get(date, p.entry_price) * p.shares
                    for a, p in positions.items()
                ), 2),
                reason=f"{reason_kind}: price={price:.2f}",
            ))

            del positions[asset]

        # Process signal events for this date
        events = events_by_date.get(date, [])
        for evt in events:
            if halted:
                break

            action = evt.action.lower()
            cm = close_maps.get(evt.asset, {})
            exec_price = evt.price if evt.price > 0 else cm.get(date, 0)

            if exec_price <= 0:
                blocked_events.append(EventLogEntry(
                    date=date, asset=evt.asset, action=action,
                    reason=evt.reason, blocked=True,
                    block_reason="No price available for this date/asset.",
                ))
                continue

            if action == "skip":
                event_log.append(EventLogEntry(
                    date=date, asset=evt.asset, action="skip",
                    reason=evt.reason, blocked=False,
                ))
                continue

            if action == "blocked":
                blocked_events.append(EventLogEntry(
                    date=date, asset=evt.asset, action="blocked",
                    reason=evt.reason, blocked=True,
                    block_reason=evt.reason,
                ))
                continue

            if action == "enter":
                # Gate checks
                block_reason = None
                if evt.confidence > 0 and evt.confidence < scenario.risk_rules.min_confidence:
                    block_reason = (
                        f"Confidence {evt.confidence:.0f} below minimum "
                        f"{scenario.risk_rules.min_confidence:.0f}")
                elif evt.asset in positions:
                    block_reason = f"Already holding {evt.asset}"

                if block_reason:
                    blocked_events.append(EventLogEntry(
                        date=date, asset=evt.asset, action="enter",
                        reason=evt.reason, blocked=True,
                        block_reason=block_reason,
                    ))
                    continue

                qty = evt.quantity if evt.quantity > 0 else 100
                trade_value = qty * exec_price
                comm, slip, cost = _estimate_cost(trade_value, scenario.costs)
                total_needed = trade_value + cost

                # Check max position
                pos_value_now = sum(
                    close_maps.get(a, {}).get(date, p.entry_price) * p.shares
                    for a, p in positions.items()
                )
                total_eq = cash + pos_value_now
                pos_pct = _pct(trade_value, total_eq)
                if pos_pct > scenario.risk_rules.max_position_pct:
                    blocked_events.append(EventLogEntry(
                        date=date, asset=evt.asset, action="enter",
                        reason=evt.reason, blocked=True,
                        block_reason=(
                            f"Position {pos_pct:.1f}% exceeds max "
                            f"{scenario.risk_rules.max_position_pct:.0f}%"),
                    ))
                    continue

                if total_needed > cash:
                    blocked_events.append(EventLogEntry(
                        date=date, asset=evt.asset, action="enter",
                        reason=evt.reason, blocked=True,
                        block_reason="Insufficient cash",
                    ))
                    continue

                cash -= total_needed
                total_fees += comm
                total_slippage += slip
                total_turnover += abs(trade_value)

                positions[evt.asset] = PositionState(
                    asset=evt.asset,
                    shares=qty,
                    entry_price=exec_price,
                    entry_date=date,
                    stop_price=evt.stop_price,
                    target_price=evt.target_price,
                    time_stop_days=evt.time_stop_days,
                    cost_basis=trade_value,
                )

                event_log.append(EventLogEntry(
                    date=date, asset=evt.asset, action="enter",
                    quantity=qty, price=exec_price,
                    value=round(trade_value, 2), cost=round(cost, 2),
                    cash_after=round(cash, 2),
                    equity_after=round(cash + pos_value_now + trade_value, 2),
                    reason=evt.reason,
                ))

            elif action == "add":
                if evt.asset not in positions:
                    blocked_events.append(EventLogEntry(
                        date=date, asset=evt.asset, action="add",
                        reason=evt.reason, blocked=True,
                        block_reason=f"No existing position in {evt.asset}",
                    ))
                    continue

                qty = evt.quantity if evt.quantity > 0 else 50
                trade_value = qty * exec_price
                comm, slip, cost = _estimate_cost(trade_value, scenario.costs)
                total_needed = trade_value + cost

                if total_needed > cash:
                    blocked_events.append(EventLogEntry(
                        date=date, asset=evt.asset, action="add",
                        reason=evt.reason, blocked=True,
                        block_reason="Insufficient cash",
                    ))
                    continue

                pos = positions[evt.asset]
                old_basis = pos.shares * pos.entry_price
                pos.shares += qty
                pos.entry_price = (old_basis + trade_value) / pos.shares if pos.shares > 0 else exec_price
                cash -= total_needed
                total_fees += comm
                total_slippage += slip
                total_turnover += abs(trade_value)

                event_log.append(EventLogEntry(
                    date=date, asset=evt.asset, action="add",
                    quantity=qty, price=exec_price,
                    value=round(trade_value, 2), cost=round(cost, 2),
                    cash_after=round(cash, 2),
                    equity_after=round(cash + sum(
                        close_maps.get(a, {}).get(date, p.entry_price) * p.shares
                        for a, p in positions.items()
                    ), 2),
                    reason=evt.reason,
                ))

            elif action == "trim":
                if evt.asset not in positions:
                    blocked_events.append(EventLogEntry(
                        date=date, asset=evt.asset, action="trim",
                        reason=evt.reason, blocked=True,
                        block_reason=f"No existing position in {evt.asset}",
                    ))
                    continue

                pos = positions[evt.asset]
                qty = abs(evt.quantity) if evt.quantity != 0 else pos.shares * 0.5
                qty = min(qty, pos.shares)

                trade_value = qty * exec_price
                comm, slip, cost = _estimate_cost(trade_value, scenario.costs)
                cash += trade_value - cost
                total_fees += comm
                total_slippage += slip
                total_turnover += abs(trade_value)

                pos.shares -= qty
                if pos.shares <= 0:
                    del positions[evt.asset]

                event_log.append(EventLogEntry(
                    date=date, asset=evt.asset, action="trim",
                    quantity=-qty, price=exec_price,
                    value=round(trade_value, 2), cost=round(cost, 2),
                    cash_after=round(cash, 2),
                    equity_after=round(cash + sum(
                        close_maps.get(a, {}).get(date, p.entry_price) * p.shares
                        for a, p in positions.items()
                    ), 2),
                    reason=evt.reason,
                ))

            elif action == "exit":
                if evt.asset not in positions:
                    blocked_events.append(EventLogEntry(
                        date=date, asset=evt.asset, action="exit",
                        reason=evt.reason, blocked=True,
                        block_reason=f"No existing position in {evt.asset}",
                    ))
                    continue

                pos = positions[evt.asset]
                trade_value = pos.shares * exec_price
                comm, slip, cost = _estimate_cost(trade_value, scenario.costs)
                cash += trade_value - cost
                total_fees += comm
                total_slippage += slip
                total_turnover += abs(trade_value)

                risk_per_share = abs(pos.entry_price - pos.stop_price) if pos.stop_price > 0 else pos.entry_price
                pnl = (exec_price - pos.entry_price) * pos.shares
                ret_pct = _pct(exec_price - pos.entry_price, pos.entry_price)
                r_mult = pnl / (risk_per_share * abs(pos.shares)) if risk_per_share > 0 and pos.shares != 0 else 0.0

                try:
                    from datetime import datetime as _dt
                    entry_dt = _dt.strptime(pos.entry_date, "%Y-%m-%d")
                    exit_dt = _dt.strptime(date, "%Y-%m-%d")
                    holding_days = (exit_dt - entry_dt).days
                except (ValueError, TypeError):
                    holding_days = 0

                trades.append(TradeRecord(
                    asset=evt.asset,
                    entry_date=pos.entry_date,
                    exit_date=date,
                    entry_price=pos.entry_price,
                    exit_price=exec_price,
                    shares=pos.shares,
                    pnl=round(pnl, 2),
                    return_pct=round(ret_pct, 2),
                    r_multiple=round(r_mult, 2),
                    holding_days=holding_days,
                    exit_reason="signal_exit",
                    total_costs=round(cost, 2),
                ))

                event_log.append(EventLogEntry(
                    date=date, asset=evt.asset, action="exit",
                    quantity=-pos.shares, price=exec_price,
                    value=round(trade_value, 2), cost=round(cost, 2),
                    cash_after=round(cash, 2),
                    equity_after=round(cash + sum(
                        close_maps.get(a, {}).get(date, p.entry_price) * p.shares
                        for a, p in positions.items()
                    ), 2),
                    reason=evt.reason,
                ))

                del positions[evt.asset]

            elif action in ("stop", "target", "time_stop"):
                # These are handled by the automatic checks above
                # But if explicitly fired as events, log them
                if evt.asset in positions:
                    pos = positions[evt.asset]
                    trade_value = pos.shares * exec_price
                    comm, slip, cost = _estimate_cost(trade_value, scenario.costs)
                    cash += trade_value - cost
                    total_fees += comm
                    total_slippage += slip
                    total_turnover += abs(trade_value)

                    risk_per_share = abs(pos.entry_price - pos.stop_price) if pos.stop_price > 0 else pos.entry_price
                    pnl = (exec_price - pos.entry_price) * pos.shares
                    ret_pct = _pct(exec_price - pos.entry_price, pos.entry_price)
                    r_mult = pnl / (risk_per_share * abs(pos.shares)) if risk_per_share > 0 and pos.shares != 0 else 0.0

                    try:
                        from datetime import datetime as _dt
                        entry_dt = _dt.strptime(pos.entry_date, "%Y-%m-%d")
                        exit_dt = _dt.strptime(date, "%Y-%m-%d")
                        holding_days = (exit_dt - entry_dt).days
                    except (ValueError, TypeError):
                        holding_days = 0

                    reason_map = {"stop": "stop_loss", "target": "target_reached", "time_stop": "time_stop"}
                    trades.append(TradeRecord(
                        asset=evt.asset,
                        entry_date=pos.entry_date,
                        exit_date=date,
                        entry_price=pos.entry_price,
                        exit_price=exec_price,
                        shares=pos.shares,
                        pnl=round(pnl, 2),
                        return_pct=round(ret_pct, 2),
                        r_multiple=round(r_mult, 2),
                        holding_days=holding_days,
                        exit_reason=reason_map.get(action, action),
                        total_costs=round(cost, 2),
                    ))

                    event_log.append(EventLogEntry(
                        date=date, asset=evt.asset, action=action,
                        quantity=-pos.shares, price=exec_price,
                        value=round(trade_value, 2), cost=round(cost, 2),
                        cash_after=round(cash, 2),
                        equity_after=round(cash + sum(
                            close_maps.get(a, {}).get(date, p.entry_price) * p.shares
                            for a, p in positions.items()
                        ), 2),
                        reason=evt.reason,
                    ))

                    del positions[evt.asset]

    # Close remaining positions at last available price
    if all_dates:
        last_date = all_dates[-1]
        for asset, pos in list(positions.items()):
            cm = close_maps.get(asset, {})
            price = cm.get(last_date, pos.entry_price)
            trade_value = pos.shares * price
            comm, slip, cost = _estimate_cost(trade_value, scenario.costs)
            cash += trade_value - cost
            total_fees += comm
            total_slippage += slip
            total_turnover += abs(trade_value)

            risk_per_share = abs(pos.entry_price - pos.stop_price) if pos.stop_price > 0 else pos.entry_price
            pnl = (price - pos.entry_price) * pos.shares
            ret_pct = _pct(price - pos.entry_price, pos.entry_price)
            r_mult = pnl / (risk_per_share * abs(pos.shares)) if risk_per_share > 0 and pos.shares != 0 else 0.0

            try:
                from datetime import datetime as _dt
                entry_dt = _dt.strptime(pos.entry_date, "%Y-%m-%d")
                exit_dt = _dt.strptime(last_date, "%Y-%m-%d")
                holding_days = (exit_dt - entry_dt).days
            except (ValueError, TypeError):
                holding_days = 0

            trades.append(TradeRecord(
                asset=asset,
                entry_date=pos.entry_date,
                exit_date=last_date,
                entry_price=pos.entry_price,
                exit_price=price,
                shares=pos.shares,
                pnl=round(pnl, 2),
                return_pct=round(ret_pct, 2),
                r_multiple=round(r_mult, 2),
                holding_days=holding_days,
                exit_reason="end_of_backtest",
                total_costs=round(cost, 2),
            ))

            event_log.append(EventLogEntry(
                date=last_date, asset=asset, action="exit",
                quantity=-pos.shares, price=price,
                value=round(trade_value, 2), cost=round(cost, 2),
                cash_after=round(cash, 2),
                equity_after=round(cash, 2),
                reason="End of backtest — closing open positions",
            ))

        positions.clear()

    # Final equity
    final_equity = cash

    # Compute metrics
    total_return = _pct(final_equity - scenario.initial_capital, scenario.initial_capital)

    winning = [t for t in trades if t.pnl > 0]
    losing = [t for t in trades if t.pnl <= 0]
    win_rate = _pct(len(winning), len(trades)) if trades else 0.0
    avg_ret = sum(t.return_pct for t in trades) / len(trades) if trades else 0.0
    avg_r = sum(t.r_multiple for t in trades) / len(trades) if trades else 0.0

    # Benchmark return
    bench_return = 0.0
    alpha = 0.0
    if scenario.benchmark and initial_bench:
        last_bench = bench_map.get(all_dates[-1]) if all_dates else None
        if last_bench:
            bench_return = _pct(last_bench - initial_bench, initial_bench)
            alpha = total_return - bench_return

    # Populate result
    result.final_equity = round(final_equity, 2)
    result.total_return_pct = round(total_return, 2)
    result.max_drawdown_pct = round(max_dd, 2)
    result.total_trades = len(trades)
    result.winning_trades = len(winning)
    result.losing_trades = len(losing)
    result.win_rate = round(win_rate, 2)
    result.avg_trade_return_pct = round(avg_ret, 2)
    result.avg_r_multiple = round(avg_r, 2)
    result.total_fees = round(total_fees, 2)
    result.total_slippage = round(total_slippage, 2)
    result.total_costs = round(total_fees + total_slippage, 2)
    result.benchmark_return_pct = round(bench_return, 2)
    result.alpha_vs_benchmark = round(alpha, 2)
    result.total_turnover = round(total_turnover, 2)
    result.trades = trades
    result.equity_curve = equity_curve
    result.event_log = event_log
    result.blocked_events = blocked_events

    return result


def run_backtest_from_dict(data: dict) -> dict:
    """Run full backtest from a JSON dict. Convenience function."""
    scenario = load_backtest_scenario(data)
    result = run_backtest(scenario)
    return _result_to_dict(result)


# ---------------------------------------------------------------------------
# JSON Serialization
# ---------------------------------------------------------------------------

def _result_to_dict(result: Any) -> Any:
    """Convert dataclass result to plain dict for JSON."""
    if hasattr(result, "__dataclass_fields__"):
        return {k: _result_to_dict(v) for k, v in result.__dict__.items()}
    if isinstance(result, dict):
        return {k: _result_to_dict(v) for k, v in result.items()}
    if isinstance(result, list):
        return [_result_to_dict(item) for item in result]
    return result


# ---------------------------------------------------------------------------
# Markdown Renderer
# ---------------------------------------------------------------------------

def render_backtest_markdown(result: BacktestResult) -> str:
    """Render backtest result as Markdown."""
    lines: List[str] = []

    lines.append("# Backtest / Signal Replay Report")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append(f"- **Initial Capital:** {result.initial_capital:,.2f}")
    lines.append(f"- **Final Equity:** {result.final_equity:,.2f}")
    lines.append(f"- **Total Return:** {result.total_return_pct:+.2f}%")
    lines.append(f"- **Max Drawdown:** {result.max_drawdown_pct:.2f}%")
    lines.append("")

    # Trade stats
    lines.append("## Trade Statistics")
    lines.append(f"- **Total Trades:** {result.total_trades}")
    lines.append(f"- **Winning Trades:** {result.winning_trades}")
    lines.append(f"- **Losing Trades:** {result.losing_trades}")
    lines.append(f"- **Win Rate:** {result.win_rate:.1f}%")
    lines.append(f"- **Avg Trade Return:** {result.avg_trade_return_pct:+.2f}%")
    lines.append(f"- **Avg R-Multiple:** {result.avg_r_multiple:+.2f}")
    lines.append("")

    # Costs
    lines.append("## Costs")
    lines.append(f"- **Total Fees:** {result.total_fees:,.2f}")
    lines.append(f"- **Total Slippage:** {result.total_slippage:,.2f}")
    lines.append(f"- **Total Costs:** {result.total_costs:,.2f}")
    lines.append(f"- **Total Turnover:** {result.total_turnover:,.2f}")
    lines.append("")

    # Benchmark
    if result.benchmark_return_pct != 0 or result.alpha_vs_benchmark != 0:
        lines.append("## Benchmark Comparison")
        lines.append(f"- **Benchmark Return:** {result.benchmark_return_pct:+.2f}%")
        lines.append(f"- **Alpha vs Benchmark:** {result.alpha_vs_benchmark:+.2f}%")
        lines.append("")

    # Trades
    if result.trades:
        lines.append("## Trades")
        lines.append("")
        lines.append("| Asset | Entry | Exit | Shares | Entry Px | Exit Px | P&L | Return | R-Mult | Days | Exit Reason |")
        lines.append("|-------|-------|------|--------|----------|---------|-----|--------|--------|------|-------------|")
        for t in result.trades:
            lines.append(
                f"| {t.asset} | {t.entry_date} | {t.exit_date} "
                f"| {t.shares:+,.0f} | {t.entry_price:,.2f} | {t.exit_price:,.2f} "
                f"| {t.pnl:+,.2f} | {t.return_pct:+.2f}% | {t.r_multiple:+.2f} "
                f"| {t.holding_days} | {t.exit_reason} |")
        lines.append("")

    # Equity curve (compact)
    if result.equity_curve:
        lines.append("## Equity Curve")
        lines.append("")
        lines.append("| Date | Cash | Positions | Total | Drawdown | Benchmark |")
        lines.append("|------|------|-----------|-------|----------|-----------|")
        for ep in result.equity_curve:
            bench_str = f"{ep.benchmark_value:,.2f}" if ep.benchmark_value is not None else "-"
            lines.append(
                f"| {ep.date} | {ep.cash:,.2f} | {ep.positions_value:,.2f} "
                f"| {ep.total_equity:,.2f} | {ep.drawdown_pct:.2f}% | {bench_str} |")
        lines.append("")

    # Event log
    if result.event_log:
        lines.append("## Event Log")
        lines.append("")
        for evt in result.event_log:
            val_str = f" value={evt.value:,.0f}" if evt.value else ""
            cost_str = f" cost={evt.cost:,.2f}" if evt.cost else ""
            lines.append(
                f"- **{evt.date}** [{evt.action}] {evt.asset}{val_str}{cost_str} — {evt.reason}")
        lines.append("")

    # Blocked events
    if result.blocked_events:
        lines.append("## Blocked / Skipped Events")
        lines.append("")
        for evt in result.blocked_events:
            lines.append(
                f"- **{evt.date}** [{evt.action}] {evt.asset} — BLOCKED: {evt.block_reason}")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by invest-signal-kit backtest lab. Not investment advice.*")
    return "\n".join(lines)
