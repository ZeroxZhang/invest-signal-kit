"""Professional investment signal analysis framework.

Deterministic, transparent scorecards and models for investment research
workflow discipline. All formulas are documented, all weights are visible,
all inputs are simple numbers (0-10 scales or raw values).

This is research tooling, not financial advice.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    """Clamp value to [lo, hi]."""
    return max(lo, min(hi, value))


def _pct(value: float, total: float) -> float:
    """Percentage, safe against division by zero."""
    return (value / total * 100) if total else 0.0


def _weighted_score(items: List[Tuple[float, float]]) -> float:
    """Compute weighted average. Each item is (score_0_10, weight)."""
    total_weight = sum(w for _, w in items)
    if total_weight == 0:
        return 0.0
    return sum(s * w for s, w in items) / total_weight


def _score_to_100(score_0_10: float) -> float:
    """Convert a 0-10 score to 0-100 scale."""
    return _clamp(score_0_10 * 10.0)


# ---------------------------------------------------------------------------
# 1. Thesis Quality Scorecard
# ---------------------------------------------------------------------------

@dataclass
class ThesisQualityInput:
    """Input factors for thesis quality assessment.

    Each factor is scored 0-10:
        0-2: poor / missing
        3-4: weak
        5-6: adequate
        7-8: strong
        9-10: exceptional
    """
    evidence_strength: float = 0.0
    """Quality and reliability of supporting evidence.
    0=no evidence, 5=mixed sources, 10=primary filings + cross-verified."""

    source_diversity: float = 0.0
    """Number and independence of information sources.
    0=single rumor, 5=3+ sources, 10=5+ independent high-quality sources."""

    thesis_clarity: float = 0.0
    """How well-defined and testable the thesis is.
    0=vague hunch, 5=clear direction, 10=specific mechanism with falsifiable claims."""

    catalyst_specificity: float = 0.0
    """How identifiable and time-bound the catalysts are.
    0=no catalyst, 5=general sector trend, 10=specific event with date."""

    time_horizon_fit: float = 0.0
    """Match between thesis timeframe and evidence horizon.
    0=mismatched, 5=roughly aligned, 10=precise fit with clear milestones."""


@dataclass
class ThesisQualityResult:
    """Result of thesis quality assessment."""
    total: float = 0.0
    grade: str = ""
    factors: Dict[str, float] = field(default_factory=dict)
    weights: Dict[str, float] = field(default_factory=dict)
    blockers: List[str] = field(default_factory=list)


def score_thesis_quality(inp: ThesisQualityInput) -> ThesisQualityResult:
    """Score thesis quality on 0-100 scale.

    Weights (default equal):
        evidence_strength:  25%
        source_diversity:   20%
        thesis_clarity:     25%
        catalyst_specificity: 15%
        time_horizon_fit:   15%

    Blockers (automatic downgrade):
        - evidence_strength < 3: thesis has no real evidence
        - thesis_clarity < 3: thesis is too vague to act on
    """
    weights = {
        "evidence_strength": 0.25,
        "source_diversity": 0.20,
        "thesis_clarity": 0.25,
        "catalyst_specificity": 0.15,
        "time_horizon_fit": 0.15,
    }

    factors = {
        "evidence_strength": _clamp(inp.evidence_strength, 0, 10),
        "source_diversity": _clamp(inp.source_diversity, 0, 10),
        "thesis_clarity": _clamp(inp.thesis_clarity, 0, 10),
        "catalyst_specificity": _clamp(inp.catalyst_specificity, 0, 10),
        "time_horizon_fit": _clamp(inp.time_horizon_fit, 0, 10),
    }

    blockers: List[str] = []
    if factors["evidence_strength"] < 3:
        blockers.append("Thesis lacks sufficient evidence (score < 3)")
    if factors["thesis_clarity"] < 3:
        blockers.append("Thesis is too vague to evaluate (score < 3)")

    weighted = _weighted_score([(factors[k], weights[k]) for k in weights])
    total = _score_to_100(weighted)

    # Blockers cap the maximum score
    if blockers:
        total = min(total, 40.0)

    return ThesisQualityResult(
        total=round(total, 1),
        grade=_grade_from_score(total),
        factors={k: round(v, 1) for k, v in factors.items()},
        weights=weights,
        blockers=blockers,
    )


# ---------------------------------------------------------------------------
# 2. Market/Price Confirmation Scorecard
# ---------------------------------------------------------------------------

@dataclass
class MarketConfirmationInput:
    """Input factors for market/price confirmation.

    Each factor scored 0-10.
    """
    trend_alignment: float = 0.0
    """Is the price trend consistent with thesis direction?
    0=contradicts, 5=neutral/sideways, 10=strong confirmation."""

    momentum: float = 0.0
    """Is momentum supporting the move?
    0=divergence, 5=flat, 10=strong momentum confirmation."""

    volume_liquidity: float = 0.0
    """Volume/liquidity confirmation.
    0=dry/illiquid, 5=normal, 10=heavy institutional volume."""

    relative_strength: float = 0.0
    """Performance vs benchmark/sector.
    0=significant underperformance, 5=in-line, 10=clear outperformance."""

    regime_alignment: float = 0.0
    """Is the broader market regime favorable?
    0=hostile regime, 5=neutral, 10=strongly favorable regime."""


@dataclass
class MarketConfirmationResult:
    """Result of market confirmation assessment."""
    total: float = 0.0
    grade: str = ""
    factors: Dict[str, float] = field(default_factory=dict)
    weights: Dict[str, float] = field(default_factory=dict)
    blockers: List[str] = field(default_factory=list)


def score_market_confirmation(inp: MarketConfirmationInput) -> MarketConfirmationResult:
    """Score market/price confirmation on 0-100 scale.

    Weights:
        trend_alignment:    30%
        momentum:           20%
        volume_liquidity:   20%
        relative_strength:  15%
        regime_alignment:   15%

    Blockers:
        - trend_alignment < 2: price action contradicts the thesis
    """
    weights = {
        "trend_alignment": 0.30,
        "momentum": 0.20,
        "volume_liquidity": 0.20,
        "relative_strength": 0.15,
        "regime_alignment": 0.15,
    }

    factors = {
        "trend_alignment": _clamp(inp.trend_alignment, 0, 10),
        "momentum": _clamp(inp.momentum, 0, 10),
        "volume_liquidity": _clamp(inp.volume_liquidity, 0, 10),
        "relative_strength": _clamp(inp.relative_strength, 0, 10),
        "regime_alignment": _clamp(inp.regime_alignment, 0, 10),
    }

    blockers: List[str] = []
    if factors["trend_alignment"] < 2:
        blockers.append("Price trend contradicts thesis direction")

    weighted = _weighted_score([(factors[k], weights[k]) for k in weights])
    total = _score_to_100(weighted)

    if blockers:
        total = min(total, 30.0)

    return MarketConfirmationResult(
        total=round(total, 1),
        grade=_grade_from_score(total),
        factors={k: round(v, 1) for k, v in factors.items()},
        weights=weights,
        blockers=blockers,
    )


# ---------------------------------------------------------------------------
# 3. Risk/Execution Scorecard
# ---------------------------------------------------------------------------

@dataclass
class RiskExecutionInput:
    """Input factors for risk and execution discipline.

    Each factor scored 0-10.
    """
    invalidation_clarity: float = 0.0
    """How clear and specific is the invalidation/stop condition?
    0=none, 5=vague, 10=precise price/time/condition level."""

    max_loss_defined: float = 0.0
    """Is the maximum acceptable loss explicitly defined?
    0=unknown, 5=rough estimate, 10=exact figure with rationale."""

    position_sizing_discipline: float = 0.0
    """Is position sizing based on risk budget, not conviction?
    0=all-in on feel, 5=rough sizing, 10=risk-budget based with confidence haircut."""

    liquidity_slippage_risk: float = 0.0
    """Assessment of liquidity and slippage risk.
    0=illiquid/high slippage, 5=moderate, 10=deep liquid market."""

    concentration_risk: float = 0.0
    """How concentrated is this position in portfolio/sector context?
    0=single-name all-in, 5=moderate, 10=well-diversified position."""

    time_stop: float = 0.0
    """Is there a time-based stop/review trigger?
    0=none, 5=loose review, 10=specific date with auto-review."""


@dataclass
class RiskExecutionResult:
    """Result of risk/execution assessment."""
    total: float = 0.0
    grade: str = ""
    factors: Dict[str, float] = field(default_factory=dict)
    weights: Dict[str, float] = field(default_factory=dict)
    blockers: List[str] = field(default_factory=list)


def score_risk_execution(inp: RiskExecutionInput) -> RiskExecutionResult:
    """Score risk/execution discipline on 0-100 scale.

    Weights:
        invalidation_clarity:       25%
        max_loss_defined:           20%
        position_sizing_discipline: 20%
        liquidity_slippage_risk:    15%
        concentration_risk:         10%
        time_stop:                  10%

    Blockers:
        - invalidation_clarity < 3: no stop = no trade
        - max_loss_defined < 2: undefined risk is unacceptable
    """
    weights = {
        "invalidation_clarity": 0.25,
        "max_loss_defined": 0.20,
        "position_sizing_discipline": 0.20,
        "liquidity_slippage_risk": 0.15,
        "concentration_risk": 0.10,
        "time_stop": 0.10,
    }

    factors = {
        "invalidation_clarity": _clamp(inp.invalidation_clarity, 0, 10),
        "max_loss_defined": _clamp(inp.max_loss_defined, 0, 10),
        "position_sizing_discipline": _clamp(inp.position_sizing_discipline, 0, 10),
        "liquidity_slippage_risk": _clamp(inp.liquidity_slippage_risk, 0, 10),
        "concentration_risk": _clamp(inp.concentration_risk, 0, 10),
        "time_stop": _clamp(inp.time_stop, 0, 10),
    }

    blockers: List[str] = []
    if factors["invalidation_clarity"] < 3:
        blockers.append("No clear invalidation/stop condition defined")
    if factors["max_loss_defined"] < 2:
        blockers.append("Maximum loss is not defined")

    weighted = _weighted_score([(factors[k], weights[k]) for k in weights])
    total = _score_to_100(weighted)

    if blockers:
        total = min(total, 35.0)

    return RiskExecutionResult(
        total=round(total, 1),
        grade=_grade_from_score(total),
        factors={k: round(v, 1) for k, v in factors.items()},
        weights=weights,
        blockers=blockers,
    )


# ---------------------------------------------------------------------------
# 4. Expected Value / Scenario Model
# ---------------------------------------------------------------------------

@dataclass
class ScenarioInput:
    """Input for expected value calculation.

    Probabilities should sum to ~1.0 (will be normalized if not).
    Returns are in percent (e.g. 15.0 means +15%).
    """
    bull_probability: float = 0.25
    bull_return_pct: float = 0.0
    base_probability: float = 0.50
    base_return_pct: float = 0.0
    bear_probability: float = 0.25
    bear_return_pct: float = 0.0


@dataclass
class ScenarioResult:
    """Result of expected value analysis."""
    expected_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    payoff_asymmetry: float = 0.0
    normalized_probabilities: Dict[str, float] = field(default_factory=dict)
    scenario_details: Dict[str, Dict[str, float]] = field(default_factory=dict)
    quality: str = ""  # "positive_ev", "marginal", "negative_ev"


def calculate_expected_value(inp: ScenarioInput) -> ScenarioResult:
    """Calculate expected value from bull/base/bear scenarios.

    Expected Return = sum(prob_i * return_i)
    Max Drawdown = min(bear_return, 0) — worst case loss
    Payoff Asymmetry = avg_upside / abs(avg_downside)
        where avg_upside = weighted avg of positive-return scenarios
              avg_downside = weighted avg of negative-return scenarios

    Quality thresholds:
        - expected_return > 3%: "positive_ev"
        - expected_return > 0%: "marginal"
        - expected_return <= 0%: "negative_ev"

    Probabilities are normalized to sum to 1.0 if they don't already.
    """
    raw_total = inp.bull_probability + inp.base_probability + inp.bear_probability
    if raw_total <= 0:
        return ScenarioResult(quality="negative_ev")

    # Normalize
    bp = inp.bull_probability / raw_total
    sp = inp.base_probability / raw_total
    rp = inp.bear_probability / raw_total

    expected = bp * inp.bull_return_pct + sp * inp.base_return_pct + rp * inp.bear_return_pct
    max_dd = min(inp.bear_return_pct, 0.0)

    # Payoff asymmetry
    upside_parts = []
    downside_parts = []
    if inp.bull_return_pct > 0:
        upside_parts.append(bp * inp.bull_return_pct)
    if inp.base_return_pct > 0:
        upside_parts.append(sp * inp.base_return_pct)
    if inp.bull_return_pct < 0:
        downside_parts.append(bp * inp.bull_return_pct)
    if inp.base_return_pct < 0:
        downside_parts.append(sp * inp.base_return_pct)
    if inp.bear_return_pct < 0:
        downside_parts.append(rp * inp.bear_return_pct)
    if inp.bear_return_pct > 0:
        upside_parts.append(rp * inp.bear_return_pct)

    avg_up = sum(upside_parts) if upside_parts else 0.0
    avg_down = abs(sum(downside_parts)) if downside_parts else 0.001
    asymmetry = avg_up / avg_down if avg_down > 0 else (999.0 if avg_up > 0 else 0.0)

    if expected > 3.0:
        quality = "positive_ev"
    elif expected > 0.0:
        quality = "marginal"
    else:
        quality = "negative_ev"

    return ScenarioResult(
        expected_return_pct=round(expected, 2),
        max_drawdown_pct=round(max_dd, 2),
        payoff_asymmetry=round(min(asymmetry, 999.0), 2),
        normalized_probabilities={
            "bull": round(bp, 3),
            "base": round(sp, 3),
            "bear": round(rp, 3),
        },
        scenario_details={
            "bull": {"probability": round(bp, 3), "return_pct": inp.bull_return_pct},
            "base": {"probability": round(sp, 3), "return_pct": inp.base_return_pct},
            "bear": {"probability": round(rp, 3), "return_pct": inp.bear_return_pct},
        },
        quality=quality,
    )


# ---------------------------------------------------------------------------
# 5. Position Sizing Helper
# ---------------------------------------------------------------------------

@dataclass
class PositionSizingInput:
    """Input for risk-budget position sizing.

    Formula:
        risk_amount = portfolio_value * max_risk_pct / 100
        shares = risk_amount / (entry_price * stop_distance_pct / 100)
        adjusted_shares = shares * confidence_factor

    Where confidence_factor = confidence / 100 (clamped 0.1 - 1.0)
    """
    portfolio_value: float = 0.0
    """Total portfolio value in currency units."""

    max_risk_pct: float = 2.0
    """Maximum risk per trade as % of portfolio (default 2%)."""

    entry_price: float = 0.0
    """Planned entry price."""

    stop_distance_pct: float = 5.0
    """Distance from entry to stop-loss in percent."""

    confidence: float = 50.0
    """Confidence in the trade (0-100), used as sizing haircut."""


@dataclass
class PositionSizingResult:
    """Result of position sizing calculation."""
    risk_amount: float = 0.0
    raw_position_size: float = 0.0
    adjusted_position_size: float = 0.0
    confidence_factor: float = 0.0
    position_value: float = 0.0
    position_pct_of_portfolio: float = 0.0
    risk_reward_at_target: float = 0.0
    notes: List[str] = field(default_factory=list)


def calculate_position_size(inp: PositionSizingInput,
                            target_return_pct: float = 0.0) -> PositionSizingResult:
    """Calculate position size using risk-budget method.

    Steps:
        1. risk_amount = portfolio_value * (max_risk_pct / 100)
        2. Per-unit risk = entry_price * (stop_distance_pct / 100)
        3. raw_shares = risk_amount / per_unit_risk
        4. confidence_factor = clamp(confidence / 100, 0.1, 1.0)
        5. adjusted_shares = raw_shares * confidence_factor
        6. position_value = adjusted_shares * entry_price

    If target_return_pct > 0, also calculates risk/reward ratio:
        R:R = target_return_pct / stop_distance_pct
    """
    notes: List[str] = []

    if inp.portfolio_value <= 0:
        return PositionSizingResult(notes=["Portfolio value must be positive"])

    if inp.entry_price <= 0:
        return PositionSizingResult(notes=["Entry price must be positive"])

    if inp.stop_distance_pct <= 0:
        return PositionSizingResult(notes=["Stop distance must be positive"])

    risk_amount = inp.portfolio_value * (inp.max_risk_pct / 100.0)
    per_unit_risk = inp.entry_price * (inp.stop_distance_pct / 100.0)
    raw_shares = risk_amount / per_unit_risk

    confidence_factor = _clamp(inp.confidence / 100.0, 0.1, 1.0)
    adjusted_shares = round(raw_shares * confidence_factor)
    position_value = adjusted_shares * inp.entry_price
    position_pct = _pct(position_value, inp.portfolio_value)

    rr = 0.0
    if target_return_pct > 0 and inp.stop_distance_pct > 0:
        rr = target_return_pct / inp.stop_distance_pct

    if position_pct > 20:
        notes.append(f"Position is {position_pct:.1f}% of portfolio — consider reducing")
    if rr > 0 and rr < 1.5:
        notes.append(f"Risk/reward ratio {rr:.1f}:1 is below 1.5:1 — marginal setup")
    if confidence_factor < 0.5:
        notes.append("Low confidence haircut applied — size reduced significantly")

    return PositionSizingResult(
        risk_amount=round(risk_amount, 2),
        raw_position_size=round(raw_shares),
        adjusted_position_size=adjusted_shares,
        confidence_factor=round(confidence_factor, 3),
        position_value=round(position_value, 2),
        position_pct_of_portfolio=round(position_pct, 2),
        risk_reward_at_target=round(rr, 2),
        notes=notes,
    )


# ---------------------------------------------------------------------------
# 6. Decision Readiness (Decision Ladder)
# ---------------------------------------------------------------------------

class DecisionLevel:
    """Decision ladder levels."""
    INFORMATION = "information"
    WATCH = "watch"
    CANDIDATE = "candidate"
    ACTION = "action"


_DECISION_ORDER = [
    DecisionLevel.INFORMATION,
    DecisionLevel.WATCH,
    DecisionLevel.CANDIDATE,
    DecisionLevel.ACTION,
]


@dataclass
class DecisionReadinessInput:
    """Input for decision readiness assessment.

    Maps to the information -> watch -> candidate -> action ladder.
    Each gate has specific requirements that must be met.
    """
    # Thesis quality score (0-100)
    thesis_quality_score: float = 0.0
    # Market confirmation score (0-100)
    market_confirmation_score: float = 0.0
    # Risk/execution score (0-100)
    risk_execution_score: float = 0.0
    # Expected value quality: "positive_ev", "marginal", "negative_ev"
    ev_quality: str = "negative_ev"
    # Whether invalidation is defined
    has_invalidation: bool = False
    # Whether trigger condition is defined
    has_trigger: bool = False
    # Whether max loss is defined
    has_max_loss: bool = False
    # Whether position sizing is calculated
    has_position_sizing: bool = False
    # Blockers from individual scorecards
    scorecard_blockers: List[str] = field(default_factory=list)


@dataclass
class DecisionReadinessResult:
    """Result of decision readiness assessment."""
    current_level: str = ""
    recommended_level: str = ""
    can_promote: bool = False
    gates: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    blockers: List[str] = field(default_factory=list)
    checklist: Dict[str, bool] = field(default_factory=dict)


def assess_decision_readiness(inp: DecisionReadinessInput) -> DecisionReadinessResult:
    """Assess where a signal sits on the decision ladder and what blocks promotion.

    Decision Ladder Gates:

    INFORMATION -> WATCH:
        - thesis_quality >= 30
        - Any evidence at all

    WATCH -> CANDIDATE:
        - thesis_quality >= 50
        - market_confirmation >= 40
        - has_invalidation
        - has_trigger

    CANDIDATE -> ACTION:
        - thesis_quality >= 65
        - market_confirmation >= 55
        - risk_execution >= 60
        - ev_quality in ("positive_ev", "marginal")
        - has_max_loss
        - has_position_sizing
        - No scorecard blockers
    """
    gates: Dict[str, Dict[str, Any]] = {}
    blockers: List[str] = []
    checklist: Dict[str, bool] = {}

    # Gate 1: INFORMATION -> WATCH
    g1_pass = inp.thesis_quality_score >= 30
    gates["information_to_watch"] = {
        "required": {"thesis_quality_min": 30},
        "actual": {"thesis_quality": inp.thesis_quality_score},
        "pass": g1_pass,
    }
    checklist["thesis_quality_30"] = inp.thesis_quality_score >= 30

    # Gate 2: WATCH -> CANDIDATE
    g2_checks = {
        "thesis_quality_50": inp.thesis_quality_score >= 50,
        "market_confirmation_40": inp.market_confirmation_score >= 40,
        "has_invalidation": inp.has_invalidation,
        "has_trigger": inp.has_trigger,
    }
    g2_pass = all(g2_checks.values())
    gates["watch_to_candidate"] = {
        "required": {
            "thesis_quality_min": 50,
            "market_confirmation_min": 40,
            "has_invalidation": True,
            "has_trigger": True,
        },
        "actual": {
            "thesis_quality": inp.thesis_quality_score,
            "market_confirmation": inp.market_confirmation_score,
            "has_invalidation": inp.has_invalidation,
            "has_trigger": inp.has_trigger,
        },
        "pass": g2_pass,
    }
    checklist.update(g2_checks)

    # Gate 3: CANDIDATE -> ACTION
    ev_ok = inp.ev_quality in ("positive_ev", "marginal")
    g3_checks = {
        "thesis_quality_65": inp.thesis_quality_score >= 65,
        "market_confirmation_55": inp.market_confirmation_score >= 55,
        "risk_execution_60": inp.risk_execution_score >= 60,
        "ev_positive_or_marginal": ev_ok,
        "has_max_loss": inp.has_max_loss,
        "has_position_sizing": inp.has_position_sizing,
        "no_scorecard_blockers": len(inp.scorecard_blockers) == 0,
    }
    g3_pass = all(g3_checks.values())
    gates["candidate_to_action"] = {
        "required": {
            "thesis_quality_min": 65,
            "market_confirmation_min": 55,
            "risk_execution_min": 60,
            "ev_quality": "positive_ev or marginal",
            "has_max_loss": True,
            "has_position_sizing": True,
            "no_scorecard_blockers": True,
        },
        "actual": {
            "thesis_quality": inp.thesis_quality_score,
            "market_confirmation": inp.market_confirmation_score,
            "risk_execution": inp.risk_execution_score,
            "ev_quality": inp.ev_quality,
            "has_max_loss": inp.has_max_loss,
            "has_position_sizing": inp.has_position_sizing,
            "scorecard_blockers_count": len(inp.scorecard_blockers),
        },
        "pass": g3_pass,
    }
    checklist.update(g3_checks)

    # Determine current and recommended level
    if g3_pass:
        recommended = DecisionLevel.ACTION
    elif g2_pass:
        recommended = DecisionLevel.CANDIDATE
    elif g1_pass:
        recommended = DecisionLevel.WATCH
    else:
        recommended = DecisionLevel.INFORMATION

    # Collect blockers for the next promotion
    if not g1_pass:
        if inp.thesis_quality_score < 30:
            blockers.append("Thesis quality too low for WATCH (need >= 30)")
    elif not g2_pass:
        for k, v in g2_checks.items():
            if not v:
                blockers.append(f"WATCH->CANDIDATE gate failed: {k}")
    elif not g3_pass:
        for k, v in g3_checks.items():
            if not v:
                blockers.append(f"CANDIDATE->ACTION gate failed: {k}")

    blockers.extend(inp.scorecard_blockers)

    return DecisionReadinessResult(
        current_level=DecisionLevel.INFORMATION,
        recommended_level=recommended,
        can_promote=(recommended == DecisionLevel.ACTION),
        gates=gates,
        blockers=blockers,
        checklist=checklist,
    )


# ---------------------------------------------------------------------------
# 7. Decision Memo Generator
# ---------------------------------------------------------------------------

@dataclass
class MemoInput:
    """All inputs needed to generate a decision memo."""
    signal_title: str = ""
    signal_summary: str = ""
    instrument_code: str = ""
    instrument_name: str = ""
    direction: str = ""
    impact_horizon: str = ""

    thesis: Optional[ThesisQualityInput] = None
    market: Optional[MarketConfirmationInput] = None
    risk: Optional[RiskExecutionInput] = None
    scenario: Optional[ScenarioInput] = None
    sizing: Optional[PositionSizingInput] = None
    target_return_pct: float = 0.0


def generate_decision_memo(inp: MemoInput) -> str:
    """Generate a Markdown decision memo from all scorecard inputs.

    Combines all framework analyses into a single document suitable
    for review, archival, or sharing.
    """
    lines: List[str] = []

    lines.append(f"# Decision Memo: {inp.signal_title or '(untitled)'}")
    lines.append("")
    if inp.instrument_code:
        lines.append(f"**Instrument:** {inp.instrument_code} — {inp.instrument_name}")
    if inp.direction:
        lines.append(f"**Direction:** {inp.direction}")
    if inp.impact_horizon:
        lines.append(f"**Horizon:** {inp.impact_horizon}")
    lines.append("")

    if inp.signal_summary:
        lines.append("## Thesis Summary")
        lines.append(inp.signal_summary)
        lines.append("")

    # Thesis Quality
    if inp.thesis:
        tq = score_thesis_quality(inp.thesis)
        lines.append("## Thesis Quality")
        lines.append(f"**Score: {tq.total}/100 ({tq.grade})**")
        lines.append("")
        lines.append("| Factor | Score | Weight |")
        lines.append("|--------|-------|--------|")
        for name, score in tq.factors.items():
            w = tq.weights.get(name, 0)
            lines.append(f"| {name.replace('_', ' ').title()} | {score}/10 | {w:.0%} |")
        if tq.blockers:
            lines.append("")
            lines.append("**Blockers:**")
            for b in tq.blockers:
                lines.append(f"- {b}")
        lines.append("")

    # Market Confirmation
    if inp.market:
        mc = score_market_confirmation(inp.market)
        lines.append("## Market / Price Confirmation")
        lines.append(f"**Score: {mc.total}/100 ({mc.grade})**")
        lines.append("")
        lines.append("| Factor | Score | Weight |")
        lines.append("|--------|-------|--------|")
        for name, score in mc.factors.items():
            w = mc.weights.get(name, 0)
            lines.append(f"| {name.replace('_', ' ').title()} | {score}/10 | {w:.0%} |")
        if mc.blockers:
            lines.append("")
            lines.append("**Blockers:**")
            for b in mc.blockers:
                lines.append(f"- {b}")
        lines.append("")

    # Risk / Execution
    if inp.risk:
        re_score = score_risk_execution(inp.risk)
        lines.append("## Risk & Execution Discipline")
        lines.append(f"**Score: {re_score.total}/100 ({re_score.grade})**")
        lines.append("")
        lines.append("| Factor | Score | Weight |")
        lines.append("|--------|-------|--------|")
        for name, score in re_score.factors.items():
            w = re_score.weights.get(name, 0)
            lines.append(f"| {name.replace('_', ' ').title()} | {score}/10 | {w:.0%} |")
        if re_score.blockers:
            lines.append("")
            lines.append("**Blockers:**")
            for b in re_score.blockers:
                lines.append(f"- {b}")
        lines.append("")

    # Expected Value
    if inp.scenario:
        ev = calculate_expected_value(inp.scenario)
        lines.append("## Expected Value / Scenario Analysis")
        lines.append(f"**Expected Return: {ev.expected_return_pct:+.2f}%** ({ev.quality.replace('_', ' ')})")
        lines.append(f"**Max Drawdown: {ev.max_drawdown_pct:.2f}%**")
        lines.append(f"**Payoff Asymmetry: {ev.payoff_asymmetry:.2f}x**")
        lines.append("")
        lines.append("| Scenario | Probability | Return |")
        lines.append("|----------|-------------|--------|")
        for name, detail in ev.scenario_details.items():
            lines.append(f"| {name.title()} | {detail['probability']:.1%} | {detail['return_pct']:+.1f}% |")
        lines.append("")

    # Position Sizing
    if inp.sizing:
        ps = calculate_position_size(inp.sizing, inp.target_return_pct)
        lines.append("## Position Sizing")
        lines.append(f"- **Risk Budget:** {ps.risk_amount:,.2f}")
        lines.append(f"- **Raw Shares:** {ps.raw_position_size:,.0f}")
        lines.append(f"- **Adjusted Shares:** {ps.adjusted_position_size:,.0f} (confidence factor: {ps.confidence_factor:.2f})")
        lines.append(f"- **Position Value:** {ps.position_value:,.2f} ({ps.position_pct_of_portfolio:.1f}% of portfolio)")
        if ps.risk_reward_at_target > 0:
            lines.append(f"- **Risk/Reward at Target:** {ps.risk_reward_at_target:.2f}:1")
        if ps.notes:
            lines.append("")
            lines.append("**Notes:**")
            for n in ps.notes:
                lines.append(f"- {n}")
        lines.append("")

    # Decision Readiness
    all_blockers: List[str] = []
    tq_result = None
    mc_result = None
    re_result = None
    ev_result = None

    if inp.thesis:
        tq_result = score_thesis_quality(inp.thesis)
        all_blockers.extend(tq_result.blockers)
    if inp.market:
        mc_result = score_market_confirmation(inp.market)
        all_blockers.extend(mc_result.blockers)
    if inp.risk:
        re_result = score_risk_execution(inp.risk)
        all_blockers.extend(re_result.blockers)
    if inp.scenario:
        ev_result = calculate_expected_value(inp.scenario)

    dri = DecisionReadinessInput(
        thesis_quality_score=tq_result.total if tq_result else 0,
        market_confirmation_score=mc_result.total if mc_result else 0,
        risk_execution_score=re_result.total if re_result else 0,
        ev_quality=ev_result.quality if ev_result else "negative_ev",
        has_invalidation=inp.risk is not None and inp.risk.invalidation_clarity >= 3,
        has_trigger=inp.thesis is not None and inp.thesis.catalyst_specificity >= 3,
        has_max_loss=inp.risk is not None and inp.risk.max_loss_defined >= 2,
        has_position_sizing=inp.sizing is not None and inp.sizing.portfolio_value > 0,
        scorecard_blockers=all_blockers,
    )
    dr = assess_decision_readiness(dri)

    lines.append("## Decision Readiness")
    lines.append(f"**Recommended Level: {dr.recommended_level.upper()}**")
    if dr.can_promote:
        lines.append("**Status: All gates passed — ready for action**")
    else:
        lines.append(f"**Status: {len(dr.blockers)} blocker(s) remaining**")
    lines.append("")
    lines.append("### Checklist")
    for check, passed in dr.checklist.items():
        mark = "x" if passed else " "
        lines.append(f"- [{mark}] {check.replace('_', ' ').title()}")
    if dr.blockers:
        lines.append("")
        lines.append("### Blockers")
        for b in dr.blockers:
            lines.append(f"- {b}")
    lines.append("")

    lines.append("---")
    lines.append("*Generated by invest-signal-kit framework. Not investment advice.*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _grade_from_score(score: float) -> str:
    """Letter grade from 0-100 score."""
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 50:
        return "C"
    if score >= 30:
        return "D"
    return "F"


# ---------------------------------------------------------------------------
# JSON serialization helpers
# ---------------------------------------------------------------------------

def _result_to_dict(result: Any) -> Dict[str, Any]:
    """Convert a dataclass result to a plain dict for JSON serialization."""
    if hasattr(result, "__dataclass_fields__"):
        return {k: _result_to_dict(v) for k, v in result.__dict__.items()}
    if isinstance(result, dict):
        return {k: _result_to_dict(v) for k, v in result.items()}
    if isinstance(result, list):
        return [_result_to_dict(item) for item in result]
    return result


def run_full_analysis(signal_data: dict) -> dict:
    """Run full framework analysis from a signal JSON dict.

    Expects the signal_data to contain optional 'framework' key with
    scorecard inputs. Falls back to deriving inputs from signal fields.
    """
    fw = signal_data.get("framework", {})

    # Thesis quality
    tq_raw = fw.get("thesis_quality", {})
    tq_input = ThesisQualityInput(
        evidence_strength=tq_raw.get("evidence_strength", 5),
        source_diversity=tq_raw.get("source_diversity", 4),
        thesis_clarity=tq_raw.get("thesis_clarity", 5),
        catalyst_specificity=tq_raw.get("catalyst_specificity", 4),
        time_horizon_fit=tq_raw.get("time_horizon_fit", 5),
    )
    tq_result = score_thesis_quality(tq_input)

    # Market confirmation
    mc_raw = fw.get("market_confirmation", {})
    mc_input = MarketConfirmationInput(
        trend_alignment=mc_raw.get("trend_alignment", 5),
        momentum=mc_raw.get("momentum", 5),
        volume_liquidity=mc_raw.get("volume_liquidity", 5),
        relative_strength=mc_raw.get("relative_strength", 5),
        regime_alignment=mc_raw.get("regime_alignment", 5),
    )
    mc_result = score_market_confirmation(mc_input)

    # Risk/execution
    re_raw = fw.get("risk_execution", {})
    re_input = RiskExecutionInput(
        invalidation_clarity=re_raw.get("invalidation_clarity", 5),
        max_loss_defined=re_raw.get("max_loss_defined", 5),
        position_sizing_discipline=re_raw.get("position_sizing_discipline", 5),
        liquidity_slippage_risk=re_raw.get("liquidity_slippage_risk", 5),
        concentration_risk=re_raw.get("concentration_risk", 5),
        time_stop=re_raw.get("time_stop", 5),
    )
    re_result = score_risk_execution(re_input)

    # Expected value
    ev_raw = fw.get("scenario", {})
    ev_input = ScenarioInput(
        bull_probability=ev_raw.get("bull_probability", 0.25),
        bull_return_pct=ev_raw.get("bull_return_pct", 10),
        base_probability=ev_raw.get("base_probability", 0.50),
        base_return_pct=ev_raw.get("base_return_pct", 3),
        bear_probability=ev_raw.get("bear_probability", 0.25),
        bear_return_pct=ev_raw.get("bear_return_pct", -8),
    )
    ev_result = calculate_expected_value(ev_input)

    # Position sizing
    ps_raw = fw.get("position_sizing", {})
    ps_input = PositionSizingInput(
        portfolio_value=ps_raw.get("portfolio_value", 100000),
        max_risk_pct=ps_raw.get("max_risk_pct", 2),
        entry_price=ps_raw.get("entry_price", 100),
        stop_distance_pct=ps_raw.get("stop_distance_pct", 5),
        confidence=ps_raw.get("confidence", 60),
    )
    target_ret = ps_raw.get("target_return_pct", ev_raw.get("bull_return_pct", 10))
    ps_result = calculate_position_size(ps_input, target_ret)

    # Decision readiness
    all_blockers = tq_result.blockers + mc_result.blockers + re_result.blockers
    dri = DecisionReadinessInput(
        thesis_quality_score=tq_result.total,
        market_confirmation_score=mc_result.total,
        risk_execution_score=re_result.total,
        ev_quality=ev_result.quality,
        has_invalidation=re_input.invalidation_clarity >= 3,
        has_trigger=tq_input.catalyst_specificity >= 3,
        has_max_loss=re_input.max_loss_defined >= 2,
        has_position_sizing=ps_input.portfolio_value > 0,
        scorecard_blockers=all_blockers,
    )
    dr_result = assess_decision_readiness(dri)

    return {
        "thesis_quality": _result_to_dict(tq_result),
        "market_confirmation": _result_to_dict(mc_result),
        "risk_execution": _result_to_dict(re_result),
        "expected_value": _result_to_dict(ev_result),
        "position_sizing": _result_to_dict(ps_result),
        "decision_readiness": _result_to_dict(dr_result),
    }
