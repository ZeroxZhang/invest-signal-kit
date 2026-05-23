"""Comprehensive tests for invest-signal-kit."""

from __future__ import annotations

import io
import json
import os
import sys
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


# =========================================================================
# Original tests (preserved)
# =========================================================================

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


# =========================================================================
# Framework Tests
# =========================================================================

class TestThesisQualityScorecard(unittest.TestCase):
    """Test thesis quality scorecard."""

    def test_default_mid_scores(self):
        from invest_signal_kit.framework import ThesisQualityInput, score_thesis_quality
        inp = ThesisQualityInput(
            evidence_strength=5, source_diversity=5, thesis_clarity=5,
            catalyst_specificity=5, time_horizon_fit=5,
        )
        result = score_thesis_quality(inp)
        self.assertAlmostEqual(result.total, 50.0, places=0)
        self.assertEqual(result.grade, "C")

    def test_high_scores(self):
        from invest_signal_kit.framework import ThesisQualityInput, score_thesis_quality
        inp = ThesisQualityInput(
            evidence_strength=9, source_diversity=8, thesis_clarity=9,
            catalyst_specificity=8, time_horizon_fit=8,
        )
        result = score_thesis_quality(inp)
        self.assertGreater(result.total, 70)
        self.assertIn(result.grade, ("A", "B"))

    def test_low_scores(self):
        from invest_signal_kit.framework import ThesisQualityInput, score_thesis_quality
        inp = ThesisQualityInput(
            evidence_strength=1, source_diversity=1, thesis_clarity=1,
            catalyst_specificity=1, time_horizon_fit=1,
        )
        result = score_thesis_quality(inp)
        self.assertLess(result.total, 30)
        self.assertEqual(result.grade, "F")

    def test_evidence_blocker(self):
        from invest_signal_kit.framework import ThesisQualityInput, score_thesis_quality
        inp = ThesisQualityInput(
            evidence_strength=2, source_diversity=8, thesis_clarity=8,
            catalyst_specificity=8, time_horizon_fit=8,
        )
        result = score_thesis_quality(inp)
        self.assertLessEqual(result.total, 40)
        self.assertTrue(any("evidence" in b.lower() for b in result.blockers))

    def test_clarity_blocker(self):
        from invest_signal_kit.framework import ThesisQualityInput, score_thesis_quality
        inp = ThesisQualityInput(
            evidence_strength=8, source_diversity=8, thesis_clarity=2,
            catalyst_specificity=8, time_horizon_fit=8,
        )
        result = score_thesis_quality(inp)
        self.assertLessEqual(result.total, 40)
        self.assertTrue(any("vague" in b.lower() for b in result.blockers))

    def test_factors_dict_keys(self):
        from invest_signal_kit.framework import ThesisQualityInput, score_thesis_quality
        result = score_thesis_quality(ThesisQualityInput())
        self.assertIn("evidence_strength", result.factors)
        self.assertIn("thesis_clarity", result.factors)
        self.assertEqual(len(result.factors), 5)

    def test_weights_sum_to_one(self):
        from invest_signal_kit.framework import ThesisQualityInput, score_thesis_quality
        result = score_thesis_quality(ThesisQualityInput())
        self.assertAlmostEqual(sum(result.weights.values()), 1.0, places=5)

    def test_score_range_clamped(self):
        from invest_signal_kit.framework import ThesisQualityInput, score_thesis_quality
        result = score_thesis_quality(ThesisQualityInput(
            evidence_strength=10, source_diversity=10, thesis_clarity=10,
            catalyst_specificity=10, time_horizon_fit=10,
        ))
        self.assertLessEqual(result.total, 100)
        self.assertGreaterEqual(result.total, 0)


class TestMarketConfirmationScorecard(unittest.TestCase):
    """Test market confirmation scorecard."""

    def test_default_mid(self):
        from invest_signal_kit.framework import MarketConfirmationInput, score_market_confirmation
        result = score_market_confirmation(MarketConfirmationInput(
            trend_alignment=5, momentum=5, volume_liquidity=5,
            relative_strength=5, regime_alignment=5,
        ))
        self.assertAlmostEqual(result.total, 50.0, places=0)

    def test_trend_blocker(self):
        from invest_signal_kit.framework import MarketConfirmationInput, score_market_confirmation
        result = score_market_confirmation(MarketConfirmationInput(
            trend_alignment=1, momentum=8, volume_liquidity=8,
            relative_strength=8, regime_alignment=8,
        ))
        self.assertLessEqual(result.total, 30)
        self.assertTrue(any("trend" in b.lower() for b in result.blockers))

    def test_high_trend_alignment_boosts_score(self):
        from invest_signal_kit.framework import MarketConfirmationInput, score_market_confirmation
        low = score_market_confirmation(MarketConfirmationInput(trend_alignment=3))
        high = score_market_confirmation(MarketConfirmationInput(trend_alignment=9))
        self.assertGreater(high.total, low.total)

    def test_weights_sum_to_one(self):
        from invest_signal_kit.framework import MarketConfirmationInput, score_market_confirmation
        result = score_market_confirmation(MarketConfirmationInput())
        self.assertAlmostEqual(sum(result.weights.values()), 1.0, places=5)


class TestRiskExecutionScorecard(unittest.TestCase):
    """Test risk/execution scorecard."""

    def test_default_mid(self):
        from invest_signal_kit.framework import RiskExecutionInput, score_risk_execution
        result = score_risk_execution(RiskExecutionInput(
            invalidation_clarity=5, max_loss_defined=5,
            position_sizing_discipline=5, liquidity_slippage_risk=5,
            concentration_risk=5, time_stop=5,
        ))
        self.assertAlmostEqual(result.total, 50.0, places=0)

    def test_invalidation_blocker(self):
        from invest_signal_kit.framework import RiskExecutionInput, score_risk_execution
        result = score_risk_execution(RiskExecutionInput(
            invalidation_clarity=2, max_loss_defined=8,
            position_sizing_discipline=8, liquidity_slippage_risk=8,
            concentration_risk=8, time_stop=8,
        ))
        self.assertLessEqual(result.total, 35)
        self.assertTrue(any("invalidation" in b.lower() for b in result.blockers))

    def test_max_loss_blocker(self):
        from invest_signal_kit.framework import RiskExecutionInput, score_risk_execution
        result = score_risk_execution(RiskExecutionInput(
            invalidation_clarity=8, max_loss_defined=1,
            position_sizing_discipline=8, liquidity_slippage_risk=8,
            concentration_risk=8, time_stop=8,
        ))
        self.assertLessEqual(result.total, 35)
        self.assertTrue(any("loss" in b.lower() for b in result.blockers))

    def test_no_blockers_when_strong(self):
        from invest_signal_kit.framework import RiskExecutionInput, score_risk_execution
        result = score_risk_execution(RiskExecutionInput(
            invalidation_clarity=8, max_loss_defined=8,
            position_sizing_discipline=8, liquidity_slippage_risk=8,
            concentration_risk=8, time_stop=8,
        ))
        self.assertEqual(result.blockers, [])
        self.assertGreater(result.total, 70)


class TestExpectedValueModel(unittest.TestCase):
    """Test expected value / scenario model."""

    def test_positive_ev(self):
        from invest_signal_kit.framework import ScenarioInput, calculate_expected_value
        result = calculate_expected_value(ScenarioInput(
            bull_probability=0.3, bull_return_pct=20,
            base_probability=0.5, base_return_pct=5,
            bear_probability=0.2, bear_return_pct=-10,
        ))
        self.assertEqual(result.quality, "positive_ev")
        self.assertGreater(result.expected_return_pct, 0)

    def test_negative_ev(self):
        from invest_signal_kit.framework import ScenarioInput, calculate_expected_value
        result = calculate_expected_value(ScenarioInput(
            bull_probability=0.2, bull_return_pct=5,
            base_probability=0.3, base_return_pct=-2,
            bear_probability=0.5, bear_return_pct=-15,
        ))
        self.assertEqual(result.quality, "negative_ev")
        self.assertLess(result.expected_return_pct, 0)

    def test_marginal_ev(self):
        from invest_signal_kit.framework import ScenarioInput, calculate_expected_value
        result = calculate_expected_value(ScenarioInput(
            bull_probability=0.25, bull_return_pct=8,
            base_probability=0.50, base_return_pct=2,
            bear_probability=0.25, bear_return_pct=-5,
        ))
        self.assertEqual(result.quality, "marginal")

    def test_probabilities_normalized(self):
        from invest_signal_kit.framework import ScenarioInput, calculate_expected_value
        result = calculate_expected_value(ScenarioInput(
            bull_probability=30, bull_return_pct=10,
            base_probability=50, base_return_pct=3,
            bear_probability=20, bear_return_pct=-5,
        ))
        total = sum(result.normalized_probabilities.values())
        self.assertAlmostEqual(total, 1.0, places=2)

    def test_max_drawdown_is_bear(self):
        from invest_signal_kit.framework import ScenarioInput, calculate_expected_value
        result = calculate_expected_value(ScenarioInput(
            bull_probability=0.25, bull_return_pct=10,
            base_probability=0.50, base_return_pct=3,
            bear_probability=0.25, bear_return_pct=-12,
        ))
        self.assertEqual(result.max_drawdown_pct, -12.0)

    def test_positive_bear_no_drawdown(self):
        from invest_signal_kit.framework import ScenarioInput, calculate_expected_value
        result = calculate_expected_value(ScenarioInput(
            bull_probability=0.25, bull_return_pct=10,
            base_probability=0.50, base_return_pct=3,
            bear_probability=0.25, bear_return_pct=1,
        ))
        self.assertEqual(result.max_drawdown_pct, 0.0)

    def test_payoff_asymmetry_positive(self):
        from invest_signal_kit.framework import ScenarioInput, calculate_expected_value
        result = calculate_expected_value(ScenarioInput(
            bull_probability=0.3, bull_return_pct=20,
            base_probability=0.5, base_return_pct=5,
            bear_probability=0.2, bear_return_pct=-8,
        ))
        self.assertGreater(result.payoff_asymmetry, 1.0)

    def test_zero_probabilities_handled(self):
        from invest_signal_kit.framework import ScenarioInput, calculate_expected_value
        result = calculate_expected_value(ScenarioInput(
            bull_probability=0, bull_return_pct=10,
            base_probability=0, base_return_pct=3,
            bear_probability=0, bear_return_pct=-5,
        ))
        self.assertEqual(result.quality, "negative_ev")

    def test_expected_value_formula_correct(self):
        from invest_signal_kit.framework import ScenarioInput, calculate_expected_value
        result = calculate_expected_value(ScenarioInput(
            bull_probability=0.5, bull_return_pct=10,
            base_probability=0.5, base_return_pct=0,
            bear_probability=0, bear_return_pct=-10,
        ))
        # Expected = 0.5*10 + 0.5*0 = 5.0
        self.assertAlmostEqual(result.expected_return_pct, 5.0, places=1)

    def test_scenario_details_present(self):
        from invest_signal_kit.framework import ScenarioInput, calculate_expected_value
        result = calculate_expected_value(ScenarioInput())
        self.assertIn("bull", result.scenario_details)
        self.assertIn("base", result.scenario_details)
        self.assertIn("bear", result.scenario_details)


class TestPositionSizing(unittest.TestCase):
    """Test position sizing helper."""

    def test_basic_sizing(self):
        from invest_signal_kit.framework import PositionSizingInput, calculate_position_size
        result = calculate_position_size(PositionSizingInput(
            portfolio_value=100000, max_risk_pct=2,
            entry_price=50, stop_distance_pct=5, confidence=80,
        ))
        # risk_amount = 100000 * 0.02 = 2000
        # per_unit_risk = 50 * 0.05 = 2.5
        # raw_shares = 2000 / 2.5 = 800
        # confidence_factor = 0.8
        # adjusted = 800 * 0.8 = 640
        self.assertEqual(result.risk_amount, 2000.0)
        self.assertEqual(result.raw_position_size, 800)
        self.assertEqual(result.adjusted_position_size, 640)

    def test_position_value(self):
        from invest_signal_kit.framework import PositionSizingInput, calculate_position_size
        result = calculate_position_size(PositionSizingInput(
            portfolio_value=100000, max_risk_pct=2,
            entry_price=50, stop_distance_pct=5, confidence=80,
        ))
        self.assertEqual(result.position_value, 640 * 50)

    def test_confidence_factor_range(self):
        from invest_signal_kit.framework import PositionSizingInput, calculate_position_size
        low = calculate_position_size(PositionSizingInput(
            portfolio_value=100000, max_risk_pct=2,
            entry_price=50, stop_distance_pct=5, confidence=5,
        ))
        self.assertGreaterEqual(low.confidence_factor, 0.1)

    def test_high_confidence_no_haircut(self):
        from invest_signal_kit.framework import PositionSizingInput, calculate_position_size
        result = calculate_position_size(PositionSizingInput(
            portfolio_value=100000, max_risk_pct=2,
            entry_price=50, stop_distance_pct=5, confidence=100,
        ))
        self.assertEqual(result.confidence_factor, 1.0)
        self.assertEqual(result.adjusted_position_size, result.raw_position_size)

    def test_risk_reward_calculation(self):
        from invest_signal_kit.framework import PositionSizingInput, calculate_position_size
        result = calculate_position_size(
            PositionSizingInput(
                portfolio_value=100000, max_risk_pct=2,
                entry_price=50, stop_distance_pct=5, confidence=80,
            ),
            target_return_pct=15,
        )
        # R:R = 15 / 5 = 3.0
        self.assertAlmostEqual(result.risk_reward_at_target, 3.0, places=1)

    def test_concentration_warning(self):
        from invest_signal_kit.framework import PositionSizingInput, calculate_position_size
        result = calculate_position_size(PositionSizingInput(
            portfolio_value=10000, max_risk_pct=10,
            entry_price=1, stop_distance_pct=1, confidence=100,
        ))
        # Very large position relative to portfolio
        self.assertTrue(any("20%" in n or "reducing" in n for n in result.notes))

    def test_low_rr_warning(self):
        from invest_signal_kit.framework import PositionSizingInput, calculate_position_size
        result = calculate_position_size(
            PositionSizingInput(
                portfolio_value=100000, max_risk_pct=2,
                entry_price=50, stop_distance_pct=10, confidence=80,
            ),
            target_return_pct=5,
        )
        # R:R = 5/10 = 0.5 < 1.5
        self.assertTrue(any("1.5:1" in n for n in result.notes))

    def test_invalid_inputs(self):
        from invest_signal_kit.framework import PositionSizingInput, calculate_position_size
        result = calculate_position_size(PositionSizingInput(portfolio_value=0))
        self.assertTrue(len(result.notes) > 0)

    def test_position_pct(self):
        from invest_signal_kit.framework import PositionSizingInput, calculate_position_size
        result = calculate_position_size(PositionSizingInput(
            portfolio_value=100000, max_risk_pct=2,
            entry_price=50, stop_distance_pct=5, confidence=100,
        ))
        # position_value = 800 * 50 = 40000
        # pct = 40000 / 100000 * 100 = 40
        self.assertAlmostEqual(result.position_pct_of_portfolio, 40.0, places=1)


class TestDecisionReadiness(unittest.TestCase):
    """Test decision readiness ladder."""

    def test_information_level(self):
        from invest_signal_kit.framework import DecisionReadinessInput, assess_decision_readiness
        result = assess_decision_readiness(DecisionReadinessInput(
            thesis_quality_score=20,
            market_confirmation_score=20,
            risk_execution_score=20,
        ))
        self.assertEqual(result.recommended_level, "information")

    def test_watch_level(self):
        from invest_signal_kit.framework import DecisionReadinessInput, assess_decision_readiness
        result = assess_decision_readiness(DecisionReadinessInput(
            thesis_quality_score=35,
            market_confirmation_score=20,
            risk_execution_score=20,
        ))
        self.assertEqual(result.recommended_level, "watch")

    def test_candidate_level(self):
        from invest_signal_kit.framework import DecisionReadinessInput, assess_decision_readiness
        result = assess_decision_readiness(DecisionReadinessInput(
            thesis_quality_score=55,
            market_confirmation_score=45,
            risk_execution_score=40,
            has_invalidation=True,
            has_trigger=True,
        ))
        self.assertEqual(result.recommended_level, "candidate")

    def test_action_level(self):
        from invest_signal_kit.framework import DecisionReadinessInput, assess_decision_readiness
        result = assess_decision_readiness(DecisionReadinessInput(
            thesis_quality_score=70,
            market_confirmation_score=60,
            risk_execution_score=65,
            ev_quality="positive_ev",
            has_invalidation=True,
            has_trigger=True,
            has_max_loss=True,
            has_position_sizing=True,
        ))
        self.assertEqual(result.recommended_level, "action")
        self.assertTrue(result.can_promote)

    def test_action_blocked_by_low_thesis(self):
        from invest_signal_kit.framework import DecisionReadinessInput, assess_decision_readiness
        result = assess_decision_readiness(DecisionReadinessInput(
            thesis_quality_score=50,  # below 65 threshold
            market_confirmation_score=60,
            risk_execution_score=65,
            ev_quality="positive_ev",
            has_invalidation=True,
            has_trigger=True,
            has_max_loss=True,
            has_position_sizing=True,
        ))
        self.assertNotEqual(result.recommended_level, "action")
        self.assertTrue(any("thesis" in b.lower() for b in result.blockers))

    def test_action_blocked_by_negative_ev(self):
        from invest_signal_kit.framework import DecisionReadinessInput, assess_decision_readiness
        result = assess_decision_readiness(DecisionReadinessInput(
            thesis_quality_score=70,
            market_confirmation_score=60,
            risk_execution_score=65,
            ev_quality="negative_ev",
            has_invalidation=True,
            has_trigger=True,
            has_max_loss=True,
            has_position_sizing=True,
        ))
        self.assertNotEqual(result.recommended_level, "action")

    def test_checklist_populated(self):
        from invest_signal_kit.framework import DecisionReadinessInput, assess_decision_readiness
        result = assess_decision_readiness(DecisionReadinessInput(
            thesis_quality_score=50,
            market_confirmation_score=45,
        ))
        self.assertIn("thesis_quality_50", result.checklist)
        self.assertIn("has_invalidation", result.checklist)

    def test_marginal_ev_allows_action(self):
        from invest_signal_kit.framework import DecisionReadinessInput, assess_decision_readiness
        result = assess_decision_readiness(DecisionReadinessInput(
            thesis_quality_score=70,
            market_confirmation_score=60,
            risk_execution_score=65,
            ev_quality="marginal",
            has_invalidation=True,
            has_trigger=True,
            has_max_loss=True,
            has_position_sizing=True,
        ))
        self.assertEqual(result.recommended_level, "action")


class TestDecisionMemo(unittest.TestCase):
    """Test decision memo generation."""

    def test_memo_contains_sections(self):
        from invest_signal_kit.framework import (
            MemoInput, ThesisQualityInput, MarketConfirmationInput,
            RiskExecutionInput, ScenarioInput, PositionSizingInput,
            generate_decision_memo,
        )
        memo = generate_decision_memo(MemoInput(
            signal_title="Test Signal",
            signal_summary="A test thesis.",
            instrument_code="TEST",
            instrument_name="Test Corp",
            direction="bullish",
            impact_horizon="1 month",
            thesis=ThesisQualityInput(
                evidence_strength=7, source_diversity=6, thesis_clarity=7,
                catalyst_specificity=6, time_horizon_fit=6,
            ),
            market=MarketConfirmationInput(
                trend_alignment=7, momentum=6, volume_liquidity=6,
                relative_strength=6, regime_alignment=6,
            ),
            risk=RiskExecutionInput(
                invalidation_clarity=7, max_loss_defined=7,
                position_sizing_discipline=6, liquidity_slippage_risk=6,
                concentration_risk=5, time_stop=5,
            ),
            scenario=ScenarioInput(
                bull_probability=0.3, bull_return_pct=15,
                base_probability=0.5, base_return_pct=3,
                bear_probability=0.2, bear_return_pct=-8,
            ),
            sizing=PositionSizingInput(
                portfolio_value=100000, max_risk_pct=2,
                entry_price=50, stop_distance_pct=5, confidence=70,
            ),
        ))
        self.assertIn("# Decision Memo:", memo)
        self.assertIn("Thesis Quality", memo)
        self.assertIn("Market / Price Confirmation", memo)
        self.assertIn("Risk & Execution", memo)
        self.assertIn("Expected Value", memo)
        self.assertIn("Position Sizing", memo)
        self.assertIn("Decision Readiness", memo)
        self.assertIn("Not investment advice", memo)

    def test_memo_minimal(self):
        from invest_signal_kit.framework import MemoInput, generate_decision_memo
        memo = generate_decision_memo(MemoInput(signal_title="Minimal"))
        self.assertIn("# Decision Memo: Minimal", memo)
        self.assertIn("Not investment advice", memo)


class TestRunFullAnalysis(unittest.TestCase):
    """Test the run_full_analysis convenience function."""

    def test_professional_signal_analysis(self):
        from invest_signal_kit.framework import run_full_analysis
        data = json.loads((EXAMPLES / "professional_signal.json").read_text())
        result = run_full_analysis(data["signal"])

        self.assertIn("thesis_quality", result)
        self.assertIn("market_confirmation", result)
        self.assertIn("risk_execution", result)
        self.assertIn("expected_value", result)
        self.assertIn("position_sizing", result)
        self.assertIn("decision_readiness", result)

        tq = result["thesis_quality"]
        self.assertIn("total", tq)
        self.assertIn("grade", tq)
        self.assertIn("factors", tq)
        self.assertGreater(tq["total"], 0)

    def test_minimal_signal_analysis(self):
        from invest_signal_kit.framework import run_full_analysis
        result = run_full_analysis({"title": "test"})
        self.assertIn("thesis_quality", result)
        self.assertIn("decision_readiness", result)


# =========================================================================
# CLI Framework/Memo Tests
# =========================================================================

class TestCLIFramework(unittest.TestCase):
    """Test CLI framework command."""

    def test_framework_outputs_json(self):
        from invest_signal_kit.cli import main
        import io
        import sys
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            ret = main(["framework", str(EXAMPLES / "professional_signal.json")])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(ret, 0)
        output = captured.getvalue()
        data = json.loads(output)
        self.assertIn("thesis_quality", data)
        self.assertIn("decision_readiness", data)

    def test_framework_writes_file(self):
        from invest_signal_kit.cli import main
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            outpath = f.name
        try:
            ret = main(["framework", str(EXAMPLES / "professional_signal.json"), "--output", outpath])
            self.assertEqual(ret, 0)
            data = json.loads(Path(outpath).read_text())
            self.assertIn("thesis_quality", data)
        finally:
            os.unlink(outpath)

    def test_framework_invalid_json_fails(self):
        from invest_signal_kit.cli import main
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            f.write("{bad json")
            f.flush()
            path = f.name
        try:
            ret = main(["framework", path])
            self.assertNotEqual(ret, 0)
        finally:
            os.unlink(path)


class TestCLIMemo(unittest.TestCase):
    """Test CLI memo command."""

    def test_memo_outputs_markdown(self):
        from invest_signal_kit.cli import main
        import io
        import sys
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            ret = main(["memo", str(EXAMPLES / "professional_signal.json")])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(ret, 0)
        output = captured.getvalue()
        self.assertIn("# Decision Memo:", output)
        self.assertIn("Thesis Quality", output)

    def test_memo_writes_file(self):
        from invest_signal_kit.cli import main
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w") as f:
            outpath = f.name
        try:
            ret = main(["memo", str(EXAMPLES / "professional_signal.json"), "--output", outpath])
            self.assertEqual(ret, 0)
            content = Path(outpath).read_text()
            self.assertIn("# Decision Memo:", content)
        finally:
            os.unlink(outpath)


# =========================================================================
# Professional Signal Example Tests
# =========================================================================

class TestProfessionalSignalExample(unittest.TestCase):
    """Test the professional_signal.json example loads and validates."""

    def test_loads_as_signal(self):
        obj, kind = load_json_file(EXAMPLES / "professional_signal.json")
        self.assertEqual(kind, "signal")
        self.assertIsInstance(obj, Signal)

    def test_validates_clean(self):
        obj, _ = load_json_file(EXAMPLES / "professional_signal.json")
        issues = validate_signal(obj)
        self.assertEqual(issues, [], f"Expected no issues, got: {issues}")

    def test_has_framework_key(self):
        data = json.loads((EXAMPLES / "professional_signal.json").read_text())
        self.assertIn("framework", data)
        self.assertIn("thesis_quality", data["framework"])
        self.assertIn("scenario", data["framework"])
        self.assertIn("position_sizing", data["framework"])


# =========================================================================
# Normalization & Regression Tests
# =========================================================================

class TestNormalizeSignalJson(unittest.TestCase):
    """Test normalize_signal_json handles all supported layouts."""

    def test_form_a_top_level_siblings(self):
        from invest_signal_kit.loader import normalize_signal_json
        data = {"signal": {"id": "x"}, "framework": {"thesis_quality": {"evidence_strength": 8}}}
        sig, fw = normalize_signal_json(data)
        self.assertEqual(sig["id"], "x")
        self.assertIn("thesis_quality", fw)

    def test_form_b_nested_framework(self):
        from invest_signal_kit.loader import normalize_signal_json
        data = {"signal": {"id": "y", "framework": {"thesis_quality": {"evidence_strength": 7}}}}
        sig, fw = normalize_signal_json(data)
        self.assertEqual(sig["id"], "y")
        self.assertEqual(fw["thesis_quality"]["evidence_strength"], 7)

    def test_form_c_raw_signal(self):
        from invest_signal_kit.loader import normalize_signal_json
        data = {"id": "z", "action_level": "information", "framework": {"thesis_quality": {}}}
        sig, fw = normalize_signal_json(data)
        self.assertEqual(sig["id"], "z")
        self.assertIn("thesis_quality", fw)

    def test_top_level_framework_wins_over_nested(self):
        from invest_signal_kit.loader import normalize_signal_json
        data = {
            "signal": {"id": "z", "framework": {"thesis_quality": {"evidence_strength": 3}}},
            "framework": {"thesis_quality": {"evidence_strength": 9}},
        }
        _, fw = normalize_signal_json(data)
        self.assertEqual(fw["thesis_quality"]["evidence_strength"], 9)

    def test_no_framework_returns_empty(self):
        from invest_signal_kit.loader import normalize_signal_json
        data = {"signal": {"id": "w"}}
        _, fw = normalize_signal_json(data)
        self.assertEqual(fw, {})

    def test_professional_signal_json_form_a(self):
        from invest_signal_kit.loader import normalize_signal_json
        data = json.loads((EXAMPLES / "professional_signal.json").read_text())
        sig, fw = normalize_signal_json(data)
        self.assertEqual(sig["id"], "2026-05-20-semiconductor-etf-001")
        self.assertIn("thesis_quality", fw)
        self.assertIn("scenario", fw)
        self.assertIn("position_sizing", fw)


class TestProfessionalSignalRegression(unittest.TestCase):
    """Regression: professional_signal.json must produce high scores and ACTION level."""

    @classmethod
    def setUpClass(cls):
        from invest_signal_kit.framework import run_full_analysis
        from invest_signal_kit.loader import normalize_signal_json
        data = json.loads((EXAMPLES / "professional_signal.json").read_text())
        sig, fw = normalize_signal_json(data)
        sig["framework"] = fw
        cls.result = run_full_analysis(sig)

    def test_thesis_quality_above_default(self):
        tq = self.result["thesis_quality"]["total"]
        self.assertGreater(tq, 60, f"thesis_quality={tq}, expected >60 (above default ~50)")

    def test_market_confirmation_above_default(self):
        mc = self.result["market_confirmation"]["total"]
        self.assertGreater(mc, 55, f"market_confirmation={mc}, expected >55")

    def test_risk_execution_above_default(self):
        re = self.result["risk_execution"]["total"]
        self.assertGreater(re, 55, f"risk_execution={re}, expected >55")

    def test_expected_value_positive(self):
        self.assertEqual(self.result["expected_value"]["quality"], "positive_ev")

    def test_decision_readiness_action(self):
        level = self.result["decision_readiness"]["recommended_level"]
        self.assertEqual(level, "action", f"recommended_level={level}, expected 'action'")

    def test_cli_framework_uses_top_level_framework(self):
        """CLI framework command must pick up top-level framework sibling."""
        from invest_signal_kit.cli import main
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            ret = main(["framework", str(EXAMPLES / "professional_signal.json")])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(ret, 0)
        data = json.loads(captured.getvalue())
        self.assertEqual(data["decision_readiness"]["recommended_level"], "action")
        self.assertGreater(data["thesis_quality"]["total"], 60)

    def test_cli_memo_uses_top_level_framework(self):
        """CLI memo command must pick up top-level framework sibling."""
        from invest_signal_kit.cli import main
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            ret = main(["memo", str(EXAMPLES / "professional_signal.json")])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(ret, 0)
        memo = captured.getvalue()
        self.assertIn("ACTION", memo)
        self.assertIn("Thesis Quality", memo)


# =========================================================================
# Portfolio Risk Engine Tests
# =========================================================================

class TestHoldingProperties(unittest.TestCase):
    """Test Holding computed properties."""

    def test_market_value(self):
        from invest_signal_kit.portfolio import Holding
        h = Holding(shares=100, current_price=50.0)
        self.assertEqual(h.market_value, 5000.0)

    def test_cost_basis(self):
        from invest_signal_kit.portfolio import Holding
        h = Holding(shares=100, entry_price=45.0, current_price=50.0)
        self.assertEqual(h.cost_basis, 4500.0)

    def test_unrealized_pnl_long(self):
        from invest_signal_kit.portfolio import Holding
        h = Holding(shares=100, entry_price=45.0, current_price=50.0, direction="long")
        self.assertEqual(h.unrealized_pnl, 500.0)

    def test_unrealized_pnl_short(self):
        from invest_signal_kit.portfolio import Holding
        h = Holding(shares=100, entry_price=50.0, current_price=45.0, direction="short")
        self.assertEqual(h.unrealized_pnl, 500.0)

    def test_unrealized_pnl_pct(self):
        from invest_signal_kit.portfolio import Holding
        h = Holding(shares=100, entry_price=40.0, current_price=50.0)
        self.assertAlmostEqual(h.unrealized_pnl_pct, 25.0, places=1)

    def test_position_risk(self):
        from invest_signal_kit.portfolio import Holding
        h = Holding(shares=100, current_price=50.0, stop_price=45.0)
        self.assertEqual(h.position_risk, 500.0)

    def test_position_risk_no_stop(self):
        from invest_signal_kit.portfolio import Holding
        h = Holding(shares=100, current_price=50.0, stop_price=0.0)
        self.assertEqual(h.position_risk, 0.0)


class TestExposureCalculation(unittest.TestCase):
    """Test exposure calculation."""

    def test_basic_exposures(self):
        from invest_signal_kit.portfolio import Holding, calculate_exposures
        holdings = [
            Holding(code="A", shares=100, current_price=50.0, sector="Tech"),
            Holding(code="B", shares=200, current_price=25.0, sector="Finance"),
        ]
        report = calculate_exposures(holdings, cash=2500.0)
        self.assertAlmostEqual(report.total_value, 12500.0, places=0)
        self.assertAlmostEqual(report.invested_value, 10000.0, places=0)
        self.assertAlmostEqual(report.invested_pct, 80.0, places=0)

    def test_position_exposure_pct(self):
        from invest_signal_kit.portfolio import Holding, calculate_exposures
        holdings = [Holding(code="A", shares=100, current_price=100.0)]
        report = calculate_exposures(holdings, cash=0.0)
        self.assertAlmostEqual(report.positions[0].exposure_pct, 100.0, places=0)

    def test_sector_aggregation(self):
        from invest_signal_kit.portfolio import Holding, calculate_exposures
        holdings = [
            Holding(code="A", shares=100, current_price=50.0, sector="Tech"),
            Holding(code="B", shares=100, current_price=50.0, sector="Tech"),
            Holding(code="C", shares=100, current_price=50.0, sector="Finance"),
        ]
        report = calculate_exposures(holdings, cash=0.0)
        sectors = {s.sector: s for s in report.sectors}
        self.assertAlmostEqual(sectors["Tech"].exposure_pct, 66.67, places=1)
        self.assertEqual(sectors["Tech"].position_count, 2)

    def test_risk_calculation(self):
        from invest_signal_kit.portfolio import Holding, calculate_exposures
        holdings = [
            Holding(code="A", shares=100, current_price=50.0, stop_price=45.0),
        ]
        report = calculate_exposures(holdings, cash=5000.0)
        # risk = 100 * (50 - 45) = 500
        self.assertAlmostEqual(report.total_risk, 500.0, places=0)
        # risk_pct = 500 / 10000 * 100 = 5%
        self.assertAlmostEqual(report.total_risk_pct, 5.0, places=1)


class TestConcentrationCheck(unittest.TestCase):
    """Test concentration limit checking."""

    def test_position_over_limit(self):
        from invest_signal_kit.portfolio import Holding, PortfolioPolicy, check_concentration
        holdings = [Holding(code="A", shares=1000, current_price=30.0)]
        policy = PortfolioPolicy(max_position_pct=20.0)
        violations = check_concentration(holdings, policy, 100000.0)
        self.assertTrue(any(v.rule == "position_concentration" for v in violations))

    def test_position_under_limit(self):
        from invest_signal_kit.portfolio import Holding, PortfolioPolicy, check_concentration
        holdings = [Holding(code="A", shares=100, current_price=50.0)]
        policy = PortfolioPolicy(max_position_pct=20.0)
        violations = check_concentration(holdings, policy, 100000.0)
        self.assertFalse(any(v.rule == "position_concentration" for v in violations))

    def test_sector_over_limit(self):
        from invest_signal_kit.portfolio import Holding, PortfolioPolicy, check_concentration
        holdings = [
            Holding(code="A", shares=500, current_price=50.0, sector="Tech"),
            Holding(code="B", shares=500, current_price=50.0, sector="Tech"),
        ]
        policy = PortfolioPolicy(max_sector_pct=30.0)
        violations = check_concentration(holdings, policy, 100000.0)
        self.assertTrue(any(v.rule == "sector_concentration" for v in violations))

    def test_sector_override_limit(self):
        from invest_signal_kit.portfolio import Holding, PortfolioPolicy, check_concentration
        holdings = [Holding(code="A", shares=500, current_price=50.0, sector="Tech")]
        policy = PortfolioPolicy(max_sector_pct=50.0, sector_limits={"Tech": 20.0})
        violations = check_concentration(holdings, policy, 100000.0)
        self.assertTrue(any(v.rule == "sector_concentration" for v in violations))

    def test_position_risk_limit(self):
        from invest_signal_kit.portfolio import Holding, PortfolioPolicy, check_concentration
        holdings = [Holding(code="A", shares=1000, current_price=50.0, stop_price=40.0)]
        policy = PortfolioPolicy(max_candidate_risk_pct=2.0)
        violations = check_concentration(holdings, policy, 100000.0)
        # risk = 1000 * 10 = 10000, risk_pct = 10%
        self.assertTrue(any(v.rule == "position_risk_limit" for v in violations))

    def test_empty_portfolio(self):
        from invest_signal_kit.portfolio import PortfolioPolicy, check_concentration
        violations = check_concentration([], PortfolioPolicy(), 0.0)
        self.assertEqual(violations, [])


class TestRiskBudget(unittest.TestCase):
    """Test risk budget checking."""

    def test_under_budget(self):
        from invest_signal_kit.portfolio import Holding, PortfolioPolicy, check_risk_budget
        holdings = [Holding(code="A", shares=100, current_price=50.0, stop_price=45.0)]
        policy = PortfolioPolicy(max_risk_budget_pct=10.0)
        result = check_risk_budget(holdings, 100000.0, policy)
        self.assertFalse(result.over_budget)
        self.assertGreater(result.remaining_budget, 0)

    def test_over_budget(self):
        from invest_signal_kit.portfolio import Holding, PortfolioPolicy, check_risk_budget
        holdings = [Holding(code="A", shares=1000, current_price=50.0, stop_price=40.0)]
        policy = PortfolioPolicy(max_risk_budget_pct=5.0)
        result = check_risk_budget(holdings, 100000.0, policy)
        # risk = 1000 * 10 = 10000, budget = 5000
        self.assertTrue(result.over_budget)

    def test_utilization_pct(self):
        from invest_signal_kit.portfolio import Holding, PortfolioPolicy, check_risk_budget
        holdings = [Holding(code="A", shares=100, current_price=50.0, stop_price=45.0)]
        policy = PortfolioPolicy(max_risk_budget_pct=10.0)
        result = check_risk_budget(holdings, 100000.0, policy)
        # risk = 500, budget = 10000, utilization = 5%
        self.assertAlmostEqual(result.utilization_pct, 5.0, places=0)

    def test_position_risks_dict(self):
        from invest_signal_kit.portfolio import Holding, PortfolioPolicy, check_risk_budget
        holdings = [Holding(code="A", shares=100, current_price=50.0, stop_price=45.0)]
        result = check_risk_budget(holdings, 100000.0, PortfolioPolicy())
        self.assertIn("A", result.position_risks)
        self.assertEqual(result.position_risks["A"], 500.0)


class TestCandidateRanking(unittest.TestCase):
    """Test candidate signal ranking."""

    def test_passing_candidate(self):
        from invest_signal_kit.portfolio import CandidateSignal, Holding, PortfolioPolicy, rank_candidates
        candidates = [CandidateSignal(
            code="X", signal_score=70, ev_quality="positive_ev",
            position_size_pct=5.0, risk_pct=1.0, sector="Tech",
        )]
        result = rank_candidates(candidates, [], PortfolioPolicy(), 100000.0)
        self.assertTrue(result[0].passes_watchlist)

    def test_failing_low_score(self):
        from invest_signal_kit.portfolio import CandidateSignal, PortfolioPolicy, rank_candidates
        candidates = [CandidateSignal(code="X", signal_score=40, ev_quality="positive_ev")]
        result = rank_candidates(candidates, [], PortfolioPolicy(watchlist_min_score=60), 100000.0)
        self.assertFalse(result[0].passes_watchlist)
        self.assertTrue(any("below min" in b for b in result[0].blockers))

    def test_failing_negative_ev(self):
        from invest_signal_kit.portfolio import CandidateSignal, PortfolioPolicy, rank_candidates
        candidates = [CandidateSignal(code="X", signal_score=70, ev_quality="negative_ev")]
        result = rank_candidates(candidates, [], PortfolioPolicy(), 100000.0)
        self.assertFalse(result[0].passes_watchlist)
        self.assertTrue(any("negative" in b.lower() for b in result[0].blockers))

    def test_failing_risk_limit(self):
        from invest_signal_kit.portfolio import CandidateSignal, PortfolioPolicy, rank_candidates
        candidates = [CandidateSignal(code="X", signal_score=70, ev_quality="positive_ev", risk_pct=5.0)]
        result = rank_candidates(candidates, [], PortfolioPolicy(max_candidate_risk_pct=2.0), 100000.0)
        self.assertFalse(result[0].passes_watchlist)

    def test_ranking_order(self):
        from invest_signal_kit.portfolio import CandidateSignal, PortfolioPolicy, rank_candidates
        candidates = [
            CandidateSignal(code="A", signal_score=60, ev_quality="positive_ev"),
            CandidateSignal(code="B", signal_score=80, ev_quality="positive_ev"),
            CandidateSignal(code="C", signal_score=70, ev_quality="positive_ev"),
        ]
        result = rank_candidates(candidates, [], PortfolioPolicy(), 100000.0)
        self.assertEqual(result[0].code, "B")
        self.assertEqual(result[1].code, "C")
        self.assertEqual(result[2].code, "A")
        self.assertEqual(result[0].rank, 1)

    def test_sector_breach_blocker(self):
        from invest_signal_kit.portfolio import CandidateSignal, Holding, PortfolioPolicy, rank_candidates
        holdings = [Holding(code="A", shares=500, current_price=50.0, sector="Tech")]
        candidates = [CandidateSignal(
            code="B", signal_score=70, ev_quality="positive_ev",
            sector="Tech", position_size_pct=20.0,
        )]
        policy = PortfolioPolicy(max_sector_pct=40.0)
        result = rank_candidates(candidates, holdings, policy, 100000.0)
        # existing sector = 25000/100000 = 25%, added = 20%, total = 45% > 40%
        self.assertFalse(result[0].passes_watchlist)


class TestStressTest(unittest.TestCase):
    """Test stress testing."""

    def test_market_crash(self):
        from invest_signal_kit.portfolio import Holding, StressScenario, run_stress_test
        holdings = [Holding(code="A", shares=100, current_price=100.0)]
        scenario = StressScenario(name="Crash", market_shock_pct=-10.0)
        result = run_stress_test(holdings, 0.0, scenario)
        # original = 10000, shocked = 9000, loss = 1000
        self.assertAlmostEqual(result.total_loss, 1000.0, places=0)
        self.assertAlmostEqual(result.total_loss_pct, 10.0, places=0)

    def test_sector_shock(self):
        from invest_signal_kit.portfolio import Holding, StressScenario, run_stress_test
        holdings = [
            Holding(code="A", shares=100, current_price=100.0, sector="Tech"),
            Holding(code="B", shares=100, current_price=100.0, sector="Finance"),
        ]
        scenario = StressScenario(name="Tech crash", sector_shocks={"Tech": -20.0})
        result = run_stress_test(holdings, 0.0, scenario)
        # A loses 2000, B loses 0, total loss = 2000
        self.assertAlmostEqual(result.total_loss, 2000.0, places=0)

    def test_single_name_shock(self):
        from invest_signal_kit.portfolio import Holding, StressScenario, run_stress_test
        holdings = [Holding(code="A", shares=100, current_price=100.0)]
        scenario = StressScenario(name="A crashes", single_name_shocks={"A": -30.0})
        result = run_stress_test(holdings, 0.0, scenario)
        self.assertAlmostEqual(result.total_loss, 3000.0, places=0)

    def test_liquidity_haircut(self):
        from invest_signal_kit.portfolio import Holding, StressScenario, run_stress_test
        holdings = [Holding(code="A", shares=100, current_price=100.0)]
        scenario = StressScenario(name="Liquidity crisis", liquidity_haircut_pct=10.0)
        result = run_stress_test(holdings, 0.0, scenario)
        # 10000 * (1 - 0.10) = 9000, loss = 1000
        self.assertAlmostEqual(result.total_loss, 1000.0, places=0)

    def test_cash_unaffected(self):
        from invest_signal_kit.portfolio import Holding, StressScenario, run_stress_test
        holdings = [Holding(code="A", shares=100, current_price=100.0)]
        scenario = StressScenario(name="Crash", market_shock_pct=-50.0)
        result = run_stress_test(holdings, 10000.0, scenario)
        # total = 20000, shocked = 5000 + 10000 = 15000, loss = 5000
        self.assertAlmostEqual(result.shocked_portfolio_value, 15000.0, places=0)

    def test_drawdown_breach(self):
        from invest_signal_kit.portfolio import Holding, StressScenario, run_stress_test
        holdings = [Holding(code="A", shares=100, current_price=100.0)]
        scenario = StressScenario(name="Crash", market_shock_pct=-20.0)
        result = run_stress_test(holdings, 0.0, scenario, max_drawdown_pct=15.0)
        self.assertTrue(result.breaches_drawdown_limit)

    def test_additive_shocks(self):
        from invest_signal_kit.portfolio import Holding, StressScenario, run_stress_test
        holdings = [Holding(code="A", shares=100, current_price=100.0, sector="Tech")]
        scenario = StressScenario(
            name="Combined", market_shock_pct=-5.0,
            sector_shocks={"Tech": -10.0}, single_name_shocks={"A": -5.0},
        )
        result = run_stress_test(holdings, 0.0, scenario)
        # total shock = -5 + -10 + -5 = -20%, loss = 2000
        self.assertAlmostEqual(result.total_loss, 2000.0, places=0)
        self.assertAlmostEqual(result.positions[0].applied_shock_pct, -20.0, places=0)


class TestPortfolioEvaluation(unittest.TestCase):
    """Test full portfolio evaluation pipeline."""

    def test_basic_evaluation(self):
        from invest_signal_kit.portfolio import (
            Holding, PortfolioPolicy, evaluate_portfolio, ExposureReport,
        )
        holdings = [Holding(code="A", shares=100, current_price=50.0, stop_price=45.0)]
        result = evaluate_portfolio(holdings, 95000.0, PortfolioPolicy())
        self.assertIsInstance(result.exposure_report, ExposureReport)
        # Position = 5000/100000 = 5% (under 20% limit)
        # Risk = 500/100000 = 0.5% (under 2% limit)
        self.assertEqual(len(result.blockers), 0)

    def test_evaluation_with_candidates(self):
        from invest_signal_kit.portfolio import (
            Holding, PortfolioPolicy, CandidateSignal, evaluate_portfolio,
        )
        holdings = [Holding(code="A", shares=100, current_price=50.0)]
        candidates = [CandidateSignal(code="B", signal_score=70, ev_quality="positive_ev")]
        result = evaluate_portfolio(holdings, 5000.0, PortfolioPolicy(), candidates=candidates)
        self.assertEqual(len(result.candidate_rankings), 1)

    def test_evaluation_with_scenarios(self):
        from invest_signal_kit.portfolio import (
            Holding, PortfolioPolicy, StressScenario, evaluate_portfolio,
        )
        holdings = [Holding(code="A", shares=100, current_price=50.0)]
        scenarios = [StressScenario(name="Crash", market_shock_pct=-10.0)]
        result = evaluate_portfolio(holdings, 5000.0, PortfolioPolicy(), scenarios=scenarios)
        self.assertEqual(len(result.stress_results), 1)

    def test_risk_budget_blocker(self):
        from invest_signal_kit.portfolio import (
            Holding, PortfolioPolicy, evaluate_portfolio,
        )
        holdings = [Holding(code="A", shares=1000, current_price=50.0, stop_price=40.0)]
        policy = PortfolioPolicy(max_risk_budget_pct=5.0)
        result = evaluate_portfolio(holdings, 0.0, policy)
        self.assertTrue(any(b.rule == "risk_budget_exceeded" for b in result.blockers))


class TestPortfolioLoaders(unittest.TestCase):
    """Test portfolio data loaders."""

    def test_load_holding(self):
        from invest_signal_kit.portfolio import load_holding
        h = load_holding({"code": "A", "shares": 100, "current_price": 50.0})
        self.assertEqual(h.code, "A")
        self.assertEqual(h.shares, 100)

    def test_load_policy(self):
        from invest_signal_kit.portfolio import load_portfolio_policy
        p = load_portfolio_policy({"max_position_pct": 30, "sector_limits": {"Tech": 20}})
        self.assertEqual(p.max_position_pct, 30.0)
        self.assertEqual(p.sector_limits["Tech"], 20.0)

    def test_load_candidate(self):
        from invest_signal_kit.portfolio import load_candidate_signal
        c = load_candidate_signal({"code": "X", "signal_score": 75})
        self.assertEqual(c.code, "X")
        self.assertEqual(c.signal_score, 75.0)

    def test_load_scenario(self):
        from invest_signal_kit.portfolio import load_stress_scenario
        s = load_stress_scenario({"name": "Crash", "market_shock_pct": -15})
        self.assertEqual(s.name, "Crash")
        self.assertEqual(s.market_shock_pct, -15.0)

    def test_load_portfolio_state(self):
        from invest_signal_kit.portfolio import load_portfolio_state
        data = {
            "holdings": [{"code": "A", "shares": 100}],
            "cash": 5000,
            "policy": {"max_position_pct": 25},
            "candidates": [{"code": "B", "signal_score": 70}],
            "scenarios": [{"name": "Crash", "market_shock_pct": -10}],
        }
        holdings, cash, policy, candidates, scenarios = load_portfolio_state(data)
        self.assertEqual(len(holdings), 1)
        self.assertEqual(cash, 5000.0)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(len(scenarios), 1)


class TestRunPortfolioAnalysis(unittest.TestCase):
    """Test the run_portfolio_analysis convenience function."""

    def test_basic_analysis(self):
        from invest_signal_kit.portfolio import run_portfolio_analysis
        data = {
            "holdings": [{"code": "A", "shares": 100, "current_price": 50.0}],
            "cash": 5000,
        }
        result = run_portfolio_analysis(data)
        self.assertIn("exposure_report", result)
        self.assertIn("risk_budget", result)

    def test_full_analysis(self):
        from invest_signal_kit.portfolio import run_portfolio_analysis
        data = json.loads((EXAMPLES / "portfolio_workflow.json").read_text())
        result = run_portfolio_analysis(data)
        self.assertIn("exposure_report", result)
        self.assertIn("candidate_rankings", result)
        self.assertIn("stress_results", result)
        self.assertGreater(len(result["stress_results"]), 0)


class TestPortfolioMarkdown(unittest.TestCase):
    """Test portfolio Markdown rendering."""

    def test_render_contains_sections(self):
        from invest_signal_kit.portfolio import (
            Holding, PortfolioPolicy, evaluate_portfolio, render_portfolio_markdown,
        )
        holdings = [Holding(code="A", name="Test", shares=100, current_price=50.0, sector="Tech")]
        result = evaluate_portfolio(holdings, 5000.0, PortfolioPolicy())
        md = render_portfolio_markdown(result)
        self.assertIn("# Portfolio Risk Report", md)
        self.assertIn("Position Exposures", md)
        self.assertIn("Risk Budget", md)
        self.assertIn("Not investment advice", md)

    def test_render_with_stress(self):
        from invest_signal_kit.portfolio import (
            Holding, PortfolioPolicy, StressScenario, evaluate_portfolio,
            render_portfolio_markdown,
        )
        holdings = [Holding(code="A", shares=100, current_price=50.0)]
        scenarios = [StressScenario(name="Crash", market_shock_pct=-10.0)]
        result = evaluate_portfolio(holdings, 5000.0, PortfolioPolicy(), scenarios=scenarios)
        md = render_portfolio_markdown(result)
        self.assertIn("Stress Test Results", md)
        self.assertIn("Crash", md)


class TestPortfolioCLI(unittest.TestCase):
    """Test portfolio CLI command."""

    def test_portfolio_json_output(self):
        from invest_signal_kit.cli import main
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            ret = main(["portfolio", str(EXAMPLES / "portfolio_workflow.json")])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(ret, 0)
        data = json.loads(captured.getvalue())
        self.assertIn("exposure_report", data)
        self.assertIn("risk_budget", data)

    def test_portfolio_markdown_output(self):
        from invest_signal_kit.cli import main
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            ret = main(["portfolio", str(EXAMPLES / "portfolio_workflow.json"), "--format", "markdown"])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(ret, 0)
        output = captured.getvalue()
        self.assertIn("# Portfolio Risk Report", output)

    def test_portfolio_invalid_json(self):
        from invest_signal_kit.cli import main
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            f.write("{bad json")
            f.flush()
            path = f.name
        try:
            ret = main(["portfolio", path])
            self.assertNotEqual(ret, 0)
        finally:
            os.unlink(path)

    def test_portfolio_writes_file(self):
        from invest_signal_kit.cli import main
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            outpath = f.name
        try:
            ret = main(["portfolio", str(EXAMPLES / "portfolio_workflow.json"), "-o", outpath])
            self.assertEqual(ret, 0)
            data = json.loads(Path(outpath).read_text())
            self.assertIn("exposure_report", data)
        finally:
            os.unlink(outpath)


class TestBatchCLI(unittest.TestCase):
    """Test batch CLI command."""

    def test_batch_json_output(self):
        from invest_signal_kit.cli import main
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            ret = main(["batch", str(EXAMPLES / "etf_signal.json"), str(EXAMPLES / "stock_shift_signal.json")])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(ret, 0)
        data = json.loads(captured.getvalue())
        self.assertIn("results", data)
        self.assertEqual(len(data["results"]), 2)

    def test_batch_markdown_output(self):
        from invest_signal_kit.cli import main
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            ret = main(["batch", str(EXAMPLES / "etf_signal.json"), "--format", "markdown"])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(ret, 0)
        output = captured.getvalue()
        self.assertIn("# Batch Analysis Results", output)


class TestPortfolioWorkflowExample(unittest.TestCase):
    """Test the portfolio_workflow.json example."""

    def test_example_loads(self):
        from invest_signal_kit.portfolio import load_portfolio_state
        data = json.loads((EXAMPLES / "portfolio_workflow.json").read_text())
        holdings, cash, policy, candidates, scenarios = load_portfolio_state(data)
        self.assertEqual(len(holdings), 5)
        self.assertGreater(cash, 0)
        self.assertEqual(len(candidates), 4)
        self.assertEqual(len(scenarios), 4)

    def test_example_analysis(self):
        from invest_signal_kit.portfolio import run_portfolio_analysis
        data = json.loads((EXAMPLES / "portfolio_workflow.json").read_text())
        result = run_portfolio_analysis(data)
        self.assertIn("exposure_report", result)
        self.assertGreater(len(result["candidate_rankings"]), 0)
        self.assertGreater(len(result["stress_results"]), 0)

    def test_example_cli_json(self):
        from invest_signal_kit.cli import main
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            ret = main(["portfolio", str(EXAMPLES / "portfolio_workflow.json")])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(ret, 0)
        data = json.loads(captured.getvalue())
        self.assertIn("exposure_report", data)

    def test_example_cli_markdown(self):
        from invest_signal_kit.cli import main
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            ret = main(["portfolio", str(EXAMPLES / "portfolio_workflow.json"), "--format", "md"])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(ret, 0)
        self.assertIn("Portfolio Risk Report", captured.getvalue())


class TestBatchErrorHandling(unittest.TestCase):
    """Regression tests for batch CLI error handling."""

    def test_batch_missing_file_with_valid(self):
        """Missing file is recorded as error; valid file still succeeds; exit 0."""
        from invest_signal_kit.cli import main

        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            ret = main([
                "batch",
                str(EXAMPLES / "etf_signal.json"),
                "/tmp/does_not_exist_signal.json",
            ])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(ret, 0)
        data = json.loads(captured.getvalue())
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(len(data["errors"]), 1)
        self.assertIn("does_not_exist", data["errors"][0]["file"])

    def test_batch_all_missing_exits_nonzero(self):
        """All files missing -> zero results -> exit 1."""
        from invest_signal_kit.cli import main

        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            ret = main(["batch", "/tmp/no_such_file_a.json", "/tmp/no_such_file_b.json"])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(ret, 1)
        data = json.loads(captured.getvalue())
        self.assertEqual(len(data["results"]), 0)
        self.assertEqual(len(data["errors"]), 2)

    def test_batch_non_signal_file(self):
        """Non-signal JSON (macro, portfolio) is recorded as error, not silently processed."""
        from invest_signal_kit.cli import main

        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            ret = main([
                "batch",
                str(EXAMPLES / "etf_signal.json"),
                str(EXAMPLES / "macro_context.json"),
                str(EXAMPLES / "portfolio_workflow.json"),
            ])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(ret, 0)
        data = json.loads(captured.getvalue())
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(len(data["errors"]), 2)
        for err in data["errors"]:
            self.assertIn("Not a signal file", err["error"])

    def test_batch_markdown_errors_section(self):
        """Markdown output includes an Errors section when errors exist."""
        from invest_signal_kit.cli import main

        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            ret = main([
                "batch",
                str(EXAMPLES / "etf_signal.json"),
                "/tmp/missing_file.json",
                "--format", "markdown",
            ])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(ret, 0)
        output = captured.getvalue()
        self.assertIn("## Errors", output)
        self.assertIn("missing_file.json", output)


class TestCLIMissingFile(unittest.TestCase):
    """Regression tests for missing-file handling in single-file commands."""

    def test_validate_missing_file(self):
        from invest_signal_kit.cli import main
        ret = main(["validate", "/tmp/no_such_file_ever.json"])
        self.assertEqual(ret, 1)

    def test_score_missing_file(self):
        from invest_signal_kit.cli import main
        ret = main(["score", "/tmp/no_such_file_ever.json"])
        self.assertEqual(ret, 1)

    def test_framework_missing_file(self):
        from invest_signal_kit.cli import main
        ret = main(["framework", "/tmp/no_such_file_ever.json"])
        self.assertEqual(ret, 1)

    def test_memo_missing_file(self):
        from invest_signal_kit.cli import main
        ret = main(["memo", "/tmp/no_such_file_ever.json"])
        self.assertEqual(ret, 1)

    def test_portfolio_missing_file(self):
        from invest_signal_kit.cli import main
        ret = main(["portfolio", "/tmp/no_such_file_ever.json"])
        self.assertEqual(ret, 1)


# =========================================================================
# Decision Journal Tests
# =========================================================================

class TestJournalLoading(unittest.TestCase):
    """Test journal loading from JSON."""

    def test_load_decision(self):
        from invest_signal_kit.journal import load_decision
        d = load_decision({"id": "J-001", "instrument_code": "AAPL", "status": "active"})
        self.assertEqual(d.id, "J-001")
        self.assertEqual(d.instrument_code, "AAPL")
        self.assertEqual(d.status, "active")

    def test_load_decision_defaults(self):
        from invest_signal_kit.journal import load_decision
        d = load_decision({})
        self.assertEqual(d.id, "")
        self.assertEqual(d.status, "planned")
        self.assertEqual(d.direction, "bullish")
        self.assertEqual(d.entry_price, 0.0)

    def test_load_journal_dict_format(self):
        from invest_signal_kit.journal import load_journal
        data = {"decisions": [{"id": "A"}, {"id": "B"}]}
        decisions = load_journal(data)
        self.assertEqual(len(decisions), 2)
        self.assertEqual(decisions[0].id, "A")
        self.assertEqual(decisions[1].id, "B")

    def test_load_journal_list_format(self):
        from invest_signal_kit.journal import load_journal
        data = [{"id": "X"}, {"id": "Y"}]
        decisions = load_journal(data)
        self.assertEqual(len(decisions), 2)

    def test_load_journal_empty(self):
        from invest_signal_kit.journal import load_journal
        decisions = load_journal({"decisions": []})
        self.assertEqual(len(decisions), 0)

    def test_decision_tags_loaded(self):
        from invest_signal_kit.journal import load_decision
        d = load_decision({"tags": ["macro", "tech"]})
        self.assertEqual(d.tags, ["macro", "tech"])

    def test_decision_numeric_fields(self):
        from invest_signal_kit.journal import load_decision
        d = load_decision({"entry_price": "150.5", "risk_budget_pct": "2.5"})
        self.assertEqual(d.entry_price, 150.5)
        self.assertEqual(d.risk_budget_pct, 2.5)


class TestLifecycleValidation(unittest.TestCase):
    """Test lifecycle validation rules."""

    def test_active_missing_exit(self):
        from invest_signal_kit.journal import Decision, validate_lifecycle
        d = Decision(id="J-1", status="active", instrument_code="AAPL")
        alerts = validate_lifecycle([d], today="2026-05-23")
        rules = {a.rule for a in alerts}
        self.assertIn("active_decision_missing_exit", rules)

    def test_active_with_exit_date_no_alert(self):
        from invest_signal_kit.journal import Decision, validate_lifecycle
        d = Decision(id="J-1", status="active", exit_date="2026-06-01")
        alerts = validate_lifecycle([d], today="2026-05-23")
        rules = {a.rule for a in alerts}
        self.assertNotIn("active_decision_missing_exit", rules)

    def test_active_with_time_stop_no_alert(self):
        from invest_signal_kit.journal import Decision, validate_lifecycle
        d = Decision(id="J-1", status="active", time_stop_date="2026-06-01")
        alerts = validate_lifecycle([d], today="2026-05-23")
        rules = {a.rule for a in alerts}
        self.assertNotIn("active_decision_missing_exit", rules)

    def test_expired_review(self):
        from invest_signal_kit.journal import Decision, validate_lifecycle
        d = Decision(id="J-1", status="exited", review_date="2026-05-01", instrument_code="AAPL")
        alerts = validate_lifecycle([d], today="2026-05-23")
        rules = {a.rule for a in alerts}
        self.assertIn("expired_review", rules)

    def test_reviewed_no_expired_alert(self):
        from invest_signal_kit.journal import Decision, validate_lifecycle
        d = Decision(id="J-1", status="reviewed", review_date="2026-05-01")
        alerts = validate_lifecycle([d], today="2026-05-23")
        rules = {a.rule for a in alerts}
        self.assertNotIn("expired_review", rules)

    def test_oversized_risk(self):
        from invest_signal_kit.journal import Decision, validate_lifecycle
        d = Decision(id="J-1", status="active", risk_budget_pct=6.5, instrument_code="AAPL")
        alerts = validate_lifecycle([d], today="2026-05-23")
        rules = {a.rule for a in alerts}
        self.assertIn("oversized_risk", rules)

    def test_risk_under_5_no_alert(self):
        from invest_signal_kit.journal import Decision, validate_lifecycle
        d = Decision(id="J-1", status="active", risk_budget_pct=3.0, exit_date="2026-06-01")
        alerts = validate_lifecycle([d], today="2026-05-23")
        rules = {a.rule for a in alerts}
        self.assertNotIn("oversized_risk", rules)

    def test_stale_thesis(self):
        from invest_signal_kit.journal import Decision, validate_lifecycle
        d = Decision(id="J-1", status="planned", decision_date="2026-01-01", instrument_code="AAPL")
        alerts = validate_lifecycle([d], today="2026-05-23")
        rules = {a.rule for a in alerts}
        self.assertIn("stale_thesis", rules)

    def test_missing_review_on_exited(self):
        from invest_signal_kit.journal import Decision, validate_lifecycle
        d = Decision(id="J-1", status="exited", instrument_code="AAPL", thesis_snapshot="test")
        alerts = validate_lifecycle([d], today="2026-05-23")
        rules = {a.rule for a in alerts}
        self.assertIn("missing_review", rules)

    def test_invalid_status(self):
        from invest_signal_kit.journal import Decision, validate_lifecycle
        d = Decision(id="J-1", status="bogus", instrument_code="AAPL")
        alerts = validate_lifecycle([d], today="2026-05-23")
        rules = {a.rule for a in alerts}
        self.assertIn("invalid_status", rules)

    def test_missing_thesis_on_active(self):
        from invest_signal_kit.journal import Decision, validate_lifecycle
        d = Decision(id="J-1", status="active", exit_date="2026-06-01", instrument_code="AAPL")
        alerts = validate_lifecycle([d], today="2026-05-23")
        rules = {a.rule for a in alerts}
        self.assertIn("missing_thesis", rules)

    def test_thesis_invalidated_not_exited(self):
        from invest_signal_kit.journal import Decision, validate_lifecycle
        d = Decision(id="J-1", status="invalidated", instrument_code="AAPL",
                     thesis_snapshot="test", outcome_category="thesis_broken")
        alerts = validate_lifecycle([d], today="2026-05-23")
        rules = {a.rule for a in alerts}
        self.assertIn("thesis_invalidated_not_exited", rules)

    def test_stop_breached_detection(self):
        from invest_signal_kit.journal import Decision, validate_lifecycle
        d = Decision(id="J-1", status="active", direction="bullish",
                     entry_price=100, stop_price=90, exit_price=85,
                     instrument_code="AAPL")
        alerts = validate_lifecycle([d], today="2026-05-23")
        rules = {a.rule for a in alerts}
        self.assertIn("stop_breached_not_exited", rules)

    def test_clean_decisions_no_alerts(self):
        from invest_signal_kit.journal import Decision, validate_lifecycle
        d = Decision(
            id="J-1", status="reviewed", instrument_code="AAPL",
            thesis_snapshot="test thesis", decision_date="2026-04-01",
            entry_date="2026-04-05", exit_date="2026-05-01",
            outcome_category="hit_target", risk_budget_pct=2.0,
        )
        alerts = validate_lifecycle([d], today="2026-05-23")
        self.assertEqual(alerts, [])


class TestReviewDecision(unittest.TestCase):
    """Test decision review logic."""

    def test_review_infers_outcome_from_exit_reason(self):
        from invest_signal_kit.journal import Decision, review_decision
        d = Decision(id="J-1", exit_reason="hit_target")
        result = review_decision(d)
        self.assertEqual(result.outcome_category, "hit_target")

    def test_review_hit_stop(self):
        from invest_signal_kit.journal import Decision, review_decision
        d = Decision(id="J-1", exit_reason="hit_stop")
        result = review_decision(d)
        self.assertEqual(result.outcome_category, "hit_stop")

    def test_review_time_stop(self):
        from invest_signal_kit.journal import Decision, review_decision
        d = Decision(id="J-1", exit_reason="time_stop")
        result = review_decision(d)
        self.assertEqual(result.outcome_category, "time_stop")

    def test_review_thesis_broken(self):
        from invest_signal_kit.journal import Decision, review_decision
        d = Decision(id="J-1", exit_reason="thesis_broken")
        result = review_decision(d)
        self.assertEqual(result.outcome_category, "thesis_broken")

    def test_review_process_errors_detected(self):
        from invest_signal_kit.journal import Decision, review_decision
        d = Decision(id="J-1", status="exited", exit_reason="manual")
        result = review_decision(d)
        self.assertIn("no_thesis_snapshot", result.process_errors)
        self.assertIn("no_stop_defined", result.process_errors)
        self.assertIn("no_target_defined", result.process_errors)

    def test_review_clean_decision_no_errors(self):
        from invest_signal_kit.journal import Decision, review_decision
        d = Decision(
            id="J-1", status="exited", exit_reason="hit_target",
            thesis_snapshot="test", stop_price=90, target_price=120,
            risk_budget_pct=2.0, exit_date="2026-05-01",
        )
        result = review_decision(d)
        self.assertEqual(result.process_errors, [])

    def test_review_oversized_risk_detected(self):
        from invest_signal_kit.journal import Decision, review_decision
        d = Decision(
            id="J-1", status="active", thesis_snapshot="test",
            stop_price=90, target_price=120, risk_budget_pct=6.0,
            review_date="2026-06-01", time_stop_date="2026-07-01",
        )
        result = review_decision(d)
        self.assertIn("oversized_risk_budget", result.process_errors)

    def test_review_explicit_outcome_overrides_inference(self):
        from invest_signal_kit.journal import Decision, review_decision
        d = Decision(id="J-1", exit_reason="manual")
        result = review_decision(d, outcome_category="process_adherence")
        self.assertEqual(result.outcome_category, "process_adherence")

    def test_review_explicit_return(self):
        from invest_signal_kit.journal import Decision, review_decision
        d = Decision(id="J-1", actual_return_pct=5.0)
        result = review_decision(d, actual_return_pct=10.0)
        self.assertEqual(result.actual_return_pct, 10.0)


class TestCalibration(unittest.TestCase):
    """Test score calibration."""

    def test_calibration_empty(self):
        from invest_signal_kit.journal import calibrate_scores
        report = calibrate_scores([])
        self.assertEqual(report.total_decisions, 0)
        self.assertEqual(report.reviewed_decisions, 0)
        self.assertEqual(len(report.buckets), 5)

    def test_calibration_groups_by_score(self):
        from invest_signal_kit.journal import Decision, calibrate_scores
        decisions = [
            Decision(id="A", status="reviewed", signal_score=80, actual_return_pct=10.0,
                     outcome_category="hit_target"),
            Decision(id="B", status="reviewed", signal_score=40, actual_return_pct=-5.0,
                     outcome_category="hit_stop"),
        ]
        report = calibrate_scores(decisions)
        self.assertEqual(report.reviewed_decisions, 2)
        # A goes to 80-100 bucket, B goes to 30-49 bucket
        high_bucket = [b for b in report.buckets if "80-100" in b.score_range][0]
        low_bucket = [b for b in report.buckets if "30-49" in b.score_range][0]
        self.assertEqual(high_bucket.decision_count, 1)
        self.assertEqual(high_bucket.win_count, 1)
        self.assertEqual(low_bucket.decision_count, 1)
        self.assertEqual(low_bucket.win_count, 0)

    def test_calibration_win_rate(self):
        from invest_signal_kit.journal import Decision, calibrate_scores
        decisions = [
            Decision(id="A", status="reviewed", signal_score=70, actual_return_pct=10.0,
                     outcome_category="hit_target"),
            Decision(id="B", status="reviewed", signal_score=72, actual_return_pct=5.0,
                     outcome_category="hit_target"),
            Decision(id="C", status="reviewed", signal_score=75, actual_return_pct=-3.0,
                     outcome_category="hit_stop"),
        ]
        report = calibrate_scores(decisions)
        self.assertAlmostEqual(report.overall_win_rate, 66.7, places=1)

    def test_calibration_avg_return(self):
        from invest_signal_kit.journal import Decision, calibrate_scores
        decisions = [
            Decision(id="A", status="reviewed", signal_score=70, actual_return_pct=10.0,
                     outcome_category="hit_target", r_multiple=2.0),
            Decision(id="B", status="reviewed", signal_score=72, actual_return_pct=-5.0,
                     outcome_category="hit_stop", r_multiple=-1.0),
        ]
        report = calibrate_scores(decisions)
        self.assertAlmostEqual(report.overall_avg_return, 2.5, places=1)
        self.assertAlmostEqual(report.overall_avg_r_multiple, 0.5, places=1)

    def test_calibration_ignores_non_reviewed(self):
        from invest_signal_kit.journal import Decision, calibrate_scores
        decisions = [
            Decision(id="A", status="active", signal_score=70),
            Decision(id="B", status="planned", signal_score=80),
            Decision(id="C", status="reviewed", signal_score=60, actual_return_pct=5.0,
                     outcome_category="hit_target"),
        ]
        report = calibrate_scores(decisions)
        self.assertEqual(report.total_decisions, 3)
        self.assertEqual(report.reviewed_decisions, 1)

    def test_calibration_fallback_score(self):
        from invest_signal_kit.journal import Decision, calibrate_scores
        # No signal_score, falls back to average of three scores
        d = Decision(
            id="A", status="reviewed", signal_score=0,
            thesis_quality_score=60, market_confirmation_score=70, risk_execution_score=80,
            actual_return_pct=5.0, outcome_category="hit_target",
        )
        report = calibrate_scores([d])
        # effective score = (60+70+80)/3 = 70 -> 65-79 bucket
        b70 = [b for b in report.buckets if "65-79" in b.score_range][0]
        self.assertEqual(b70.decision_count, 1)


class TestAttribution(unittest.TestCase):
    """Test performance attribution."""

    def test_attribution_basic(self):
        from invest_signal_kit.journal import Decision, compute_attribution
        d = Decision(
            id="J-1", status="reviewed", instrument_code="AAPL",
            actual_return_pct=10.0, market_move_pct=5.0,
            sector_move_pct=3.0, idiosyncratic_move_pct=2.0,
            position_size_pct=8.0, outcome_category="hit_target",
        )
        results = compute_attribution([d])
        self.assertEqual(len(results), 1)
        a = results[0]
        self.assertEqual(a.total_return_pct, 10.0)
        self.assertEqual(a.market_move_pct, 5.0)
        self.assertEqual(a.sector_move_pct, 3.0)
        self.assertEqual(a.idiosyncratic_move_pct, 2.0)
        self.assertAlmostEqual(a.residual_pct, 0.0, places=1)
        self.assertAlmostEqual(a.sizing_contribution_pct, 0.8, places=1)

    def test_attribution_residual(self):
        from invest_signal_kit.journal import Decision, compute_attribution
        d = Decision(
            id="J-1", status="reviewed", actual_return_pct=10.0,
            market_move_pct=3.0, sector_move_pct=2.0,
            idiosyncratic_move_pct=1.0, outcome_category="hit_target",
        )
        results = compute_attribution([d])
        # residual = 10 - (3+2+1) = 4
        self.assertAlmostEqual(results[0].residual_pct, 4.0, places=1)

    def test_attribution_ignores_non_reviewed(self):
        from invest_signal_kit.journal import Decision, compute_attribution
        d = Decision(id="J-1", status="active", actual_return_pct=5.0)
        results = compute_attribution([d])
        self.assertEqual(len(results), 0)

    def test_attribution_empty(self):
        from invest_signal_kit.journal import compute_attribution
        results = compute_attribution([])
        self.assertEqual(results, [])


class TestJournalExample(unittest.TestCase):
    """Test the decision_journal.json example."""

    def test_example_loads(self):
        from invest_signal_kit.journal import load_journal
        data = json.loads((EXAMPLES / "decision_journal.json").read_text())
        decisions = load_journal(data)
        self.assertEqual(len(decisions), 10)

    def test_example_has_all_statuses(self):
        from invest_signal_kit.journal import load_journal
        data = json.loads((EXAMPLES / "decision_journal.json").read_text())
        decisions = load_journal(data)
        statuses = {d.status for d in decisions}
        self.assertIn("planned", statuses)
        self.assertIn("active", statuses)
        self.assertIn("exited", statuses)
        self.assertIn("invalidated", statuses)
        self.assertIn("reviewed", statuses)

    def test_example_has_reviewed_decisions(self):
        from invest_signal_kit.journal import load_journal, calibrate_scores
        data = json.loads((EXAMPLES / "decision_journal.json").read_text())
        decisions = load_journal(data)
        report = calibrate_scores(decisions)
        self.assertGreater(report.reviewed_decisions, 0)

    def test_example_has_attribution(self):
        from invest_signal_kit.journal import load_journal, compute_attribution
        data = json.loads((EXAMPLES / "decision_journal.json").read_text())
        decisions = load_journal(data)
        attributions = compute_attribution(decisions)
        self.assertGreater(len(attributions), 0)

    def test_example_lifecycle_validation(self):
        from invest_signal_kit.journal import load_journal, validate_lifecycle
        data = json.loads((EXAMPLES / "decision_journal.json").read_text())
        decisions = load_journal(data)
        alerts = validate_lifecycle(decisions, today="2026-05-23")
        # Should have some alerts (missing reviews, oversized risk, etc.)
        self.assertGreater(len(alerts), 0)

    def test_example_run_journal_analysis(self):
        from invest_signal_kit.journal import run_journal_analysis
        data = json.loads((EXAMPLES / "decision_journal.json").read_text())
        result = run_journal_analysis(data)
        self.assertIn("decisions", result)
        self.assertIn("alerts", result)
        self.assertIn("calibration", result)
        self.assertIn("attribution", result)
        self.assertEqual(len(result["decisions"]), 10)

    def test_example_calibration_has_buckets(self):
        from invest_signal_kit.journal import run_journal_analysis
        data = json.loads((EXAMPLES / "decision_journal.json").read_text())
        result = run_journal_analysis(data)
        buckets = result["calibration"]["buckets"]
        self.assertEqual(len(buckets), 5)
        # At least one bucket should have decisions
        total_in_buckets = sum(b["decision_count"] for b in buckets)
        self.assertGreater(total_in_buckets, 0)


class TestJournalCLI(unittest.TestCase):
    """Test journal CLI commands."""

    def test_journal_json_output(self):
        from invest_signal_kit.cli import main
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            ret = main(["journal", str(EXAMPLES / "decision_journal.json")])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(ret, 0)
        data = json.loads(captured.getvalue())
        self.assertIn("decisions", data)
        self.assertIn("alerts", data)
        self.assertIn("calibration", data)

    def test_journal_markdown_output(self):
        from invest_signal_kit.cli import main
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            ret = main(["journal", str(EXAMPLES / "decision_journal.json"), "--format", "markdown"])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(ret, 0)
        output = captured.getvalue()
        self.assertIn("# Decision Journal Report", output)
        self.assertIn("Score Calibration", output)

    def test_journal_writes_file(self):
        from invest_signal_kit.cli import main
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            outpath = f.name
        try:
            ret = main(["journal", str(EXAMPLES / "decision_journal.json"), "-o", outpath])
            self.assertEqual(ret, 0)
            data = json.loads(Path(outpath).read_text())
            self.assertIn("decisions", data)
        finally:
            os.unlink(outpath)

    def test_journal_missing_file(self):
        from invest_signal_kit.cli import main
        ret = main(["journal", "/tmp/no_such_journal.json"])
        self.assertEqual(ret, 1)

    def test_journal_invalid_json(self):
        from invest_signal_kit.cli import main
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            f.write("{bad json")
            f.flush()
            path = f.name
        try:
            ret = main(["journal", path])
            self.assertNotEqual(ret, 0)
        finally:
            os.unlink(path)

    def test_review_json_output(self):
        from invest_signal_kit.cli import main
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            ret = main(["review", str(EXAMPLES / "decision_journal.json")])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(ret, 0)
        data = json.loads(captured.getvalue())
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_review_markdown_output(self):
        from invest_signal_kit.cli import main
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            ret = main(["review", str(EXAMPLES / "decision_journal.json"), "--format", "md"])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(ret, 0)
        self.assertIn("# Decision Process Review", captured.getvalue())

    def test_calibrate_json_output(self):
        from invest_signal_kit.cli import main
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            ret = main(["calibrate", str(EXAMPLES / "decision_journal.json")])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(ret, 0)
        data = json.loads(captured.getvalue())
        self.assertIn("buckets", data)
        self.assertIn("overall_win_rate", data)

    def test_calibrate_markdown_output(self):
        from invest_signal_kit.cli import main
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            ret = main(["calibrate", str(EXAMPLES / "decision_journal.json"), "--format", "md"])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(ret, 0)
        self.assertIn("# Score Calibration Report", captured.getvalue())

    def test_review_missing_file(self):
        from invest_signal_kit.cli import main
        ret = main(["review", "/tmp/no_such_journal.json"])
        self.assertEqual(ret, 1)

    def test_calibrate_missing_file(self):
        from invest_signal_kit.cli import main
        ret = main(["calibrate", "/tmp/no_such_journal.json"])
        self.assertEqual(ret, 1)


class TestJournalMarkdown(unittest.TestCase):
    """Test journal markdown rendering."""

    def test_render_contains_sections(self):
        from invest_signal_kit.journal import Decision, render_journal_markdown
        decisions = [
            Decision(id="J-1", instrument_code="AAPL", status="reviewed",
                     entry_price=150, exit_price=165, actual_return_pct=10.0,
                     signal_score=75, outcome_category="hit_target"),
        ]
        md = render_journal_markdown(decisions)
        self.assertIn("# Decision Journal Report", md)
        self.assertIn("Decisions", md)
        self.assertIn("Not investment advice", md)

    def test_render_with_alerts(self):
        from invest_signal_kit.journal import Decision, LifecycleAlert, render_journal_markdown
        alerts = [LifecycleAlert(rule="test", message="Test alert", severity="warning")]
        md = render_journal_markdown([Decision(id="J-1", status="active")], alerts=alerts)
        self.assertIn("Lifecycle Alerts", md)
        self.assertIn("Test alert", md)

    def test_render_with_calibration(self):
        from invest_signal_kit.journal import Decision, CalibrationReport, CalibrationBucket, render_journal_markdown
        cal = CalibrationReport(
            reviewed_decisions=2, total_decisions=2,
            overall_win_rate=50.0, overall_avg_return=2.5,
            buckets=[CalibrationBucket(score_range="test", decision_count=2, win_count=1,
                                       loss_count=1, win_rate=50.0, avg_return_pct=2.5)],
        )
        md = render_journal_markdown([Decision(id="J-1", status="reviewed")], calibration=cal)
        self.assertIn("Score Calibration", md)


if __name__ == "__main__":
    unittest.main()
