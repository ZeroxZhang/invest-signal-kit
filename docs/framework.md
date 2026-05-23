# Professional Framework Documentation

The `invest-signal-kit` framework provides deterministic, transparent scorecards and models for investment research workflow discipline. All formulas are documented, all weights are visible, all inputs are simple numbers (0-10 scales or raw values).

This is research tooling, not financial advice.

## Overview

The framework consists of six interconnected models:

1. **Thesis Quality Scorecard** — evaluates the investment thesis itself
2. **Market/Price Confirmation Scorecard** — checks if market action confirms the thesis
3. **Risk/Execution Scorecard** — assesses risk management discipline
4. **Expected Value / Scenario Model** — probability-weighted outcome analysis
5. **Position Sizing Helper** — risk-budget based sizing with confidence haircut
6. **Decision Readiness** — information/watch/candidate/action decision ladder

## 1. Thesis Quality Scorecard

Evaluates the quality of the investment thesis on a 0-100 scale.

### Input Factors (each 0-10)

| Factor | Weight | Description |
|--------|--------|-------------|
| Evidence Strength | 25% | Quality and reliability of supporting evidence. 0=no evidence, 5=mixed sources, 10=primary filings + cross-verified. |
| Source Diversity | 20% | Number and independence of information sources. 0=single rumor, 5=3+ sources, 10=5+ independent high-quality sources. |
| Thesis Clarity | 25% | How well-defined and testable the thesis is. 0=vague hunch, 5=clear direction, 10=specific mechanism with falsifiable claims. |
| Catalyst Specificity | 15% | How identifiable and time-bound the catalysts are. 0=no catalyst, 5=general sector trend, 10=specific event with date. |
| Time Horizon Fit | 15% | Match between thesis timeframe and evidence horizon. 0=mismatched, 5=roughly aligned, 10=precise fit with clear milestones. |

### Formula

```
weighted_score = sum(factor_score * weight) / sum(weights)
total = weighted_score * 10   (scale to 0-100)
```

### Blockers (automatic cap at 40/100)

- `evidence_strength < 3`: thesis has no real evidence
- `thesis_clarity < 3`: thesis is too vague to act on

## 2. Market/Price Confirmation Scorecard

Evaluates whether market action confirms the thesis direction (0-100).

### Input Factors

| Factor | Weight | Description |
|--------|--------|-------------|
| Trend Alignment | 30% | Is the price trend consistent with thesis direction? 0=contradicts, 5=neutral, 10=strong confirmation. |
| Momentum | 20% | Is momentum supporting the move? 0=divergence, 5=flat, 10=strong momentum. |
| Volume/Liquidity | 20% | Volume/liquidity confirmation. 0=dry, 5=normal, 10=heavy institutional volume. |
| Relative Strength | 15% | Performance vs benchmark/sector. 0=underperformance, 5=in-line, 10=outperformance. |
| Regime Alignment | 15% | Is the broader market regime favorable? 0=hostile, 5=neutral, 10=favorable. |

### Formula

Same weighted average as Thesis Quality.

### Blockers (cap at 30/100)

- `trend_alignment < 2`: price action contradicts the thesis

## 3. Risk/Execution Scorecard

Assesses risk management and execution discipline (0-100).

### Input Factors

| Factor | Weight | Description |
|--------|--------|-------------|
| Invalidation Clarity | 25% | How clear is the stop/invalidation condition? 0=none, 5=vague, 10=precise level. |
| Max Loss Defined | 20% | Is maximum acceptable loss defined? 0=unknown, 5=rough, 10=exact figure. |
| Position Sizing Discipline | 20% | Is sizing based on risk budget? 0=all-in, 5=rough, 10=risk-budget based. |
| Liquidity/Slippage Risk | 15% | Assessment of execution risk. 0=illiquid, 5=moderate, 10=deep market. |
| Concentration Risk | 10% | How concentrated in portfolio/sector? 0=single-name, 5=moderate, 10=diversified. |
| Time Stop | 10% | Is there a time-based review trigger? 0=none, 5=loose, 10=specific date. |

### Blockers (cap at 35/100)

- `invalidation_clarity < 3`: no stop = no trade
- `max_loss_defined < 2`: undefined risk is unacceptable

## 4. Expected Value / Scenario Model

Calculates expected value from bull/base/bear scenarios.

### Inputs

| Field | Description |
|-------|-------------|
| bull_probability | Probability of bull case (0-1) |
| bull_return_pct | Return in bull case (percent) |
| base_probability | Probability of base case (0-1) |
| base_return_pct | Return in base case (percent) |
| bear_probability | Probability of bear case (0-1) |
| bear_return_pct | Return in bear case (percent) |

### Formulas

```
Probabilities are normalized to sum to 1.0 if they don't already.

Expected Return = bull_prob * bull_ret + base_prob * base_ret + bear_prob * bear_ret

Max Drawdown = min(bear_return, 0)

Payoff Asymmetry = avg_upside / abs(avg_downside)
    where avg_upside = weighted sum of positive-return scenarios
          avg_downside = weighted sum of negative-return scenarios
```

### Quality Classification

| Expected Return | Quality |
|----------------|---------|
| > 3% | `positive_ev` |
| 0% - 3% | `marginal` |
| <= 0% | `negative_ev` |

## 5. Position Sizing Helper

Risk-budget based position sizing with confidence haircut.

### Inputs

| Field | Description |
|-------|-------------|
| portfolio_value | Total portfolio value |
| max_risk_pct | Max risk per trade as % of portfolio (default 2%) |
| entry_price | Planned entry price |
| stop_distance_pct | Distance from entry to stop-loss (%) |
| confidence | Confidence in trade (0-100), used as haircut |
| target_return_pct | Target return for risk/reward calculation |

### Formula

```
risk_amount = portfolio_value * (max_risk_pct / 100)
per_unit_risk = entry_price * (stop_distance_pct / 100)
raw_shares = risk_amount / per_unit_risk

confidence_factor = clamp(confidence / 100, 0.1, 1.0)
adjusted_shares = round(raw_shares * confidence_factor)
position_value = adjusted_shares * entry_price
position_pct = position_value / portfolio_value * 100

risk_reward = target_return_pct / stop_distance_pct
```

### Warnings

- Position > 20% of portfolio: "consider reducing"
- Risk/reward < 1.5:1: "marginal setup"
- Confidence factor < 0.5: "size reduced significantly"

## 6. Decision Readiness (Decision Ladder)

The decision ladder maps investment decisions through four levels:

```
INFORMATION → WATCH → CANDIDATE → ACTION
```

### Gate Requirements

**INFORMATION → WATCH:**
- Thesis quality score >= 30

**WATCH → CANDIDATE:**
- Thesis quality score >= 50
- Market confirmation score >= 40
- Invalidation condition defined
- Trigger condition defined

**CANDIDATE → ACTION:**
- Thesis quality score >= 65
- Market confirmation score >= 55
- Risk/execution score >= 60
- Expected value quality: positive or marginal
- Max loss defined
- Position sizing calculated
- No scorecard blockers

## Usage from Python

```python
from invest_signal_kit.framework import (
    ThesisQualityInput, score_thesis_quality,
    MarketConfirmationInput, score_market_confirmation,
    RiskExecutionInput, score_risk_execution,
    ScenarioInput, calculate_expected_value,
    PositionSizingInput, calculate_position_size,
    DecisionReadinessInput, assess_decision_readiness,
    generate_decision_memo, MemoInput,
)

# Score thesis quality
tq = score_thesis_quality(ThesisQualityInput(
    evidence_strength=8,
    source_diversity=7,
    thesis_clarity=7,
    catalyst_specificity=6,
    time_horizon_fit=7,
))
print(tq.total, tq.grade)  # 70.5 "B"

# Full analysis from JSON
from invest_signal_kit.framework import run_full_analysis
import json
data = json.load(open("examples/professional_signal.json"))
result = run_full_analysis(data["signal"])
```

## Usage from CLI

```bash
# Full framework analysis
python3 -m invest_signal_kit framework examples/professional_signal.json

# Generate decision memo
python3 -m invest_signal_kit memo examples/professional_signal.json

# Save to file
python3 -m invest_signal_kit memo examples/professional_signal.json --output memo.md
```
