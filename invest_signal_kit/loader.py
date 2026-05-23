"""Load JSON signal/macro files into typed objects."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple, Union

from .schema import (
    _FORBIDDEN_MACRO_FIELDS,
    ActionLevel,
    AssetType,
    DataQuality,
    Direction,
    Evidence,
    EvidenceLevel,
    Instrument,
    KeyVariable,
    MacroContext,
    NotesForTasks,
    Signal,
)


def _enum_or_default(enum_cls, value, default):
    """Try to parse an enum value, fall back to default."""
    if value is None:
        return default
    try:
        return enum_cls(value)
    except (ValueError, KeyError):
        return default


def _load_evidence(raw: dict) -> Evidence:
    return Evidence(
        source=raw.get("source", ""),
        date=raw.get("date", ""),
        quote_or_data=raw.get("quote_or_data", ""),
        url=raw.get("url", ""),
        evidence_level=_enum_or_default(EvidenceLevel, raw.get("evidence_level"), EvidenceLevel.C),
        note=raw.get("note", ""),
    )


def _load_instrument(raw: dict) -> Instrument:
    return Instrument(
        code=raw.get("code", ""),
        name=raw.get("name", ""),
        asset_type=_enum_or_default(AssetType, raw.get("asset_type"), AssetType.ETF),
    )


def load_signal(data: dict) -> Signal:
    """Construct a Signal from a parsed JSON dict."""
    raw_instrument = data.get("instrument")
    instrument = _load_instrument(raw_instrument) if raw_instrument else None

    return Signal(
        id=data.get("id", ""),
        title=data.get("title", ""),
        summary=data.get("summary", ""),
        source_task=data.get("source_task", ""),
        signal_type=data.get("signal_type", ""),
        instrument=instrument,
        evidence=[_load_evidence(e) for e in data.get("evidence", [])],
        direction=_enum_or_default(Direction, data.get("direction"), Direction.UNCERTAIN),
        impact_horizon=data.get("impact_horizon", ""),
        confidence=int(data.get("confidence", 0)),
        data_quality=_enum_or_default(DataQuality, data.get("data_quality"), DataQuality.UNVERIFIED),
        action_level=_enum_or_default(ActionLevel, data.get("action_level"), ActionLevel.INFORMATION),
        suggested_action=data.get("suggested_action", ""),
        trigger_condition=data.get("trigger_condition", ""),
        invalidation_condition=data.get("invalidation_condition", ""),
        max_risk=data.get("max_risk", ""),
        risk_note=data.get("risk_note", ""),
    )


def _load_key_variable(raw: dict) -> KeyVariable:
    return KeyVariable(
        name=raw.get("name", ""),
        change=raw.get("change", ""),
        confidence=int(raw.get("confidence", 0)),
        data_quality=_enum_or_default(DataQuality, raw.get("data_quality"), DataQuality.UNVERIFIED),
        possible_affected_themes=raw.get("possible_affected_themes", []),
        source=raw.get("source", ""),
        date=raw.get("date", ""),
        url=raw.get("url", ""),
    )


def _load_notes_for_tasks(raw: dict) -> NotesForTasks:
    return NotesForTasks(
        theme=raw.get("theme", ""),
        background=raw.get("background", ""),
        what_to_verify=raw.get("what_to_verify", ""),
    )


def load_macro_context(data: dict) -> MacroContext:
    """Construct a MacroContext from a parsed JSON dict.

    Forbidden trade-action fields (suggested_action, action_level,
    trigger_condition, max_risk) are captured in ``extra_fields`` so
    that validators can detect and reject them.
    """
    extra = {k: v for k, v in data.items() if k in _FORBIDDEN_MACRO_FIELDS}
    return MacroContext(
        date=data.get("date", ""),
        source_task=data.get("source_task", ""),
        risk_appetite=data.get("risk_appetite", ""),
        market_regime=data.get("market_regime", ""),
        key_variables=[_load_key_variable(v) for v in data.get("key_variables", [])],
        notes_for_tasks=[_load_notes_for_tasks(n) for n in data.get("notes_for_tasks", [])],
        summary=data.get("summary", ""),
        extra_fields=extra,
    )


def load_json_file(path: Union[str, Path]) -> Tuple[Union[Signal, MacroContext], str]:
    """Load a JSON file and return (object, kind) where kind is 'signal' or 'macro'.

    Raises ValueError on invalid JSON.
    Raises KeyError if neither 'signal' nor 'macro_context' key is found
    (or the top-level dict doesn't match either pattern).
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}, got {type(data).__name__}")

    # Detect kind: explicit key or heuristic
    if "signal" in data:
        return load_signal(data["signal"]), "signal"
    if "macro_context" in data:
        return load_macro_context(data["macro_context"]), "macro"

    # Heuristic: if it has 'action_level' or 'evidence', treat as signal
    if "action_level" in data or "evidence" in data:
        return load_signal(data), "signal"

    # Heuristic: if it has 'risk_appetite' or 'key_variables', treat as macro
    if "risk_appetite" in data or "key_variables" in data:
        return load_macro_context(data), "macro"

    raise ValueError(
        f"Cannot determine type of JSON in {path}. "
        "Wrap with {{\"signal\": ...}} or {{\"macro_context\": ...}}, "
        "or include action_level/evidence for signals or risk_appetite/key_variables for macro."
    )
