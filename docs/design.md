# Design

## Goal

`invest-signal-kit` provides a compact protocol for investment research signals. The design favors clarity, portability, and auditability over market-data integration.

The package is stdlib-only so it can run in local scripts, CI, scheduled jobs, or agent environments without API keys or network access.

## Architecture

- `schema.py`: typed dataclasses and enums for signals, macro context, instruments, evidence, and validation issues.
- `loader.py`: JSON parsing and conversion into typed objects.
- `validators.py`: rule checks for confidence, evidence quality, action readiness, and macro/trade separation.
- `scoring.py`: transparent 0-100 scoring from confidence, evidence strength, data quality, and risk completeness.
- `render.py`: Markdown reports for human review.
- `cli.py`: command-line interface for validate, score, and render workflows.

## Signal vs Macro Context

Signals can describe ETF, stock, index, bond, commodity, or other instrument-level research. They may include action levels, suggested actions, triggers, invalidation rules, and risk notes.

Macro context is background only. It can describe risk appetite, market regime, key variables, and notes for downstream tasks. It must not contain trade action fields. The loader preserves forbidden fields in `MacroContext.extra_fields`, allowing validators to reject action fields that appear in JSON input.

## Rule Rationale

Evidence levels follow a conservative hierarchy:

- `A`: filings, exchange documents, regulatory disclosures, financial reports
- `B`: reputable financial media, cross-verified sources, industry checks
- `C`: single-source media, rumors, social discussion
- `D`: unverifiable claims, title bait, unsupported narratives

Action-level signals are intentionally hard to pass. They require high confidence, strong evidence, explicit risk controls, and acceptable data quality. This keeps the tool from turning weak narratives into action labels.

## Non-Goals

- No automatic trading
- No brokerage integration
- No live market-data dependency
- No guarantee of returns
- No private portfolio assumptions
