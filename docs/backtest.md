# Backtest / Signal Replay Lab

The backtest module provides deterministic event-driven backtesting from a JSON scenario file. It simulates signal events over price series and tracks portfolio performance, costs, and risk metrics.

## Data Model

### BacktestScenario

| Field | Type | Description |
|-------|------|-------------|
| `initial_capital` | float | Starting cash (default: 100000) |
| `price_series` | dict[str, list] | OHLCV bars keyed by asset code |
| `signal_events` | list | Ordered signal events to process |
| `benchmark` | list | OHLCV bars for benchmark comparison |
| `costs` | CostConfig | Transaction cost model |
| `risk_rules` | RiskRules | Risk policy constraints |

### SignalEvent

| Field | Type | Description |
|-------|------|-------------|
| `date` | str | Event date (YYYY-MM-DD) |
| `asset` | str | Asset code |
| `action` | str | enter, add, trim, exit, stop, target, time_stop, skip, blocked |
| `quantity` | float | Shares to trade (0 = default) |
| `price` | float | Override execution price (0 = close) |
| `reason` | str | Human-readable reason |
| `confidence` | float | Signal confidence 0-100 |
| `stop_price` | float | Stop-loss price |
| `target_price` | float | Target price |
| `time_stop_days` | int | Maximum holding period |

### Event Types

| Event | Behavior |
|-------|----------|
| `enter` | Open a new position. Blocked if confidence below min, already holding, position too large, or insufficient cash. |
| `add` | Add shares to existing position. Blocked if no position or insufficient cash. |
| `trim` | Reduce position size. |
| `exit` | Close entire position. |
| `stop` | Close position at stop price (also triggered automatically). |
| `target` | Close position at target price (also triggered automatically). |
| `time_stop` | Close position after holding period (also triggered automatically). |
| `skip` | Logged but not executed. |
| `blocked` | Logged as blocked with reason. |

### CostConfig

| Field | Default | Description |
|-------|---------|-------------|
| `commission_per_trade` | 0.0 | Fixed commission per trade |
| `slippage_bps` | 5.0 | Slippage in basis points |

### RiskRules

| Field | Default | Description |
|-------|---------|-------------|
| `max_position_pct` | 25.0 | Max single position as % of equity |
| `max_drawdown_pct` | 20.0 | Max drawdown before halting |
| `min_confidence` | 60.0 | Min confidence to enter |

## Metrics

The engine computes:

- **Total Return**: (final_equity - initial_capital) / initial_capital * 100
- **Max Drawdown**: Largest peak-to-trough decline
- **Win Rate**: winning_trades / total_trades * 100
- **Avg Trade Return**: Mean return_pct across all trades
- **Avg R-Multiple**: Mean R-multiple (P&L / risk per share / shares)
- **Total Costs**: Fees + slippage
- **Benchmark Return**: Benchmark price change over period
- **Alpha**: Total return minus benchmark return

### R-Multiple Formula

```
risk_per_share = |entry_price - stop_price|  (if stop defined, else entry_price)
pnl = (exit_price - entry_price) * shares
r_multiple = pnl / (risk_per_share * |shares|)
```

## CLI Usage

```bash
# JSON output (default)
python3 -m invest_signal_kit backtest examples/backtest_scenario.json

# Markdown report
python3 -m invest_signal_kit backtest examples/backtest_scenario.json --format markdown

# Save to file
python3 -m invest_signal_kit backtest examples/backtest_scenario.json -o report.md
```

## Python API

```python
from invest_signal_kit.backtest import load_backtest_scenario, run_backtest, render_backtest_markdown
import json

with open("examples/backtest_scenario.json") as f:
    data = json.load(f)

scenario = load_backtest_scenario(data)
result = run_backtest(scenario)
print(f"Return: {result.total_return_pct:+.2f}%")
print(f"Max DD: {result.max_drawdown_pct:.2f}%")
print(f"Trades: {result.total_trades}")
```

## Web UI

The **Backtest** tab provides:

- JSON editor for scenario input
- "Load Example" button for pre-loaded demo
- "Run Backtest" to execute simulation
- Summary metrics (performance, trade stats, costs, benchmark)
- ASCII equity curve visualization
- Equity curve table
- Trade table with P&L, R-multiples, exit reasons
- Event log
- Blocked/skipped events with reasons

## Simulation Algorithm

1. Build chronological date list from all price series.
2. For each date:
   - Update position values from close prices.
   - Check automatic stop/target/time-stop conditions.
   - Process signal events (enter, add, trim, exit, etc.).
   - Apply risk rules (max position, max drawdown halt).
   - Log all events with costs.
3. Close remaining open positions at last available price.
4. Compute summary metrics and populate result.
