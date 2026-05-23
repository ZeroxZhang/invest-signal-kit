# Portfolio Optimizer / Efficient Frontier Lab

Deterministic portfolio optimization from historical price series. Computes
return statistics, finds optimal portfolios under constraints, and generates
the efficient frontier -- all using stdlib-only Python (no NumPy/SciPy).

**This is research tooling, not financial advice.**

## Quick Start

```bash
# Optimize from example config
python -m invest_signal_kit optimize-portfolio examples/optimizer_config.json --format markdown

# Override risk-free rate and max weight
python -m invest_signal_kit optimize-portfolio examples/optimizer_config.json --risk-free-rate 0.05 --max-weight 0.40

# Output to file
python -m invest_signal_kit optimize-portfolio examples/optimizer_config.json -o results.json
```

## What It Does

Given a `price_series` (same format used by backtest and Monte Carlo), the
optimizer:

1. **Computes return statistics** -- annualized mean returns, volatilities,
   covariance matrix, and correlation matrix from daily log-returns.

2. **Finds optimal portfolios:**
   - **Minimum Variance** -- lowest possible portfolio volatility.
   - **Maximum Sharpe** -- best risk-adjusted return (using risk-free rate).
   - **Risk Parity** -- equal risk contribution from each asset.
   - **Target Return** -- minimum-variance portfolio meeting a return target.
   - **Target Volatility** -- maximum-return portfolio within a vol budget.

3. **Generates the efficient frontier** -- a grid of minimum-variance
   portfolios across the range of achievable returns.

4. **Reports risk contribution** -- fraction of total portfolio risk from
   each asset.

5. **Computes turnover** -- sum of absolute weight changes vs. current
   portfolio weights.

## Configuration

All parameters are set in the JSON config file or overridden via CLI flags.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `risk_free_rate` | 0.04 | Annualized risk-free rate for Sharpe calculation |
| `min_weight` | 0.0 | Minimum weight per asset |
| `max_weight` | 1.0 | Maximum weight per asset |
| `max_single_position` | 1.0 | Tighter cap on any single asset |
| `cash_weight` | 0.0 | Fraction held in cash (not optimized) |
| `long_only` | true | If true, weights must be >= 0 |
| `pinned_weights` | {} | Fixed weights for specific assets |
| `current_weights` | {} | Current weights for turnover calculation |
| `target_return` | null | Target annualized return |
| `target_volatility` | null | Target annualized volatility |
| `frontier_points` | 50 | Number of efficient frontier points |
| `seed` | 42 | Random seed for deterministic results |
| `search_iterations` | 5000 | Random samples per optimization |

## Config Format

```json
{
  "risk_free_rate": 0.04,
  "max_weight": 0.50,
  "current_weights": {"AAPL": 0.40, "MSFT": 0.35, "TSLA": 0.25},
  "target_return": 0.10,
  "target_volatility": 0.20,
  "seed": 42,
  "price_series": {
    "AAPL": [{"date": "2025-07-01", "close": 170}, ...],
    "MSFT": [{"date": "2025-07-01", "close": 360}, ...],
    "TSLA": [{"date": "2025-07-01", "close": 240}, ...]
  }
}
```

The `price_series` format is identical to the one used by `backtest` and
`monte-carlo` commands, so the same file can be reused.

## Input Compatibility

The optimizer accepts the same JSON formats as other commands:

- **optimizer_config.json** -- dedicated format with all optimizer fields.
- **generated_scenario.json** -- backtest scenario (uses `price_series` key).
- **monte_carlo_config.json** -- Monte Carlo config (uses `price_series` key).

When using backtest/MC configs, optimizer-specific fields use their defaults
unless overridden via CLI flags.

## Output

### JSON Output

Full structured output including:
- `return_stats` -- mean returns, volatilities, covariance, correlation
- `min_variance` / `max_sharpe` / `risk_parity` -- optimal portfolios
- `target_return_portfolio` / `target_volatility_portfolio` -- if configured
- `frontier` -- efficient frontier points
- `warnings` -- constraint violations or data issues

### Markdown Output

Human-readable report with tables for return statistics, correlation matrix,
optimal portfolio weights/risk contributions, and efficient frontier.

## Algorithms

### Minimum Variance

Random search over the feasible weight space. Generates `search_iterations`
random weight vectors, applies constraints, and selects the one with lowest
portfolio variance.

### Maximum Sharpe

Same random search approach, maximizing `(return - risk_free_rate) / volatility`.

### Risk Parity

Iterative Newton-like algorithm that adjusts weights so each asset contributes
equally to total portfolio risk. Converges when weight changes fall below
1e-8.

### Target Return / Target Volatility

Filtered random search: only portfolios meeting the target constraint are
considered, then the best (min-variance or max-return) is selected.

### Efficient Frontier

Grid of target returns from the minimum to maximum asset return. For each
target, finds the minimum-variance portfolio via the target-return algorithm.

## Constraints

- **Long-only**: weights >= 0 (default).
- **Min/max weight**: per-asset bounds.
- **Max single position**: tighter cap for any one asset.
- **Cash weight**: fixed fraction not subject to optimization.
- **Pinned weights**: assets with fixed weights that are not optimized.

Constraints are applied after each random sample via clipping and
renormalization of free (non-pinned) weights.

## Limitations

- Uses random search, not quadratic programming. Results are approximate but
  deterministic (same seed = same output).
- Assumes log-returns are stationary over the observation window.
- Does not account for transaction costs, taxes, or market impact.
- Short-selling is supported (set `long_only: false`) but results may be
  extreme.

## Web UI

The portfolio optimizer is also available as a tab in the web UI:

```bash
python -m invest_signal_kit serve
```

Navigate to the "Optimizer" tab, paste or load a config, and run the
optimizer interactively.

## Full Workflow

```bash
# 1. Import price data
python -m invest_signal_kit import price data/prices.csv -o examples/prices.json

# 2. Build scenario
python -m invest_signal_kit build-scenario --prices examples/prices.json -o examples/scenario.json

# 3. Run backtest
python -m invest_signal_kit backtest examples/scenario.json --format markdown

# 4. Monte Carlo risk simulation
python -m invest_signal_kit monte-carlo examples/monte_carlo_config.json --format markdown

# 5. Portfolio optimization
python -m invest_signal_kit optimize-portfolio examples/optimizer_config.json --format markdown

# 6. Rebalance plan
python -m invest_signal_kit rebalance examples/rebalance_plan.json --format markdown
```
