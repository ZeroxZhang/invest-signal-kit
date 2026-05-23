"""Transparent 0-100 scoring for signals."""

from __future__ import annotations

from typing import Dict

from .schema import DataQuality, EvidenceLevel, Signal


def score_signal(sig: Signal) -> Dict[str, object]:
    """Score a signal on a transparent 0-100 scale.

    Components (weights):
        - confidence:        30 pts (scaled from 0-100)
        - evidence_strength: 30 pts
        - data_quality:      20 pts
        - risk_completeness: 20 pts

    Returns dict with: score, grade, breakdown.
    """
    confidence_pts = _score_confidence(sig.confidence)
    evidence_pts = _score_evidence(sig)
    quality_pts = _score_data_quality(sig.data_quality)
    risk_pts = _score_risk_completeness(sig)

    total = confidence_pts + evidence_pts + quality_pts + risk_pts
    total = max(0, min(100, total))

    return {
        "score": total,
        "grade": _grade(total),
        "breakdown": {
            "confidence": confidence_pts,
            "evidence_strength": evidence_pts,
            "data_quality": quality_pts,
            "risk_completeness": risk_pts,
        },
    }


def _score_confidence(confidence: int) -> int:
    """30 pts scaled linearly from confidence 0-100."""
    return round(confidence * 30 / 100)


def _score_evidence(sig: Signal) -> int:
    """30 pts based on evidence levels present.

    Best evidence level present determines base score:
        A present: 25 base
        B present: 20 base
        C present: 10 base
        D only:    0 base
        none:      5 base (no evidence at all is slightly better than D-only)

    Bonus +5 if multiple independent A/B sources.
    """
    if not sig.evidence:
        return 5

    levels = {e.evidence_level for e in sig.evidence}

    if EvidenceLevel.A in levels:
        base = 25
    elif EvidenceLevel.B in levels:
        base = 20
    elif EvidenceLevel.C in levels:
        base = 10
    else:
        base = 0

    # Bonus for multiple independent strong sources
    ab_count = sum(
        1 for e in sig.evidence
        if e.evidence_level in (EvidenceLevel.A, EvidenceLevel.B)
    )
    if ab_count >= 2:
        base += 5

    return min(30, base)


def _score_data_quality(dq: DataQuality) -> int:
    """20 pts based on data quality label."""
    return {
        DataQuality.VERIFIED: 20,
        DataQuality.ESTIMATED: 14,
        DataQuality.MIXED: 10,
        DataQuality.STALE: 6,
        DataQuality.MISSING: 0,
        DataQuality.UNVERIFIED: 0,
    }.get(dq, 0)


def _score_risk_completeness(sig: Signal) -> int:
    """20 pts based on presence of risk-related fields."""
    pts = 0
    if sig.trigger_condition:
        pts += 5
    if sig.invalidation_condition:
        pts += 5
    if sig.max_risk:
        pts += 5
    if sig.risk_note:
        pts += 5
    return pts


def _grade(score: int) -> str:
    """Letter grade from score."""
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 50:
        return "C"
    if score >= 30:
        return "D"
    return "F"
