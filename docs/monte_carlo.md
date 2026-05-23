# Monte Carlo Risk Simulator / Drawdown Lab

Deterministic Monte Carlo simulation for portfolio and backtest risk analysis.

## Overview

The Monte Carlo simulator generates thousands of possible portfolio paths using historical return distributions. It quantifies downside risk, tail events, and drawdown probability beyond what a single backtest can show.

Key capabilities:
- **Bootstrap resampling**: sample from actual historical daily log-returns
- **Parametric normal**: fit mean/std to historical returns, sample from normal distribution
- **Multi-asset portfolios**: explicit weights per asset, optional cash allocation
- **Rebalancing cadence**: daily, weekly, monthly, or never
- **Stress overlays**: one-time shock, volatility multiplier, drift adjustment
- **Deterministic**: seeded PRNG produces identical output on every run

## Data Model

### MonteCarloConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| initial_capital | float | 100000 | Starting portfolio value |
| num_simulations | int | 1000 | Number of simulation paths |
| horizon_days | int | 252 | Trading days to simulate |
| seed | int | 42 | Random seed for determinism |
| method | str | "bootstrap" | "bootstrap" or "parametric" |
| weights | list | equal | Per-asset weight allocations |
| cash_weight | float | 0.0 | Fraction held in cash (earns 0%) |
| rebalance_cadence | str | "monthly" | "daily", "weekly", "monthly", "never" |
| stress | dict | {} | Stress overlay parameters |
| drawdown_breach_pct | float | 20.0 | Threshold for breach probability |
| confidence_levels | list | [5,25,50,75,95] | Percentiles to compute |

### StressOverlay

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| shock_pct | float | 0.0 | One-time percentage shock at start |
| vol_multiplier | float | 1.0 | Scale return volatility |
| drift_adjust_pct | float | 0.0 | Annualized drift adjustment |

### MonteCarloResult

Output fields:
- **Equity bands**: median_final_equity, mean_final_equity, p5_equity, p25_equity, p75_equity, p95_equity
- **Return metrics**: median_return_pct, mean_return_pct
- **Risk metrics**: prob_loss, prob_drawdown_breach, max_drawdown_median, max_drawdown_p95, max_drawdown_worst
- **Tail risk**: expected_shortfall_pct (CVaR), worst_path_final_equity, worst_path_return_pct
- **Visualization**: sample_paths (first 50 paths for charting)

## JSON Config Format

```json
{
  "initial_capital": 100000,
  "num_simulations": 1000,
  "horizon_days": 252,
  "seed": 42,
  "method": "bootstrap",
  "price_series": {
    "AAPL": [{"date": "2026-01-02", "close": 182}, ...],
    "MSFT": [{"date": "2026-01-02", "close": 372}, ...]
  },
  "weights": [
    {"asset": "AAPL", "weight": 0.5},
    {"asset": "MSFT", "weight": 0.5}
  ],
  "cash_weight": 0.0,
  "rebalance_cadence": "monthly",
  "stress": {
    "shock_pct": -0.10,
    "vol_multiplier": 1.5,
    "drift_adjust_pct": -3.0
  },
  "drawdown_breach_pct": 20,
  "confidence_levels": [5, 25, 50, 75, 95]
}
```

The `price_series` format is the same as used by the backtest engine. Each asset needs at least 2 price points to compute returns.

## CLI Usage

```bash
# Basic simulation
python3 -m invest_signal_kit monte-carlo examples/monte_carlo_config.json

# Markdown report
python3 -m invest_signal_kit monte-carlo examples/monte_carlo_config.json --format markdown

# Stress overlay
python3 -m invest_signal_kit monte-carlo examples/monte_carlo_stress.json --format markdown

# CLI overrides
python3 -m invest_signal_kit monte-carlo config.json \
  --simulations 2000 \
  --seed 123 \
  --method parametric \
  --horizon 126 \
  --weights "AAPL:0.5,MSFT:0.3,TSLA:0.2" \
  --cash-weight 0.1 \
  --rebalance weekly \
  --drawdown-breach 25
```

## Python API

```python
import json
from invest_signal_kit.monte_carlo import (
    load_monte_carlo_config,
    run_monte_carlo,
    render_monte_carlo_markdown,
)

with open("examples/monte_carlo_config.json") as f:
    data = json.load(f)

config, return_series = load_monte_carlo_config(data)
result = run_monte_carlo(config, return_series)

print(f"Median equity: {result.median_final_equity:,.2f}")
print(f"P5 (downside): {result.p5_equity:,.2f}")
print(f"P95 (upside): {result.p95_equity:,.2f}")
print(f"Prob of loss: {result.prob_loss:.1f}%")
print(f"CVaR (5%): {result.expected_shortfall_pct:+.2f}%")

# Markdown report
md = render_monte_carlo_markdown(result)
```

## Simulation Methods

### Bootstrap Resampling
Samples daily log-returns from the historical series with replacement. Preserves the actual distribution shape, including fat tails and skewness. Best when you have enough history (20+ data points).

### Parametric Normal
Fits mean and standard deviation to historical returns, then samples from a normal distribution. Smoother than bootstrap but may underestimate tail risk. Useful when history is short or you want to stress-test distributional assumptions.

## Stress Overlays

Stress overlays modify simulated returns to model adverse conditions:

- **shock_pct**: Applied once on day 1. E.g., -0.10 models a 10% market crash at simulation start.
- **vol_multiplier**: Scales all daily returns' magnitude. 1.5x means 50% more volatile than history.
- **drift_adjust_pct**: Annualized adjustment added to daily returns. -3.0 reduces expected annual return by 3%.

These can be combined. For example, a severe stress scenario might use shock_pct=-0.15, vol_multiplier=2.0, drift_adjust_pct=-5.0.

## Web UI

The **Monte Carlo** tab in the web workstation provides:
- JSON editor for config
- Load Example / Load Stress Example buttons
- Run Simulation to execute client-side
- Summary metrics (equity bands, risk metrics)
- Sample path visualization
- Final equity distribution histogram
- Percentile table

Start with: `python3 -m invest_signal_kit serve --port 8765`
