# invest-signal-kit

A stdlib-only Python toolkit for structured, auditable investment signal analysis. Includes a professional finance framework with scorecards, scenario modeling, position sizing, and a browser-based workstation UI.

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

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install .
```

No runtime dependencies are required.

## Quick Start

### CLI

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
```

After installation, the console script is also available:

```bash
invest-signal-kit validate examples/etf_signal.json
invest-signal-kit serve --port 8765
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
- **Decision Memo**: generated memo summarizing all scorecards, readiness, and risk controls
- **Example Gallery**: pre-loaded examples for different signal types

See [docs/ui.md](docs/ui.md) for detailed UI documentation.

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
```

## Disclaimer

This project is for education and investment research workflow hygiene only. It is not financial advice, investment advice, a solicitation, or a trading system. You are responsible for independent verification and final decisions.
