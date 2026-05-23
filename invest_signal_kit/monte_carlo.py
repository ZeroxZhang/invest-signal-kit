"""Monte Carlo Risk Simulator / Drawdown Lab.

Deterministic Monte Carlo simulation for portfolio and backtest risk analysis.
Supports bootstrap resampling and parametric normal simulation with seeded
randomness. Multi-asset portfolios with weights, optional cash allocation,
rebalancing cadence, and scenario stress overlays.

This is research tooling, not financial advice. No live data, no
brokerage integration, no optimization.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------

@dataclass
class AssetReturnSeries:
    """Historical daily log-returns for one asset."""
    asset: str = ""
    dates: List[str] = field(default_factory=list)
    prices: List[float] = field(default_factory=list)
    log_returns: List[float] = field(default_factory=list)
    mean_return: float = 0.0
    std_return: float = 0.0


@dataclass
class PortfolioWeight:
    """Weight allocation for one asset."""
    asset: str = ""
    weight: float = 0.0


@dataclass
class StressOverlay:
    """Stress scenario applied to simulation paths."""
    shock_pct: float = 0.0
    """One-time percentage shock applied at start (e.g. -0.10 = -10%)."""
    vol_multiplier: float = 1.0
    """Multiply all returns' volatility by this factor."""
    drift_adjust_pct: float = 0.0
    """Add/subtract annualized drift adjustment in percent."""


@dataclass
class MonteCarloConfig:
    """Configuration for a Monte Carlo simulation."""
    initial_capital: float = 100000.0
    num_simulations: int = 1000
    horizon_days: int = 252
    seed: int = 42
    method: str = "bootstrap"
    """'bootstrap' or 'parametric'."""
    weights: List[PortfolioWeight] = field(default_factory=list)
    cash_weight: float = 0.0
    """Fraction held in cash (0.0-1.0). Cash earns 0%."""
    rebalance_cadence: str = "monthly"
    """'daily', 'weekly', 'monthly', or 'never'."""
    stress: StressOverlay = field(default_factory=StressOverlay)
    drawdown_breach_pct: float = 20.0
    """Drawdown threshold for breach probability."""
    confidence_levels: List[float] = field(default_factory=lambda: [5.0, 25.0, 50.0, 75.0, 95.0])
    sample_count: int = 50
    """Number of sample paths to keep for visualization."""


@dataclass
class DrawdownPath:
    """Drawdown stats for a single simulation path."""
    max_drawdown_pct: float = 0.0
    final_equity: float = 0.0
    breached: bool = False


@dataclass
class MonteCarloResult:
    """Complete Monte Carlo simulation result."""
    # Config snapshot
    initial_capital: float = 0.0
    num_simulations: int = 0
    horizon_days: int = 0
    seed: int = 0
    method: str = ""
    rebalance_cadence: str = ""
    cash_weight: float = 0.0

    # Asset info
    assets: List[str] = field(default_factory=list)
    weights: Dict[str, float] = field(default_factory=dict)

    # Stress
    stress_shock_pct: float = 0.0
    stress_vol_multiplier: float = 1.0
    stress_drift_adjust_pct: float = 0.0

    # Equity band metrics (at horizon)
    median_final_equity: float = 0.0
    mean_final_equity: float = 0.0
    p5_equity: float = 0.0
    p25_equity: float = 0.0
    p75_equity: float = 0.0
    p95_equity: float = 0.0

    # Return metrics
    median_return_pct: float = 0.0
    mean_return_pct: float = 0.0

    # Risk metrics
    prob_loss: float = 0.0
    """Probability of any loss at horizon."""
    prob_drawdown_breach: float = 0.0
    """Probability of breaching drawdown threshold."""
    max_drawdown_median: float = 0.0
    max_drawdown_p95: float = 0.0
    max_drawdown_worst: float = 0.0

    # Tail risk
    expected_shortfall_pct: float = 0.0
    """CVaR: average loss in worst 5% of outcomes."""
    worst_path_final_equity: float = 0.0
    worst_path_max_drawdown_pct: float = 0.0
    worst_path_return_pct: float = 0.0

    # Percentile table
    percentile_table: List[Dict[str, float]] = field(default_factory=list)

    # Per-simulation summary
    final_equities: List[float] = field(default_factory=list)
    max_drawdowns: List[float] = field(default_factory=list)
    drawdown_breaches: int = 0

    # Sample paths for visualization (first N paths)
    sample_paths: List[List[float]] = field(default_factory=list)
    sample_count: int = 50


# ---------------------------------------------------------------------------
# Return Series Loading
# ---------------------------------------------------------------------------

def _compute_log_returns(prices: List[float]) -> List[float]:
    """Compute log returns from a price series."""
    returns = []
    for i in range(1, len(prices)):
        if prices[i - 1] > 0 and prices[i] > 0:
            returns.append(math.log(prices[i] / prices[i - 1]))
        else:
            returns.append(0.0)
    return returns


def load_return_series_from_prices(
    asset: str, prices: List[Dict[str, Any]]
) -> AssetReturnSeries:
    """Load return series from a list of price dicts (date, close)."""
    sorted_prices = sorted(prices, key=lambda p: str(p.get("date", "")))
    dates = [str(p.get("date", "")) for p in sorted_prices]
    close_prices = [float(p.get("close", 0)) for p in sorted_prices]
    log_rets = _compute_log_returns(close_prices)

    mean_ret = sum(log_rets) / len(log_rets) if log_rets else 0.0
    if len(log_rets) > 1:
        variance = sum((r - mean_ret) ** 2 for r in log_rets) / (len(log_rets) - 1)
        std_ret = math.sqrt(variance)
    else:
        std_ret = 0.0

    return AssetReturnSeries(
        asset=asset,
        dates=dates,
        prices=close_prices,
        log_returns=log_rets,
        mean_return=mean_ret,
        std_return=std_ret,
    )


def load_return_series_from_backtest(data: dict) -> Dict[str, AssetReturnSeries]:
    """Load return series from a backtest scenario JSON dict."""
    series = {}
    for asset, bars in data.get("price_series", {}).items():
        series[asset] = load_return_series_from_prices(asset, bars)
    return series


def load_return_series_from_config(data: dict) -> Dict[str, AssetReturnSeries]:
    """Load return series from a monte carlo config dict.

    Supports two formats:
    1. price_series: {"ASSET": [{"date": "...", "close": N}, ...]}
    2. Backtest scenario format (same key)
    """
    series = {}
    for asset, bars in data.get("price_series", {}).items():
        series[asset] = load_return_series_from_prices(asset, bars)
    return series


# ---------------------------------------------------------------------------
# Simulation Engine
# ---------------------------------------------------------------------------

def _percentile(sorted_vals: List[float], p: float) -> float:
    """Compute percentile from a sorted list."""
    if not sorted_vals:
        return 0.0
    n = len(sorted_vals)
    k = (p / 100.0) * (n - 1)
    f = int(math.floor(k))
    c = min(f + 1, n - 1)
    d = k - f
    return sorted_vals[f] * (1 - d) + sorted_vals[c] * d


def _rebalance_offset(cadence: str) -> int:
    """Days between rebalances."""
    if cadence == "daily":
        return 1
    if cadence == "weekly":
        return 5
    if cadence == "monthly":
        return 21
    return 0  # never


def _apply_stress(
    daily_return: float, stress: StressOverlay, annual_drift_adj: float
) -> float:
    """Apply stress adjustments to a daily return."""
    # Volatility multiplier scales deviation from zero
    adjusted = daily_return * stress.vol_multiplier
    # Drift adjustment (annualized -> daily)
    adjusted += annual_drift_adj
    return adjusted


def run_monte_carlo(
    config: MonteCarloConfig,
    return_series: Dict[str, AssetReturnSeries],
) -> MonteCarloResult:
    """Run a deterministic Monte Carlo simulation.

    Algorithm:
    1. Build pooled return samples (bootstrap) or per-asset params (parametric).
    2. For each simulation, generate daily portfolio returns over horizon.
    3. Apply rebalancing cadence, stress overlays, and cash allocation.
    4. Track equity path, drawdown, and terminal metrics.
    5. Aggregate across simulations.
    """
    rng = random.Random(config.seed)

    # Validate weights
    asset_names = sorted(return_series.keys())
    weight_map: Dict[str, float] = {}
    if config.weights:
        for w in config.weights:
            weight_map[w.asset] = w.weight
    else:
        # Equal weight across assets
        n = len(asset_names)
        if n > 0:
            eq_w = 1.0 / n
            for a in asset_names:
                weight_map[a] = eq_w

    # Normalize weights so risky + cash = 1.0
    risky_total = sum(weight_map.get(a, 0.0) for a in asset_names)
    cash_w = config.cash_weight
    if risky_total + cash_w > 0:
        scale = 1.0 - cash_w
        if risky_total > 0:
            for a in asset_names:
                weight_map[a] = (weight_map.get(a, 0.0) / risky_total) * scale
        else:
            cash_w = 1.0
    else:
        cash_w = 1.0

    # Annualized drift adjustment per day
    daily_drift_adj = config.stress.drift_adjust_pct / 100.0 / 252.0

    # Build bootstrap pools or parametric stats per asset
    bootstrap_pools: Dict[str, List[float]] = {}
    param_mean: Dict[str, float] = {}
    param_std: Dict[str, float] = {}

    for asset in asset_names:
        rs = return_series[asset]
        rets = rs.log_returns
        if not rets:
            rets = [0.0]
        bootstrap_pools[asset] = rets
        param_mean[asset] = rs.mean_return
        param_std[asset] = rs.std_return

    rebal_offset = _rebalance_offset(config.rebalance_cadence)

    # Run simulations
    all_final_equities: List[float] = []
    all_max_drawdowns: List[float] = []
    breach_count = 0
    sample_paths: List[List[float]] = []

    for sim_idx in range(config.num_simulations):
        equity = config.initial_capital
        peak_equity = equity
        max_dd = 0.0
        path = [equity]

        # Current asset allocations (in $)
        asset_values: Dict[str, float] = {}
        for a in asset_names:
            asset_values[a] = equity * weight_map.get(a, 0.0)
        cash_value = equity * cash_w

        for day in range(config.horizon_days):
            # Rebalance check
            do_rebalance = (rebal_offset > 0 and day > 0 and day % rebal_offset == 0)

            if do_rebalance:
                total_now = cash_value + sum(asset_values.values())
                for a in asset_names:
                    asset_values[a] = total_now * weight_map.get(a, 0.0)
                cash_value = total_now * cash_w

            # Generate daily returns per asset
            daily_pnl = 0.0
            for a in asset_names:
                w = weight_map.get(a, 0.0)
                if w <= 0:
                    continue

                if config.method == "bootstrap":
                    ret = rng.choice(bootstrap_pools[a])
                else:
                    # Parametric normal
                    mu = param_mean[a]
                    sigma = param_std[a]
                    if sigma > 0:
                        ret = rng.gauss(mu, sigma)
                    else:
                        ret = mu

                # Apply stress
                ret = _apply_stress(ret, config.stress, daily_drift_adj)

                # One-time shock on first day
                if day == 0 and config.stress.shock_pct != 0:
                    ret += config.stress.shock_pct

                asset_values[a] *= math.exp(ret)
                daily_pnl += asset_values[a] - (equity * w if day == 0 else 0)

            # Update equity
            equity = cash_value + sum(asset_values.values())
            if equity > peak_equity:
                peak_equity = equity
            dd = ((peak_equity - equity) / peak_equity * 100) if peak_equity > 0 else 0.0
            if dd > max_dd:
                max_dd = dd

            path.append(equity)

        # Terminal metrics
        all_final_equities.append(equity)
        all_max_drawdowns.append(max_dd)
        if max_dd >= config.drawdown_breach_pct:
            breach_count += 1

        # Keep sample paths for visualization
        if sim_idx < config.sample_count:
            sample_paths.append(path)

    # Sort for percentile computation
    sorted_equities = sorted(all_final_equities)
    sorted_drawdowns = sorted(all_max_drawdowns)

    # Return metrics
    initial = config.initial_capital
    returns = [(e - initial) / initial * 100 for e in all_final_equities]
    sorted_returns = sorted(returns)

    # Expected shortfall (CVaR) - average of worst 5%
    var_index = max(1, int(len(sorted_returns) * 0.05))
    worst_5 = sorted_returns[:var_index]
    es = sum(worst_5) / len(worst_5) if worst_5 else 0.0

    # Worst path
    worst_idx = all_final_equities.index(min(all_final_equities))

    # Percentile table
    pct_table = []
    for p in config.confidence_levels:
        pct_table.append({
            "percentile": p,
            "equity": round(_percentile(sorted_equities, p), 2),
            "return_pct": round(_percentile(sorted_returns, p), 4),
        })

    result = MonteCarloResult(
        initial_capital=initial,
        num_simulations=config.num_simulations,
        horizon_days=config.horizon_days,
        seed=config.seed,
        method=config.method,
        rebalance_cadence=config.rebalance_cadence,
        cash_weight=config.cash_weight,
        assets=asset_names,
        weights={a: round(weight_map.get(a, 0.0), 4) for a in asset_names},
        stress_shock_pct=config.stress.shock_pct,
        stress_vol_multiplier=config.stress.vol_multiplier,
        stress_drift_adjust_pct=config.stress.drift_adjust_pct,
        median_final_equity=round(_percentile(sorted_equities, 50), 2),
        mean_final_equity=round(sum(all_final_equities) / len(all_final_equities), 2),
        p5_equity=round(_percentile(sorted_equities, 5), 2),
        p25_equity=round(_percentile(sorted_equities, 25), 2),
        p75_equity=round(_percentile(sorted_equities, 75), 2),
        p95_equity=round(_percentile(sorted_equities, 95), 2),
        median_return_pct=round(_percentile(sorted_returns, 50), 4),
        mean_return_pct=round(sum(sorted_returns) / len(sorted_returns), 4),
        prob_loss=round(sum(1 for r in returns if r < 0) / len(returns) * 100, 2),
        prob_drawdown_breach=round(breach_count / config.num_simulations * 100, 2),
        max_drawdown_median=round(_percentile(sorted_drawdowns, 50), 2),
        max_drawdown_p95=round(_percentile(sorted_drawdowns, 95), 2),
        max_drawdown_worst=round(max(all_max_drawdowns), 2),
        expected_shortfall_pct=round(es, 4),
        worst_path_final_equity=round(min(all_final_equities), 2),
        worst_path_max_drawdown_pct=round(max(all_max_drawdowns), 2),
        worst_path_return_pct=round(min(returns), 4),
        percentile_table=pct_table,
        final_equities=[round(e, 2) for e in all_final_equities],
        max_drawdowns=[round(d, 2) for d in all_max_drawdowns],
        drawdown_breaches=breach_count,
        sample_paths=[[round(v, 2) for v in p] for p in sample_paths],
        sample_count=config.sample_count,
    )

    return result


# ---------------------------------------------------------------------------
# Config Loader
# ---------------------------------------------------------------------------

def load_monte_carlo_config(data: dict) -> Tuple[MonteCarloConfig, Dict[str, AssetReturnSeries]]:
    """Load MonteCarloConfig and return series from a JSON dict.

    Expected format:
    {
        "initial_capital": 100000,
        "num_simulations": 1000,
        "horizon_days": 252,
        "seed": 42,
        "method": "bootstrap",
        "price_series": {"AAPL": [{"date": "...", "close": N}, ...], ...},
        "weights": [{"asset": "AAPL", "weight": 0.5}, ...],
        "cash_weight": 0.1,
        "rebalance_cadence": "monthly",
        "stress": {"shock_pct": -0.10, "vol_multiplier": 1.5, "drift_adjust_pct": -2.0},
        "drawdown_breach_pct": 20,
        "confidence_levels": [5, 25, 50, 75, 95]
    }
    """
    config = MonteCarloConfig(
        initial_capital=float(data.get("initial_capital", 100000)),
        num_simulations=int(data.get("num_simulations", 1000)),
        horizon_days=int(data.get("horizon_days", 252)),
        seed=int(data.get("seed", 42)),
        method=str(data.get("method", "bootstrap")),
        cash_weight=float(data.get("cash_weight", 0.0)),
        rebalance_cadence=str(data.get("rebalance_cadence", "monthly")),
        drawdown_breach_pct=float(data.get("drawdown_breach_pct", 20.0)),
    )

    # Confidence levels
    if "confidence_levels" in data:
        config.confidence_levels = [float(x) for x in data["confidence_levels"]]

    # Weights
    for w in data.get("weights", []):
        config.weights.append(PortfolioWeight(
            asset=str(w.get("asset", "")),
            weight=float(w.get("weight", 0.0)),
        ))

    # Stress
    stress_data = data.get("stress", {})
    if stress_data:
        config.stress = StressOverlay(
            shock_pct=float(stress_data.get("shock_pct", 0.0)),
            vol_multiplier=float(stress_data.get("vol_multiplier", 1.0)),
            drift_adjust_pct=float(stress_data.get("drift_adjust_pct", 0.0)),
        )

    # Return series
    return_series = load_return_series_from_config(data)

    return config, return_series


def run_monte_carlo_from_dict(data: dict) -> dict:
    """Run Monte Carlo from a JSON dict. Convenience function."""
    config, return_series = load_monte_carlo_config(data)
    result = run_monte_carlo(config, return_series)
    return _result_to_dict(result)


# ---------------------------------------------------------------------------
# JSON Serialization
# ---------------------------------------------------------------------------

def _result_to_dict(result: Any) -> Any:
    """Convert dataclass result to plain dict for JSON."""
    if hasattr(result, "__dataclass_fields__"):
        return {k: _result_to_dict(v) for k, v in result.__dict__.items()}
    if isinstance(result, dict):
        return {k: _result_to_dict(v) for k, v in result.items()}
    if isinstance(result, list):
        return [_result_to_dict(item) for item in result]
    return result


# ---------------------------------------------------------------------------
# Markdown Renderer
# ---------------------------------------------------------------------------

def render_monte_carlo_markdown(result: MonteCarloResult) -> str:
    """Render Monte Carlo result as Markdown."""
    lines: List[str] = []

    lines.append("# Monte Carlo Risk Simulator Report")
    lines.append("")

    # Config
    lines.append("## Configuration")
    lines.append(f"- **Initial Capital:** {result.initial_capital:,.2f}")
    lines.append(f"- **Simulations:** {result.num_simulations:,}")
    lines.append(f"- **Horizon:** {result.horizon_days} trading days")
    lines.append(f"- **Method:** {result.method}")
    lines.append(f"- **Seed:** {result.seed}")
    lines.append(f"- **Rebalance:** {result.rebalance_cadence}")
    if result.cash_weight > 0:
        lines.append(f"- **Cash Allocation:** {result.cash_weight:.1%}")
    lines.append("")

    # Assets & weights
    lines.append("## Portfolio Weights")
    for asset in result.assets:
        w = result.weights.get(asset, 0.0)
        lines.append(f"- **{asset}:** {w:.1%}")
    if result.cash_weight > 0:
        lines.append(f"- **Cash:** {result.cash_weight:.1%}")
    lines.append("")

    # Stress overlay
    if result.stress_shock_pct != 0 or result.stress_vol_multiplier != 1.0 or result.stress_drift_adjust_pct != 0:
        lines.append("## Stress Overlay")
        if result.stress_shock_pct != 0:
            lines.append(f"- **One-Time Shock:** {result.stress_shock_pct:+.1%}")
        if result.stress_vol_multiplier != 1.0:
            lines.append(f"- **Volatility Multiplier:** {result.stress_vol_multiplier:.2f}x")
        if result.stress_drift_adjust_pct != 0:
            lines.append(f"- **Drift Adjustment:** {result.stress_drift_adjust_pct:+.2f}% annualized")
        lines.append("")

    # Equity bands
    lines.append("## Final Equity Distribution")
    lines.append(f"- **Mean:** {result.mean_final_equity:,.2f}")
    lines.append(f"- **Median:** {result.median_final_equity:,.2f}")
    lines.append(f"- **5th Percentile (P5):** {result.p5_equity:,.2f}")
    lines.append(f"- **25th Percentile (P25):** {result.p25_equity:,.2f}")
    lines.append(f"- **75th Percentile (P75):** {result.p75_equity:,.2f}")
    lines.append(f"- **95th Percentile (P95):** {result.p95_equity:,.2f}")
    lines.append("")

    # Return metrics
    lines.append("## Return Metrics")
    lines.append(f"- **Mean Return:** {result.mean_return_pct:+.2f}%")
    lines.append(f"- **Median Return:** {result.median_return_pct:+.2f}%")
    lines.append("")

    # Risk metrics
    lines.append("## Risk Metrics")
    lines.append(f"- **Probability of Loss:** {result.prob_loss:.1f}%")
    lines.append(f"- **Probability of Drawdown Breach:** {result.prob_drawdown_breach:.1f}%")
    lines.append(f"- **Max Drawdown (Median):** {result.max_drawdown_median:.2f}%")
    lines.append(f"- **Max Drawdown (P95):** {result.max_drawdown_p95:.2f}%")
    lines.append(f"- **Max Drawdown (Worst):** {result.max_drawdown_worst:.2f}%")
    lines.append(f"- **Expected Shortfall (CVaR 5%):** {result.expected_shortfall_pct:+.2f}%")
    lines.append("")

    # Worst path
    lines.append("## Worst Path Summary")
    lines.append(f"- **Worst Final Equity:** {result.worst_path_final_equity:,.2f}")
    lines.append(f"- **Worst Return:** {result.worst_path_return_pct:+.2f}%")
    lines.append(f"- **Worst Max Drawdown:** {result.worst_path_max_drawdown_pct:.2f}%")
    lines.append("")

    # Percentile table
    lines.append("## Percentile Table")
    lines.append("")
    lines.append("| Percentile | Equity | Return |")
    lines.append("|------------|--------|--------|")
    for row in result.percentile_table:
        lines.append(
            f"| P{row['percentile']:.0f} "
            f"| {row['equity']:,.2f} "
            f"| {row['return_pct']:+.2f}% |"
        )
    lines.append("")

    lines.append("---")
    lines.append("*Generated by invest-signal-kit Monte Carlo simulator. Not investment advice.*")
    return "\n".join(lines)
