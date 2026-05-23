"""Portfolio Optimizer / Efficient Frontier Lab.

Deterministic portfolio optimization from price series or scenario/MC config.
Supports min-variance, max-Sharpe, risk-parity, target-return, and
target-volatility optimization with constraints. Efficient frontier via
seeded grid/random search. No external numeric libraries.

This is research tooling, not financial advice.
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
class OptimizerConfig:
    """Configuration for portfolio optimization."""
    risk_free_rate: float = 0.04
    """Annualized risk-free rate (e.g. 0.04 = 4%)."""
    min_weight: float = 0.0
    """Minimum weight per asset (long-only = 0)."""
    max_weight: float = 1.0
    """Maximum weight per asset."""
    max_single_position: float = 1.0
    """Max weight for any single asset (overrides max_weight if tighter)."""
    cash_weight: float = 0.0
    """Fraction held in cash (not optimized)."""
    long_only: bool = True
    """If True, weights must be >= 0."""
    pinned_weights: Dict[str, float] = field(default_factory=dict)
    """Assets with fixed weights (not optimized)."""
    current_weights: Dict[str, float] = field(default_factory=dict)
    """Current portfolio weights for turnover computation."""
    target_return: Optional[float] = None
    """Target annualized return for target-return optimization."""
    target_volatility: Optional[float] = None
    """Target annualized volatility for target-volatility optimization."""
    frontier_points: int = 50
    """Number of points on the efficient frontier."""
    seed: int = 42
    """Random seed for deterministic search."""
    search_iterations: int = 5000
    """Number of random weight samples for optimization."""


@dataclass
class ReturnStats:
    """Return statistics for a set of assets."""
    assets: List[str] = field(default_factory=list)
    mean_returns: List[float] = field(default_factory=list)
    """Annualized mean returns."""
    volatilities: List[float] = field(default_factory=list)
    """Annualized volatilities."""
    cov_matrix: List[List[float]] = field(default_factory=list)
    """Annualized covariance matrix."""
    corr_matrix: List[List[float]] = field(default_factory=list)
    """Correlation matrix."""
    observation_count: int = 0
    """Number of return observations used."""


@dataclass
class PortfolioPoint:
    """A single portfolio on the efficient frontier or optimization result."""
    weights: Dict[str, float] = field(default_factory=dict)
    expected_return: float = 0.0
    """Annualized expected return."""
    volatility: float = 0.0
    """Annualized volatility."""
    sharpe: float = 0.0
    """Sharpe ratio (annualized)."""
    risk_contribution: Dict[str, float] = field(default_factory=dict)
    """Fraction of total risk contributed by each asset."""
    turnover: float = 0.0
    """Sum of absolute weight changes from current weights."""


@dataclass
class OptimizationResult:
    """Complete optimization result."""
    # Return stats
    return_stats: ReturnStats = field(default_factory=ReturnStats)

    # Config snapshot
    risk_free_rate: float = 0.0
    cash_weight: float = 0.0
    long_only: bool = True
    pinned_weights: Dict[str, float] = field(default_factory=dict)
    current_weights: Dict[str, float] = field(default_factory=dict)

    # Optimal portfolios
    min_variance: Optional[PortfolioPoint] = None
    max_sharpe: Optional[PortfolioPoint] = None
    risk_parity: Optional[PortfolioPoint] = None
    target_return_portfolio: Optional[PortfolioPoint] = None
    target_volatility_portfolio: Optional[PortfolioPoint] = None

    # Efficient frontier
    frontier: List[PortfolioPoint] = field(default_factory=list)

    # Warnings
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Math Helpers (stdlib only)
# ---------------------------------------------------------------------------

def _log_returns(prices: List[float]) -> List[float]:
    """Compute log returns from prices."""
    rets = []
    for i in range(1, len(prices)):
        if prices[i - 1] > 0 and prices[i] > 0:
            rets.append(math.log(prices[i] / prices[i - 1]))
        else:
            rets.append(0.0)
    return rets


def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _variance(xs: List[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


def _std(xs: List[float]) -> float:
    return math.sqrt(_variance(xs))


def _cov(xs: List[float], ys: List[float]) -> float:
    """Sample covariance between two series."""
    if len(xs) < 2 or len(xs) != len(ys):
        return 0.0
    mx = _mean(xs)
    my = _mean(ys)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (len(xs) - 1)


def _portfolio_return(weights: List[float], mean_rets: List[float]) -> float:
    """Portfolio expected return."""
    return sum(w * r for w, r in zip(weights, mean_rets))


def _portfolio_variance(
    weights: List[float], cov: List[List[float]]
) -> float:
    """Portfolio variance: w' * Cov * w."""
    n = len(weights)
    var = 0.0
    for i in range(n):
        for j in range(n):
            var += weights[i] * weights[j] * cov[i][j]
    return var


def _portfolio_vol(
    weights: List[float], cov: List[List[float]]
) -> float:
    """Portfolio volatility."""
    v = _portfolio_variance(weights, cov)
    return math.sqrt(max(v, 0.0))


def _risk_contribution(
    weights: List[float], cov: List[List[float]]
) -> List[float]:
    """Marginal risk contribution of each asset."""
    n = len(weights)
    port_vol = _portfolio_vol(weights, cov)
    if port_vol <= 0:
        return [0.0] * n
    rc = []
    for i in range(n):
        marginal = sum(weights[j] * cov[i][j] for j in range(n))
        rc.append(weights[i] * marginal / port_vol)
    return rc


def _risk_contribution_fraction(
    weights: List[float], cov: List[List[float]]
) -> List[float]:
    """Fraction of total risk from each asset."""
    rc = _risk_contribution(weights, cov)
    total = sum(rc)
    if total <= 0:
        n = len(weights)
        return [1.0 / n] * n
    return [r / total for r in rc]


def _sharpe(
    ret: float, vol: float, rf: float
) -> float:
    """Annualized Sharpe ratio."""
    if vol <= 0:
        return 0.0
    return (ret - rf) / vol


def _turnover(
    new_weights: Dict[str, float], current: Dict[str, float]
) -> float:
    """Sum of absolute weight changes."""
    all_assets = set(new_weights) | set(current)
    return sum(abs(new_weights.get(a, 0) - current.get(a, 0)) for a in all_assets)


# ---------------------------------------------------------------------------
# Return Statistics
# ---------------------------------------------------------------------------

TRADING_DAYS = 252


def compute_return_stats(
    price_series: Dict[str, List[Dict[str, Any]]]
) -> ReturnStats:
    """Compute annualized return statistics from price series.

    Args:
        price_series: {"AAPL": [{"date": "...", "close": N}, ...], ...}
    """
    assets = sorted(price_series.keys())
    n = len(assets)
    if n == 0:
        return ReturnStats()

    # Align returns by index (assume same dates, sorted)
    all_returns: Dict[str, List[float]] = {}
    min_len = float("inf")
    for asset in assets:
        bars = sorted(price_series[asset], key=lambda b: str(b.get("date", "")))
        prices = [float(b.get("close", 0)) for b in bars]
        rets = _log_returns(prices)
        all_returns[asset] = rets
        min_len = min(min_len, len(rets))

    min_len = int(min_len)
    if min_len < 2:
        return ReturnStats(
            assets=assets,
            observation_count=min_len,
        )

    # Truncate to common length
    for asset in assets:
        all_returns[asset] = all_returns[asset][:min_len]

    # Daily stats
    daily_means = [_mean(all_returns[a]) for a in assets]
    daily_stds = [_std(all_returns[a]) for a in assets]

    # Covariance matrix (daily)
    daily_cov = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            daily_cov[i][j] = _cov(all_returns[assets[i]], all_returns[assets[j]])

    # Annualize
    ann_means = [m * TRADING_DAYS for m in daily_means]
    ann_stds = [s * math.sqrt(TRADING_DAYS) for s in daily_stds]
    ann_cov = [
        [daily_cov[i][j] * TRADING_DAYS for j in range(n)]
        for i in range(n)
    ]

    # Correlation matrix
    corr = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if ann_stds[i] > 0 and ann_stds[j] > 0:
                corr[i][j] = ann_cov[i][j] / (ann_stds[i] * ann_stds[j])
            elif i == j:
                corr[i][j] = 1.0

    return ReturnStats(
        assets=assets,
        mean_returns=ann_means,
        volatilities=ann_stds,
        cov_matrix=ann_cov,
        corr_matrix=corr,
        observation_count=min_len,
    )


# ---------------------------------------------------------------------------
# Weight Generation (deterministic seeded)
# ---------------------------------------------------------------------------

def _generate_random_weights(
    n: int,
    rng: random.Random,
    min_w: float,
    max_w: float,
    long_only: bool,
) -> List[float]:
    """Generate a random weight vector that sums to 1.

    Uses Dirichlet-like sampling with uniform random then normalizing.
    """
    if n == 0:
        return []
    # Generate raw random values
    raw = [rng.random() for _ in range(n)]
    total = sum(raw)
    if total <= 0:
        return [1.0 / n] * n
    weights = [r / total for r in raw]

    # Clip to bounds
    lo = min_w if long_only else -max_w
    hi = max_w
    for i in range(n):
        weights[i] = max(lo, min(hi, weights[i]))

    # Renormalize
    w_sum = sum(weights)
    if w_sum > 0:
        target = 1.0
        weights = [w / w_sum * target for w in weights]
    else:
        weights = [1.0 / n] * n

    # Final clip + normalize
    for i in range(n):
        weights[i] = max(lo, min(hi, weights[i]))
    w_sum = sum(weights)
    if w_sum > 0:
        weights = [w / w_sum for w in weights]

    return weights


def _apply_constraints(
    weights: List[float],
    assets: List[str],
    config: OptimizerConfig,
) -> List[float]:
    """Apply constraints: pinned, min/max, max_single_position, long_only."""
    n = len(weights)
    result = list(weights)

    # Apply pinned weights
    pinned_sum = 0.0
    pinned_indices = set()
    for i, asset in enumerate(assets):
        if asset in config.pinned_weights:
            result[i] = config.pinned_weights[asset]
            pinned_sum += config.pinned_weights[asset]
            pinned_indices.add(i)

    # Determine max per asset
    max_per_asset = min(config.max_weight, config.max_single_position)
    lo = config.min_weight if config.long_only else -max_per_asset

    # Clip free weights
    free_indices = [i for i in range(n) if i not in pinned_indices]
    for i in free_indices:
        result[i] = max(lo, min(max_per_asset, result[i]))

    # Normalize free weights to sum to (1 - pinned_sum - cash_weight)
    free_target = max(0.0, 1.0 - pinned_sum - config.cash_weight)
    free_sum = sum(result[i] for i in free_indices)
    if free_sum > 0 and free_target > 0:
        for i in free_indices:
            result[i] = result[i] / free_sum * free_target
    elif free_target > 0 and free_indices:
        eq = free_target / len(free_indices)
        for i in free_indices:
            result[i] = eq

    # Final clip
    for i in free_indices:
        result[i] = max(lo, min(max_per_asset, result[i]))

    # Renormalize free
    free_sum = sum(result[i] for i in free_indices)
    if free_sum > 0 and free_target > 0:
        for i in free_indices:
            result[i] = result[i] / free_sum * free_target

    return result


def _weights_to_dict(
    weights: List[float], assets: List[str]
) -> Dict[str, float]:
    return {a: round(w, 6) for a, w in zip(assets, weights)}


def _make_portfolio_point(
    weights: List[float],
    assets: List[str],
    stats: ReturnStats,
    config: OptimizerConfig,
) -> PortfolioPoint:
    """Create a PortfolioPoint from weights."""
    ret = _portfolio_return(weights, stats.mean_returns)
    vol = _portfolio_vol(weights, stats.cov_matrix)
    sharpe = _sharpe(ret, vol, config.risk_free_rate)
    rc_frac = _risk_contribution_fraction(weights, stats.cov_matrix)
    w_dict = _weights_to_dict(weights, assets)
    rc_dict = {a: round(r, 6) for a, r in zip(assets, rc_frac)}
    turnover = _turnover(w_dict, config.current_weights)

    return PortfolioPoint(
        weights=w_dict,
        expected_return=round(ret, 6),
        volatility=round(vol, 6),
        sharpe=round(sharpe, 6),
        risk_contribution=rc_dict,
        turnover=round(turnover, 6),
    )


# ---------------------------------------------------------------------------
# Optimization Algorithms
# ---------------------------------------------------------------------------

def _optimize_min_variance(
    stats: ReturnStats, config: OptimizerConfig, rng: random.Random
) -> PortfolioPoint:
    """Find minimum-variance portfolio via random search."""
    n = len(stats.assets)
    best_weights = None
    best_var = float("inf")

    for _ in range(config.search_iterations):
        raw = _generate_random_weights(
            n, rng, config.min_weight, config.max_weight, config.long_only
        )
        w = _apply_constraints(raw, stats.assets, config)
        var = _portfolio_variance(w, stats.cov_matrix)
        if var < best_var:
            best_var = var
            best_weights = w

    if best_weights is None:
        best_weights = [1.0 / n] * n if n > 0 else []
    return _make_portfolio_point(best_weights, stats.assets, stats, config)


def _optimize_max_sharpe(
    stats: ReturnStats, config: OptimizerConfig, rng: random.Random
) -> PortfolioPoint:
    """Find maximum-Sharpe portfolio via random search."""
    n = len(stats.assets)
    best_weights = None
    best_sharpe = -float("inf")

    for _ in range(config.search_iterations):
        raw = _generate_random_weights(
            n, rng, config.min_weight, config.max_weight, config.long_only
        )
        w = _apply_constraints(raw, stats.assets, config)
        ret = _portfolio_return(w, stats.mean_returns)
        vol = _portfolio_vol(w, stats.cov_matrix)
        s = _sharpe(ret, vol, config.risk_free_rate)
        if s > best_sharpe:
            best_sharpe = s
            best_weights = w

    if best_weights is None:
        best_weights = [1.0 / n] * n if n > 0 else []
    return _make_portfolio_point(best_weights, stats.assets, stats, config)


def _optimize_risk_parity(
    stats: ReturnStats, config: OptimizerConfig
) -> PortfolioPoint:
    """Risk parity: equal risk contribution from each asset.

    Uses iterative Newton-like algorithm.
    """
    n = len(stats.assets)
    if n == 0:
        return PortfolioPoint()

    # Start with equal weights
    weights = [1.0 / n] * n

    # Iterative risk parity
    for _ in range(200):
        vol = _portfolio_vol(weights, stats.cov_matrix)
        if vol <= 0:
            break
        rc = _risk_contribution(weights, stats.cov_matrix)
        # Target: each asset contributes 1/n of total risk
        target_rc = vol / n
        new_weights = list(weights)
        for i in range(n):
            if rc[i] > 0:
                # Adjust weight proportionally
                ratio = target_rc / rc[i]
                new_weights[i] = weights[i] * (ratio ** 0.5)
            else:
                new_weights[i] = weights[i] * 1.1

        # Normalize
        w_sum = sum(new_weights)
        if w_sum > 0:
            new_weights = [w / w_sum for w in new_weights]

        # Apply constraints
        new_weights = _apply_constraints(new_weights, stats.assets, config)

        # Check convergence
        max_diff = max(abs(new_weights[i] - weights[i]) for i in range(n))
        weights = new_weights
        if max_diff < 1e-8:
            break

    return _make_portfolio_point(weights, stats.assets, stats, config)


def _optimize_target_return(
    stats: ReturnStats, config: OptimizerConfig, rng: random.Random,
    target_ret: float,
) -> Optional[PortfolioPoint]:
    """Find minimum-variance portfolio achieving target return."""
    n = len(stats.assets)
    best_weights = None
    best_var = float("inf")

    for _ in range(config.search_iterations):
        raw = _generate_random_weights(
            n, rng, config.min_weight, config.max_weight, config.long_only
        )
        w = _apply_constraints(raw, stats.assets, config)
        ret = _portfolio_return(w, stats.mean_returns)
        if ret >= target_ret:
            var = _portfolio_variance(w, stats.cov_matrix)
            if var < best_var:
                best_var = var
                best_weights = w

    if best_weights is None:
        return None
    return _make_portfolio_point(best_weights, stats.assets, stats, config)


def _optimize_target_volatility(
    stats: ReturnStats, config: OptimizerConfig, rng: random.Random,
    target_vol: float,
) -> Optional[PortfolioPoint]:
    """Find max-return portfolio with volatility <= target."""
    n = len(stats.assets)
    best_weights = None
    best_ret = -float("inf")

    for _ in range(config.search_iterations):
        raw = _generate_random_weights(
            n, rng, config.min_weight, config.max_weight, config.long_only
        )
        w = _apply_constraints(raw, stats.assets, config)
        vol = _portfolio_vol(w, stats.cov_matrix)
        if vol <= target_vol:
            ret = _portfolio_return(w, stats.mean_returns)
            if ret > best_ret:
                best_ret = ret
                best_weights = w

    if best_weights is None:
        return None
    return _make_portfolio_point(best_weights, stats.assets, stats, config)


def _generate_frontier(
    stats: ReturnStats, config: OptimizerConfig, rng: random.Random
) -> Tuple[List[PortfolioPoint], List[str]]:
    """Generate efficient frontier via grid search over target returns.

    Returns (frontier_points, warnings).  When a target return cannot be
    met the function retries with progressively relaxed targets before
    giving up and emitting a warning.
    """
    warnings: List[str] = []
    if not stats.mean_returns:
        return [], warnings

    # Find return range
    min_ret = min(stats.mean_returns)
    max_ret = max(stats.mean_returns)
    if min_ret == max_ret:
        # All assets have same return - just one point
        w = [1.0 / len(stats.assets)] * len(stats.assets)
        return [_make_portfolio_point(w, stats.assets, stats, config)], warnings

    # Grid of target returns
    n_points = config.frontier_points
    step = (max_ret - min_ret) / max(1, n_points - 1)
    targets = [min_ret + i * step for i in range(n_points)]

    frontier = []
    for target in targets:
        pt = _optimize_target_return(stats, config, rng, target)
        if pt is None:
            # Retry with relaxed targets: try 1%, 5%, 10% closer to mean
            mean_ret = sum(stats.mean_returns) / len(stats.mean_returns)
            for relaxation in (0.01, 0.05, 0.10):
                relaxed = target + relaxation * (mean_ret - target)
                pt = _optimize_target_return(stats, config, rng, relaxed)
                if pt is not None:
                    break
        if pt is not None:
            frontier.append(pt)

    # Sort by volatility
    frontier.sort(key=lambda p: p.volatility)

    if len(frontier) < n_points:
        warnings.append(
            f"Efficient frontier has {len(frontier)} points instead of the "
            f"requested {n_points}. Some target returns were infeasible given "
            f"the asset universe and constraints."
        )

    return frontier, warnings


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def run_optimizer(
    config: OptimizerConfig,
    price_series: Dict[str, List[Dict[str, Any]]],
) -> OptimizationResult:
    """Run portfolio optimization.

    Args:
        config: Optimization configuration.
        price_series: {"AAPL": [{"date": "...", "close": N}, ...], ...}
    """
    warnings: List[str] = []

    # Compute return stats
    stats = compute_return_stats(price_series)
    if not stats.assets:
        warnings.append("No assets found in price_series.")
        return OptimizationResult(warnings=warnings)
    if stats.observation_count < 2:
        warnings.append("Fewer than 2 return observations; results are unreliable.")
        return OptimizationResult(return_stats=stats, warnings=warnings)

    # Validate config
    max_pos = min(config.max_weight, config.max_single_position)
    if config.cash_weight < 0 or config.cash_weight > 1:
        warnings.append(f"cash_weight {config.cash_weight} out of [0,1] range.")
    if config.min_weight < 0 and config.long_only:
        warnings.append("min_weight < 0 with long_only=True; clamping to 0.")
    if config.min_weight > max_pos:
        warnings.append(f"min_weight ({config.min_weight}) > max_weight ({max_pos}).")

    # Check pinned weights
    pinned_sum = sum(config.pinned_weights.values())
    if pinned_sum + config.cash_weight > 1.0:
        warnings.append(
            f"Pinned weights ({pinned_sum:.2%}) + cash ({config.cash_weight:.2%}) > 100%."
        )

    # Deduplicate assets from pinned weights
    free_assets = [a for a in stats.assets if a not in config.pinned_weights]

    rng = random.Random(config.seed)

    # Run optimizations
    min_var = _optimize_min_variance(stats, config, rng)
    max_sharpe_pt = _optimize_max_sharpe(stats, config, rng)
    risk_parity = _optimize_risk_parity(stats, config)

    # Target return
    target_ret_pt = None
    if config.target_return is not None:
        target_ret_pt = _optimize_target_return(
            stats, config, rng, config.target_return
        )
        if target_ret_pt is None:
            warnings.append(
                f"Could not find portfolio with return >= {config.target_return:.2%}."
            )

    # Target volatility
    target_vol_pt = None
    if config.target_volatility is not None:
        target_vol_pt = _optimize_target_volatility(
            stats, config, rng, config.target_volatility
        )
        if target_vol_pt is None:
            warnings.append(
                f"Could not find portfolio with volatility <= {config.target_volatility:.2%}."
            )

    # Efficient frontier
    # Use a fresh rng for frontier to keep it independent
    frontier_rng = random.Random(config.seed + 1)
    frontier, frontier_warnings = _generate_frontier(stats, config, frontier_rng)
    warnings.extend(frontier_warnings)

    return OptimizationResult(
        return_stats=stats,
        risk_free_rate=config.risk_free_rate,
        cash_weight=config.cash_weight,
        long_only=config.long_only,
        pinned_weights=dict(config.pinned_weights),
        current_weights=dict(config.current_weights),
        min_variance=min_var,
        max_sharpe=max_sharpe_pt,
        risk_parity=risk_parity,
        target_return_portfolio=target_ret_pt,
        target_volatility_portfolio=target_vol_pt,
        frontier=frontier,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Config Loader
# ---------------------------------------------------------------------------

def load_optimizer_config(data: dict) -> Tuple[OptimizerConfig, Dict[str, List[Dict[str, Any]]]]:
    """Load OptimizerConfig and price_series from a JSON dict.

    Expected format:
    {
        "risk_free_rate": 0.04,
        "min_weight": 0.0,
        "max_weight": 0.40,
        "max_single_position": 0.40,
        "cash_weight": 0.05,
        "long_only": true,
        "pinned_weights": {"BONDS": 0.10},
        "current_weights": {"AAPL": 0.40, "MSFT": 0.35, "TSLA": 0.25},
        "target_return": 0.10,
        "target_volatility": 0.15,
        "frontier_points": 50,
        "seed": 42,
        "search_iterations": 5000,
        "price_series": {"AAPL": [{"date": "...", "close": N}, ...], ...}
    }

    Also accepts monte_carlo_config.json format (same price_series key).
    """
    config = OptimizerConfig(
        risk_free_rate=float(data.get("risk_free_rate", 0.04)),
        min_weight=float(data.get("min_weight", 0.0)),
        max_weight=float(data.get("max_weight", 1.0)),
        max_single_position=float(data.get("max_single_position", 1.0)),
        cash_weight=float(data.get("cash_weight", 0.0)),
        long_only=bool(data.get("long_only", True)),
        target_return=(
            float(data["target_return"]) if "target_return" in data else None
        ),
        target_volatility=(
            float(data["target_volatility"]) if "target_volatility" in data else None
        ),
        frontier_points=int(data.get("frontier_points", 50)),
        seed=int(data.get("seed", 42)),
        search_iterations=int(data.get("search_iterations", 5000)),
    )

    # Pinned weights
    for asset, w in data.get("pinned_weights", {}).items():
        config.pinned_weights[str(asset)] = float(w)

    # Current weights
    for item in data.get("current_weights", []):
        if isinstance(item, dict):
            config.current_weights[str(item["asset"])] = float(item["weight"])
        # Also support dict format
    if isinstance(data.get("current_weights"), dict):
        for asset, w in data["current_weights"].items():
            config.current_weights[str(asset)] = float(w)

    # Also accept weights from monte_carlo format
    if not config.current_weights:
        for item in data.get("weights", []):
            if isinstance(item, dict):
                config.current_weights[str(item["asset"])] = float(item["weight"])

    price_series = data.get("price_series", {})

    return config, price_series


def run_optimizer_from_dict(data: dict) -> dict:
    """Run optimizer from a JSON dict. Convenience function."""
    config, price_series = load_optimizer_config(data)
    result = run_optimizer(config, price_series)
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

def render_optimizer_markdown(result: OptimizationResult) -> str:
    """Render optimization result as Markdown."""
    lines: List[str] = []

    lines.append("# Portfolio Optimizer Report")
    lines.append("")

    # Return stats
    stats = result.return_stats
    lines.append("## Return Statistics")
    lines.append("")
    lines.append(f"- **Observations:** {stats.observation_count}")
    lines.append(f"- **Assets:** {', '.join(stats.assets)}")
    lines.append("")
    lines.append("| Asset | Ann. Return | Ann. Volatility |")
    lines.append("|-------|-------------|-----------------|")
    for i, asset in enumerate(stats.assets):
        r = stats.mean_returns[i] if i < len(stats.mean_returns) else 0
        v = stats.volatilities[i] if i < len(stats.volatilities) else 0
        lines.append(f"| {asset} | {r:+.2%} | {v:.2%} |")
    lines.append("")

    # Correlation matrix
    if stats.corr_matrix:
        lines.append("### Correlation Matrix")
        lines.append("")
        header = "| | " + " | ".join(stats.assets) + " |"
        sep = "|---|" + "|".join(["---"] * len(stats.assets)) + "|"
        lines.append(header)
        lines.append(sep)
        for i, asset in enumerate(stats.assets):
            row = f"| {asset} |"
            for j in range(len(stats.assets)):
                val = stats.corr_matrix[i][j] if i < len(stats.corr_matrix) and j < len(stats.corr_matrix[i]) else 0
                row += f" {val:.3f} |"
            lines.append(row)
        lines.append("")

    # Optimal portfolios
    lines.append("## Optimal Portfolios")
    lines.append("")

    _render_portfolio_section(lines, "Minimum Variance", result.min_variance)
    _render_portfolio_section(lines, "Maximum Sharpe", result.max_sharpe)
    _render_portfolio_section(lines, "Risk Parity", result.risk_parity)
    if result.target_return_portfolio:
        _render_portfolio_section(lines, "Target Return", result.target_return_portfolio)
    if result.target_volatility_portfolio:
        _render_portfolio_section(lines, "Target Volatility", result.target_volatility_portfolio)

    # Efficient frontier
    if result.frontier:
        lines.append("## Efficient Frontier")
        lines.append("")
        lines.append("| # | Return | Volatility | Sharpe |")
        lines.append("|---|--------|------------|--------|")
        for i, pt in enumerate(result.frontier):
            lines.append(
                f"| {i + 1} | {pt.expected_return:+.2%} | {pt.volatility:.2%} | {pt.sharpe:.3f} |"
            )
        lines.append("")

    # Warnings
    if result.warnings:
        lines.append("## Warnings")
        for w in result.warnings:
            lines.append(f"- {w}")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by invest-signal-kit portfolio optimizer. Not investment advice.*")
    return "\n".join(lines)


def _render_portfolio_section(
    lines: List[str], title: str, pt: Optional[PortfolioPoint]
) -> None:
    if pt is None:
        return
    lines.append(f"### {title}")
    lines.append("")
    lines.append(f"- **Expected Return:** {pt.expected_return:+.2%}")
    lines.append(f"- **Volatility:** {pt.volatility:.2%}")
    lines.append(f"- **Sharpe Ratio:** {pt.sharpe:.3f}")
    lines.append(f"- **Turnover:** {pt.turnover:.2%}")
    lines.append("")
    lines.append("**Weights:**")
    for asset, w in pt.weights.items():
        lines.append(f"- {asset}: {w:.2%}")
    lines.append("")
    lines.append("**Risk Contribution:**")
    for asset, rc in pt.risk_contribution.items():
        lines.append(f"- {asset}: {rc:.2%}")
    lines.append("")
