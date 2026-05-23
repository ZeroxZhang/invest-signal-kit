"""Comprehensive tests for invest-signal-kit."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from invest_signal_kit.loader import load_json_file, load_signal, load_macro_context
from invest_signal_kit.schema import (
    ActionLevel,
    DataQuality,
    Direction,
    Evidence,
    EvidenceLevel,
    Instrument,
    KeyVariable,
    MacroContext,
    Signal,
    ValidationIssue,
)
from invest_signal_kit.scoring import score_signal
from invest_signal_kit.render import render_signal_markdown, render_macro_markdown
from invest_signal_kit.validators import validate_signal, validate_macro

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


class TestValidateValidActionSignal(unittest.TestCase):
    """A well-formed candidate signal with A/B evidence should pass."""

    def test_etf_signal_valid(self):
        obj, kind = load_json_file(EXAMPLES / "etf_signal.json")
        self.assertEqual(kind, "signal")
        self.assertIsInstance(obj, Signal)
        issues = validate_signal(obj)
        self.assertEqual(issues, [], f"Expected no issues, got: {issues}")

    def test_stock_shift_signal_valid(self):
        obj, kind = load_json_file(EXAMPLES / "stock_shift_signal.json")
        self.assertEqual(kind, "signal")
        issues = validate_signal(obj)
        self.assertEqual(issues, [])


class TestValidateInvalidActionSignal(unittest.TestCase):
    """An action signal missing trigger/risk fields and with D-only evidence should fail."""

    def setUp(self):
        self.obj, self.kind = load_json_file(EXAMPLES / "invalid_action_signal.json")

    def test_kind_is_signal(self):
        self.assertEqual(self.kind, "signal")

    def test_has_issues(self):
        issues = validate_signal(self.obj)
        self.assertGreater(len(issues), 0)

    def test_missing_trigger(self):
        issues = validate_signal(self.obj)
        rules = {i.rule for i in issues}
        self.assertIn("action_trigger", rules)

    def test_missing_invalidation(self):
        issues = validate_signal(self.obj)
        rules = {i.rule for i in issues}
        self.assertIn("action_invalidation", rules)

    def test_missing_max_risk(self):
        issues = validate_signal(self.obj)
        rules = {i.rule for i in issues}
        self.assertIn("action_max_risk", rules)

    def test_missing_risk_note(self):
        issues = validate_signal(self.obj)
        rules = {i.rule for i in issues}
        self.assertIn("action_risk_note", rules)

    def test_low_confidence(self):
        issues = validate_signal(self.obj)
        rules = {i.rule for i in issues}
        self.assertIn("action_confidence", rules)

    def test_d_only_evidence(self):
        issues = validate_signal(self.obj)
        rules = {i.rule for i in issues}
        self.assertIn("d_only_evidence", rules)

    def test_no_ab_evidence(self):
        issues = validate_signal(self.obj)
        rules = {i.rule for i in issues}
        self.assertIn("action_evidence_ab", rules)

    def test_bad_data_quality(self):
        issues = validate_signal(self.obj)
        rules = {i.rule for i in issues}
        self.assertIn("action_data_quality", rules)


class TestDOnlyEvidenceCandidateRejection(unittest.TestCase):
    """A candidate signal with only D-level evidence should be rejected."""

    def test_d_only_candidate(self):
        sig = Signal(
            action_level=ActionLevel.CANDIDATE,
            confidence=80,
            data_quality=DataQuality.VERIFIED,
            evidence=[Evidence(source="rumor", evidence_level=EvidenceLevel.D)],
            trigger_condition="something happens",
            invalidation_condition="something else happens",
        )
        issues = validate_signal(sig)
        rules = {i.rule for i in issues}
        self.assertIn("d_only_evidence", rules)


class TestMacroActionFieldRejection(unittest.TestCase):
    """MacroContext must never contain trade action fields."""

    def test_valid_macro_passes(self):
        obj, kind = load_json_file(EXAMPLES / "macro_context.json")
        self.assertEqual(kind, "macro")
        self.assertIsInstance(obj, MacroContext)
        issues = validate_macro(obj)
        self.assertEqual(issues, [])

    def test_suggested_action_rejected(self):
        ctx = MacroContext(date="2026-05-20", extra_fields={"suggested_action": "buy now"})
        issues = validate_macro(ctx)
        rules = {i.rule for i in issues}
        self.assertIn("macro_action_field", rules)

    def test_action_level_rejected(self):
        ctx = MacroContext(date="2026-05-20", extra_fields={"action_level": "action"})
        issues = validate_macro(ctx)
        rules = {i.rule for i in issues}
        self.assertIn("macro_action_field", rules)

    def test_trigger_condition_rejected(self):
        ctx = MacroContext(date="2026-05-20", extra_fields={"trigger_condition": "price > 100"})
        issues = validate_macro(ctx)
        rules = {i.rule for i in issues}
        self.assertIn("macro_action_field", rules)

    def test_max_risk_rejected(self):
        ctx = MacroContext(date="2026-05-20", extra_fields={"max_risk": "10%"})
        issues = validate_macro(ctx)
        rules = {i.rule for i in issues}
        self.assertIn("macro_action_field", rules)

    def test_loader_preserves_forbidden_macro_fields_for_validation(self):
        ctx = load_macro_context({
            "date": "2026-05-20",
            "risk_appetite": "rising",
            "suggested_action": "buy immediately",
        })

        self.assertEqual(ctx.extra_fields["suggested_action"], "buy immediately")
        rules = {i.rule for i in validate_macro(ctx)}
        self.assertIn("macro_action_field", rules)


class TestScoringOrder(unittest.TestCase):
    """Higher quality signals should score higher."""

    def _make_signal(self, confidence, evidence_levels, data_quality, has_risk=True):
        evidence = [Evidence(source="x", evidence_level=lv) for lv in evidence_levels]
        return Signal(
            confidence=confidence,
            evidence=evidence,
            data_quality=data_quality,
            trigger_condition="t" if has_risk else "",
            invalidation_condition="i" if has_risk else "",
            max_risk="r" if has_risk else "",
            risk_note="n" if has_risk else "",
        )

    def test_higher_confidence_higher_score(self):
        low = score_signal(self._make_signal(30, [EvidenceLevel.B], DataQuality.VERIFIED))
        high = score_signal(self._make_signal(90, [EvidenceLevel.B], DataQuality.VERIFIED))
        self.assertGreater(high["score"], low["score"])

    def test_ab_evidence_beats_c(self):
        ab = score_signal(self._make_signal(70, [EvidenceLevel.A], DataQuality.VERIFIED))
        c = score_signal(self._make_signal(70, [EvidenceLevel.C], DataQuality.VERIFIED))
        self.assertGreater(ab["score"], c["score"])

    def test_verified_beats_missing(self):
        v = score_signal(self._make_signal(70, [EvidenceLevel.B], DataQuality.VERIFIED))
        m = score_signal(self._make_signal(70, [EvidenceLevel.B], DataQuality.MISSING))
        self.assertGreater(v["score"], m["score"])

    def test_risk_fields_boost_score(self):
        with_risk = score_signal(self._make_signal(70, [EvidenceLevel.B], DataQuality.VERIFIED, True))
        without_risk = score_signal(self._make_signal(70, [EvidenceLevel.B], DataQuality.VERIFIED, False))
        self.assertGreater(with_risk["score"], without_risk["score"])

    def test_grade_present(self):
        result = score_signal(self._make_signal(90, [EvidenceLevel.A, EvidenceLevel.B], DataQuality.VERIFIED))
        self.assertIn(result["grade"], ("A", "B", "C", "D", "F"))

    def test_score_range(self):
        result = score_signal(self._make_signal(50, [EvidenceLevel.C], DataQuality.MIXED))
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 100)


class TestCLIBehavior(unittest.TestCase):
    """Test CLI commands return correct exit codes and output."""

    def test_validate_valid_exits_zero(self):
        from invest_signal_kit.cli import main
        ret = main(["validate", str(EXAMPLES / "etf_signal.json")])
        self.assertEqual(ret, 0)

    def test_validate_invalid_exits_nonzero(self):
        from invest_signal_kit.cli import main
        ret = main(["validate", str(EXAMPLES / "invalid_action_signal.json")])
        self.assertNotEqual(ret, 0)

    def test_score_outputs_json(self):
        from invest_signal_kit.cli import main
        import io
        import sys
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            ret = main(["score", str(EXAMPLES / "etf_signal.json")])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(ret, 0)
        output = captured.getvalue()
        data = json.loads(output)
        self.assertIn("score", data)
        self.assertIn("grade", data)
        self.assertIn("breakdown", data)

    def test_render_writes_file(self):
        from invest_signal_kit.cli import main
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w") as f:
            outpath = f.name
        try:
            ret = main(["render", str(EXAMPLES / "etf_signal.json"), "--output", outpath])
            self.assertEqual(ret, 0)
            content = Path(outpath).read_text(encoding="utf-8")
            self.assertIn("# Signal:", content)
            self.assertIn("invest-signal-kit", content)
        finally:
            os.unlink(outpath)

    def test_render_macro_context(self):
        from invest_signal_kit.cli import main
        import io
        import sys
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            ret = main(["render", str(EXAMPLES / "macro_context.json")])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(ret, 0)
        output = captured.getvalue()
        self.assertIn("# Macro Context:", output)
        self.assertIn("Risk Appetite", output)


class TestLoaderEdgeCases(unittest.TestCase):
    """Test loader handles various input formats."""

    def test_invalid_json_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            f.write("{invalid json")
            f.flush()
            path = f.name
        try:
            with self.assertRaises(ValueError) as ctx:
                load_json_file(path)
            self.assertIn("Invalid JSON", str(ctx.exception))
        finally:
            os.unlink(path)

    def test_non_dict_json_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump([1, 2, 3], f)
            f.flush()
            path = f.name
        try:
            with self.assertRaises(ValueError) as ctx:
                load_json_file(path)
            self.assertIn("Expected a JSON object", str(ctx.exception))
        finally:
            os.unlink(path)

    def test_signal_wrapped_key(self):
        data = {"signal": {"title": "test", "confidence": 50}}
        obj, kind = load_signal(data["signal"]), "signal"
        self.assertEqual(kind, "signal")
        self.assertEqual(obj.title, "test")

    def test_macro_wrapped_key(self):
        data = {"macro_context": {"date": "2026-01-01", "risk_appetite": "rising"}}
        obj, kind = load_macro_context(data["macro_context"]), "macro"
        self.assertEqual(kind, "macro")
        self.assertEqual(obj.risk_appetite, "rising")

    def test_unknown_type_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump({"foo": "bar"}, f)
            f.flush()
            path = f.name
        try:
            with self.assertRaises(ValueError) as ctx:
                load_json_file(path)
            self.assertIn("Cannot determine type", str(ctx.exception))
        finally:
            os.unlink(path)


class TestConfidenceRange(unittest.TestCase):
    """Confidence must be 0-100."""

    def test_over_100_fails(self):
        sig = Signal(confidence=101, action_level=ActionLevel.INFORMATION)
        issues = validate_signal(sig)
        rules = {i.rule for i in issues}
        self.assertIn("confidence_range", rules)

    def test_negative_fails(self):
        sig = Signal(confidence=-1, action_level=ActionLevel.INFORMATION)
        issues = validate_signal(sig)
        rules = {i.rule for i in issues}
        self.assertIn("confidence_range", rules)

    def test_boundary_0_passes(self):
        sig = Signal(confidence=0, action_level=ActionLevel.INFORMATION)
        issues = validate_signal(sig)
        rules = {i.rule for i in issues}
        self.assertNotIn("confidence_range", rules)

    def test_boundary_100_passes(self):
        sig = Signal(confidence=100, action_level=ActionLevel.INFORMATION)
        issues = validate_signal(sig)
        rules = {i.rule for i in issues}
        self.assertNotIn("confidence_range", rules)


class TestRenderOutput(unittest.TestCase):
    """Rendered output should contain key sections."""

    def test_signal_render_contains_sections(self):
        sig = Signal(
            id="test-001",
            title="Test Signal",
            summary="A test.",
            confidence=80,
            action_level=ActionLevel.CANDIDATE,
            direction=Direction.BULLISH,
            data_quality=DataQuality.VERIFIED,
            instrument=Instrument(code="510300", name="CSI 300 ETF"),
            evidence=[Evidence(source="test", evidence_level=EvidenceLevel.A)],
            trigger_condition="price > 4.0",
            invalidation_condition="price < 3.5",
            max_risk="10%",
            risk_note="Market volatility",
        )
        md = render_signal_markdown(sig)
        self.assertIn("# Signal:", md)
        self.assertIn("Test Signal", md)
        self.assertIn("Confidence", md)
        self.assertIn("Evidence", md)
        self.assertIn("Risk & Conditions", md)
        self.assertIn("Not investment advice", md)

    def test_macro_render_contains_sections(self):
        ctx = MacroContext(
            date="2026-05-20",
            risk_appetite="rising",
            market_regime="balanced",
            key_variables=[KeyVariable(name="rates", confidence=80)],
        )
        md = render_macro_markdown(ctx)
        self.assertIn("# Macro Context:", md)
        self.assertIn("Risk Appetite", md)
        self.assertIn("Key Variables", md)
        self.assertIn("rates", md)


if __name__ == "__main__":
    unittest.main()
