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

    args = parser.parse_args(argv)

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
