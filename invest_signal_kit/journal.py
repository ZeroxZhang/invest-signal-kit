"""Decision Journal and Post-Decision Review Engine.

Tracks investment decisions through their full lifecycle: planned -> active ->
exited / invalidated -> reviewed.  Provides lifecycle validation, outcome
review, score calibration, and performance attribution.

All formulas are deterministic and transparent.  This is research tooling,
not financial advice.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DecisionStatus:
    """Decision lifecycle statuses."""
    PLANNED = "planned"
    ACTIVE = "active"
    EXITED = "exited"
    INVALIDATED = "invalidated"
    REVIEWED = "reviewed"


_VALID_STATUSES = frozenset({
    DecisionStatus.PLANNED,
    DecisionStatus.ACTIVE,
    DecisionStatus.EXITED,
    DecisionStatus.INVALIDATED,
    DecisionStatus.REVIEWED,
})

# Allowed transitions
_TRANSITIONS: Dict[str, List[str]] = {
    DecisionStatus.PLANNED: [DecisionStatus.ACTIVE, DecisionStatus.INVALIDATED],
    DecisionStatus.ACTIVE: [DecisionStatus.EXITED, DecisionStatus.INVALIDATED],
    DecisionStatus.EXITED: [DecisionStatus.REVIEWED],
    DecisionStatus.INVALIDATED: [DecisionStatus.REVIEWED],
    DecisionStatus.REVIEWED: [],
}


class ExitReason:
    """Reasons for exiting a decision."""
    HIT_TARGET = "hit_target"
    HIT_STOP = "hit_stop"
    TIME_STOP = "time_stop"
    THESIS_BROKEN = "thesis_broken"
    OPPORTUNITY_COST = "opportunity_cost"
    MANUAL = "manual"


class OutcomeCategory:
    """Post-decision review outcome categories."""
    HIT_TARGET = "hit_target"
    HIT_STOP = "hit_stop"
    TIME_STOP = "time_stop"
    THESIS_BROKEN = "thesis_broken"
    OPPORTUNITY_COST = "opportunity_cost"
    PROCESS_ADHERENCE = "process_adherence"


# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------

@dataclass
class Decision:
    """A single tracked investment decision.

    Lifecycle: planned -> active -> exited | invalidated -> reviewed
    """
    # Identity
    id: str = ""
    instrument_code: str = ""
    instrument_name: str = ""
    direction: str = "bullish"
    sector: str = ""

    # Lifecycle
    status: str = DecisionStatus.PLANNED
    decision_date: str = ""
    entry_date: str = ""
    exit_date: str = ""

    # Thesis
    thesis_snapshot: str = ""
    thesis_quality_score: float = 0.0
    market_confirmation_score: float = 0.0
    risk_execution_score: float = 0.0
    signal_score: float = 0.0
    ev_quality: str = ""

    # Risk / sizing
    entry_price: float = 0.0
    exit_price: float = 0.0
    target_price: float = 0.0
    stop_price: float = 0.0
    risk_budget_pct: float = 0.0
    position_size_pct: float = 0.0

    # Decision metadata
    decision_level: str = "information"
    tags: List[str] = field(default_factory=list)

    # Review scheduling
    review_date: str = ""
    time_stop_date: str = ""

    # Exit data
    exit_reason: str = ""

    # Outcome (populated after review)
    actual_return_pct: float = 0.0
    r_multiple: float = 0.0
    outcome_category: str = ""
    process_score: float = 0.0
    review_notes: str = ""

    # Attribution
    market_move_pct: float = 0.0
    sector_move_pct: float = 0.0
    idiosyncratic_move_pct: float = 0.0
    sizing_contribution_pct: float = 0.0
    attribution_notes: str = ""


@dataclass
class LifecycleAlert:
    """A lifecycle validation finding."""
    rule: str
    message: str
    severity: str = "warning"  # "warning" or "error"
    decision_id: str = ""


@dataclass
class CalibrationBucket:
    """Aggregated outcome stats for a score range."""
    score_range: str = ""
    decision_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    win_rate: float = 0.0
    avg_return_pct: float = 0.0
    avg_r_multiple: float = 0.0
    total_return_pct: float = 0.0
    process_error_count: int = 0


@dataclass
class CalibrationReport:
    """Full calibration analysis across all reviewed decisions."""
    total_decisions: int = 0
    reviewed_decisions: int = 0
    buckets: List[CalibrationBucket] = field(default_factory=list)
    overall_win_rate: float = 0.0
    overall_avg_return: float = 0.0
    overall_avg_r_multiple: float = 0.0


@dataclass
class AttributionBreakdown:
    """Performance attribution for a single decision."""
    decision_id: str = ""
    instrument_code: str = ""
    total_return_pct: float = 0.0
    market_move_pct: float = 0.0
    sector_move_pct: float = 0.0
    idiosyncratic_move_pct: float = 0.0
    sizing_contribution_pct: float = 0.0
    residual_pct: float = 0.0
    notes: str = ""


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_decision(raw: dict) -> Decision:
    """Load a Decision from a dict."""
    return Decision(
        id=raw.get("id", ""),
        instrument_code=raw.get("instrument_code", ""),
        instrument_name=raw.get("instrument_name", ""),
        direction=raw.get("direction", "bullish"),
        sector=raw.get("sector", ""),
        status=raw.get("status", DecisionStatus.PLANNED),
        decision_date=raw.get("decision_date", ""),
        entry_date=raw.get("entry_date", ""),
        exit_date=raw.get("exit_date", ""),
        thesis_snapshot=raw.get("thesis_snapshot", ""),
        thesis_quality_score=float(raw.get("thesis_quality_score", 0)),
        market_confirmation_score=float(raw.get("market_confirmation_score", 0)),
        risk_execution_score=float(raw.get("risk_execution_score", 0)),
        signal_score=float(raw.get("signal_score", 0)),
        ev_quality=raw.get("ev_quality", ""),
        entry_price=float(raw.get("entry_price", 0)),
        exit_price=float(raw.get("exit_price", 0)),
        target_price=float(raw.get("target_price", 0)),
        stop_price=float(raw.get("stop_price", 0)),
        risk_budget_pct=float(raw.get("risk_budget_pct", 0)),
        position_size_pct=float(raw.get("position_size_pct", 0)),
        decision_level=raw.get("decision_level", "information"),
        tags=list(raw.get("tags", [])),
        review_date=raw.get("review_date", ""),
        time_stop_date=raw.get("time_stop_date", ""),
        exit_reason=raw.get("exit_reason", ""),
        actual_return_pct=float(raw.get("actual_return_pct", 0)),
        r_multiple=float(raw.get("r_multiple", 0)),
        outcome_category=raw.get("outcome_category", ""),
        process_score=float(raw.get("process_score", 0)),
        review_notes=raw.get("review_notes", ""),
        market_move_pct=float(raw.get("market_move_pct", 0)),
        sector_move_pct=float(raw.get("sector_move_pct", 0)),
        idiosyncratic_move_pct=float(raw.get("idiosyncratic_move_pct", 0)),
        sizing_contribution_pct=float(raw.get("sizing_contribution_pct", 0)),
        attribution_notes=raw.get("attribution_notes", ""),
    )


def load_journal(data: dict) -> List[Decision]:
    """Load a decision journal from a JSON dict.

    Expected format:
        {"decisions": [...]}
    or a bare list of decision dicts (legacy).
    """
    if isinstance(data, list):
        return [load_decision(d) for d in data]
    raw_list = data.get("decisions", [])
    return [load_decision(d) for d in raw_list]


# ---------------------------------------------------------------------------
# Lifecycle Validation
# ---------------------------------------------------------------------------

def validate_lifecycle(decisions: List[Decision], today: str = "") -> List[LifecycleAlert]:
    """Validate decision lifecycle state and return alerts.

    Rules checked:
    1. active_decision_missing_exit: active decision with no exit_date and no time_stop_date
    2. expired_review: review_date is in the past and status is not reviewed
    3. stop_breached_not_exited: entry_price vs stop_price suggests stop was hit but status is still active
    4. thesis_invalidated_not_exited: status is invalidated but no exit_date
    5. oversized_risk: risk_budget_pct > 5% (configurable threshold)
    6. stale_thesis: decision_date is more than 90 days ago and status is still planned
    7. invalid_status: status not in valid set
    8. missing_thesis: no thesis_snapshot on active/exited decisions
    9. missing_review: exited/invalidated decisions with no outcome_category
    """
    if not today:
        today = _dt.date.today().isoformat()

    alerts: List[LifecycleAlert] = []

    for d in decisions:
        # Invalid status
        if d.status not in _VALID_STATUSES:
            alerts.append(LifecycleAlert(
                rule="invalid_status",
                message=f"Decision {d.id}: invalid status '{d.status}'",
                severity="error",
                decision_id=d.id,
            ))
            continue

        # Active: missing exit
        if d.status == DecisionStatus.ACTIVE:
            if not d.exit_date and not d.time_stop_date:
                alerts.append(LifecycleAlert(
                    rule="active_decision_missing_exit",
                    message=f"Decision {d.id} ({d.instrument_code}): active with no exit or time-stop date",
                    severity="warning",
                    decision_id=d.id,
                ))

            # Stop breached detection (only when we have price data)
            if d.stop_price > 0 and d.entry_price > 0:
                if d.direction == "bullish" and d.entry_price > d.stop_price:
                    # For bullish, stop < entry; if current known exit < stop, it breached
                    # We can only check if there's an exit_price
                    if d.exit_price > 0 and d.exit_price < d.stop_price:
                        alerts.append(LifecycleAlert(
                            rule="stop_breached_not_exited",
                            message=f"Decision {d.id} ({d.instrument_code}): exit price {d.exit_price} is below stop {d.stop_price}",
                            severity="error",
                            decision_id=d.id,
                        ))

            # Missing thesis
            if not d.thesis_snapshot:
                alerts.append(LifecycleAlert(
                    rule="missing_thesis",
                    message=f"Decision {d.id} ({d.instrument_code}): active decision has no thesis snapshot",
                    severity="warning",
                    decision_id=d.id,
                ))

        # Exited / invalidated: missing review
        if d.status in (DecisionStatus.EXITED, DecisionStatus.INVALIDATED):
            if not d.outcome_category:
                alerts.append(LifecycleAlert(
                    rule="missing_review",
                    message=f"Decision {d.id} ({d.instrument_code}): {d.status} but no outcome review",
                    severity="warning",
                    decision_id=d.id,
                ))
            if not d.thesis_snapshot:
                alerts.append(LifecycleAlert(
                    rule="missing_thesis",
                    message=f"Decision {d.id} ({d.instrument_code}): {d.status} decision has no thesis snapshot",
                    severity="warning",
                    decision_id=d.id,
                ))

        # Thesis invalidated but not exited
        if d.status == DecisionStatus.INVALIDATED and not d.exit_date:
            alerts.append(LifecycleAlert(
                rule="thesis_invalidated_not_exited",
                message=f"Decision {d.id} ({d.instrument_code}): invalidated but no exit date recorded",
                severity="warning",
                decision_id=d.id,
            ))

        # Expired review
        if d.review_date and d.review_date < today and d.status != DecisionStatus.REVIEWED:
            alerts.append(LifecycleAlert(
                rule="expired_review",
                message=f"Decision {d.id} ({d.instrument_code}): review date {d.review_date} has passed",
                severity="warning",
                decision_id=d.id,
            ))

        # Oversized risk
        if d.risk_budget_pct > 5.0:
            alerts.append(LifecycleAlert(
                rule="oversized_risk",
                message=f"Decision {d.id} ({d.instrument_code}): risk budget {d.risk_budget_pct:.1f}% exceeds 5% threshold",
                severity="warning",
                decision_id=d.id,
            ))

        # Stale thesis
        if d.status == DecisionStatus.PLANNED and d.decision_date:
            try:
                dd = _dt.date.fromisoformat(d.decision_date)
                days = (_dt.date.fromisoformat(today) - dd).days
                if days > 90:
                    alerts.append(LifecycleAlert(
                        rule="stale_thesis",
                        message=f"Decision {d.id} ({d.instrument_code}): planned for {days} days — thesis may be stale",
                        severity="warning",
                        decision_id=d.id,
                    ))
            except (ValueError, TypeError):
                pass

    return alerts


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------

@dataclass
class ReviewResult:
    """Result of reviewing a single decision."""
    decision_id: str = ""
    instrument_code: str = ""
    outcome_category: str = ""
    actual_return_pct: float = 0.0
    r_multiple: float = 0.0
    process_score: float = 0.0
    process_errors: List[str] = field(default_factory=list)
    notes: str = ""


def review_decision(decision: Decision,
                    outcome_category: str = "",
                    actual_return_pct: float = 0.0,
                    r_multiple: float = 0.0,
                    process_score: float = 0.0,
                    notes: str = "") -> ReviewResult:
    """Generate a review result for a decision.

    If outcome_category is not provided, it is inferred from exit_reason.
    Process errors are detected by checking decision metadata.
    """
    # Infer outcome from exit reason if not given
    if not outcome_category:
        outcome_category = _infer_outcome(decision.exit_reason)

    # Process adherence check
    process_errors = _check_process(decision)

    # Auto-adjust process score based on errors
    if process_errors and process_score == 0:
        # Default: start at 10, subtract 2 per error, floor at 0
        process_score = max(0.0, 10.0 - len(process_errors) * 2.0)

    return ReviewResult(
        decision_id=decision.id,
        instrument_code=decision.instrument_code,
        outcome_category=outcome_category,
        actual_return_pct=actual_return_pct if actual_return_pct != 0 else decision.actual_return_pct,
        r_multiple=r_multiple if r_multiple != 0 else decision.r_multiple,
        process_score=process_score if process_score != 0 else decision.process_score,
        process_errors=process_errors,
        notes=notes or decision.review_notes,
    )


def _infer_outcome(exit_reason: str) -> str:
    """Infer outcome category from exit reason."""
    mapping = {
        ExitReason.HIT_TARGET: OutcomeCategory.HIT_TARGET,
        ExitReason.HIT_STOP: OutcomeCategory.HIT_STOP,
        ExitReason.TIME_STOP: OutcomeCategory.TIME_STOP,
        ExitReason.THESIS_BROKEN: OutcomeCategory.THESIS_BROKEN,
        ExitReason.OPPORTUNITY_COST: OutcomeCategory.OPPORTUNITY_COST,
        ExitReason.MANUAL: OutcomeCategory.PROCESS_ADHERENCE,
    }
    return mapping.get(exit_reason, OutcomeCategory.PROCESS_ADHERENCE)


def _check_process(d: Decision) -> List[str]:
    """Check decision process adherence. Returns list of process errors."""
    errors: List[str] = []

    if not d.thesis_snapshot:
        errors.append("no_thesis_snapshot")

    if d.status in (DecisionStatus.ACTIVE, DecisionStatus.EXITED):
        if d.stop_price <= 0:
            errors.append("no_stop_defined")
        if d.target_price <= 0:
            errors.append("no_target_defined")
        if d.risk_budget_pct <= 0:
            errors.append("no_risk_budget")
        if d.risk_budget_pct > 5.0:
            errors.append("oversized_risk_budget")

    if d.status == DecisionStatus.EXITED:
        if not d.exit_reason:
            errors.append("no_exit_reason")
        if not d.exit_date:
            errors.append("no_exit_date")

    if d.status == DecisionStatus.ACTIVE:
        if d.review_date and d.time_stop_date:
            pass  # good
        elif not d.review_date and not d.time_stop_date:
            errors.append("no_review_or_time_stop")

    return errors


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------

# Score bucket boundaries
_BUCKET_EDGES = [(0, 30), (30, 50), (50, 65), (65, 80), (80, 101)]
_BUCKET_LABELS = ["0-29 (F/D)", "30-49 (D/C)", "50-64 (C)", "65-79 (B)", "80-100 (A)"]


def calibrate_scores(decisions: List[Decision]) -> CalibrationReport:
    """Group reviewed decisions by initial score and compare realized outcomes.

    Uses signal_score as the primary grouping key.  Falls back to
    (thesis_quality_score + market_confirmation_score + risk_execution_score) / 3
    when signal_score is 0.

    Score buckets:
        0-29: F/D
        30-49: D/C
        50-64: C
        65-79: B
        80-100: A

    Outputs per bucket: count, win rate, avg return, avg R-multiple, process errors.
    A "win" is defined as actual_return_pct > 0.
    """
    reviewed = [d for d in decisions if d.status in (
        DecisionStatus.REVIEWED, DecisionStatus.EXITED,
    ) and d.outcome_category]

    buckets: List[CalibrationBucket] = []
    for (lo, hi), label in zip(_BUCKET_EDGES, _BUCKET_LABELS):
        bucket_decisions = [
            d for d in reviewed
            if lo <= _effective_score(d) < hi
        ]
        if not bucket_decisions:
            buckets.append(CalibrationBucket(score_range=label))
            continue

        n = len(bucket_decisions)
        wins = [d for d in bucket_decisions if d.actual_return_pct > 0]
        losses = [d for d in bucket_decisions if d.actual_return_pct <= 0]
        returns = [d.actual_return_pct for d in bucket_decisions]
        r_multiples = [d.r_multiple for d in bucket_decisions if d.r_multiple != 0]
        process_errors = sum(
            len(_check_process(d)) for d in bucket_decisions
        )

        buckets.append(CalibrationBucket(
            score_range=label,
            decision_count=n,
            win_count=len(wins),
            loss_count=len(losses),
            win_rate=round(len(wins) / n * 100, 1) if n else 0.0,
            avg_return_pct=round(sum(returns) / n, 2) if n else 0.0,
            avg_r_multiple=round(sum(r_multiples) / len(r_multiples), 2) if r_multiples else 0.0,
            total_return_pct=round(sum(returns), 2),
            process_error_count=process_errors,
        ))

    # Overall stats
    n_reviewed = len(reviewed)
    all_returns = [d.actual_return_pct for d in reviewed]
    all_r = [d.r_multiple for d in reviewed if d.r_multiple != 0]
    overall_wins = sum(1 for d in reviewed if d.actual_return_pct > 0)

    return CalibrationReport(
        total_decisions=len(decisions),
        reviewed_decisions=n_reviewed,
        buckets=buckets,
        overall_win_rate=round(overall_wins / n_reviewed * 100, 1) if n_reviewed else 0.0,
        overall_avg_return=round(sum(all_returns) / n_reviewed, 2) if n_reviewed else 0.0,
        overall_avg_r_multiple=round(sum(all_r) / len(all_r), 2) if all_r else 0.0,
    )


def _effective_score(d: Decision) -> float:
    """Get the effective score for calibration grouping."""
    if d.signal_score > 0:
        return d.signal_score
    scores = [d.thesis_quality_score, d.market_confirmation_score, d.risk_execution_score]
    nonzero = [s for s in scores if s > 0]
    return sum(nonzero) / len(nonzero) if nonzero else 0.0


# ---------------------------------------------------------------------------
# Attribution
# ---------------------------------------------------------------------------

def compute_attribution(decisions: List[Decision]) -> List[AttributionBreakdown]:
    """Compute performance attribution for reviewed decisions.

    Decomposition (additive):
        total_return = market_move + sector_move + idiosyncratic_move
        sizing_contribution = total_return * (position_size_pct / 100)
        residual = total_return - (market_move + sector_move + idiosyncratic_move)

    Attribution is only computed for decisions with outcome data.
    """
    results: List[AttributionBreakdown] = []

    reviewed = [d for d in decisions if d.status in (
        DecisionStatus.REVIEWED, DecisionStatus.EXITED,
    ) and d.outcome_category]

    for d in reviewed:
        total = d.actual_return_pct
        market = d.market_move_pct
        sector = d.sector_move_pct
        idio = d.idiosyncratic_move_pct

        decomposed = market + sector + idio
        residual = round(total - decomposed, 2)
        sizing = round(total * (d.position_size_pct / 100), 2) if d.position_size_pct > 0 else 0.0

        results.append(AttributionBreakdown(
            decision_id=d.id,
            instrument_code=d.instrument_code,
            total_return_pct=round(total, 2),
            market_move_pct=round(market, 2),
            sector_move_pct=round(sector, 2),
            idiosyncratic_move_pct=round(idio, 2),
            sizing_contribution_pct=sizing,
            residual_pct=residual,
            notes=d.attribution_notes,
        ))

    return results


# ---------------------------------------------------------------------------
# Markdown Renderer
# ---------------------------------------------------------------------------

def render_journal_markdown(decisions: List[Decision],
                            alerts: Optional[List[LifecycleAlert]] = None,
                            calibration: Optional[CalibrationReport] = None,
                            attributions: Optional[List[AttributionBreakdown]] = None,
                            ) -> str:
    """Render a full journal report in Markdown."""
    lines: List[str] = []
    lines.append("# Decision Journal Report")
    lines.append("")

    # Summary counts
    status_counts: Dict[str, int] = {}
    for d in decisions:
        status_counts[d.status] = status_counts.get(d.status, 0) + 1
    lines.append("## Summary")
    for s in _VALID_STATUSES:
        if s in status_counts:
            lines.append(f"- **{s.title()}:** {status_counts[s]}")
    lines.append(f"- **Total:** {len(decisions)}")
    lines.append("")

    # Lifecycle Alerts
    if alerts is None:
        alerts = validate_lifecycle(decisions)
    if alerts:
        lines.append("## Lifecycle Alerts")
        for a in alerts:
            marker = "ERROR" if a.severity == "error" else "WARNING"
            lines.append(f"- [{marker}] {a.message}")
        lines.append("")

    # Decisions Table
    lines.append("## Decisions")
    lines.append("")
    lines.append("| ID | Instrument | Status | Entry | Exit | Return | R-Multiple | Score |")
    lines.append("|----|-----------|--------|-------|------|--------|------------|-------|")
    for d in decisions:
        ret_str = f"{d.actual_return_pct:+.1f}%" if d.actual_return_pct != 0 else "-"
        r_str = f"{d.r_multiple:.2f}" if d.r_multiple != 0 else "-"
        score_str = f"{d.signal_score:.0f}" if d.signal_score > 0 else "-"
        exit_str = f"{d.exit_price:.2f}" if d.exit_price else "-"
        lines.append(
            f"| {d.id} | {d.instrument_code} | {d.status} "
            f"| {d.entry_price:.2f} | {exit_str} "
            f"| {ret_str} | {r_str} | {score_str} |"
        )
    lines.append("")

    # Calibration
    if calibration is None and decisions:
        calibration = calibrate_scores(decisions)
    if calibration and calibration.reviewed_decisions > 0:
        lines.append("## Score Calibration")
        lines.append("")
        lines.append(f"**Reviewed:** {calibration.reviewed_decisions} / {calibration.total_decisions} decisions")
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

    # Attribution
    if attributions is None and decisions:
        attributions = compute_attribution(decisions)
    if attributions:
        lines.append("## Performance Attribution")
        lines.append("")
        lines.append("| ID | Code | Total | Market | Sector | Idio | Sizing | Residual |")
        lines.append("|----|------|-------|--------|--------|------|--------|----------|")
        for a in attributions:
            lines.append(
                f"| {a.decision_id} | {a.instrument_code} "
                f"| {a.total_return_pct:+.1f}% | {a.market_move_pct:+.1f}% "
                f"| {a.sector_move_pct:+.1f}% | {a.idiosyncratic_move_pct:+.1f}% "
                f"| {a.sizing_contribution_pct:+.1f}% | {a.residual_pct:+.1f}% |"
            )
        lines.append("")

    lines.append("---")
    lines.append("*Generated by invest-signal-kit decision journal. Not investment advice.*")
    return "\n".join(lines)


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


def run_journal_analysis(data: dict) -> dict:
    """Run full journal analysis from a JSON dict.

    Convenience function: loads journal, validates lifecycle,
    runs calibration and attribution, returns JSON-serializable dict.
    """
    decisions = load_journal(data)
    alerts = validate_lifecycle(decisions)
    calibration = calibrate_scores(decisions)
    attributions = compute_attribution(decisions)

    return {
        "decisions": [_result_to_dict(d) for d in decisions],
        "alerts": [_result_to_dict(a) for a in alerts],
        "calibration": _result_to_dict(calibration),
        "attribution": [_result_to_dict(a) for a in attributions],
    }
