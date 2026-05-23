# Decision Journal

The decision journal tracks investment decisions through their full lifecycle and provides post-decision review, score calibration, and performance attribution.

## Data Model

### Decision Lifecycle

A decision moves through these statuses:

```
planned → active → exited → reviewed
                    ↘ invalidated → reviewed
```

| Status | Meaning |
|--------|---------|
| `planned` | Thesis captured, not yet entered |
| `active` | Position is live |
| `exited` | Position closed (target, stop, time, manual) |
| `invalidated` | Thesis broken before exit |
| `reviewed` | Post-decision review complete |

### Decision Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier |
| `instrument_code` | string | Ticker / symbol |
| `instrument_name` | string | Full name |
| `direction` | string | `bullish` / `bearish` |
| `sector` | string | Sector classification |
| `status` | string | Lifecycle status |
| `decision_date` | string | ISO date when decision was made |
| `entry_date` | string | ISO date of entry |
| `exit_date` | string | ISO date of exit |
| `thesis_snapshot` | string | Thesis at time of decision |
| `thesis_quality_score` | float | 0-100 thesis quality score |
| `market_confirmation_score` | float | 0-100 market confirmation score |
| `risk_execution_score` | float | 0-100 risk/execution score |
| `signal_score` | float | 0-100 combined signal score |
| `ev_quality` | string | `positive_ev` / `marginal` / `negative_ev` |
| `entry_price` | float | Entry price |
| `exit_price` | float | Exit price |
| `target_price` | float | Target price |
| `stop_price` | float | Stop-loss price |
| `risk_budget_pct` | float | Risk as % of portfolio |
| `position_size_pct` | float | Position size as % of portfolio |
| `decision_level` | string | Decision ladder level |
| `tags` | list | Free-form tags |
| `review_date` | string | Scheduled review date |
| `time_stop_date` | string | Time-based stop date |
| `exit_reason` | string | Why the position was exited |
| `actual_return_pct` | float | Realized return |
| `r_multiple` | float | R-multiple (return / initial risk) |
| `outcome_category` | string | Review outcome category |
| `process_score` | float | Process adherence score (0-10) |
| `review_notes` | string | Post-decision notes |
| `market_move_pct` | float | Market contribution to return |
| `sector_move_pct` | float | Sector contribution |
| `idiosyncratic_move_pct` | float | Idiosyncratic contribution |
| `sizing_contribution_pct` | float | Sizing/risk contribution |
| `attribution_notes` | string | Attribution commentary |

### Exit Reasons

| Reason | Description |
|--------|-------------|
| `hit_target` | Price reached target |
| `hit_stop` | Price hit stop-loss |
| `time_stop` | Time-based exit triggered |
| `thesis_broken` | Core thesis invalidated |
| `opportunity_cost` | Rotated to better opportunity |
| `manual` | Discretionary exit |

### Outcome Categories

Same as exit reasons, plus `process_adherence` for decisions reviewed on process quality alone.

## Lifecycle Validation Rules

| Rule | Severity | Trigger |
|------|----------|---------|
| `active_decision_missing_exit` | warning | Active decision with no exit_date and no time_stop_date |
| `expired_review` | warning | review_date in the past, status not `reviewed` |
| `stop_breached_not_exited` | error | exit_price < stop_price for bullish active decision |
| `thesis_invalidated_not_exited` | warning | status is `invalidated` but no exit_date |
| `oversized_risk` | warning | risk_budget_pct > 5% |
| `stale_thesis` | warning | `planned` for > 90 days |
| `invalid_status` | error | Status not in valid set |
| `missing_thesis` | warning | Active/exited decision with no thesis_snapshot |
| `missing_review` | warning | Exited/invalidated with no outcome_category |

## Post-Decision Review

The `review` command checks process adherence for each decision:

- **no_thesis_snapshot**: Decision recorded without a thesis
- **no_stop_defined**: Active/exited decision without a stop price
- **no_target_defined**: Active/exited decision without a target price
- **no_risk_budget**: No risk budget defined
- **oversized_risk_budget**: Risk budget exceeds 5%
- **no_exit_reason**: Exited decision without a recorded exit reason
- **no_exit_date**: Exited decision without an exit date
- **no_review_or_time_stop**: Active decision with neither review_date nor time_stop_date

Process score starts at 10 and drops by 2 per error (floor 0).

## Score Calibration

Groups reviewed decisions by initial score into buckets:

| Bucket | Score Range | Grade |
|--------|-------------|-------|
| 0-29 (F/D) | 0-29 | F/D |
| 30-49 (D/C) | 30-49 | D/C |
| 50-64 (C) | 50-64 | C |
| 65-79 (B) | 65-79 | B |
| 80-100 (A) | 80-100 | A |

Per bucket outputs:
- Decision count
- Win rate (return > 0)
- Average return
- Average R-multiple
- Process error count

Score priority: `signal_score` first, then average of thesis/market/risk scores.

## Performance Attribution

Decomposes realized return into additive components:

```
total_return = market_move + sector_move + idiosyncratic_move
residual = total_return - (market + sector + idiosyncratic)
sizing_contribution = total_return * (position_size_pct / 100)
```

Attribution is computed for reviewed/exited decisions with outcome data.

## CLI Usage

### Journal Analysis

```bash
# Full analysis (JSON output)
python3 -m invest_signal_kit journal examples/decision_journal.json

# Markdown report
python3 -m invest_signal_kit journal examples/decision_journal.json --format markdown

# Write to file
python3 -m invest_signal_kit journal examples/decision_journal.json -o journal_report.md
```

### Process Review

```bash
# JSON output
python3 -m invest_signal_kit review examples/decision_journal.json

# Markdown output
python3 -m invest_signal_kit review examples/decision_journal.json --format md
```

### Score Calibration

```bash
# JSON output
python3 -m invest_signal_kit calibrate examples/decision_journal.json

# Markdown output
python3 -m invest_signal_kit calibrate examples/decision_journal.json --format md
```

## Web UI

The Journal tab in the web workstation provides:

1. **Journal Editor**: Paste or load decision journal JSON
2. **Summary Metrics**: Counts by status (active, exited, reviewed, etc.)
3. **Calibration Summary**: Overall win rate, avg return, avg R-multiple, and per-bucket table
4. **Lifecycle Alerts**: Warnings and errors from lifecycle validation
5. **Decisions Table**: Full decision list with status, return, R-multiple, score, and tags
6. **Attribution Table**: Performance decomposition for reviewed decisions

Access via the **Journal** tab after starting the server:

```bash
python3 -m invest_signal_kit serve --port 8765
```

## JSON Format

```json
{
  "decisions": [
    {
      "id": "DJ-2026-001",
      "instrument_code": "510300",
      "instrument_name": "CSI 300 ETF",
      "direction": "bullish",
      "sector": "Index",
      "status": "reviewed",
      "decision_date": "2026-01-15",
      "entry_date": "2026-01-20",
      "exit_date": "2026-03-10",
      "thesis_snapshot": "Policy-driven recovery...",
      "thesis_quality_score": 72,
      "market_confirmation_score": 65,
      "risk_execution_score": 70,
      "signal_score": 75,
      "ev_quality": "positive_ev",
      "entry_price": 3.85,
      "exit_price": 4.28,
      "target_price": 4.30,
      "stop_price": 3.60,
      "risk_budget_pct": 2.0,
      "position_size_pct": 8.0,
      "decision_level": "action",
      "tags": ["macro", "policy"],
      "exit_reason": "hit_target",
      "actual_return_pct": 11.17,
      "r_multiple": 1.72,
      "outcome_category": "hit_target",
      "process_score": 9.0,
      "market_move_pct": 7.5,
      "sector_move_pct": 3.2,
      "idiosyncratic_move_pct": 0.47
    }
  ]
}
```

See `examples/decision_journal.json` for a complete example with 10 decisions across all lifecycle states.
