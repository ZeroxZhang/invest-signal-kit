"""Portfolio rebalance and trade planning engine.

Deterministic order generation from current holdings, target allocations,
candidate signals, risk policy, trade constraints, and cost assumptions.
Produces proposed orders (BUY, SELL, TRIM, ADD, HOLD, SKIP) with
before/after exposure, guardrail checks, and phased execution plans.

This is research tooling, not financial advice. No broker integration,
no automatic trading.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------

@dataclass
class RebalanceHolding:
    """A current portfolio position for rebalancing."""
    code: str = ""
    name: str = ""
    asset_type: str = "stock"
    sector: str = ""
    shares: float = 0.0
    entry_price: float = 0.0
    current_price: float = 0.0
    stop_price: float = 0.0
    direction: str = "long"

    @property
    def market_value(self) -> float:
        return self.shares * self.current_price

    @property
    def cost_basis(self) -> float:
        return self.shares * self.entry_price

    @property
    def unrealized_pnl(self) -> float:
        if self.direction == "short":
            return (self.entry_price - self.current_price) * self.shares
        return (self.current_price - self.entry_price) * self.shares


@dataclass
class RebalancePolicy:
    """Risk policy and guardrail limits for rebalancing."""
    max_position_pct: float = 20.0
    """Maximum single position as % of total portfolio value after rebalance."""

    max_sector_pct: float = 35.0
    """Maximum single sector as % of total portfolio value after rebalance."""

    max_risk_budget_pct: float = 6.0
    """Maximum total risk as % of portfolio."""

    min_cash_reserve_pct: float = 5.0
    """Minimum cash as % of total portfolio value after rebalance."""

    max_turnover_pct: float = 50.0
    """Maximum total order value as % of portfolio (buy + sell)."""

    max_single_order_pct: float = 10.0
    """Maximum single order value as % of portfolio."""

    min_order_value: float = 500.0
    """Minimum order value. Orders below this are skipped."""

    lot_size: int = 1
    """Lot size for rounding share quantities."""

    rebalance_threshold_pct: float = 2.0
    """Minimum drift from target to trigger a rebalance order."""

    watchlist_min_score: float = 60.0
    """Minimum signal score for candidate trades to pass gates."""

    sector_limits: Dict[str, float] = field(default_factory=dict)
    """Per-sector override limits. Key = sector name, value = max %."""


@dataclass
class TargetAllocation:
    """Target weight for a position or sector."""
    code: str = ""
    """Instrument code. Empty string means sector-level target."""
    sector: str = ""
    """Sector name. Used for sector-level targets."""
    target_pct: float = 0.0
    """Target weight as % of total portfolio."""


@dataclass
class CandidateTrade:
    """A candidate signal for potential inclusion in the rebalance plan."""
    code: str = ""
    name: str = ""
    direction: str = "bullish"
    asset_type: str = "stock"
    sector: str = ""
    current_price: float = 0.0
    stop_price: float = 0.0
    signal_score: float = 0.0
    action_level: str = "information"
    thesis_quality: float = 0.0
    market_confirmation: float = 0.0
    risk_execution: float = 0.0
    ev_quality: str = "negative_ev"
    proposed_shares: float = 0.0
    """Proposed number of shares to buy."""
    proposed_value: float = 0.0
    """Proposed order value (may be set instead of shares)."""


@dataclass
class CostAssumptions:
    """Transaction cost model."""
    commission_per_order: float = 0.0
    """Fixed commission per order."""

    slippage_bps: float = 5.0
    """Slippage in basis points of trade value."""

    min_commission: float = 0.0
    """Minimum commission per order."""


@dataclass
class TradeConstraints:
    """Trade-level constraints."""
    lot_size: int = 1
    """Round share quantities to this lot size."""
    min_order_value: float = 500.0
    """Skip orders below this value."""
    max_order_value_pct: float = 10.0
    """Max single order as % of portfolio."""


# ---------------------------------------------------------------------------
# Output Data Structures
# ---------------------------------------------------------------------------

@dataclass
class ProposedOrder:
    """A single proposed order in the rebalance plan."""
    action: str = "HOLD"
    """BUY, SELL, TRIM, ADD, HOLD, or SKIP."""
    code: str = ""
    name: str = ""
    sector: str = ""
    asset_type: str = ""
    direction: str = "long"
    shares: float = 0.0
    """Number of shares to trade (positive = buy, negative = sell)."""
    order_value: float = 0.0
    """Absolute value of the order."""
    estimated_commission: float = 0.0
    estimated_slippage: float = 0.0
    estimated_total_cost: float = 0.0
    price: float = 0.0
    """Execution price assumption (current price)."""
    current_weight_pct: float = 0.0
    """Position weight before order."""
    target_weight_pct: float = 0.0
    """Target weight after order."""
    new_weight_pct: float = 0.0
    """Projected weight after order."""
    drift_pct: float = 0.0
    """Difference between current and target weight."""
    rationale: str = ""
    """Human-readable explanation of why this order was generated."""
    blockers: List[str] = field(default_factory=list)
    """Reasons this order cannot proceed."""
    warnings: List[str] = field(default_factory=list)
    """Non-blocking concerns about this order."""
    phase: str = "immediate"
    """Execution phase: immediate, wait-for-trigger, reduce-risk-first, blocked."""
    priority: int = 0
    """Sort order within phase (lower = earlier)."""


@dataclass
class GuardrailCheck:
    """Result of a single guardrail check."""
    rule: str = ""
    description: str = ""
    current_value: float = 0.0
    limit_value: float = 0.0
    passes: bool = True
    severity: str = "info"
    """info, warning, or error."""


@dataclass
class ExecutionPhase:
    """A group of orders in the same execution phase."""
    phase: str = ""
    description: str = ""
    orders: List[ProposedOrder] = field(default_factory=list)
    total_value: float = 0.0


@dataclass
class RebalanceResult:
    """Complete rebalance plan result."""
    # Before state
    before_total_value: float = 0.0
    before_cash: float = 0.0
    before_invested: float = 0.0
    before_positions: List[Dict[str, Any]] = field(default_factory=list)
    before_sectors: List[Dict[str, Any]] = field(default_factory=list)

    # After state
    after_total_value: float = 0.0
    after_cash: float = 0.0
    after_invested: float = 0.0
    after_positions: List[Dict[str, Any]] = field(default_factory=list)
    after_sectors: List[Dict[str, Any]] = field(default_factory=list)

    # Orders
    orders: List[ProposedOrder] = field(default_factory=list)
    buy_count: int = 0
    sell_count: int = 0
    trim_count: int = 0
    add_count: int = 0
    hold_count: int = 0
    skip_count: int = 0

    # Costs
    total_commission: float = 0.0
    total_slippage: float = 0.0
    total_cost: float = 0.0
    turnover_value: float = 0.0
    turnover_pct: float = 0.0

    # Guardrails
    guardrails: List[GuardrailCheck] = field(default_factory=list)
    guardrail_breaches: int = 0

    # Execution plan
    execution_phases: List[ExecutionPhase] = field(default_factory=list)

    # Blockers and warnings
    blockers: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core Rebalance Engine
# ---------------------------------------------------------------------------

def _pct(value: float, total: float) -> float:
    """Percentage, safe against division by zero."""
    return (value / total * 100) if total else 0.0


def _round_lots(shares: float, lot_size: int) -> float:
    """Round share quantity down to nearest lot size."""
    if lot_size <= 0:
        return shares
    return float(int(shares / lot_size) * lot_size)


def _compute_position_map(
    holdings: List[RebalanceHolding],
) -> Dict[str, RebalanceHolding]:
    """Build code -> holding map. Last wins on duplicate codes."""
    pos_map: Dict[str, RebalanceHolding] = {}
    for h in holdings:
        if h.code:
            pos_map[h.code] = h
    return pos_map


def _compute_sector_values(
    holdings: List[RebalanceHolding],
) -> Dict[str, float]:
    """Aggregate market value by sector."""
    sector_vals: Dict[str, float] = {}
    for h in holdings:
        s = h.sector or "Unknown"
        sector_vals[s] = sector_vals.get(s, 0.0) + h.market_value
    return sector_vals


def _compute_weights(
    holdings: List[RebalanceHolding],
    cash: float,
) -> Tuple[float, Dict[str, float], Dict[str, float]]:
    """Compute total value, position weights, sector weights."""
    total = sum(h.market_value for h in holdings) + cash
    pos_weights = {h.code: _pct(h.market_value, total) for h in holdings if h.code}
    sector_vals = _compute_sector_values(holdings)
    sector_weights = {s: _pct(v, total) for s, v in sector_vals.items()}
    return total, pos_weights, sector_weights


def _estimate_cost(
    order_value: float,
    cost: CostAssumptions,
) -> Tuple[float, float, float]:
    """Estimate commission, slippage, and total cost for an order."""
    commission = max(cost.commission_per_order, cost.min_commission)
    slippage = order_value * (cost.slippage_bps / 10000)
    return round(commission, 2), round(slippage, 2), round(commission + slippage, 2)


def _check_candidate_gates(
    candidate: CandidateTrade,
    min_score: float = 60.0,
) -> List[str]:
    """Check if a candidate signal passes readiness gates.

    Gates:
    1. signal_score >= min_score
    2. action_level in (candidate, action)
    3. ev_quality not negative_ev
    4. has positive proposed_shares or proposed_value
    """
    blockers = []
    if candidate.signal_score < min_score:
        blockers.append(
            f"Signal score {candidate.signal_score:.0f} below minimum {min_score:.0f}")
    if candidate.action_level not in ("candidate", "action"):
        blockers.append(
            f"Action level '{candidate.action_level}' not yet candidate/action")
    if candidate.ev_quality == "negative_ev":
        blockers.append("Expected value is negative")
    if candidate.proposed_shares <= 0 and candidate.proposed_value <= 0:
        blockers.append("No proposed position size")
    return blockers


def generate_orders(
    holdings: List[RebalanceHolding],
    cash: float,
    policy: RebalancePolicy,
    targets: List[TargetAllocation],
    candidates: Optional[List[CandidateTrade]] = None,
    costs: Optional[CostAssumptions] = None,
) -> RebalanceResult:
    """Generate rebalance orders from current state, targets, and candidates.

    Algorithm:
    1. Compute current portfolio state (weights, sectors).
    2. Build target weight map from allocations.
    3. For each holding: compute drift from target, generate TRIM/ADD/HOLD.
    4. For each candidate signal: check gates, generate BUY/SKIP.
    5. Apply trade constraints (lot size, min order, max order).
    6. Enforce guardrails (max position, max sector, min cash, max turnover).
    7. Assign execution phases.
    8. Compute before/after exposure and costs.
    """
    if costs is None:
        costs = CostAssumptions()

    pos_map = _compute_position_map(holdings)
    total_value, pos_weights, sector_weights = _compute_weights(holdings, cash)

    # Build target map
    target_map: Dict[str, float] = {}
    target_sector_map: Dict[str, float] = {}
    for t in targets:
        if t.code:
            target_map[t.code] = t.target_pct
        elif t.sector:
            target_sector_map[t.sector] = t.target_pct

    orders: List[ProposedOrder] = []
    after_holdings = list(holdings)
    after_cash = cash
    constraints = TradeConstraints(
        lot_size=policy.lot_size,
        min_order_value=policy.min_order_value,
        max_order_value_pct=policy.max_single_order_pct,
    )

    # --- Phase 1: Generate orders for existing holdings ---
    for h in holdings:
        if not h.code:
            continue

        current_wt = pos_weights.get(h.code, 0.0)
        target_wt = target_map.get(h.code, None)
        order = ProposedOrder(
            code=h.code,
            name=h.name,
            sector=h.sector,
            asset_type=h.asset_type,
            direction=h.direction,
            price=h.current_price,
            current_weight_pct=round(current_wt, 2),
        )

        if target_wt is None:
            # No target specified — hold
            order.action = "HOLD"
            order.target_weight_pct = round(current_wt, 2)
            order.new_weight_pct = round(current_wt, 2)
            order.rationale = "No target allocation specified; maintaining position."
            order.phase = "immediate"
            orders.append(order)
            continue

        drift = current_wt - target_wt
        order.target_weight_pct = round(target_wt, 2)
        order.drift_pct = round(drift, 2)

        if abs(drift) < policy.rebalance_threshold_pct:
            # Within threshold — hold
            order.action = "HOLD"
            order.new_weight_pct = round(current_wt, 2)
            order.rationale = (
                f"Current weight {current_wt:.1f}% is within "
                f"{policy.rebalance_threshold_pct:.1f}% of target {target_wt:.1f}%. "
                f"Drift {drift:+.2f}% is below threshold.")
            order.phase = "immediate"
            orders.append(order)
            continue

        if drift > 0:
            # Overweight — trim or sell
            excess_value = (drift / 100) * total_value
            excess_shares = excess_value / h.current_price if h.current_price > 0 else 0
            excess_shares = _round_lots(excess_shares, constraints.lot_size)

            if excess_shares <= 0 or excess_value < constraints.min_order_value:
                order.action = "SKIP"
                order.rationale = (
                    f"Calculated trim of {excess_shares:.0f} shares "
                    f"(${excess_value:,.0f}) below minimum order "
                    f"${constraints.min_order_value:,.0f}.")
                order.phase = "blocked"
                orders.append(order)
                continue

            # Check if selling entire position
            if excess_shares >= h.shares:
                order.action = "SELL"
                order.shares = -h.shares
                order.order_value = round(h.shares * h.current_price, 2)
                order.rationale = (
                    f"Selling entire position. Current {current_wt:.1f}% "
                    f"drifts {drift:+.1f}% from target {target_wt:.1f}%.")
            else:
                order.action = "TRIM"
                order.shares = -excess_shares
                order.order_value = round(excess_shares * h.current_price, 2)
                order.rationale = (
                    f"Trimming {excess_shares:.0f} shares to reduce weight "
                    f"from {current_wt:.1f}% toward target {target_wt:.1f}%.")

            # Cost estimate
            comm, slip, total_c = _estimate_cost(order.order_value, costs)
            order.estimated_commission = comm
            order.estimated_slippage = slip
            order.estimated_total_cost = total_c

            new_shares = h.shares + order.shares  # order.shares is negative
            new_value = new_shares * h.current_price
            order.new_weight_pct = round(_pct(new_value, total_value), 2)

            # Trim reduces risk — immediate
            order.phase = "immediate"
            order.priority = 1

        else:
            # Underweight — add or buy
            deficit_value = (-drift / 100) * total_value
            deficit_shares = deficit_value / h.current_price if h.current_price > 0 else 0
            deficit_shares = _round_lots(deficit_shares, constraints.lot_size)

            if deficit_shares <= 0 or deficit_value < constraints.min_order_value:
                order.action = "SKIP"
                order.rationale = (
                    f"Calculated add of {deficit_shares:.0f} shares "
                    f"(${deficit_value:,.0f}) below minimum order "
                    f"${constraints.min_order_value:,.0f}.")
                order.phase = "blocked"
                orders.append(order)
                continue

            # Check max single order
            max_order_val = total_value * (constraints.max_order_value_pct / 100)
            if deficit_value > max_order_val:
                deficit_shares = _round_lots(
                    max_order_val / h.current_price, constraints.lot_size)
                deficit_value = deficit_shares * h.current_price
                order.warnings.append(
                    f"Order capped at ${max_order_val:,.0f} "
                    f"({constraints.max_order_value_pct:.0f}% of portfolio).")

            # Check if we have enough cash
            comm, slip, total_c = _estimate_cost(deficit_value, costs)
            total_needed = deficit_value + total_c
            if total_needed > after_cash:
                # Reduce to available cash
                avail = max(0, after_cash - comm - slip)
                deficit_shares = _round_lots(
                    avail / h.current_price, constraints.lot_size)
                deficit_value = deficit_shares * h.current_price
                comm, slip, total_c = _estimate_cost(deficit_value, costs)
                if deficit_shares <= 0:
                    order.action = "SKIP"
                    order.rationale = "Insufficient cash for this order."
                    order.phase = "blocked"
                    order.blockers.append("Insufficient cash")
                    orders.append(order)
                    continue
                order.warnings.append(
                    f"Order reduced to {deficit_shares:.0f} shares due to cash constraint.")

            order.action = "ADD"
            order.shares = deficit_shares
            order.order_value = round(deficit_value, 2)
            order.estimated_commission = comm
            order.estimated_slippage = slip
            order.estimated_total_cost = total_c

            new_shares = h.shares + deficit_shares
            new_value = new_shares * h.current_price
            order.new_weight_pct = round(_pct(new_value, total_value), 2)
            order.rationale = (
                f"Adding {deficit_shares:.0f} shares to increase weight "
                f"from {current_wt:.1f}% toward target {target_wt:.1f}%.")

            # Phase: check if this worsens risk
            if current_wt > policy.max_position_pct:
                order.phase = "reduce-risk-first"
                order.priority = 3
                order.warnings.append(
                    "Position already above max; consider trimming other positions first.")
            elif after_cash - total_needed < total_value * (policy.min_cash_reserve_pct / 100):
                order.phase = "wait-for-trigger"
                order.priority = 2
                order.warnings.append(
                    "Order would reduce cash below reserve target.")
            else:
                order.phase = "immediate"
                order.priority = 2

        orders.append(order)

    # --- Phase 2: Generate orders for candidate signals ---
    candidates = candidates or []
    for c in candidates:
        order = ProposedOrder(
            code=c.code,
            name=c.name,
            sector=c.sector,
            asset_type=c.asset_type,
            direction=c.direction,
            price=c.current_price,
        )

        # Check gates
        gate_blockers = _check_candidate_gates(c, policy.watchlist_min_score)
        if gate_blockers:
            order.action = "SKIP"
            order.blockers = gate_blockers
            order.rationale = (
                f"Candidate {c.code} does not pass readiness gates: "
                + "; ".join(gate_blockers))
            order.phase = "blocked"
            order.current_weight_pct = 0.0
            order.target_weight_pct = 0.0
            orders.append(order)
            continue

        # Determine order size
        if c.proposed_shares > 0:
            buy_shares = _round_lots(c.proposed_shares, constraints.lot_size)
        elif c.proposed_value > 0 and c.current_price > 0:
            buy_shares = _round_lots(c.proposed_value / c.current_price, constraints.lot_size)
        else:
            order.action = "SKIP"
            order.rationale = "No valid proposed position size."
            order.phase = "blocked"
            orders.append(order)
            continue

        buy_value = buy_shares * c.current_price
        comm, slip, total_c = _estimate_cost(buy_value, costs)
        total_needed = buy_value + total_c

        # Check min order
        if buy_value < constraints.min_order_value:
            order.action = "SKIP"
            order.rationale = (
                f"Order value ${buy_value:,.0f} below minimum "
                f"${constraints.min_order_value:,.0f}.")
            order.phase = "blocked"
            orders.append(order)
            continue

        # Check max single order
        max_order_val = total_value * (constraints.max_order_value_pct / 100)
        if buy_value > max_order_val:
            buy_shares = _round_lots(
                max_order_val / c.current_price, constraints.lot_size)
            buy_value = buy_shares * c.current_price
            comm, slip, total_c = _estimate_cost(buy_value, costs)
            order.warnings.append(
                f"Order capped at ${max_order_val:,.0f} "
                f"({constraints.max_order_value_pct:.0f}% of portfolio).")

        # Check cash
        if total_needed > after_cash:
            avail = max(0, after_cash - comm - slip)
            buy_shares = _round_lots(avail / c.current_price, constraints.lot_size)
            buy_value = buy_shares * c.current_price
            comm, slip, total_c = _estimate_cost(buy_value, costs)
            if buy_shares <= 0:
                order.action = "SKIP"
                order.rationale = "Insufficient cash for candidate trade."
                order.phase = "blocked"
                order.blockers.append("Insufficient cash")
                orders.append(order)
                continue
            order.warnings.append(
                f"Order reduced to {buy_shares:.0f} shares due to cash constraint.")

        order.action = "BUY"
        order.shares = buy_shares
        order.order_value = round(buy_value, 2)
        order.estimated_commission = comm
        order.estimated_slippage = slip
        order.estimated_total_cost = total_c
        order.current_weight_pct = 0.0

        # Target weight includes this new position
        new_total = total_value  # approximate
        order.target_weight_pct = round(_pct(buy_value, new_total), 2)
        order.new_weight_pct = round(_pct(buy_value, new_total), 2)

        target_in_targets = target_map.get(c.code)
        if target_in_targets is not None:
            order.target_weight_pct = round(target_in_targets, 2)

        order.rationale = (
            f"Candidate signal passes gates (score={c.signal_score:.0f}, "
            f"level={c.action_level}, ev={c.ev_quality}). "
            f"Buying {buy_shares:.0f} shares at ${c.current_price:,.2f}.")

        # Phase: new positions go through reduce-risk-first if risk is elevated
        if c.signal_score >= 70 and c.action_level == "action":
            order.phase = "immediate"
            order.priority = 4
        else:
            order.phase = "wait-for-trigger"
            order.priority = 5
            order.warnings.append(
                "Consider waiting for stronger signal confirmation.")

        orders.append(order)

    # --- Phase 3: Apply guardrails and compute after-state ---
    _apply_guardrails(orders, holdings, cash, policy, total_value, costs)
    result = _build_result(orders, holdings, cash, policy, total_value, costs)

    return result


def _apply_guardrails(
    orders: List[ProposedOrder],
    holdings: List[RebalanceHolding],
    cash: float,
    policy: RebalancePolicy,
    total_value: float,
    costs: CostAssumptions,
) -> None:
    """Apply policy guardrails and block/downgrade orders as needed."""
    # Compute projected after-state
    projected_positions: Dict[str, float] = {}
    for h in holdings:
        if h.code:
            projected_positions[h.code] = h.market_value

    projected_cash = cash
    total_buy_value = 0.0
    total_sell_value = 0.0

    # Check max single order
    max_order_val = total_value * (policy.max_single_order_pct / 100)
    for o in orders:
        if o.action in ("BUY", "ADD") and o.order_value > max_order_val:
            o.blockers.append(
                f"Order value ${o.order_value:,.0f} exceeds max single order "
                f"${max_order_val:,.0f} ({policy.max_single_order_pct:.0f}%)")
            if o.phase != "blocked":
                o.phase = "blocked"

        # Track projected state for orders that aren't blocked
        if o.phase != "blocked" and o.action in ("BUY", "ADD"):
            projected_positions[o.code] = projected_positions.get(o.code, 0.0) + o.order_value
            projected_cash -= o.order_value + o.estimated_total_cost
            total_buy_value += o.order_value
        elif o.phase != "blocked" and o.action in ("SELL", "TRIM"):
            projected_positions[o.code] = projected_positions.get(o.code, 0.0) - o.order_value
            projected_cash += o.order_value - o.estimated_total_cost
            total_sell_value += o.order_value

    # Check max position after orders
    for o in orders:
        if o.phase == "blocked":
            continue
        pos_val = projected_positions.get(o.code, 0.0)
        pos_pct = _pct(pos_val, total_value)
        limit = policy.max_position_pct
        if pos_pct > limit:
            o.warnings.append(
                f"Post-order position weight {pos_pct:.1f}% would exceed "
                f"max {limit:.0f}%. Consider reducing order size.")
            # Downgrade to wait-for-trigger if not already blocked
            if o.phase == "immediate":
                o.phase = "wait-for-trigger"

    # Check sector limits after orders
    sector_vals: Dict[str, float] = {}
    for h in holdings:
        s = h.sector or "Unknown"
        sector_vals[s] = sector_vals.get(s, 0.0) + h.market_value

    for o in orders:
        if o.phase == "blocked":
            continue
        if o.action in ("BUY", "ADD"):
            s = o.sector or "Unknown"
            sector_vals[s] = sector_vals.get(s, 0.0) + o.order_value
        elif o.action in ("SELL", "TRIM"):
            s = o.sector or "Unknown"
            sector_vals[s] = sector_vals.get(s, 0.0) - o.order_value

    for o in orders:
        if o.phase == "blocked":
            continue
        s = o.sector or "Unknown"
        sector_pct = _pct(sector_vals.get(s, 0.0), total_value)
        limit = policy.sector_limits.get(s, policy.max_sector_pct)
        if sector_pct > limit:
            o.warnings.append(
                f"Post-order sector '{s}' would be {sector_pct:.1f}%, "
                f"limit is {limit:.0f}%.")

    # Check cash reserve
    cash_pct = _pct(projected_cash, total_value)
    if cash_pct < policy.min_cash_reserve_pct:
        # Downgrade buy orders
        for o in orders:
            if o.action in ("BUY", "ADD") and o.phase == "immediate":
                o.phase = "wait-for-trigger"
                o.warnings.append(
                    f"Post-order cash {cash_pct:.1f}% would be below "
                    f"reserve target {policy.min_cash_reserve_pct:.0f}%.")

    # Check turnover
    turnover = total_buy_value + total_sell_value
    turnover_pct = _pct(turnover, total_value)
    if turnover_pct > policy.max_turnover_pct:
        for o in orders:
            if o.action in ("BUY", "ADD") and o.phase == "immediate":
                o.warnings.append(
                    f"Total turnover {turnover_pct:.1f}% exceeds "
                    f"max {policy.max_turnover_pct:.0f}%.")


def _build_result(
    orders: List[ProposedOrder],
    holdings: List[RebalanceHolding],
    cash: float,
    policy: RebalancePolicy,
    total_value: float,
    costs: CostAssumptions,
) -> RebalanceResult:
    """Build the full RebalanceResult from generated orders."""
    result = RebalanceResult()

    # Before state
    result.before_total_value = round(total_value, 2)
    result.before_cash = round(cash, 2)
    result.before_invested = round(total_value - cash, 2)

    sector_vals = _compute_sector_values(holdings)
    for h in holdings:
        if not h.code:
            continue
        result.before_positions.append({
            "code": h.code,
            "name": h.name,
            "sector": h.sector,
            "shares": h.shares,
            "market_value": round(h.market_value, 2),
            "weight_pct": round(_pct(h.market_value, total_value), 2),
        })

    for s, v in sorted(sector_vals.items()):
        result.before_sectors.append({
            "sector": s,
            "market_value": round(v, 2),
            "weight_pct": round(_pct(v, total_value), 2),
        })

    # Count actions
    for o in orders:
        if o.action == "BUY":
            result.buy_count += 1
        elif o.action == "SELL":
            result.sell_count += 1
        elif o.action == "TRIM":
            result.trim_count += 1
        elif o.action == "ADD":
            result.add_count += 1
        elif o.action == "HOLD":
            result.hold_count += 1
        elif o.action == "SKIP":
            result.skip_count += 1

    result.orders = orders

    # Costs
    for o in orders:
        if o.phase != "blocked" and o.action not in ("HOLD", "SKIP"):
            result.total_commission += o.estimated_commission
            result.total_slippage += o.estimated_slippage
            result.total_cost += o.estimated_total_cost
            result.turnover_value += o.order_value

    result.total_commission = round(result.total_commission, 2)
    result.total_slippage = round(result.total_slippage, 2)
    result.total_cost = round(result.total_cost, 2)
    result.turnover_value = round(result.turnover_value, 2)
    result.turnover_pct = round(_pct(result.turnover_value, total_value), 2)

    # Compute after state
    after_positions = {}
    for h in holdings:
        if h.code:
            after_positions[h.code] = {
                "code": h.code,
                "name": h.name,
                "sector": h.sector,
                "shares": h.shares,
                "price": h.current_price,
            }

    after_cash = cash
    for o in orders:
        if o.phase == "blocked" or o.action in ("HOLD", "SKIP"):
            continue
        if o.code in after_positions:
            after_positions[o.code]["shares"] += o.shares
        if o.action in ("BUY", "ADD"):
            after_cash -= o.order_value + o.estimated_total_cost
        elif o.action in ("SELL", "TRIM"):
            after_cash += o.order_value - o.estimated_total_cost

    after_invested = sum(
        p["shares"] * p["price"] for p in after_positions.values()
    )
    after_total = after_invested + after_cash

    result.after_total_value = round(after_total, 2)
    result.after_cash = round(after_cash, 2)
    result.after_invested = round(after_invested, 2)

    after_sector_vals: Dict[str, float] = {}
    for p in after_positions.values():
        mv = p["shares"] * p["price"]
        result.after_positions.append({
            "code": p["code"],
            "name": p["name"],
            "sector": p["sector"],
            "shares": round(p["shares"], 4),
            "market_value": round(mv, 2),
            "weight_pct": round(_pct(mv, after_total), 2),
        })
        s = p["sector"] or "Unknown"
        after_sector_vals[s] = after_sector_vals.get(s, 0.0) + mv

    for s, v in sorted(after_sector_vals.items()):
        result.after_sectors.append({
            "sector": s,
            "market_value": round(v, 2),
            "weight_pct": round(_pct(v, after_total), 2),
        })

    # Guardrails
    guardrails = []

    # Position limits
    for p in result.after_positions:
        g = GuardrailCheck(
            rule="max_position",
            description=f"Position {p['code']} weight after rebalance",
            current_value=p["weight_pct"],
            limit_value=policy.max_position_pct,
            passes=p["weight_pct"] <= policy.max_position_pct,
            severity="warning" if p["weight_pct"] <= policy.max_position_pct else "error",
        )
        guardrails.append(g)

    # Sector limits
    for s in result.after_sectors:
        limit = policy.sector_limits.get(s["sector"], policy.max_sector_pct)
        g = GuardrailCheck(
            rule="max_sector",
            description=f"Sector '{s['sector']}' weight after rebalance",
            current_value=s["weight_pct"],
            limit_value=limit,
            passes=s["weight_pct"] <= limit,
            severity="warning" if s["weight_pct"] <= limit else "error",
        )
        guardrails.append(g)

    # Cash reserve
    cash_pct = _pct(after_cash, after_total)
    g = GuardrailCheck(
        rule="min_cash_reserve",
        description="Cash reserve after rebalance",
        current_value=round(cash_pct, 2),
        limit_value=policy.min_cash_reserve_pct,
        passes=cash_pct >= policy.min_cash_reserve_pct,
        severity="warning" if cash_pct >= policy.min_cash_reserve_pct else "error",
    )
    guardrails.append(g)

    # Turnover
    g = GuardrailCheck(
        rule="max_turnover",
        description="Total turnover as % of portfolio",
        current_value=result.turnover_pct,
        limit_value=policy.max_turnover_pct,
        passes=result.turnover_pct <= policy.max_turnover_pct,
        severity="warning" if result.turnover_pct <= policy.max_turnover_pct else "error",
    )
    guardrails.append(g)

    result.guardrails = guardrails
    result.guardrail_breaches = sum(1 for g in guardrails if not g.passes)

    # Execution phases
    phase_map: Dict[str, List[ProposedOrder]] = {}
    for o in orders:
        phase_map.setdefault(o.phase, []).append(o)

    phase_descriptions = {
        "immediate": "Orders that can execute now without constraint violations.",
        "wait-for-trigger": "Orders pending a trigger condition (price, cash, or signal).",
        "reduce-risk-first": "Orders that require reducing existing risk before execution.",
        "blocked": "Orders blocked by guardrail or readiness constraints.",
    }

    for phase_name in ["immediate", "wait-for-trigger", "reduce-risk-first", "blocked"]:
        phase_orders = phase_map.get(phase_name, [])
        if not phase_orders:
            continue
        phase_orders.sort(key=lambda o: o.priority)
        ep = ExecutionPhase(
            phase=phase_name,
            description=phase_descriptions.get(phase_name, ""),
            orders=phase_orders,
            total_value=round(sum(o.order_value for o in phase_orders), 2),
        )
        result.execution_phases.append(ep)

    # Aggregate blockers/warnings
    for o in orders:
        for b in o.blockers:
            result.blockers.append(f"{o.code}: {b}")
        for w in o.warnings:
            result.warnings.append(f"{o.code}: {w}")

    return result


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_rebalance_holding(data: dict) -> RebalanceHolding:
    """Load a RebalanceHolding from a dict."""
    return RebalanceHolding(
        code=data.get("code", ""),
        name=data.get("name", ""),
        asset_type=data.get("asset_type", "stock"),
        sector=data.get("sector", ""),
        shares=float(data.get("shares", 0)),
        entry_price=float(data.get("entry_price", 0)),
        current_price=float(data.get("current_price", 0)),
        stop_price=float(data.get("stop_price", 0)),
        direction=data.get("direction", "long"),
    )


def load_rebalance_policy(data: dict) -> RebalancePolicy:
    """Load a RebalancePolicy from a dict."""
    return RebalancePolicy(
        max_position_pct=float(data.get("max_position_pct", 20)),
        max_sector_pct=float(data.get("max_sector_pct", 35)),
        max_risk_budget_pct=float(data.get("max_risk_budget_pct", 6)),
        min_cash_reserve_pct=float(data.get("min_cash_reserve_pct", 5)),
        max_turnover_pct=float(data.get("max_turnover_pct", 50)),
        max_single_order_pct=float(data.get("max_single_order_pct", 10)),
        min_order_value=float(data.get("min_order_value", 500)),
        lot_size=int(data.get("lot_size", 1)),
        rebalance_threshold_pct=float(data.get("rebalance_threshold_pct", 2)),
        watchlist_min_score=float(data.get("watchlist_min_score", 60)),
        sector_limits=data.get("sector_limits", {}),
    )


def load_target_allocation(data: dict) -> TargetAllocation:
    """Load a TargetAllocation from a dict."""
    return TargetAllocation(
        code=data.get("code", ""),
        sector=data.get("sector", ""),
        target_pct=float(data.get("target_pct", 0)),
    )


def load_candidate_trade(data: dict) -> CandidateTrade:
    """Load a CandidateTrade from a dict."""
    return CandidateTrade(
        code=data.get("code", ""),
        name=data.get("name", ""),
        direction=data.get("direction", "bullish"),
        asset_type=data.get("asset_type", "stock"),
        sector=data.get("sector", ""),
        current_price=float(data.get("current_price", 0)),
        stop_price=float(data.get("stop_price", 0)),
        signal_score=float(data.get("signal_score", 0)),
        action_level=data.get("action_level", "information"),
        thesis_quality=float(data.get("thesis_quality", 0)),
        market_confirmation=float(data.get("market_confirmation", 0)),
        risk_execution=float(data.get("risk_execution", 0)),
        ev_quality=data.get("ev_quality", "negative_ev"),
        proposed_shares=float(data.get("proposed_shares", 0)),
        proposed_value=float(data.get("proposed_value", 0)),
    )


def load_cost_assumptions(data: dict) -> CostAssumptions:
    """Load CostAssumptions from a dict."""
    return CostAssumptions(
        commission_per_order=float(data.get("commission_per_order", 0)),
        slippage_bps=float(data.get("slippage_bps", 5)),
        min_commission=float(data.get("min_commission", 0)),
    )


def load_rebalance_plan(data: dict) -> Tuple[
    List[RebalanceHolding], float, RebalancePolicy,
    List[TargetAllocation], List[CandidateTrade], CostAssumptions,
]:
    """Load a full rebalance plan from a dict.

    Expected format:
    {
        "holdings": [...],
        "cash": 50000,
        "policy": {...},
        "targets": [...],
        "candidates": [...],
        "costs": {...}
    }
    """
    holdings = [load_rebalance_holding(h) for h in data.get("holdings", [])]
    cash = float(data.get("cash", 0))
    policy = load_rebalance_policy(data.get("policy", {}))
    targets = [load_target_allocation(t) for t in data.get("targets", [])]
    candidates = [load_candidate_trade(c) for c in data.get("candidates", [])]
    costs = load_cost_assumptions(data.get("costs", {}))

    return holdings, cash, policy, targets, candidates, costs


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


def run_rebalance_analysis(data: dict) -> dict:
    """Run full rebalance analysis from a JSON dict.

    Convenience function that loads, generates orders, and serializes.
    """
    holdings, cash, policy, targets, candidates, costs = load_rebalance_plan(data)
    result = generate_orders(holdings, cash, policy, targets, candidates, costs)
    return _result_to_dict(result)


# ---------------------------------------------------------------------------
# Markdown Renderer
# ---------------------------------------------------------------------------

def render_rebalance_markdown(result: RebalanceResult) -> str:
    """Render rebalance plan as Markdown."""
    lines: List[str] = []

    lines.append("# Rebalance / Trade Plan")
    lines.append("")

    # Before Summary
    lines.append("## Current Portfolio")
    lines.append(f"- **Total Value:** {result.before_total_value:,.2f}")
    lines.append(f"- **Cash:** {result.before_cash:,.2f} "
                 f"({_pct(result.before_cash, result.before_total_value):.1f}%)")
    lines.append(f"- **Invested:** {result.before_invested:,.2f} "
                 f"({_pct(result.before_invested, result.before_total_value):.1f}%)")
    lines.append("")

    if result.before_positions:
        lines.append("### Current Positions")
        lines.append("")
        lines.append("| Code | Name | Sector | Shares | Value | Weight % |")
        lines.append("|------|------|--------|--------|-------|----------|")
        for p in result.before_positions:
            lines.append(
                f"| {p['code']} | {p['name']} | {p['sector']} "
                f"| {p['shares']:,.0f} | {p['market_value']:,.0f} "
                f"| {p['weight_pct']:.1f}% |")
        lines.append("")

    if result.before_sectors:
        lines.append("### Current Sectors")
        lines.append("")
        lines.append("| Sector | Value | Weight % |")
        lines.append("|--------|-------|----------|")
        for s in result.before_sectors:
            lines.append(f"| {s['sector']} | {s['market_value']:,.0f} | {s['weight_pct']:.1f}% |")
        lines.append("")

    # Proposed Orders
    lines.append("## Proposed Orders")
    lines.append("")

    active_orders = [o for o in result.orders if o.action not in ("HOLD", "SKIP")]
    hold_orders = [o for o in result.orders if o.action == "HOLD"]
    skip_orders = [o for o in result.orders if o.action == "SKIP"]

    if active_orders:
        lines.append("| Action | Code | Name | Shares | Value | Cost | Current % | Target % | Phase |")
        lines.append("|--------|------|------|--------|-------|------|-----------|----------|-------|")
        for o in active_orders:
            shares_str = f"{o.shares:+,.0f}"
            lines.append(
                f"| **{o.action}** | {o.code} | {o.name} "
                f"| {shares_str} | {o.order_value:,.0f} "
                f"| {o.estimated_total_cost:,.0f} "
                f"| {o.current_weight_pct:.1f}% | {o.target_weight_pct:.1f}% "
                f"| {o.phase} |")
        lines.append("")

        # Rationale for each active order
        lines.append("### Order Rationale")
        lines.append("")
        for o in active_orders:
            lines.append(f"**{o.action} {o.code}** ({o.name})")
            lines.append(f"- {o.rationale}")
            if o.blockers:
                for b in o.blockers:
                    lines.append(f"- BLOCKER: {b}")
            if o.warnings:
                for w in o.warnings:
                    lines.append(f"- WARNING: {w}")
            lines.append("")

    if hold_orders:
        lines.append("### Hold Positions")
        lines.append("")
        for o in hold_orders:
            lines.append(f"- **{o.code}** ({o.name}): {o.rationale}")
        lines.append("")

    if skip_orders:
        lines.append("### Skipped Orders")
        lines.append("")
        for o in skip_orders:
            lines.append(f"- **{o.code}** ({o.name}): {o.rationale}")
            if o.blockers:
                for b in o.blockers:
                    lines.append(f"  - BLOCKER: {b}")
        lines.append("")

    # Costs
    lines.append("## Transaction Costs")
    lines.append(f"- **Total Commission:** {result.total_commission:,.2f}")
    lines.append(f"- **Total Slippage:** {result.total_slippage:,.2f}")
    lines.append(f"- **Total Cost:** {result.total_cost:,.2f}")
    lines.append(f"- **Turnover:** {result.turnover_value:,.2f} ({result.turnover_pct:.1f}%)")
    lines.append("")

    # After Summary
    lines.append("## Projected Portfolio After Rebalance")
    lines.append(f"- **Total Value:** {result.after_total_value:,.2f}")
    lines.append(f"- **Cash:** {result.after_cash:,.2f} "
                 f"({_pct(result.after_cash, result.after_total_value):.1f}%)")
    lines.append(f"- **Invested:** {result.after_invested:,.2f} "
                 f"({_pct(result.after_invested, result.after_total_value):.1f}%)")
    lines.append("")

    if result.after_positions:
        lines.append("### Projected Positions")
        lines.append("")
        lines.append("| Code | Name | Sector | Shares | Value | Weight % |")
        lines.append("|------|------|--------|--------|-------|----------|")
        for p in result.after_positions:
            lines.append(
                f"| {p['code']} | {p['name']} | {p['sector']} "
                f"| {p['shares']:,.0f} | {p['market_value']:,.0f} "
                f"| {p['weight_pct']:.1f}% |")
        lines.append("")

    if result.after_sectors:
        lines.append("### Projected Sectors")
        lines.append("")
        lines.append("| Sector | Value | Weight % |")
        lines.append("|--------|-------|----------|")
        for s in result.after_sectors:
            lines.append(f"| {s['sector']} | {s['market_value']:,.0f} | {s['weight_pct']:.1f}% |")
        lines.append("")

    # Guardrails
    lines.append("## Guardrails")
    lines.append("")
    if result.guardrails:
        lines.append("| Rule | Description | Current | Limit | Status |")
        lines.append("|------|-------------|---------|-------|--------|")
        for g in result.guardrails:
            status = "PASS" if g.passes else "BREACH"
            lines.append(
                f"| {g.rule} | {g.description} "
                f"| {g.current_value:.1f}% | {g.limit_value:.1f}% | {status} |")
        lines.append("")

    if result.guardrail_breaches > 0:
        lines.append(f"**{result.guardrail_breaches} guardrail breach(es) detected.**")
        lines.append("")

    # Execution Plan
    lines.append("## Execution Plan")
    lines.append("")
    for phase in result.execution_phases:
        lines.append(f"### {phase.phase.replace('-', ' ').title()}")
        lines.append(f"*{phase.description}*")
        lines.append("")
        if phase.orders:
            lines.append("| Action | Code | Shares | Value | Phase |")
            lines.append("|--------|------|--------|-------|-------|")
            for o in phase.orders:
                lines.append(
                    f"| {o.action} | {o.code} | {o.shares:+,.0f} "
                    f"| {o.order_value:,.0f} | {o.phase} |")
            lines.append(f"- **Phase Total:** {phase.total_value:,.0f}")
            lines.append("")

    # Blockers and Warnings
    if result.blockers:
        lines.append("## Blockers")
        for b in result.blockers:
            lines.append(f"- {b}")
        lines.append("")

    if result.warnings:
        lines.append("## Warnings")
        for w in result.warnings:
            lines.append(f"- {w}")
        lines.append("")

    # Summary stats
    lines.append("## Order Summary")
    lines.append(f"- Buy: {result.buy_count}")
    lines.append(f"- Sell: {result.sell_count}")
    lines.append(f"- Trim: {result.trim_count}")
    lines.append(f"- Add: {result.add_count}")
    lines.append(f"- Hold: {result.hold_count}")
    lines.append(f"- Skip: {result.skip_count}")
    lines.append("")

    lines.append("---")
    lines.append("*Generated by invest-signal-kit rebalance engine. Not investment advice.*")
    return "\n".join(lines)
