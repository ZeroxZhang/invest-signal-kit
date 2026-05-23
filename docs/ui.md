# Web UI Documentation

The invest-signal-kit web UI is a professional investment signal workstation. It runs entirely in the browser with no external dependencies, no build step, and no API keys.

## Getting Started

### Option 1: Direct file open

Open `web/index.html` in a modern browser. All functionality works without a server.

### Option 2: Local server

```bash
# Using the CLI
python3 -m invest_signal_kit serve --port 8765

# Or using Python directly
cd web && python3 -m http.server 8765
```

Then open `http://localhost:8765` in your browser.

## Tabs

### Signal Lab

The main workspace for working with signal JSON.

- **Input panel**: paste or edit signal JSON in the left panel
- **Output panel**: validation results, scores, rendered Markdown, or framework analysis in the right panel
- **Buttons**:
  - **Validate**: check if the signal passes all validation rules
  - **Score**: compute the 0-100 signal score with breakdown
  - **Render MD**: convert signal to formatted Markdown
  - **Full Analysis**: run the complete professional framework analysis

### Scorecards

Interactive scorecards with sliders for real-time scoring.

- **Thesis Quality**: five factors (evidence strength, source diversity, thesis clarity, catalyst specificity, time horizon fit)
- **Market / Price Confirmation**: five factors (trend alignment, momentum, volume/liquidity, relative strength, regime alignment)
- **Risk & Execution Discipline**: six factors (invalidation clarity, max loss defined, position sizing discipline, liquidity/slippage, concentration risk, time stop)
- **Decision Readiness**: visual decision ladder showing current recommended level, checklist of gate requirements, and blockers

Each scorecard shows:
- Per-factor scores with weights
- Total score (0-100) with letter grade
- Blockers that cap the maximum score

### Scenario & Sizing

Two panels for quantitative analysis.

**Expected Value / Scenario Model:**
- Enter bull/base/bear probabilities and returns
- See expected return, max drawdown, payoff asymmetry, and quality classification
- Probabilities are auto-normalized if they don't sum to 1.0

**Risk-Budget Position Sizing:**
- Enter portfolio value, max risk %, entry price, stop distance, confidence, target return
- See risk budget, raw/adjusted shares, position value, portfolio %, and risk/reward ratio
- Confidence haircut automatically reduces size for lower-confidence trades

### Portfolio

Portfolio risk workstation with:
- Holdings editor (paste or load example)
- Portfolio summary (total value, cash, invested, total risk)
- Risk budget utilization bar
- Position exposure table
- Sector exposure table
- Candidate watchlist with pass/fail criteria
- Stress test results
- Portfolio blockers and warnings

### Rebalance

Trade plan generator with:
- Rebalance plan editor (paste or load example)
- Before/after portfolio summary (total value, cash, invested)
- Transaction cost summary (commission, slippage, turnover)
- Proposed order blotter with action, shares, value, cost, phase
- Order rationale with blockers and warnings
- Guardrail status table (position limits, sector limits, cash reserve, turnover)
- Execution plan grouped by phase (immediate, wait-for-trigger, reduce-risk-first, blocked)
- Side-by-side current vs projected position tables

### Decision Memo

Generate a comprehensive Markdown decision memo that combines:
- Signal metadata (title, instrument, direction, horizon)
- Thesis quality scorecard with factor breakdown
- Market confirmation scorecard
- Risk/execution scorecard
- Expected value analysis
- Position sizing calculation
- Decision readiness assessment with checklist and blockers

Click "Generate from Scorecards" to create a memo from the current scorecard and scenario values. The memo can be copied to clipboard for sharing or archival.

### Example Gallery

Pre-loaded examples demonstrating different signal types and workflows:

1. **ETF Candidate Signal**: valid ETF candidate with A/B evidence, trigger/invalidation, and risk controls
2. **Stock Shift / Watch Signal**: event-driven signal at INFORMATION/WATCH level with mixed evidence
3. **Professional Full Analysis**: complete signal with framework scorecard inputs, scenario model, and position sizing
4. **Macro Context**: macro environment context (demonstrates macro validation)
5. **Invalid Action Signal**: intentionally invalid action-level signal (demonstrates validation failures)
6. **Portfolio Workflow**: multi-asset portfolio with policy, candidates, and stress scenarios
7. **Decision Journal**: multi-decision journal with lifecycle, calibration, and attribution
8. **Rebalance Trade Plan**: portfolio rebalance with targets, candidates, constraints, and cost assumptions

Click any example card to load it into the appropriate tab. Portfolio, journal, and rebalance examples load into their dedicated tabs with auto-analysis.

## Design Philosophy

The UI follows a professional investment workstation aesthetic:
- Dark theme with muted colors for reduced eye strain
- High information density without clutter
- Monospace fonts for data and numbers
- No marketing copy, no purple gradients, no hero sections
- Disclaimers present but not prominent

## Browser Compatibility

Works in all modern browsers (Chrome, Firefox, Safari, Edge). No polyfills or transpilation needed. Uses ES6+ features (arrow functions, template literals, destructuring).
