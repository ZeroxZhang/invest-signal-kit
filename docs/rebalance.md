# Rebalance / Trade Plan Engine

The rebalance engine generates deterministic trade plans from current portfolio state, target allocations, candidate signals, risk policy, and trade constraints.

This is research tooling, not financial advice. No broker integration, no automatic trading.

## Data Model

### Input

A rebalance plan JSON contains:

```json
{
    "holdings": [ ... ],
    "cash": 75000,
    "policy": { ... },
    "targets": [ ... ],
    "candidates": [ ... ],
    "costs": { ... }
}
```

#### Holdings

Each holding represents a current portfolio position:

| Field | Type | Description |
|-------|------|-------------|
| `code` | string | Instrument identifier |
| `name` | string | Instrument name |
| `asset_type` | string | `stock`, `ETF`, `bond`, etc. |
| `sector` | string | Sector classification |
| `shares` | number | Current share count |
| `entry_price` | number | Average entry price |
| `current_price` | number | Current market price |
| `stop_price` | number | Stop-loss price |
| `direction` | string | `long` or `short` |

#### Policy

Risk policy and guardrail limits:

| Field | Default | Description |
|-------|---------|-------------|
| `max_position_pct` | 20 | Maximum single position as % of portfolio |
| `max_sector_pct` | 35 | Maximum single sector as % of portfolio |
| `max_risk_budget_pct` | 6 | Maximum total risk as % of portfolio |
| `min_cash_reserve_pct` | 5 | Minimum cash as % of portfolio after rebalance |
| `max_turnover_pct` | 50 | Maximum total order value as % of portfolio |
| `max_single_order_pct` | 10 | Maximum single order value as % of portfolio |
| `min_order_value` | 500 | Minimum order value; orders below are skipped |
| `lot_size` | 1 | Round share quantities to this lot size |
| `rebalance_threshold_pct` | 2 | Minimum drift from target to trigger an order |
| `watchlist_min_score` | 60 | Minimum signal score for candidate trades |
| `sector_limits` | {} | Per-sector override limits |

#### Targets

Target allocations specify desired portfolio weights:

```json
{"code": "NVDA", "target_pct": 18.0}
```

Each target maps an instrument code to its desired weight as % of total portfolio.

#### Candidates

Candidate signals for potential new positions:

| Field | Type | Description |
|-------|------|-------------|
| `code` | string | Instrument identifier |
| `name` | string | Instrument name |
| `direction` | string | `bullish` or `bearish` |
| `sector` | string | Sector classification |
| `current_price` | number | Current market price |
| `signal_score` | number | Score from signal scoring engine (0-100) |
| `action_level` | string | `information`, `watch`, `candidate`, or `action` |
| `ev_quality` | string | `positive_ev`, `marginal`, or `negative_ev` |
| `proposed_shares` | number | Proposed number of shares to buy |
| `proposed_value` | number | Proposed order value (alternative to shares) |

#### Costs

Transaction cost assumptions:

| Field | Default | Description |
|-------|---------|-------------|
| `commission_per_order` | 0 | Fixed commission per order |
| `slippage_bps` | 5 | Slippage in basis points of trade value |
| `min_commission` | 0 | Minimum commission per order |

### Output

The engine produces a `RebalanceResult` with:

- **Before/after state**: total value, cash, invested, position weights, sector weights
- **Orders**: action, shares, value, costs, rationale, blockers, warnings, phase
- **Guardrails**: position limits, sector limits, cash reserve, turnover
- **Execution plan**: phased order groups
- **Costs**: total commission, slippage, turnover

## Order Actions

| Action | Meaning |
|--------|---------|
| `BUY` | Open a new position from a candidate signal |
| `SELL` | Close an entire position |
| `TRIM` | Reduce an overweight position |
| `ADD` | Increase an underweight position |
| `HOLD` | Position is within target threshold |
| `SKIP` | Order blocked by constraints or readiness gates |

## Formulas

### Drift Calculation

```
current_weight = position_market_value / total_portfolio_value * 100
drift = current_weight - target_weight
```

If `|drift| < rebalance_threshold_pct`, the position is held.

### Order Sizing

For overweight positions (drift > 0):
```
excess_value = (drift / 100) * total_value
excess_shares = round_lots(excess_value / current_price, lot_size)
```

For underweight positions (drift < 0):
```
deficit_value = (-drift / 100) * total_value
deficit_shares = round_lots(deficit_value / current_price, lot_size)
```

### Cost Estimation

```
commission = max(commission_per_order, min_commission)
slippage = order_value * (slippage_bps / 10000)
total_cost = commission + slippage
```

### Candidate Gate Checks

A candidate signal passes gates when:
1. `signal_score >= watchlist_min_score`
2. `action_level` is `candidate` or `action`
3. `ev_quality` is not `negative_ev`
4. Has positive `proposed_shares` or `proposed_value`

## Execution Phases

| Phase | Meaning |
|-------|---------|
| `immediate` | Can execute now without constraint violations |
| `wait-for-trigger` | Pending a trigger condition (price, cash, or signal) |
| `reduce-risk-first` | Requires reducing existing risk before execution |
| `blocked` | Blocked by guardrail or readiness constraints |

## Guardrails

After generating orders, the engine checks:

1. **Max position**: post-order position weight <= `max_position_pct`
2. **Max sector**: post-order sector weight <= `max_sector_pct` (or per-sector override)
3. **Min cash reserve**: post-order cash >= `min_cash_reserve_pct` of portfolio
4. **Max turnover**: total order value <= `max_turnover_pct` of portfolio
5. **Max single order**: each order value <= `max_single_order_pct` of portfolio
6. **Min order value**: each order value >= `min_order_value`
7. **Lot size**: share quantities rounded to `lot_size`

Orders that would breach guardrails are downgraded or blocked with clear rationale.

## CLI Usage

```bash
# JSON output (default)
python3 -m invest_signal_kit rebalance examples/rebalance_plan.json

# Markdown report
python3 -m invest_signal_kit rebalance examples/rebalance_plan.json --format markdown

# Save to file
python3 -m invest_signal_kit rebalance examples/rebalance_plan.json -o plan.md
```

## Web UI

The **Rebalance** tab provides:
- JSON editor for rebalance plan input
- Load Example button to populate with sample data
- Generate Plan button to run the engine
- Before/after portfolio summary
- Order blotter with action, shares, value, cost, phase
- Order rationale with blockers and warnings
- Guardrail status table
- Execution plan by phase
- Side-by-side current vs projected positions

## Python API

```python
from invest_signal_kit.rebalance import (
    load_rebalance_plan,
    generate_orders,
    render_rebalance_markdown,
)

# Load from dict
holdings, cash, policy, targets, candidates, costs = load_rebalance_plan(data)

# Generate orders
result = generate_orders(holdings, cash, policy, targets, candidates, costs)

# Render markdown
md = render_rebalance_markdown(result)
```
