# Usage

## Validate

From a virtual environment with the package installed:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install .
```

```bash
python3 -m invest_signal_kit validate examples/etf_signal.json
```

Expected output:

```text
VALID - signal passed all validation rules.
```

Invalid examples return a nonzero exit code:

```bash
python3 -m invest_signal_kit validate examples/invalid_action_signal.json
```

## Score

```bash
python3 -m invest_signal_kit score examples/etf_signal.json
```

The score output is JSON:

```json
{
  "score": 92,
  "grade": "A",
  "breakdown": {
    "confidence": 22,
    "evidence_strength": 30,
    "data_quality": 20,
    "risk_completeness": 20
  }
}
```

Scores are deterministic workflow-quality scores, not return forecasts.

## Render Markdown

```bash
python3 -m invest_signal_kit render examples/etf_signal.json --output out.md
```

The rendered file includes summary, instrument, evidence, risk conditions, and disclaimer sections.

## JSON Shape

Signals can be wrapped:

```json
{
  "signal": {
    "id": "2026-05-20-example-001",
    "title": "Example signal",
    "confidence": 75,
    "data_quality": "verified",
    "action_level": "candidate",
    "evidence": []
  }
}
```

Macro context can be wrapped:

```json
{
  "macro_context": {
    "date": "2026-05-20",
    "risk_appetite": "rising",
    "market_regime": "balanced"
  }
}
```

For production use, prefer complete fields matching the example files.
