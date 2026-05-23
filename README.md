# invest-signal-kit

A stdlib-only Python toolkit for structured, auditable investment signal analysis. Includes a professional finance framework with scorecards, scenario modeling, position sizing, portfolio risk management, a decision journal with lifecycle tracking and post-decision review, and a browser-based workstation UI.

It does not pick stocks, automate trades, or promise returns. Its job is narrower: validate whether a research note has enough evidence, data-quality labeling, trigger conditions, invalidation conditions, and risk discipline before it is promoted from information to watch, candidate, or action.

## Why This Exists

Investment workflows often mix facts, rumors, intuition, and risk controls in one paragraph. That makes decisions hard to review later. This project separates those pieces into a simple schema:

- evidence level: `A`, `B`, `C`, `D`
- data quality: `verified`, `estimated`, `mixed`, `stale`, `missing`, `unverified`
- action level: `information`, `watch`, `candidate`, `action`
- explicit trigger, invalidation, max risk, and risk note fields

The professional framework adds:
- thesis quality scorecard (evidence, source diversity, clarity, catalyst, time horizon)
- market/price confirmation scorecard (trend, momentum, volume, relative strength, regime)
- risk/execution scorecard (invalidation, max loss, sizing discipline, liquidity, concentration, time stop)
- expected value / scenario model (bull/base/bear EV, payoff asymmetry)
- position sizing helper (risk-budget based with confidence haircut)
- decision readiness ladder (information → watch → candidate → action)
- decision journal with lifecycle tracking (planned → active → exited → reviewed)
- post-decision review with process adherence scoring
- score calibration (compare initial scores to realized outcomes)
- performance attribution (market, sector, idiosyncratic, sizing decomposition)

## Install

```bash
git clone https://github.com/ZeroxZhang/invest-signal-kit.git
cd invest-signal-kit
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install .
```

No runtime dependencies are required.

## Quick Start

### Fastest Path: Use The Web Workstation

Start the local server:

```bash
python3 -m invest_signal_kit serve --port 8765
```

Open:

```text
http://127.0.0.1:8765
```

Then use the product like this:

1. Open the **Examples** tab.
2. Click **Professional Full Analysis**.
3. Go back to **Signal Lab**.
4. Click **Validate** to check whether the signal meets the schema and promotion rules.
5. Click **Full Analysis** to run the professional framework.
6. Open **Scorecards** to inspect thesis quality, market confirmation, risk/execution, and the decision ladder.
7. Open **Scenario & Sizing** to adjust bull/base/bear probabilities, expected returns, risk budget, stop distance, and confidence.
8. Open **Decision Memo** and click **Generate from Scorecards** to create a review-ready Markdown memo.

The web UI is fully local. It uses no API keys, no external services, no brokerage connection, and no automatic trading.

### Fastest Path: Use The CLI

```bash
# Validate a signal
python3 -m invest_signal_kit validate examples/etf_signal.json

# Score a signal (0-100)
python3 -m invest_signal_kit score examples/etf_signal.json

# Render Markdown report
python3 -m invest_signal_kit render examples/etf_signal.json --output out.md

# Run professional framework analysis
python3 -m invest_signal_kit framework examples/professional_signal.json

# Generate decision memo
python3 -m invest_signal_kit memo examples/professional_signal.json --output memo.md

# Launch the web UI workstation
python3 -m invest_signal_kit serve --port 8765

# Decision journal analysis
python3 -m invest_signal_kit journal examples/decision_journal.json --format markdown

# Review process adherence
python3 -m invest_signal_kit review examples/decision_journal.json --format md

# Calibrate scores against outcomes
python3 -m invest_signal_kit calibrate examples/decision_journal.json --format md
```

After installation, the console script is also available:

```bash
invest-signal-kit validate examples/etf_signal.json
invest-signal-kit serve --port 8765
```

### What Each Command Is For

| Command | Use it when you want to... | Example |
|---------|-----------------------------|---------|
| `validate` | Check whether a signal/macro JSON follows the rules | `python3 -m invest_signal_kit validate examples/etf_signal.json` |
| `score` | Get the original 0-100 signal quality score | `python3 -m invest_signal_kit score examples/etf_signal.json` |
| `render` | Turn a signal/macro JSON into a Markdown report | `python3 -m invest_signal_kit render examples/etf_signal.json -o out.md` |
| `framework` | Run the professional scorecards, EV model, sizing model, and decision ladder | `python3 -m invest_signal_kit framework examples/professional_signal.json` |
| `memo` | Generate a Markdown decision memo from signal + framework inputs | `python3 -m invest_signal_kit memo examples/professional_signal.json -o memo.md` |
| `portfolio` | Run portfolio risk analysis (exposures, limits, stress tests, candidates) | `python3 -m invest_signal_kit portfolio examples/portfolio_workflow.json` |
| `batch` | Run framework analysis on multiple signal files at once | `python3 -m invest_signal_kit batch examples/etf_signal.json examples/stock_shift_signal.json` |
| `journal` | Run full decision journal analysis (lifecycle, calibration, attribution) | `python3 -m invest_signal_kit journal examples/decision_journal.json` |
| `review` | Review decisions for process adherence and errors | `python3 -m invest_signal_kit review examples/decision_journal.json` |
| `calibrate` | Calibrate decision scores against realized outcomes | `python3 -m invest_signal_kit calibrate examples/decision_journal.json` |
| `rebalance` | Generate rebalance/trade plan from holdings, targets, and candidates | `python3 -m invest_signal_kit rebalance examples/rebalance_plan.json` |
| `backtest` | Run backtest / signal replay from a scenario JSON | `python3 -m invest_signal_kit backtest examples/backtest_scenario.json` |
| `serve` | Launch the local browser workstation | `python3 -m invest_signal_kit serve --port 8765` |

## Practical Workflow

Use the toolkit as a promotion pipeline. Do not start at "buy/sell"; start at evidence quality.

### 1. Capture A Raw Signal

Create a JSON file for the idea. For a basic candidate signal, include evidence, confidence, data quality, trigger, invalidation, and risk fields:

```json
{
  "signal": {
    "id": "2026-05-20-semiconductor-etf-001",
    "title": "Semiconductor ETF breakout watch",
    "summary": "Semiconductor sector showing strength with policy tailwinds and volume expansion.",
    "source_task": "ETF pre-market analysis",
    "signal_type": "ETF",
    "instrument": {
      "code": "512480",
      "name": "Semiconductor ETF",
      "asset_type": "ETF"
    },
    "evidence": [
      {
        "source": "Exchange fund flow data",
        "date": "2026-05-19",
        "quote_or_data": "Net inflow 120M CNY over 3 days",
        "evidence_level": "A"
      }
    ],
    "direction": "bullish",
    "impact_horizon": "1-3 months",
    "confidence": 75,
    "data_quality": "verified",
    "action_level": "candidate",
    "suggested_action": "Watch for volume confirmation above 1.2x 20-day average",
    "trigger_condition": "Breaks above resistance with volume confirmation",
    "invalidation_condition": "Falls below support or sector trend breaks",
    "max_risk": "8% drawdown from entry to stop-loss",
    "risk_note": "Single-sector concentration risk."
  }
}
```

Validate it:

```bash
python3 -m invest_signal_kit validate my_signal.json
```

Expected successful output:

```text
VALID - signal passed all validation rules.
```

If it fails, the CLI prints every issue, for example missing trigger, missing invalidation, insufficient confidence, or D-only evidence.

### 2. Add Professional Framework Inputs

For deeper analysis, add a top-level `framework` object next to `signal`:

```json
{
  "signal": {
    "title": "Example signal"
  },
  "framework": {
    "thesis_quality": {
      "evidence_strength": 8,
      "source_diversity": 7,
      "thesis_clarity": 7,
      "catalyst_specificity": 6,
      "time_horizon_fit": 7
    },
    "market_confirmation": {
      "trend_alignment": 7,
      "momentum": 6,
      "volume_liquidity": 7,
      "relative_strength": 7,
      "regime_alignment": 6
    },
    "risk_execution": {
      "invalidation_clarity": 8,
      "max_loss_defined": 7,
      "position_sizing_discipline": 6,
      "liquidity_slippage_risk": 7,
      "concentration_risk": 4,
      "time_stop": 5
    },
    "scenario": {
      "bull_probability": 0.30,
      "bull_return_pct": 15,
      "base_probability": 0.45,
      "base_return_pct": 5,
      "bear_probability": 0.25,
      "bear_return_pct": -8
    },
    "position_sizing": {
      "portfolio_value": 500000,
      "max_risk_pct": 2,
      "entry_price": 1.02,
      "stop_distance_pct": 4,
      "confidence": 75,
      "target_return_pct": 15
    }
  }
}
```

Run the full framework:

```bash
python3 -m invest_signal_kit framework examples/professional_signal.json
```

The result includes:

- `thesis_quality.total`: thesis score from 0-100
- `market_confirmation.total`: price/market confirmation score from 0-100
- `risk_execution.total`: execution discipline score from 0-100
- `expected_value.expected_return_pct`: probability-weighted expected return
- `position_sizing.adjusted_position_size`: risk-budget sizing after confidence haircut
- `decision_readiness.recommended_level`: `information`, `watch`, `candidate`, or `action`
- `decision_readiness.blockers`: explicit reasons the idea cannot be promoted

### 3. Generate A Decision Memo

```bash
python3 -m invest_signal_kit memo examples/professional_signal.json --output memo.md
```

This creates a Markdown memo with:

- instrument and direction
- thesis summary
- scorecard tables
- expected value summary
- risk-budget position sizing
- decision readiness checklist
- blockers, if any

Use this memo for review, journaling, or post-mortems.

### 4. Interpret Decision Levels

| Level | Meaning | Typical action |
|-------|---------|----------------|
| `information` | Interesting note, but not enough structure or evidence | Save it, collect sources, do not act |
| `watch` | Thesis has enough evidence to monitor | Define price/data triggers and invalidation |
| `candidate` | Evidence, trigger, and invalidation are present | Build scenario model and sizing plan |
| `action` | Framework gates pass | Eligible for human review; still not automatic advice |

`action` means "process-ready for review", not "guaranteed profitable" and not "auto-trade".

### 5. Recommended Daily Usage

For a normal research workflow:

```bash
# 1. Validate structure and promotion rules
python3 -m invest_signal_kit validate my_signal.json

# 2. Run the professional framework
python3 -m invest_signal_kit framework my_signal.json --output analysis.json

# 3. Generate a decision memo
python3 -m invest_signal_kit memo my_signal.json --output memo.md

# 4. Open the UI for interactive scenario and sizing adjustments
python3 -m invest_signal_kit serve --port 8765
```

If you only have a raw news item, start it as `information`. Promote it only after evidence, trigger, invalidation, and risk controls are explicit.

### 6. Portfolio Risk Management

For portfolio-level analysis, create a portfolio JSON with holdings, policy, candidates, and stress scenarios:

```bash
# Run portfolio analysis (JSON output)
python3 -m invest_signal_kit portfolio examples/portfolio_workflow.json

# Markdown report
python3 -m invest_signal_kit portfolio examples/portfolio_workflow.json --format markdown

# Save to file
python3 -m invest_signal_kit portfolio examples/portfolio_workflow.json -o portfolio_report.md
```

The portfolio engine checks:
- Position and sector exposures against concentration limits
- Risk budget utilization
- Candidate signals against watchlist criteria
- Stress scenarios (market crash, sector shock, single-name shock, liquidity crisis)

Or use the **Portfolio** tab in the web UI to load, edit, and analyze portfolio data interactively.

### 7. Rebalance / Trade Planning

Generate a structured rebalance plan from current holdings, target allocations, and candidate signals:

```bash
# Generate rebalance plan (JSON output)
python3 -m invest_signal_kit rebalance examples/rebalance_plan.json

# Markdown report
python3 -m invest_signal_kit rebalance examples/rebalance_plan.json --format markdown

# Save to file
python3 -m invest_signal_kit rebalance examples/rebalance_plan.json -o rebalance_plan.md
```

The rebalance engine:
- Computes current portfolio weights and compares to targets
- Generates BUY, SELL, TRIM, ADD, HOLD, or SKIP orders with deterministic rationale
- Enforces guardrails: max position %, max sector %, min cash reserve, max turnover, lot size, min order value
- Evaluates candidate signals against readiness gates (score, action level, EV quality)
- Estimates transaction costs (commission + slippage)
- Assigns execution phases: immediate, wait-for-trigger, reduce-risk-first, blocked
- Shows before/after portfolio exposure, sector weights, and guardrail status

Or use the **Rebalance** tab in the web UI to load, edit, and generate trade plans interactively.

### 8. Backtest / Signal Replay

Run a deterministic backtest from a JSON scenario with price series, signal events, and risk rules:

```bash
# JSON output (default)
python3 -m invest_signal_kit backtest examples/backtest_scenario.json

# Markdown report
python3 -m invest_signal_kit backtest examples/backtest_scenario.json --format markdown

# Save to file
python3 -m invest_signal_kit backtest examples/backtest_scenario.json -o report.md
```

The backtest engine:
- Simulates enter, add, trim, exit, stop, target, time-stop, skip, and blocked events
- Tracks cash, positions, equity curve, trades, event log, costs, drawdown, turnover
- Computes total return, max drawdown, win rate, average R-multiple, alpha vs benchmark
- Enforces risk rules: max position %, max drawdown halt, min confidence gates
- Estimates transaction costs (commission + slippage)

Or use the **Backtest** tab in the web UI to load, edit, and run backtest scenarios interactively.

### 9. Batch Signal Analysis

Analyze multiple signals at once:

```bash
# Compare signals side-by-side
python3 -m invest_signal_kit batch examples/etf_signal.json examples/stock_shift_signal.json --format markdown
```

### Web UI

Open `web/index.html` in a browser, or serve locally:

```bash
python3 -m invest_signal_kit serve --port 8765
```

The UI includes:
- **Signal Lab**: paste/edit JSON, validate, score, render Markdown, run full analysis
- **Scorecards**: interactive sliders for thesis/market/risk factors with weighted scores and blockers
- **Scenario & Sizing**: bull/base/bear expected value, risk-budget position sizing calculator
- **Portfolio**: portfolio risk workstation with exposures, risk budget, candidate rankings, stress tests
- **Rebalance**: trade plan generator with order blotter, guardrails, execution phases, before/after analysis
- **Decision Memo**: generated memo summarizing all scorecards, readiness, and risk controls
- **Example Gallery**: pre-loaded examples for different signal types and portfolio workflows

See [docs/ui.md](docs/ui.md) for detailed UI documentation.

## Input Format Details

### Evidence Levels

| Level | Meaning |
|-------|---------|
| `A` | Primary or authoritative source, preferably cross-checkable |
| `B` | Credible secondary source or structured data source |
| `C` | Useful but incomplete context |
| `D` | Weak, rumor-like, or not enough to support candidate/action decisions |

Candidate and action signals should not rely only on `D` evidence.

### Data Quality

Allowed values:

```text
verified, estimated, mixed, stale, missing, unverified
```

Action-level signals cannot use `missing` or `unverified` data quality.

### Framework Scale

Most scorecard inputs use a 0-10 scale:

| Score | Meaning |
|-------|---------|
| `0-2` | Missing, poor, or contradictory |
| `3-4` | Weak |
| `5-6` | Adequate |
| `7-8` | Strong |
| `9-10` | Exceptional |

The framework converts these inputs into weighted 0-100 scores.

## Common Recipes

### Validate A New Idea Before A Meeting

```bash
python3 -m invest_signal_kit validate my_signal.json
python3 -m invest_signal_kit memo my_signal.json --output meeting_memo.md
```

Bring `meeting_memo.md` to the review and discuss blockers first.

### Compare Two Signals

```bash
python3 -m invest_signal_kit framework signal_a.json --output signal_a.analysis.json
python3 -m invest_signal_kit framework signal_b.json --output signal_b.analysis.json
```

Compare:

- decision level
- expected return
- max drawdown
- payoff asymmetry
- position size as percentage of portfolio
- number and severity of blockers

### Test A Bear Case

Open **Scenario & Sizing** in the UI and increase:

- `bear_probability`
- absolute value of `bear_return_pct`
- `stop_distance_pct`

Then watch how expected value, drawdown, sizing, and risk notes change.

### Turn A Signal Into A Research Journal Entry

```bash
mkdir -p journal
python3 -m invest_signal_kit memo my_signal.json --output journal/2026-05-23-my-signal.md
```

Later, compare the memo against what actually happened.

## Troubleshooting

### `No module named invest_signal_kit`

Install the package from the project root:

```bash
python3 -m pip install .
```

Or run commands from the repository root:

```bash
python3 -m invest_signal_kit validate examples/etf_signal.json
```

### Port `8765` Is Already In Use

Use a different port:

```bash
python3 -m invest_signal_kit serve --port 8877
```

Then open:

```text
http://127.0.0.1:8877
```

### Framework Scores Look Like Defaults

Make sure your JSON has either:

```json
{
  "signal": {},
  "framework": {}
}
```

or:

```json
{
  "signal": {
    "framework": {}
  }
}
```

If both are present, the top-level `framework` is used.

## Professional Framework

The framework provides six deterministic, transparent models for investment research discipline:

| Model | Purpose |
|-------|---------|
| Thesis Quality | Evaluate evidence strength, source diversity, clarity, catalysts, time horizon |
| Market Confirmation | Check trend, momentum, volume, relative strength, regime alignment |
| Risk/Execution | Assess invalidation, max loss, sizing discipline, liquidity, concentration |
| Expected Value | Bull/base/bear scenario analysis with payoff asymmetry |
| Position Sizing | Risk-budget sizing with confidence haircut |
| Decision Readiness | Information → Watch → Candidate → Action ladder with gates |

All formulas are documented in [docs/framework.md](docs/framework.md). All inputs are 0-10 scales or raw values. No black boxes.

## Examples

| File | Type | Description |
|------|------|-------------|
| `examples/etf_signal.json` | signal | Valid ETF candidate signal |
| `examples/stock_shift_signal.json` | signal | Valid event/watch signal |
| `examples/professional_signal.json` | signal + framework | Full professional analysis with scorecards, scenario, sizing |
| `examples/macro_context.json` | macro | Valid macro context |
| `examples/invalid_action_signal.json` | signal (invalid) | Intentionally invalid action signal |
| `examples/portfolio_workflow.json` | portfolio | Multi-asset portfolio with policy, candidates, and stress scenarios |
| `examples/decision_journal.json` | journal | Multi-decision journal with lifecycle, calibration, and attribution |
| `examples/rebalance_plan.json` | rebalance | Rebalance plan with targets, candidates, constraints, and cost assumptions |
| `examples/backtest_scenario.json` | backtest | Multi-asset backtest with signals, benchmark, costs, and risk rules |

## Validation Rules

Action-level signals require:

- confidence of at least `70`
- at least one `A` or `B` evidence item
- no `D` evidence as primary support
- `trigger_condition`
- `invalidation_condition`
- `max_risk`
- `risk_note`
- data quality other than `missing` or `unverified`

Candidate and action signals both require trigger and invalidation conditions. D-only evidence can never justify candidate/action status.

Macro context files are deliberately separate from trade signals. If a macro file contains fields like `suggested_action`, `action_level`, `trigger_condition`, or `max_risk`, validation fails.

## Development

Run tests:

```bash
python3 -m unittest discover -s tests -v
```

Run CLI smoke checks:

```bash
python3 -m invest_signal_kit validate examples/etf_signal.json
python3 -m invest_signal_kit score examples/etf_signal.json
python3 -m invest_signal_kit framework examples/professional_signal.json
python3 -m invest_signal_kit memo examples/professional_signal.json
python3 -m invest_signal_kit render examples/etf_signal.json --output /tmp/render.md
python3 -m invest_signal_kit portfolio examples/portfolio_workflow.json
python3 -m invest_signal_kit batch examples/etf_signal.json examples/stock_shift_signal.json
```

## Disclaimer

This project is for education and investment research workflow hygiene only. It is not financial advice, investment advice, a solicitation, or a trading system. You are responsible for independent verification and final decisions.
