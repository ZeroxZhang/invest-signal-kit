"""CLI entry point for invest-signal-kit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .loader import load_json_file
from .render import render_macro_markdown, render_signal_markdown
from .schema import MacroContext, Signal
from .scoring import score_signal
from .validators import validate_macro, validate_signal


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="invest-signal-kit",
        description="Validate, score, and render investment signals.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- validate ---
    p_val = sub.add_parser("validate", help="Validate a signal or macro JSON file")
    p_val.add_argument("file", help="Path to JSON file")

    # --- score ---
    p_score = sub.add_parser("score", help="Score a signal JSON file")
    p_score.add_argument("file", help="Path to JSON file")

    # --- render ---
    p_render = sub.add_parser("render", help="Render a signal or macro JSON to Markdown")
    p_render.add_argument("file", help="Path to JSON file")
    p_render.add_argument("--output", "-o", help="Output file path (default: stdout)")

    # --- framework ---
    p_fw = sub.add_parser("framework", help="Run professional framework analysis on a signal JSON")
    p_fw.add_argument("file", help="Path to JSON file with framework inputs")
    p_fw.add_argument("--output", "-o", help="Output file path (default: stdout)")

    # --- memo ---
    p_memo = sub.add_parser("memo", help="Generate a decision memo from a signal JSON")
    p_memo.add_argument("file", help="Path to JSON file with framework inputs")
    p_memo.add_argument("--output", "-o", help="Output file path (default: stdout)")

    # --- serve ---
    p_serve = sub.add_parser("serve", help="Serve the web UI locally")
    p_serve.add_argument("--port", type=int, default=8765, help="Port to listen on (default: 8765)")
    p_serve.add_argument("--bind", default="127.0.0.1", help="Address to bind (default: 127.0.0.1)")

    args = parser.parse_args(argv)

    if args.command == "serve":
        return _cmd_serve(args.port, args.bind)

    try:
        obj, kind = load_json_file(args.file)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.command == "validate":
        return _cmd_validate(obj, kind)
    elif args.command == "score":
        return _cmd_score(obj, kind)
    elif args.command == "render":
        return _cmd_render(obj, kind, getattr(args, "output", None))
    elif args.command == "framework":
        return _cmd_framework(args.file, getattr(args, "output", None))
    elif args.command == "memo":
        return _cmd_memo(args.file, getattr(args, "output", None))

    return 0


def _cmd_validate(obj, kind: str) -> int:
    if isinstance(obj, Signal):
        issues = validate_signal(obj)
    elif isinstance(obj, MacroContext):
        issues = validate_macro(obj)
    else:
        print("Error: unknown object type", file=sys.stderr)
        return 1

    if not issues:
        print(f"VALID - {kind} passed all validation rules.")
        return 0

    print(f"INVALID - {len(issues)} issue(s) found:")
    for issue in issues:
        print(f"  [{issue.severity}] {issue.rule}: {issue.message}")
    return 1


def _cmd_score(obj, kind: str) -> int:
    if not isinstance(obj, Signal):
        print("Error: scoring only supports signals, not macro context.", file=sys.stderr)
        return 1

    result = score_signal(obj)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _cmd_render(obj, kind: str, output: str | None) -> int:
    if isinstance(obj, Signal):
        md = render_signal_markdown(obj)
    elif isinstance(obj, MacroContext):
        md = render_macro_markdown(obj)
    else:
        print("Error: unknown object type", file=sys.stderr)
        return 1

    if output:
        Path(output).write_text(md, encoding="utf-8")
        print(f"Written to {output}")
    else:
        print(md)
    return 0


def _cmd_framework(file_path: str, output: str | None) -> int:
    """Run professional framework analysis."""
    from .framework import run_full_analysis

    text = Path(file_path).read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"Error: Invalid JSON: {exc}", file=sys.stderr)
        return 1

    # Unwrap if needed
    if "signal" in data:
        data = data["signal"]

    result = run_full_analysis(data)
    out = json.dumps(result, indent=2, ensure_ascii=False)

    if output:
        Path(output).write_text(out, encoding="utf-8")
        print(f"Written to {output}")
    else:
        print(out)
    return 0


def _cmd_memo(file_path: str, output: str | None) -> int:
    """Generate a decision memo."""
    from .framework import (
        MarketConfirmationInput,
        MemoInput,
        PositionSizingInput,
        RiskExecutionInput,
        ScenarioInput,
        ThesisQualityInput,
        generate_decision_memo,
    )

    text = Path(file_path).read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"Error: Invalid JSON: {exc}", file=sys.stderr)
        return 1

    # Unwrap if needed
    signal_data = data.get("signal", data)
    fw = signal_data.get("framework", {})

    # Build memo input
    tq_raw = fw.get("thesis_quality", {})
    mc_raw = fw.get("market_confirmation", {})
    re_raw = fw.get("risk_execution", {})
    ev_raw = fw.get("scenario", {})
    ps_raw = fw.get("position_sizing", {})

    inst = signal_data.get("instrument", {})

    memo_inp = MemoInput(
        signal_title=signal_data.get("title", ""),
        signal_summary=signal_data.get("summary", ""),
        instrument_code=inst.get("code", ""),
        instrument_name=inst.get("name", ""),
        direction=signal_data.get("direction", ""),
        impact_horizon=signal_data.get("impact_horizon", ""),
        thesis=ThesisQualityInput(**tq_raw) if tq_raw else None,
        market=MarketConfirmationInput(**mc_raw) if mc_raw else None,
        risk=RiskExecutionInput(**re_raw) if re_raw else None,
        scenario=ScenarioInput(**ev_raw) if ev_raw else None,
        sizing=PositionSizingInput(**ps_raw) if ps_raw else None,
        target_return_pct=ps_raw.get("target_return_pct", ev_raw.get("bull_return_pct", 10)),
    )

    md = generate_decision_memo(memo_inp)

    if output:
        Path(output).write_text(md, encoding="utf-8")
        print(f"Written to {output}")
    else:
        print(md)
    return 0


def _cmd_serve(port: int, bind: str) -> int:
    """Serve the web UI using stdlib http.server."""
    import http.server
    import os

    web_dir = Path(__file__).resolve().parent.parent / "web"
    if not web_dir.is_dir():
        print(f"Error: web directory not found at {web_dir}", file=sys.stderr)
        return 1

    os.chdir(web_dir)
    handler = http.server.SimpleHTTPRequestHandler
    server = http.server.HTTPServer((bind, port), handler)
    print(f"Serving web UI at http://{bind}:{port}")
    print(f"  Serving from: {web_dir}")
    print("  Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0
