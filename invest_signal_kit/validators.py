"""Validation rules for signals and macro context."""

from __future__ import annotations

from typing import List

from .schema import (
    ActionLevel,
    DataQuality,
    EvidenceLevel,
    MacroContext,
    Signal,
    ValidationIssue,
)


def validate_signal(sig: Signal) -> List[ValidationIssue]:
    """Validate a Signal and return a list of issues (may be empty)."""
    issues: List[ValidationIssue] = []

    _check_required_signal_fields(sig, issues)

    # --- confidence range ---
    if not (0 <= sig.confidence <= 100):
        issues.append(ValidationIssue(
            rule="confidence_range",
            message=f"confidence must be 0-100, got {sig.confidence}",
        ))

    # --- action-level checks ---
    if sig.action_level == ActionLevel.ACTION:
        _check_action_level(sig, issues)

    # --- candidate-level checks ---
    if sig.action_level in (ActionLevel.CANDIDATE, ActionLevel.ACTION):
        _check_candidate_action(sig, issues)

    # --- D evidence cannot justify candidate/action alone ---
    if sig.action_level in (ActionLevel.CANDIDATE, ActionLevel.ACTION):
        _check_d_evidence(sig, issues)

    return issues


def _check_required_signal_fields(sig: Signal, issues: List[ValidationIssue]) -> None:
    """Check the base fields expected on every published signal."""
    required = {
        "id": sig.id,
        "title": sig.title,
        "summary": sig.summary,
        "source_task": sig.source_task,
        "signal_type": sig.signal_type,
        "impact_horizon": sig.impact_horizon,
        "suggested_action": sig.suggested_action,
    }
    for field_name, value in required.items():
        if not value:
            issues.append(ValidationIssue(
                rule=f"required_{field_name}",
                message=f"signal requires {field_name}",
            ))

    if sig.instrument is None:
        issues.append(ValidationIssue(
            rule="required_instrument",
            message="signal requires instrument",
        ))
    else:
        if not sig.instrument.code:
            issues.append(ValidationIssue(
                rule="required_instrument_code",
                message="signal instrument requires code",
            ))
        if not sig.instrument.name:
            issues.append(ValidationIssue(
                rule="required_instrument_name",
                message="signal instrument requires name",
            ))

    if not sig.evidence:
        issues.append(ValidationIssue(
            rule="required_evidence",
            message="signal requires at least one evidence item",
        ))


def _check_action_level(sig: Signal, issues: List[ValidationIssue]) -> None:
    """Rules that apply only to action-level signals."""
    if sig.confidence < 70:
        issues.append(ValidationIssue(
            rule="action_confidence",
            message=f"action-level signal requires confidence >= 70, got {sig.confidence}",
        ))

    # Must have at least one A or B evidence
    has_ab = any(
        e.evidence_level in (EvidenceLevel.A, EvidenceLevel.B)
        for e in sig.evidence
    )
    if not has_ab:
        issues.append(ValidationIssue(
            rule="action_evidence_ab",
            message="action-level signal requires at least one A or B evidence item",
        ))

    # No D evidence as primary support
    if sig.evidence and sig.evidence[0].evidence_level == EvidenceLevel.D:
        issues.append(ValidationIssue(
            rule="action_no_d_primary",
            message="D evidence cannot be used as primary support for action-level signal",
        ))

    # Required fields
    if not sig.trigger_condition:
        issues.append(ValidationIssue(
            rule="action_trigger",
            message="action-level signal requires trigger_condition",
        ))
    if not sig.invalidation_condition:
        issues.append(ValidationIssue(
            rule="action_invalidation",
            message="action-level signal requires invalidation_condition",
        ))
    if not sig.max_risk:
        issues.append(ValidationIssue(
            rule="action_max_risk",
            message="action-level signal requires max_risk",
        ))
    if not sig.risk_note:
        issues.append(ValidationIssue(
            rule="action_risk_note",
            message="action-level signal requires risk_note",
        ))

    # data_quality must not be missing or unverified
    if sig.data_quality in (DataQuality.MISSING, DataQuality.UNVERIFIED):
        issues.append(ValidationIssue(
            rule="action_data_quality",
            message=f"action-level signal requires data_quality not missing/unverified, got {sig.data_quality.value}",
        ))


def _check_candidate_action(sig: Signal, issues: List[ValidationIssue]) -> None:
    """Rules that apply to both candidate and action signals."""
    if not sig.trigger_condition:
        issues.append(ValidationIssue(
            rule="candidate_trigger",
            message=f"{sig.action_level.value}-level signal requires trigger_condition",
        ))
    if not sig.invalidation_condition:
        issues.append(ValidationIssue(
            rule="candidate_invalidation",
            message=f"{sig.action_level.value}-level signal requires invalidation_condition",
        ))


def _check_d_evidence(sig: Signal, issues: List[ValidationIssue]) -> None:
    """D evidence alone cannot justify candidate/action."""
    if not sig.evidence:
        return
    all_d = all(e.evidence_level == EvidenceLevel.D for e in sig.evidence)
    if all_d:
        issues.append(ValidationIssue(
            rule="d_only_evidence",
            message="D-only evidence cannot justify candidate/action signal",
        ))


# --- MacroContext validation ---

_MACRO_ACTION_FIELDS = (
    "suggested_action",
    "action_level",
    "trigger_condition",
    "max_risk",
)


def validate_macro(ctx: MacroContext) -> List[ValidationIssue]:
    """Validate a MacroContext and return a list of issues."""
    issues: List[ValidationIssue] = []

    # MacroContext must never contain trade action fields.
    # Forbidden fields from input JSON are captured in extra_fields.
    for fld in _MACRO_ACTION_FIELDS:
        if fld in ctx.extra_fields and ctx.extra_fields[fld]:
            issues.append(ValidationIssue(
                rule="macro_action_field",
                message=f"MacroContext must not contain trade action field '{fld}'",
            ))

    return issues
