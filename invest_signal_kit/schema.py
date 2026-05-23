"""Data classes and enums for investment signals."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional


class EvidenceLevel(enum.Enum):
    """Evidence strength等级.

    A: 公司公告、交易所文件、监管披露、财报
    B: 权威财经媒体、多源交叉验证、产业链确认
    C: 单一媒体、传闻、社媒热度
    D: 无法核验、标题党、盘后小作文
    """
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class DataQuality(enum.Enum):
    """Data quality label."""
    VERIFIED = "verified"
    ESTIMATED = "estimated"
    MIXED = "mixed"
    STALE = "stale"
    MISSING = "missing"
    UNVERIFIED = "unverified"


class ActionLevel(enum.Enum):
    """Decision layer for a signal."""
    INFORMATION = "information"
    WATCH = "watch"
    CANDIDATE = "candidate"
    ACTION = "action"


class Direction(enum.Enum):
    """Signal direction."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    UNCERTAIN = "uncertain"


class AssetType(enum.Enum):
    """Instrument asset type."""
    ETF = "ETF"
    STOCK = "stock"
    INDEX = "index"
    BOND = "bond"
    COMMODITY = "commodity"
    OTHER = "other"


@dataclass
class Evidence:
    """A single piece of evidence supporting a signal."""
    source: str
    date: str = ""
    quote_or_data: str = ""
    url: str = ""
    evidence_level: EvidenceLevel = EvidenceLevel.C
    note: str = ""


@dataclass
class Instrument:
    """Financial instrument metadata."""
    code: str
    name: str = ""
    asset_type: AssetType = AssetType.ETF


@dataclass
class ValidationIssue:
    """A single validation finding."""
    rule: str
    message: str
    severity: str = "error"  # "error" or "warning"


@dataclass
class Signal:
    """A structured investment signal."""
    id: str = ""
    title: str = ""
    summary: str = ""
    source_task: str = ""
    signal_type: str = ""
    instrument: Optional[Instrument] = None
    evidence: List[Evidence] = field(default_factory=list)
    direction: Direction = Direction.UNCERTAIN
    impact_horizon: str = ""
    confidence: int = 0
    data_quality: DataQuality = DataQuality.UNVERIFIED
    action_level: ActionLevel = ActionLevel.INFORMATION
    suggested_action: str = ""
    trigger_condition: str = ""
    invalidation_condition: str = ""
    max_risk: str = ""
    risk_note: str = ""


@dataclass
class KeyVariable:
    """A macro variable tracked in MacroContext."""
    name: str
    change: str = ""
    confidence: int = 0
    data_quality: DataQuality = DataQuality.UNVERIFIED
    possible_affected_themes: List[str] = field(default_factory=list)
    source: str = ""
    date: str = ""
    url: str = ""


@dataclass
class NotesForTasks:
    """Notes from macro context for downstream tasks."""
    theme: str = ""
    background: str = ""
    what_to_verify: str = ""


_FORBIDDEN_MACRO_FIELDS = frozenset({
    "suggested_action",
    "action_level",
    "trigger_condition",
    "max_risk",
})


@dataclass
class MacroContext:
    """Macro environment context — must NOT contain trade action fields.

    Forbidden fields (suggested_action, action_level, trigger_condition,
    max_risk) that appear in input JSON are captured in ``extra_fields``
    so that validators can detect and reject them.
    """
    date: str = ""
    source_task: str = ""
    risk_appetite: str = ""
    market_regime: str = ""
    key_variables: List[KeyVariable] = field(default_factory=list)
    notes_for_tasks: List[NotesForTasks] = field(default_factory=list)
    summary: str = ""
    extra_fields: Dict[str, object] = field(default_factory=dict)
