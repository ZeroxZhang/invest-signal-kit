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


if __name__ == "__main__":
    unittest.main()
