"""Scenario Builder.

Merge imported prices, signals, benchmark, costs, and risk rules into
a valid backtest scenario JSON compatible with invest-signal-kit's
backtest replay lab.

This module takes normalized data from the importer module and combines
it into a BacktestScenario-compatible dict that can be saved to JSON
or fed directly into run_backtest().

This is research tooling, not financial advice. No external APIs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .importer import ImportResult, ImportError


# ---------------------------------------------------------------------------
# Scenario Builder Data Model
# ---------------------------------------------------------------------------

@dataclass
class ScenarioConfig:
    """Configuration for building a backtest scenario."""
    name: str = ""
    """Human-readable scenario name."""
    initial_capital: float = 100000.0
    """Starting cash for the backtest."""
    commission_per_trade: float = 1.0
    """Fixed commission per trade."""
    slippage_bps: float = 5.0
    """Slippage in basis points."""
    max_position_pct: float = 25.0
    """Max single position as % of equity."""
    max_drawdown_pct: float = 20.0
    """Max portfolio drawdown before halting."""
    min_confidence: float = 60.0
    """Min signal confidence to enter."""


@dataclass
class ScenarioBuildResult:
    """Result of building a backtest scenario."""
    scenario: Optional[Dict[str, Any]] = None
    """The built scenario dict, ready for JSON serialization."""
    errors: List[ImportError] = field(default_factory=list)
    """Build errors."""
    warnings: List[ImportError] = field(default_factory=list)
    """Non-fatal issues."""
    asset_count: int = 0
    """Number of distinct assets in price series."""
    event_count: int = 0
    """Number of signal events."""
    has_benchmark: bool = False
    """Whether benchmark data was included."""


# ---------------------------------------------------------------------------
# Price Series Organization
# ---------------------------------------------------------------------------

def _organize_price_series(
    price_data: List[Dict[str, Any]],
    asset_name: str = "IMPORTED",
) -> Dict[str, List[Dict[str, Any]]]:
    """Organize flat price list into asset-keyed dict.

    If the price data has an 'asset' column, group by asset.
    Otherwise, use the provided asset_name.
    """
    if not price_data:
        return {}

    # Check if data has asset column
    if "asset" in price_data[0]:
        series: Dict[str, List[Dict[str, Any]]] = {}
        for entry in price_data:
            asset = str(entry.get("asset", asset_name))
            clean = {k: v for k, v in entry.items() if k != "asset"}
            series.setdefault(asset, []).append(clean)
        # Sort each series by date
        for asset in series:
            series[asset].sort(key=lambda d: d["date"])
        return series

    # Single asset
    sorted_data = sorted(price_data, key=lambda d: d["date"])
    return {asset_name: sorted_data}


# ---------------------------------------------------------------------------
# Core Builder
# ---------------------------------------------------------------------------

def build_scenario(
    prices: Optional[List[Dict[str, Any]]] = None,
    signals: Optional[List[Dict[str, Any]]] = None,
    benchmark: Optional[List[Dict[str, Any]]] = None,
    config: Optional[ScenarioConfig] = None,
    price_asset_name: str = "IMPORTED",
) -> ScenarioBuildResult:
    """Build a backtest scenario from imported components.

    Args:
        prices: Normalized price data list (from importer).
        signals: Normalized signal event list (from importer).
        benchmark: Normalized benchmark price list (from importer).
        config: Scenario configuration (capital, costs, risk rules).
        price_asset_name: Default asset name for single-asset price imports.

    Returns:
        ScenarioBuildResult with the built scenario or errors.
    """
    if config is None:
        config = ScenarioConfig()

    errors: List[ImportError] = []
    warnings: List[ImportError] = []

    # Validate we have at least prices
    if not prices:
        errors.append(ImportError(message="No price data provided. At least one price series is required."))
        return ScenarioBuildResult(errors=errors)

    # Organize price series
    price_series = _organize_price_series(prices, price_asset_name)

    if not price_series:
        errors.append(ImportError(message="Could not organize price data into series."))
        return ScenarioBuildResult(errors=errors)

    # Validate signal events reference available assets
    asset_names = set(price_series.keys())
    validated_signals = []
    if signals:
        for i, sig in enumerate(signals, start=1):
            asset = sig.get("asset", "")
            if asset not in asset_names:
                warnings.append(ImportError(
                    row=i, column="asset",
                    message=f"Signal references asset '{asset}' which has no price data. "
                            f"Available: {', '.join(sorted(asset_names))}. Signal will be included "
                            f"but may be blocked during backtest."))
            validated_signals.append(sig)

    # Build the scenario dict
    scenario: Dict[str, Any] = {
        "initial_capital": config.initial_capital,
        "price_series": price_series,
        "signal_events": validated_signals,
        "costs": {
            "commission_per_trade": config.commission_per_trade,
            "slippage_bps": config.slippage_bps,
        },
        "risk_rules": {
            "max_position_pct": config.max_position_pct,
            "max_drawdown_pct": config.max_drawdown_pct,
            "min_confidence": config.min_confidence,
        },
    }

    # Add benchmark if provided
    if benchmark:
        scenario["benchmark"] = sorted(benchmark, key=lambda d: d["date"])

    # Add name if provided
    if config.name:
        scenario["name"] = config.name

    return ScenarioBuildResult(
        scenario=scenario,
        errors=errors,
        warnings=warnings,
        asset_count=len(price_series),
        event_count=len(validated_signals),
        has_benchmark=bool(benchmark),
    )


def build_scenario_from_results(
    prices_result: Optional[ImportResult] = None,
    signals_result: Optional[ImportResult] = None,
    benchmark_result: Optional[ImportResult] = None,
    config: Optional[ScenarioConfig] = None,
    price_asset_name: str = "IMPORTED",
) -> ScenarioBuildResult:
    """Build a scenario directly from ImportResult objects.

    Collects errors from all import results, then builds if all imports succeeded.
    """
    all_errors: List[ImportError] = []
    all_warnings: List[ImportError] = []

    if prices_result:
        all_errors.extend(prices_result.errors)
        all_warnings.extend(prices_result.warnings)
    if signals_result:
        all_errors.extend(signals_result.errors)
        all_warnings.extend(signals_result.warnings)
    if benchmark_result:
        all_errors.extend(benchmark_result.errors)
        all_warnings.extend(benchmark_result.warnings)

    if all_errors:
        return ScenarioBuildResult(errors=all_errors, warnings=all_warnings)

    return build_scenario(
        prices=prices_result.data if prices_result else None,
        signals=signals_result.data if signals_result else None,
        benchmark=benchmark_result.data if benchmark_result else None,
        config=config,
        price_asset_name=price_asset_name,
    )


# ---------------------------------------------------------------------------
# JSON I/O
# ---------------------------------------------------------------------------

def save_scenario(result: ScenarioBuildResult, path: str) -> None:
    """Save a built scenario to a JSON file."""
    if result.scenario is None:
        raise ValueError("No scenario to save (build_result.scenario is None).")
    Path(path).write_text(
        json.dumps(result.scenario, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_scenario_config(data: dict) -> ScenarioConfig:
    """Load a ScenarioConfig from a dict."""
    return ScenarioConfig(
        name=str(data.get("name", "")),
        initial_capital=float(data.get("initial_capital", 100000)),
        commission_per_trade=float(data.get("commission_per_trade", 1)),
        slippage_bps=float(data.get("slippage_bps", 5)),
        max_position_pct=float(data.get("max_position_pct", 25)),
        max_drawdown_pct=float(data.get("max_drawdown_pct", 20)),
        min_confidence=float(data.get("min_confidence", 60)),
    )


# ---------------------------------------------------------------------------
# Markdown Renderer
# ---------------------------------------------------------------------------

def render_scenario_markdown(result: ScenarioBuildResult) -> str:
    """Render scenario build result as Markdown."""
    lines: List[str] = []
    lines.append("# Scenario Build Report")
    lines.append("")

    if result.errors:
        lines.append("## Errors")
        for e in result.errors:
            loc = f"row {e.row}" if e.row else "file"
            if e.column:
                loc += f", column '{e.column}'"
            lines.append(f"- **[{loc}]** {e.message}")
        lines.append("")

    if result.warnings:
        lines.append("## Warnings")
        for w in result.warnings:
            loc = f"row {w.row}" if w.row else "file"
            if w.column:
                loc += f", column '{w.column}'"
            lines.append(f"- [{loc}] {w.message}")
        lines.append("")

    if result.scenario:
        lines.append("## Scenario Summary")
        sc = result.scenario
        lines.append(f"- **Initial Capital:** {sc.get('initial_capital', 0):,.2f}")
        lines.append(f"- **Assets:** {result.asset_count}")
        lines.append(f"- **Signal Events:** {result.event_count}")
        lines.append(f"- **Benchmark:** {'Yes' if result.has_benchmark else 'No'}")

        costs = sc.get("costs", {})
        lines.append(f"- **Commission/Trade:** {costs.get('commission_per_trade', 0):.2f}")
        lines.append(f"- **Slippage:** {costs.get('slippage_bps', 0):.1f} bps")

        risk = sc.get("risk_rules", {})
        lines.append(f"- **Max Position:** {risk.get('max_position_pct', 0):.0f}%")
        lines.append(f"- **Max Drawdown:** {risk.get('max_drawdown_pct', 0):.0f}%")
        lines.append(f"- **Min Confidence:** {risk.get('min_confidence', 0):.0f}")
        lines.append("")

        # Asset detail
        series = sc.get("price_series", {})
        if series:
            lines.append("### Price Series")
            lines.append("")
            lines.append("| Asset | Bars | Date Range |")
            lines.append("|-------|------|------------|")
            for asset, bars in series.items():
                if bars:
                    date_range = f"{bars[0]['date']} to {bars[-1]['date']}"
                    lines.append(f"| {asset} | {len(bars)} | {date_range} |")
                else:
                    lines.append(f"| {asset} | 0 | - |")
            lines.append("")

        # Signal event summary
        events = sc.get("signal_events", [])
        if events:
            action_counts: Dict[str, int] = {}
            for e in events:
                a = e.get("action", "unknown")
                action_counts[a] = action_counts.get(a, 0) + 1
            lines.append("### Signal Events")
            lines.append("")
            for action, count in sorted(action_counts.items()):
                lines.append(f"- **{action}:** {count}")
            lines.append("")

    if not result.errors:
        lines.append("Scenario built successfully and is ready for backtest.")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by invest-signal-kit scenario builder. Not investment advice.*")
    return "\n".join(lines)
