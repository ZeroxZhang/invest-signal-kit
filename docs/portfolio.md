# Portfolio Risk Engine

The portfolio risk engine extends invest-signal-kit from single-signal analysis to portfolio-level investment decision and risk management.

## Data Model

### Holding

A single portfolio position:

| Field | Type | Description |
|-------|------|-------------|
| `code` | string | Instrument code (e.g. "512480") |
| `name` | string | Instrument name |
| `asset_type` | string | ETF, stock, index, bond, commodity, other |
| `sector` | string | Sector classification |
| `shares` | float | Number of shares held |
| `entry_price` | float | Average entry price |
| `current_price` | float | Current market price |
| `stop_price` | float | Stop-loss price level |
| `direction` | string | "long" or "short" |

### PortfolioPolicy

Risk policy limits:

| Field | Default | Description |
|-------|---------|-------------|
| `max_position_pct` | 20 | Maximum single position as % of portfolio |
| `max_sector_pct` | 35 | Maximum single sector as % of portfolio |
| `max_risk_budget_pct` | 6 | Maximum total risk as % of portfolio |
| `max_drawdown_pct` | 15 | Maximum acceptable drawdown from peak |
| `watchlist_min_score` | 60 | Minimum score for candidate to pass watchlist |
| `max_candidate_risk_pct` | 2 | Maximum per-trade risk as % of portfolio |
| `sector_limits` | {} | Per-sector override limits |

### CandidateSignal

A proposed trade for portfolio evaluation:

| Field | Type | Description |
|-------|------|-------------|
| `code` | string | Instrument code |
| `name` | string | Instrument name |
| `direction` | string | bullish/bearish/neutral |
| `sector` | string | Sector classification |
| `expected_return_pct` | float | Expected return % |
| `risk_pct` | float | Risk as % of position (stop distance) |
| `position_size_pct` | float | Proposed size as % of portfolio |
| `signal_score` | float | Score from signal engine (0-100) |
| `action_level` | string | information/watch/candidate/action |
| `thesis_quality` | float | Thesis quality score (0-100) |
| `market_confirmation` | float | Market confirmation score (0-100) |
| `risk_execution` | float | Risk execution score (0-100) |
| `ev_quality` | string | positive_ev/marginal/negative_ev |

### StressScenario

Deterministic stress test:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Scenario name |
| `description` | string | Scenario description |
| `market_shock_pct` | float | Broad market shock (applied to all) |
| `sector_shocks` | dict | Per-sector shocks {sector: shock_pct} |
| `single_name_shocks` | dict | Per-instrument shocks {code: shock_pct} |
| `liquidity_haircut_pct` | float | Liquidity haircut (multiplicative) |

## Formulas

### Exposure Calculation

```
position_value = shares * current_price
total_invested = sum(position_value)
total_portfolio = total_invested + cash
exposure_pct = position_value / total_portfolio * 100
sector_pct = sum(position_values_in_sector) / total_portfolio * 100
position_risk = shares * |current_price - stop_price|
total_risk_pct = sum(position_risk) / total_portfolio * 100
```

### Concentration Check

Three rules are checked:

1. **Position concentration**: `position_pct > max_position_pct`
2. **Sector concentration**: `sector_pct > max_sector_pct` (or per-sector override)
3. **Position risk limit**: `position_risk_pct > max_candidate_risk_pct`

### Risk Budget

```
risk_budget = total_value * max_risk_budget_pct / 100
total_risk = sum(shares * |current - stop|) for all holdings
utilization = total_risk / risk_budget * 100
remaining = risk_budget - total_risk
```

Portfolio is "over budget" when `total_risk > risk_budget`.

### Stress Testing

Per position:
```
effective_shock = market_shock + sector_shock + single_name_shock
shocked_value = current_value * (1 + effective_shock/100) * (1 - liquidity_haircut/100)
```

- Market shock applies to ALL positions
- Sector shock is additive, only to matching sector
- Single-name shock is additive, only to matching code
- Liquidity haircut is multiplicative, applied after other shocks
- Cash is unaffected by any shock

### Candidate Ranking

Pass criteria:
1. `signal_score >= watchlist_min_score`
2. Adding position does not breach `max_position_pct`
3. Adding position does not breach `max_sector_pct`
4. `risk_pct <= max_candidate_risk_pct`
5. `ev_quality` is not `negative_ev`

Ranking: primary by `signal_score` descending, secondary by `expected_return_pct` descending.

## CLI Usage

### Portfolio Analysis

```bash
# JSON output
invest-signal-kit portfolio examples/portfolio_workflow.json

# Markdown output
invest-signal-kit portfolio examples/portfolio_workflow.json --format markdown

# Save to file
invest-signal-kit portfolio examples/portfolio_workflow.json -o report.json
```

### Batch Analysis

```bash
# Analyze multiple signals
invest-signal-kit batch examples/etf_signal.json examples/stock_shift_signal.json

# Markdown summary
invest-signal-kit batch examples/*.json --format markdown -o batch_report.md
```

## Web UI

The Portfolio tab in the web UI provides:

1. **Portfolio editor** - paste or load portfolio JSON
2. **Summary metrics** - total value, cash, invested, total risk
3. **Risk budget gauge** - visual utilization bar with color coding
4. **Position exposures table** - per-position value, exposure %, P&L, risk
5. **Sector exposures table** - aggregated by sector
6. **Candidate watchlist** - ranked candidates with pass/fail and issues
7. **Stress test results** - scenario cards with position-level breakdown
8. **Blockers & warnings** - portfolio-level issues

### Loading Data

- Click "Load Example" to load the built-in portfolio example
- Or paste your own portfolio JSON into the editor and click "Analyze"

## JSON Format

```json
{
  "holdings": [
    {
      "code": "512480",
      "name": "Semiconductor ETF",
      "asset_type": "ETF",
      "sector": "Technology",
      "shares": 50000,
      "entry_price": 1.02,
      "current_price": 1.08,
      "stop_price": 0.96,
      "direction": "long"
    }
  ],
  "cash": 150000,
  "policy": {
    "max_position_pct": 25,
    "max_sector_pct": 40,
    "max_risk_budget_pct": 8,
    "max_drawdown_pct": 15,
    "watchlist_min_score": 55,
    "max_candidate_risk_pct": 2,
    "sector_limits": {"Technology": 30}
  },
  "candidates": [...],
  "scenarios": [...]
}
```

See `examples/portfolio_workflow.json` for a complete example.

## Disclaimer

This is research tooling, not financial advice. No real brokerage integration, no trading automation.
