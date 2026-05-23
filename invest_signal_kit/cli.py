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

    # --- portfolio ---
    p_port = sub.add_parser("portfolio", help="Run portfolio risk analysis on a portfolio JSON")
    p_port.add_argument("file", help="Path to portfolio JSON file")
    p_port.add_argument("--output", "-o", help="Output file path (default: stdout)")
    p_port.add_argument("--format", choices=["json", "markdown", "md"], default="json",
                        help="Output format (default: json)")

    # --- batch ---
    p_batch = sub.add_parser("batch", help="Run framework analysis on multiple signal files")
    p_batch.add_argument("files", nargs="+", help="Path(s) to signal JSON files")
    p_batch.add_argument("--output", "-o", help="Output file path (default: stdout)")
    p_batch.add_argument("--format", choices=["json", "markdown", "md"], default="json",
                         help="Output format (default: json)")

    # --- journal ---
    p_journal = sub.add_parser("journal", help="Run decision journal analysis on a journal JSON")
    p_journal.add_argument("file", help="Path to decision journal JSON file")
    p_journal.add_argument("--output", "-o", help="Output file path (default: stdout)")
    p_journal.add_argument("--format", choices=["json", "markdown", "md"], default="json",
                           help="Output format (default: json)")

    # --- review ---
    p_review = sub.add_parser("review", help="Review a decision journal for process adherence")
    p_review.add_argument("file", help="Path to decision journal JSON file")
    p_review.add_argument("--output", "-o", help="Output file path (default: stdout)")
    p_review.add_argument("--format", choices=["json", "markdown", "md"], default="json",
                          help="Output format (default: json)")

    # --- calibrate ---
    p_cal = sub.add_parser("calibrate", help="Calibrate decision scores against realized outcomes")
    p_cal.add_argument("file", help="Path to decision journal JSON file")
    p_cal.add_argument("--output", "-o", help="Output file path (default: stdout)")
    p_cal.add_argument("--format", choices=["json", "markdown", "md"], default="json",
                       help="Output format (default: json)")

    # --- rebalance ---
    p_rebal = sub.add_parser("rebalance", help="Generate rebalance/trade plan from a rebalance JSON")
    p_rebal.add_argument("file", help="Path to rebalance plan JSON file")
    p_rebal.add_argument("--output", "-o", help="Output file path (default: stdout)")
    p_rebal.add_argument("--format", choices=["json", "markdown", "md"], default="json",
                         help="Output format (default: json)")

    # --- backtest ---
    p_bt = sub.add_parser("backtest", help="Run backtest / signal replay from a scenario JSON")
    p_bt.add_argument("file", help="Path to backtest scenario JSON file")
    p_bt.add_argument("--output", "-o", help="Output file path (default: stdout)")
    p_bt.add_argument("--format", choices=["json", "markdown", "md"], default="json",
                      help="Output format (default: json)")

    # --- serve ---
    p_serve = sub.add_parser("serve", help="Serve the web UI locally")
    p_serve.add_argument("--port", type=int, default=8765, help="Port to listen on (default: 8765)")
    p_serve.add_argument("--bind", default="127.0.0.1", help="Address to bind (default: 127.0.0.1)")

    args = parser.parse_args(argv)

    if args.command == "serve":
        return _cmd_serve(args.port, args.bind)

    if args.command == "portfolio":
        return _cmd_portfolio(args.file, getattr(args, "output", None),
                              getattr(args, "format", "json"))

    if args.command == "batch":
        return _cmd_batch(args.files, getattr(args, "output", None),
                          getattr(args, "format", "json"))

    if args.command == "journal":
        return _cmd_journal(args.file, getattr(args, "output", None),
                            getattr(args, "format", "json"))

    if args.command == "review":
        return _cmd_review(args.file, getattr(args, "output", None),
                           getattr(args, "format", "json"))

    if args.command == "calibrate":
        return _cmd_calibrate(args.file, getattr(args, "output", None),
                              getattr(args, "format", "json"))

    if args.command == "rebalance":
        return _cmd_rebalance(args.file, getattr(args, "output", None),
                              getattr(args, "format", "json"))

    if args.command == "backtest":
        return _cmd_backtest(args.file, getattr(args, "output", None),
                             getattr(args, "format", "json"))

    try:
        obj, kind = load_json_file(args.file)
    except (ValueError, OSError) as exc:
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
    from .loader import normalize_signal_json

    try:
        text = Path(file_path).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"Error: Invalid JSON: {exc}", file=sys.stderr)
        return 1

    try:
        signal_data, fw_data = normalize_signal_json(data)
    except (ValueError, KeyError, TypeError) as exc:
        print(f"Error: Not a signal file: {exc}", file=sys.stderr)
        return 1
    signal_data["framework"] = fw_data

    result = run_full_analysis(signal_data)
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

    try:
        text = Path(file_path).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"Error: Invalid JSON: {exc}", file=sys.stderr)
        return 1

    # Unwrap if needed
    from .loader import normalize_signal_json

    try:
        signal_data, fw = normalize_signal_json(data)
    except (ValueError, KeyError, TypeError) as exc:
        print(f"Error: Not a signal file: {exc}", file=sys.stderr)
        return 1

    # Build memo input
    tq_raw = fw.get("thesis_quality", {})
    mc_raw = fw.get("market_confirmation", {})
    re_raw = fw.get("risk_execution", {})
    ev_raw = fw.get("scenario", {})
    ps_raw = fw.get("position_sizing", {})
    target_return_pct = ps_raw.pop("target_return_pct", ev_raw.get("bull_return_pct", 10))

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
        target_return_pct=target_return_pct,
    )

    md = generate_decision_memo(memo_inp)

    if output:
        Path(output).write_text(md, encoding="utf-8")
        print(f"Written to {output}")
    else:
        print(md)
    return 0


def _cmd_portfolio(file_path: str, output: str | None, fmt: str) -> int:
    """Run portfolio risk analysis."""
    from .portfolio import load_portfolio_state, evaluate_portfolio, render_portfolio_markdown
    from .portfolio import _result_to_dict

    try:
        text = Path(file_path).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"Error: Invalid JSON: {exc}", file=sys.stderr)
        return 1

    try:
        holdings, cash, policy, candidates, scenarios = load_portfolio_state(data)
    except (ValueError, KeyError, TypeError) as exc:
        print(f"Error loading portfolio data: {exc}", file=sys.stderr)
        return 1

    result = evaluate_portfolio(holdings, cash, policy, candidates, scenarios)

    if fmt in ("markdown", "md"):
        out = render_portfolio_markdown(result)
    else:
        out = json.dumps(_result_to_dict(result), indent=2, ensure_ascii=False)

    if output:
        Path(output).write_text(out, encoding="utf-8")
        print(f"Written to {output}")
    else:
        print(out)
    return 0


def _cmd_batch(files: list, output: str | None, fmt: str) -> int:
    """Run framework analysis on multiple signal files.

    Exit code: 0 if at least one file produced a result (errors are listed
    in the output).  1 only when zero files succeed.
    """
    from .framework import run_full_analysis
    from .loader import normalize_signal_json

    results = []
    errors = []

    for file_path in files:
        try:
            text = Path(file_path).read_text(encoding="utf-8")
        except OSError as exc:
            errors.append({"file": file_path, "error": str(exc)})
            continue

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            errors.append({"file": file_path, "error": f"Invalid JSON: {exc}"})
            continue

        try:
            signal_data, fw_data = normalize_signal_json(data)
        except (ValueError, KeyError, TypeError) as exc:
            errors.append({"file": file_path, "error": f"Not a signal file: {exc}"})
            continue

        signal_data["framework"] = fw_data

        analysis = run_full_analysis(signal_data)
        analysis["_file"] = file_path
        analysis["_title"] = signal_data.get("title", Path(file_path).stem)
        results.append(analysis)

    if fmt in ("markdown", "md"):
        lines = ["# Batch Analysis Results", ""]
        for r in results:
            title = r.pop("_title", "untitled")
            fpath = r.pop("_file", "")
            lines.append(f"## {title}")
            lines.append(f"*Source: {fpath}*")
            lines.append("")
            tq = r.get("thesis_quality", {})
            mc = r.get("market_confirmation", {})
            re_r = r.get("risk_execution", {})
            ev = r.get("expected_value", {})
            dr = r.get("decision_readiness", {})
            lines.append(f"- Thesis Quality: {tq.get('total', 0)}/100 ({tq.get('grade', '?')})")
            lines.append(f"- Market Confirmation: {mc.get('total', 0)}/100 ({mc.get('grade', '?')})")
            lines.append(f"- Risk Execution: {re_r.get('total', 0)}/100 ({re_r.get('grade', '?')})")
            lines.append(f"- EV: {ev.get('expected_return_pct', 0):+.2f}% ({ev.get('quality', '?')})")
            lines.append(f"- Recommended: **{dr.get('recommended_level', '?').upper()}**")
            lines.append("")
        if errors:
            lines.append("## Errors")
            for e in errors:
                lines.append(f"- {e['file']}: {e['error']}")
            lines.append("")
        lines.append("---")
        lines.append("*Generated by invest-signal-kit batch. Not investment advice.*")
        out = "\n".join(lines)
    else:
        out = json.dumps({"results": results, "errors": errors}, indent=2, ensure_ascii=False)

    if output:
        Path(output).write_text(out, encoding="utf-8")
        print(f"Written to {output}")
    else:
        print(out)

    return 0 if results else 1


def _cmd_journal(file_path: str, output: str | None, fmt: str) -> int:
    """Run full decision journal analysis."""
    from .journal import (
        calibrate_scores,
        compute_attribution,
        load_journal,
        render_journal_markdown,
        validate_lifecycle,
        _result_to_dict,
    )

    try:
        text = Path(file_path).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"Error: Invalid JSON: {exc}", file=sys.stderr)
        return 1

    try:
        decisions = load_journal(data)
    except (ValueError, KeyError, TypeError) as exc:
        print(f"Error loading journal: {exc}", file=sys.stderr)
        return 1

    if not decisions:
        print("Error: no decisions found in journal file", file=sys.stderr)
        return 1

    alerts = validate_lifecycle(decisions)
    calibration = calibrate_scores(decisions)
    attributions = compute_attribution(decisions)

    if fmt in ("markdown", "md"):
        out = render_journal_markdown(decisions, alerts, calibration, attributions)
    else:
        result = {
            "decisions": [_result_to_dict(d) for d in decisions],
            "alerts": [_result_to_dict(a) for a in alerts],
            "calibration": _result_to_dict(calibration),
            "attribution": [_result_to_dict(a) for a in attributions],
        }
        out = json.dumps(result, indent=2, ensure_ascii=False)

    if output:
        Path(output).write_text(out, encoding="utf-8")
        print(f"Written to {output}")
    else:
        print(out)
    return 0


def _cmd_review(file_path: str, output: str | None, fmt: str) -> int:
    """Review decisions for process adherence."""
    from .journal import (
        load_journal,
        review_decision,
        _result_to_dict,
    )

    try:
        text = Path(file_path).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"Error: Invalid JSON: {exc}", file=sys.stderr)
        return 1

    try:
        decisions = load_journal(data)
    except (ValueError, KeyError, TypeError) as exc:
        print(f"Error loading journal: {exc}", file=sys.stderr)
        return 1

    if not decisions:
        print("Error: no decisions found in journal file", file=sys.stderr)
        return 1

    reviews = [review_decision(d) for d in decisions]

    if fmt in ("markdown", "md"):
        lines = ["# Decision Process Review", ""]
        for r in reviews:
            lines.append(f"## {r.decision_id} ({r.instrument_code})")
            lines.append(f"- **Outcome:** {r.outcome_category or 'pending'}")
            lines.append(f"- **Return:** {r.actual_return_pct:+.2f}%")
            lines.append(f"- **R-Multiple:** {r.r_multiple:.2f}")
            lines.append(f"- **Process Score:** {r.process_score:.1f}/10")
            if r.process_errors:
                lines.append("- **Process Errors:**")
                for e in r.process_errors:
                    lines.append(f"  - {e}")
            if r.notes:
                lines.append(f"- **Notes:** {r.notes}")
            lines.append("")
        lines.append("---")
        lines.append("*Generated by invest-signal-kit review. Not investment advice.*")
        out = "\n".join(lines)
    else:
        out = json.dumps([_result_to_dict(r) for r in reviews], indent=2, ensure_ascii=False)

    if output:
        Path(output).write_text(out, encoding="utf-8")
        print(f"Written to {output}")
    else:
        print(out)
    return 0


def _cmd_calibrate(file_path: str, output: str | None, fmt: str) -> int:
    """Calibrate decision scores against realized outcomes."""
    from .journal import (
        calibrate_scores,
        load_journal,
        render_journal_markdown,
        _result_to_dict,
    )

    try:
        text = Path(file_path).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"Error: Invalid JSON: {exc}", file=sys.stderr)
        return 1

    try:
        decisions = load_journal(data)
    except (ValueError, KeyError, TypeError) as exc:
        print(f"Error loading journal: {exc}", file=sys.stderr)
        return 1

    if not decisions:
        print("Error: no decisions found in journal file", file=sys.stderr)
        return 1

    calibration = calibrate_scores(decisions)

    if fmt in ("markdown", "md"):
        lines = ["# Score Calibration Report", ""]
        lines.append(f"**Total Decisions:** {calibration.total_decisions}")
        lines.append(f"**Reviewed Decisions:** {calibration.reviewed_decisions}")
        lines.append(f"**Overall Win Rate:** {calibration.overall_win_rate:.1f}%")
        lines.append(f"**Overall Avg Return:** {calibration.overall_avg_return:+.2f}%")
        if calibration.overall_avg_r_multiple != 0:
            lines.append(f"**Overall Avg R-Multiple:** {calibration.overall_avg_r_multiple:.2f}")
        lines.append("")
        lines.append("| Score Bucket | Count | Win Rate | Avg Return | Avg R | Process Errors |")
        lines.append("|-------------|-------|----------|------------|-------|----------------|")
        for b in calibration.buckets:
            if b.decision_count == 0:
                lines.append(f"| {b.score_range} | 0 | - | - | - | - |")
            else:
                r_str = f"{b.avg_r_multiple:.2f}" if b.avg_r_multiple != 0 else "-"
                lines.append(
                    f"| {b.score_range} | {b.decision_count} "
                    f"| {b.win_rate:.1f}% | {b.avg_return_pct:+.2f}% "
                    f"| {r_str} | {b.process_error_count} |"
                )
        lines.append("")
        lines.append("---")
        lines.append("*Generated by invest-signal-kit calibrate. Not investment advice.*")
        out = "\n".join(lines)
    else:
        out = json.dumps(_result_to_dict(calibration), indent=2, ensure_ascii=False)

    if output:
        Path(output).write_text(out, encoding="utf-8")
        print(f"Written to {output}")
    else:
        print(out)
    return 0


def _cmd_rebalance(file_path: str, output: str | None, fmt: str) -> int:
    """Generate rebalance/trade plan."""
    from .rebalance import (
        load_rebalance_plan,
        generate_orders,
        render_rebalance_markdown,
        _result_to_dict,
    )

    try:
        text = Path(file_path).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"Error: Invalid JSON: {exc}", file=sys.stderr)
        return 1

    try:
        holdings, cash, policy, targets, candidates, costs = load_rebalance_plan(data)
    except (ValueError, KeyError, TypeError) as exc:
        print(f"Error loading rebalance plan: {exc}", file=sys.stderr)
        return 1

    result = generate_orders(holdings, cash, policy, targets, candidates, costs)

    if fmt in ("markdown", "md"):
        out = render_rebalance_markdown(result)
    else:
        out = json.dumps(_result_to_dict(result), indent=2, ensure_ascii=False)

    if output:
        Path(output).write_text(out, encoding="utf-8")
        print(f"Written to {output}")
    else:
        print(out)
    return 0


def _cmd_backtest(file_path: str, output: str | None, fmt: str) -> int:
    """Run backtest / signal replay."""
    from .backtest import (
        load_backtest_scenario,
        run_backtest,
        render_backtest_markdown,
        _result_to_dict,
    )

    try:
        text = Path(file_path).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"Error: Invalid JSON: {exc}", file=sys.stderr)
        return 1

    try:
        scenario = load_backtest_scenario(data)
    except (ValueError, KeyError, TypeError) as exc:
        print(f"Error loading backtest scenario: {exc}", file=sys.stderr)
        return 1

    result = run_backtest(scenario)

    if fmt in ("markdown", "md"):
        out = render_backtest_markdown(result)
    else:
        out = json.dumps(_result_to_dict(result), indent=2, ensure_ascii=False)

    if output:
        Path(output).write_text(out, encoding="utf-8")
        print(f"Written to {output}")
    else:
        print(out)
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
