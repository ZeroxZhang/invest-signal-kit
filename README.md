# invest-signal-kit

`invest-signal-kit` is a small, stdlib-only Python toolkit for turning investment research notes into structured, auditable signals.

It does not pick stocks, automate trades, or promise returns. Its job is narrower: validate whether a research note has enough evidence, data-quality labeling, trigger conditions, invalidation conditions, and risk discipline before it is promoted from information to watch, candidate, or action.

## Why This Exists

Investment workflows often mix facts, rumors, intuition, and risk controls in one paragraph. That makes decisions hard to review later. This project separates those pieces into a simple schema:

- evidence level: `A`, `B`, `C`, `D`
- data quality: `verified`, `estimated`, `mixed`, `stale`, `missing`, `unverified`
- action level: `information`, `watch`, `candidate`, `action`
- explicit trigger, invalidation, max risk, and risk note fields

The result is a portable protocol you can use in CLI workflows, scheduled reports, notebooks, or agent-generated research.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install .
```

No runtime dependencies are required.

## Quick Start

Validate a signal:

```bash
python3 -m invest_signal_kit validate examples/etf_signal.json
```

Score a signal:

```bash
python3 -m invest_signal_kit score examples/etf_signal.json
```

Render a Markdown report:

```bash
python3 -m invest_signal_kit render examples/etf_signal.json --output out.md
```

After editable install, the console script is also available:

```bash
invest-signal-kit validate examples/etf_signal.json
```

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

## Examples

- `examples/etf_signal.json`: valid ETF candidate signal
- `examples/stock_shift_signal.json`: valid event/watch signal
- `examples/macro_context.json`: valid macro context
- `examples/invalid_action_signal.json`: intentionally invalid action signal

## Development

Run tests:

```bash
python3 -m unittest discover -s tests -v
```

Run the CLI smoke checks:

```bash
python3 -m invest_signal_kit validate examples/etf_signal.json
python3 -m invest_signal_kit score examples/etf_signal.json
python3 -m invest_signal_kit render examples/etf_signal.json --output /tmp/invest_signal_render.md
```

## Disclaimer

This project is for education and investment research workflow hygiene only. It is not financial advice, investment advice, a solicitation, or a trading system. You are responsible for independent verification and final decisions.
