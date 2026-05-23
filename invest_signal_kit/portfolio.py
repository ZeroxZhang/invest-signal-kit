"""Portfolio-level risk policy engine.

Deterministic, transparent formulas for portfolio holdings, sector/asset
exposures, concentration limits, risk budget tracking, stress testing,
candidate ranking, and portfolio-level blockers/warnings.

This is research tooling, not financial advice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------

@dataclass
class Holding:
    """A single portfolio position."""
    code: str = ""
    name: str = ""
    asset_type: str = "stock"
    sector: str = ""
    shares: float = 0.0
    entry_price: float = 0.0
    current_price: float = 0.0
    stop_price: float = 0.0
    direction: str = "long"

    @property
    def market_value(self) -> float:
        return self.shares * self.current_price

    @property
    def cost_basis(self) -> float:
        return self.shares * self.entry_price

    @property
    def unrealized_pnl(self) -> float:
        if self.direction == "short":
            return (self.entry_price - self.current_price) * self.shares
        return (self.current_price - self.entry_price) * self.shares

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.cost_basis == 0:
            return 0.0
        return (self.unrealized_pnl / self.cost_basis) * 100

    @property
    def risk_per_share(self) -> float:
        if self.stop_price <= 0:
            return 0.0
        if self.direction == "short":
            return self.stop_price - self.current_price
        return self.current_price - self.stop_price

    @property
    def position_risk(self) -> float:
        """Total risk = shares * |current - stop|."""
        return self.shares * abs(self.risk_per_share)


@dataclass
class PortfolioPolicy:
    """Risk policy limits for a portfolio."""
    max_position_pct: float = 20.0
    """Maximum single position as % of total portfolio value."""

    max_sector_pct: float = 35.0
    """Maximum single sector as % of total portfolio value."""

    max_risk_budget_pct: float = 6.0
    """Maximum total risk (sum of position risks) as % of portfolio."""

    max_drawdown_pct: float = 15.0
    """Maximum acceptable drawdown from peak."""

    watchlist_min_score: float = 60.0
    """Minimum score for a candidate signal to pass the watchlist filter."""

    max_candidate_risk_pct: float = 2.0
    """Maximum per-trade risk as % of portfolio for candidate signals."""

    sector_limits: Dict[str, float] = field(default_factory=dict)
    """Per-sector override limits. Key = sector name, value = max %."""


@dataclass
class CandidateSignal:
    """A proposed trade or signal for portfolio evaluation."""
    code: str = ""
    name: str = ""
    direction: str = "bullish"
    asset_type: str = "stock"
    sector: str = ""
    expected_return_pct: float = 0.0
    risk_pct: float = 0.0
    """Risk as % of position (stop distance)."""
    position_size_pct: float = 0.0
    """Proposed position size as % of portfolio."""
    signal_score: float = 0.0
    """Score from the signal scoring engine (0-100)."""
    action_level: str = "information"
    thesis_quality: float = 0.0
    market_confirmation: float = 0.0
    risk_execution: float = 0.0
    ev_quality: str = "negative_ev"


@dataclass
class StressScenario:
    """Deterministic stress test scenario."""
    name: str = ""
    description: str = ""
    market_shock_pct: float = 0.0
    """Broad market shock applied to all positions (e.g. -10 for -10%)."""
    sector_shocks: Dict[str, float] = field(default_factory=dict)
    """Per-sector shocks. Key = sector name, value = shock %."""
    single_name_shocks: Dict[str, float] = field(default_factory=dict)
    """Per-instrument shocks. Key = code, value = shock %."""
    liquidity_haircut_pct: float = 0.0
    """Liquidity haircut applied to all positions (reduces value)."""


# ---------------------------------------------------------------------------
# Exposure Calculation
# ---------------------------------------------------------------------------

@dataclass
class PositionExposure:
    """Exposure breakdown for a single position."""
    code: str = ""
    name: str = ""
    sector: str = ""
    asset_type: str = ""
    market_value: float = 0.0
    exposure_pct: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    position_risk: float = 0.0
    risk_pct: float = 0.0


@dataclass
class SectorExposure:
    """Aggregated exposure for a sector."""
    sector: str = ""
    market_value: float = 0.0
    exposure_pct: float = 0.0
    position_count: int = 0
    position_codes: List[str] = field(default_factory=list)


@dataclass
class ExposureReport:
    """Full exposure breakdown."""
    total_value: float = 0.0
    cash: float = 0.0
    invested_value: float = 0.0
    invested_pct: float = 0.0
    positions: List[PositionExposure] = field(default_factory=list)
    sectors: List[SectorExposure] = field(default_factory=list)
    total_risk: float = 0.0
    total_risk_pct: float = 0.0


def calculate_exposures(holdings: List[Holding], cash: float) -> ExposureReport:
    """Calculate position and sector exposures.

    Formula:
        position_value = shares * current_price
        total_invested = sum(position_value)
        total_portfolio = total_invested + cash
        exposure_pct = position_value / total_portfolio * 100
        sector_pct = sum(position_values_in_sector) / total_portfolio * 100
        position_risk = shares * |current_price - stop_price|
        total_risk_pct = sum(position_risk) / total_portfolio * 100
    """
    invested_value = sum(h.market_value for h in holdings)
    total_value = invested_value + cash

    positions = []
    for h in holdings:
        exp_pct = _pct(h.market_value, total_value)
        positions.append(PositionExposure(
            code=h.code,
            name=h.name,
            sector=h.sector,
            asset_type=h.asset_type,
            market_value=round(h.market_value, 2),
            exposure_pct=round(exp_pct, 2),
            unrealized_pnl=round(h.unrealized_pnl, 2),
            unrealized_pnl_pct=round(h.unrealized_pnl_pct, 2),
            position_risk=round(h.position_risk, 2),
            risk_pct=round(_pct(h.position_risk, total_value), 2),
        ))

    # Sector aggregation
    sector_map: Dict[str, Dict[str, Any]] = {}
    for h in holdings:
        s = h.sector or "Unknown"
        if s not in sector_map:
            sector_map[s] = {"value": 0.0, "count": 0, "codes": []}
        sector_map[s]["value"] += h.market_value
        sector_map[s]["count"] += 1
        sector_map[s]["codes"].append(h.code)

    sectors = []
    for s, info in sorted(sector_map.items()):
        sectors.append(SectorExposure(
            sector=s,
            market_value=round(info["value"], 2),
            exposure_pct=round(_pct(info["value"], total_value), 2),
            position_count=info["count"],
            position_codes=info["codes"],
        ))

    total_risk = sum(h.position_risk for h in holdings)

    return ExposureReport(
        total_value=round(total_value, 2),
        cash=round(cash, 2),
        invested_value=round(invested_value, 2),
        invested_pct=round(_pct(invested_value, total_value), 2),
        positions=positions,
        sectors=sectors,
        total_risk=round(total_risk, 2),
        total_risk_pct=round(_pct(total_risk, total_value), 2),
    )


# ---------------------------------------------------------------------------
# Concentration Check
# ---------------------------------------------------------------------------

@dataclass
class ConcentrationViolation:
    """A single concentration limit violation."""
    rule: str = ""
    message: str = ""
    severity: str = "warning"
    actual_pct: float = 0.0
    limit_pct: float = 0.0


def check_concentration(holdings: List[Holding], policy: PortfolioPolicy,
                        total_value: float) -> List[ConcentrationViolation]:
    """Check portfolio against concentration limits.

    Rules checked:
    1. Single position > max_position_pct
    2. Sector > max_sector_pct (or per-sector override)
    3. Single position risk > max_candidate_risk_pct (2% default)
    """
    violations = []

    if total_value <= 0:
        return violations

    # Position concentration
    for h in holdings:
        pos_pct = _pct(h.market_value, total_value)
        if pos_pct > policy.max_position_pct:
            violations.append(ConcentrationViolation(
                rule="position_concentration",
                message=f"{h.code} ({h.name}) is {pos_pct:.1f}% of portfolio, limit is {policy.max_position_pct:.0f}%",
                severity="warning",
                actual_pct=round(pos_pct, 2),
                limit_pct=policy.max_position_pct,
            ))

    # Sector concentration
    sector_values: Dict[str, float] = {}
    for h in holdings:
        s = h.sector or "Unknown"
        sector_values[s] = sector_values.get(s, 0.0) + h.market_value

    for sector, value in sector_values.items():
        sector_pct = _pct(value, total_value)
        limit = policy.sector_limits.get(sector, policy.max_sector_pct)
        if sector_pct > limit:
            violations.append(ConcentrationViolation(
                rule="sector_concentration",
                message=f"Sector '{sector}' is {sector_pct:.1f}% of portfolio, limit is {limit:.0f}%",
                severity="warning",
                actual_pct=round(sector_pct, 2),
                limit_pct=limit,
            ))

    # Per-position risk limit
    for h in holdings:
        risk_pct = _pct(h.position_risk, total_value)
        if risk_pct > policy.max_candidate_risk_pct:
            violations.append(ConcentrationViolation(
                rule="position_risk_limit",
                message=f"{h.code} risk is {risk_pct:.1f}% of portfolio, limit is {policy.max_candidate_risk_pct:.0f}%",
                severity="error",
                actual_pct=round(risk_pct, 2),
                limit_pct=policy.max_candidate_risk_pct,
            ))

    return violations


# ---------------------------------------------------------------------------
# Risk Budget
# ---------------------------------------------------------------------------

@dataclass
class RiskBudgetReport:
    """Risk budget utilization report."""
    total_risk: float = 0.0
    total_risk_pct: float = 0.0
    risk_budget: float = 0.0
    risk_budget_pct: float = 0.0
    remaining_budget: float = 0.0
    remaining_budget_pct: float = 0.0
    utilization_pct: float = 0.0
    over_budget: bool = False
    position_risks: Dict[str, float] = field(default_factory=dict)


def check_risk_budget(holdings: List[Holding], total_value: float,
                      policy: PortfolioPolicy) -> RiskBudgetReport:
    """Check portfolio risk budget utilization.

    Formula:
        risk_budget = total_value * max_risk_budget_pct / 100
        total_risk = sum(shares * |current - stop|) for all holdings
        utilization = total_risk / risk_budget * 100
        remaining = risk_budget - total_risk
    """
    risk_budget = total_value * (policy.max_risk_budget_pct / 100)
    total_risk = sum(h.position_risk for h in holdings)
    remaining = max(0, risk_budget - total_risk)
    utilization = _pct(total_risk, risk_budget) if risk_budget > 0 else 0.0

    position_risks = {}
    for h in holdings:
        if h.code:
            position_risks[h.code] = round(h.position_risk, 2)

    return RiskBudgetReport(
        total_risk=round(total_risk, 2),
        total_risk_pct=round(_pct(total_risk, total_value), 2),
        risk_budget=round(risk_budget, 2),
        risk_budget_pct=policy.max_risk_budget_pct,
        remaining_budget=round(remaining, 2),
        remaining_budget_pct=round(_pct(remaining, total_value), 2),
        utilization_pct=round(utilization, 2),
        over_budget=total_risk > risk_budget,
        position_risks=position_risks,
    )


# ---------------------------------------------------------------------------
# Candidate Ranking / Watchlist
# ---------------------------------------------------------------------------

@dataclass
class CandidateRank:
    """Evaluation result for a candidate signal."""
    code: str = ""
    name: str = ""
    direction: str = ""
    sector: str = ""
    signal_score: float = 0.0
    action_level: str = ""
    expected_return_pct: float = 0.0
    risk_pct: float = 0.0
    position_size_pct: float = 0.0
    rank: int = 0
    passes_watchlist: bool = False
    blockers: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def rank_candidates(candidates: List[CandidateSignal], holdings: List[Holding],
                    policy: PortfolioPolicy,
                    total_value: float) -> List[CandidateRank]:
    """Rank candidate signals against portfolio policy.

    Pass criteria:
    1. signal_score >= watchlist_min_score
    2. Adding position does not breach max_position_pct
    3. Adding position does not breach max_sector_pct
    4. Position risk <= max_candidate_risk_pct
    5. EV quality not negative_ev

    Ranking: primary by signal_score descending, secondary by expected_return descending.
    """
    # Current sector exposure
    sector_values: Dict[str, float] = {}
    for h in holdings:
        s = h.sector or "Unknown"
        sector_values[s] = sector_values.get(s, 0.0) + h.market_value

    # Current positions
    position_values: Dict[str, float] = {}
    for h in holdings:
        if h.code:
            position_values[h.code] = position_values.get(h.code, 0.0) + h.market_value

    ranks = []
    for c in candidates:
        blockers = []
        warnings = []

        # Score gate
        if c.signal_score < policy.watchlist_min_score:
            blockers.append(
                f"Signal score {c.signal_score:.0f} below minimum {policy.watchlist_min_score:.0f}")

        # EV gate
        if c.ev_quality == "negative_ev":
            blockers.append("Expected value is negative")

        # Position size gate
        if c.position_size_pct > 0 and c.position_size_pct > policy.max_position_pct:
            blockers.append(
                f"Proposed size {c.position_size_pct:.1f}% exceeds position limit {policy.max_position_pct:.0f}%")

        # Sector gate
        if c.sector:
            existing = sector_values.get(c.sector, 0.0)
            added = total_value * (c.position_size_pct / 100) if c.position_size_pct > 0 else 0.0
            new_sector_pct = _pct(existing + added, total_value)
            limit = policy.sector_limits.get(c.sector, policy.max_sector_pct)
            if new_sector_pct > limit:
                blockers.append(
                    f"Sector '{c.sector}' would be {new_sector_pct:.1f}%, limit is {limit:.0f}%")

        # Risk gate
        if c.risk_pct > policy.max_candidate_risk_pct:
            blockers.append(
                f"Trade risk {c.risk_pct:.1f}% exceeds per-trade limit {policy.max_candidate_risk_pct:.0f}%")

        # Warnings
        if c.action_level in ("information", "watch") and c.signal_score >= policy.watchlist_min_score:
            warnings.append(f"Signal is at '{c.action_level}' level — not yet candidate/action")

        if c.thesis_quality > 0 and c.thesis_quality < 50:
            warnings.append(f"Low thesis quality ({c.thesis_quality:.0f}/100)")

        ranks.append(CandidateRank(
            code=c.code,
            name=c.name,
            direction=c.direction,
            sector=c.sector,
            signal_score=c.signal_score,
            action_level=c.action_level,
            expected_return_pct=c.expected_return_pct,
            risk_pct=c.risk_pct,
            position_size_pct=c.position_size_pct,
            passes_watchlist=len(blockers) == 0,
            blockers=blockers,
            warnings=warnings,
        ))

    # Sort: passes first, then by score descending, then by return descending
    ranks.sort(key=lambda r: (not r.passes_watchlist, -r.signal_score, -r.expected_return_pct))
    for i, r in enumerate(ranks):
        r.rank = i + 1

    return ranks


# ---------------------------------------------------------------------------
# Stress Testing
# ---------------------------------------------------------------------------

@dataclass
class StressPositionResult:
    """Stress test result for a single position."""
    code: str = ""
    name: str = ""
    sector: str = ""
    original_value: float = 0.0
    shocked_value: float = 0.0
    loss: float = 0.0
    loss_pct: float = 0.0
    applied_shock_pct: float = 0.0


@dataclass
class StressResult:
    """Result of a single stress scenario."""
    scenario_name: str = ""
    description: str = ""
    original_portfolio_value: float = 0.0
    shocked_portfolio_value: float = 0.0
    total_loss: float = 0.0
    total_loss_pct: float = 0.0
    positions: List[StressPositionResult] = field(default_factory=list)
    breaches_drawdown_limit: bool = False


def run_stress_test(holdings: List[Holding], cash: float,
                    scenario: StressScenario,
                    max_drawdown_pct: float = 15.0) -> StressResult:
    """Run deterministic stress test on portfolio.

    Formula per position:
        effective_shock = market_shock + sector_shock(code) + single_name_shock(code)
        shocked_value = current_value * (1 + effective_shock/100) * (1 - liquidity_haircut/100)

    Market shock applies to ALL positions. Sector shock is additive and only
    applies to matching sector. Single-name shock is additive and only applies
    to matching code. Liquidity haircut is multiplicative and reduces the
    already-shocked value.
    """
    invested_value = sum(h.market_value for h in holdings)
    total_value = invested_value + cash

    position_results = []
    total_shocked = 0.0

    for h in holdings:
        # Base shock
        shock = scenario.market_shock_pct

        # Sector overlay
        if h.sector and h.sector in scenario.sector_shocks:
            shock += scenario.sector_shocks[h.sector]

        # Single-name overlay
        if h.code in scenario.single_name_shocks:
            shock += scenario.single_name_shocks[h.code]

        shocked_val = h.market_value * (1 + shock / 100)

        # Liquidity haircut
        if scenario.liquidity_haircut_pct > 0:
            shocked_val *= (1 - scenario.liquidity_haircut_pct / 100)

        loss = h.market_value - shocked_val
        loss_pct = _pct(loss, h.market_value) if h.market_value > 0 else 0.0

        position_results.append(StressPositionResult(
            code=h.code,
            name=h.name,
            sector=h.sector,
            original_value=round(h.market_value, 2),
            shocked_value=round(shocked_val, 2),
            loss=round(loss, 2),
            loss_pct=round(loss_pct, 2),
            applied_shock_pct=round(shock, 2),
        ))
        total_shocked += shocked_val

    total_shocked += cash  # Cash unaffected
    total_loss = total_value - total_shocked
    total_loss_pct = _pct(total_loss, total_value) if total_value > 0 else 0.0

    return StressResult(
        scenario_name=scenario.name,
        description=scenario.description,
        original_portfolio_value=round(total_value, 2),
        shocked_portfolio_value=round(total_shocked, 2),
        total_loss=round(total_loss, 2),
        total_loss_pct=round(total_loss_pct, 2),
        positions=position_results,
        breaches_drawdown_limit=total_loss_pct > max_drawdown_pct,
    )


# ---------------------------------------------------------------------------
# Portfolio Evaluation (Full Pipeline)
# ---------------------------------------------------------------------------

@dataclass
class PortfolioBlocker:
    """A portfolio-level blocker or warning."""
    rule: str = ""
    message: str = ""
    severity: str = "warning"


@dataclass
class PortfolioEvaluation:
    """Complete portfolio evaluation result."""
    exposure_report: ExposureReport = field(default_factory=ExposureReport)
    concentration_violations: List[ConcentrationViolation] = field(default_factory=list)
    risk_budget: RiskBudgetReport = field(default_factory=RiskBudgetReport)
    candidate_rankings: List[CandidateRank] = field(default_factory=list)
    stress_results: List[StressResult] = field(default_factory=list)
    blockers: List[PortfolioBlocker] = field(default_factory=list)
    warnings: List[PortfolioBlocker] = field(default_factory=list)


def evaluate_portfolio(holdings: List[Holding], cash: float,
                       policy: PortfolioPolicy,
                       candidates: Optional[List[CandidateSignal]] = None,
                       scenarios: Optional[List[StressScenario]] = None,
                       ) -> PortfolioEvaluation:
    """Run full portfolio evaluation pipeline.

    Steps:
    1. Calculate exposures (position + sector)
    2. Check concentration limits
    3. Check risk budget
    4. Rank candidates against policy
    5. Run stress scenarios
    6. Aggregate blockers and warnings
    """
    # 1. Exposures
    exposure_report = calculate_exposures(holdings, cash)
    total_value = exposure_report.total_value

    # 2. Concentration
    concentration_violations = check_concentration(holdings, policy, total_value)

    # 3. Risk budget
    risk_budget = check_risk_budget(holdings, total_value, policy)

    # 4. Candidates
    candidate_rankings = []
    if candidates:
        candidate_rankings = rank_candidates(candidates, holdings, policy, total_value)

    # 5. Stress tests
    stress_results = []
    if scenarios:
        for scenario in scenarios:
            result = run_stress_test(holdings, cash, scenario, policy.max_drawdown_pct)
            stress_results.append(result)

    # 6. Blockers and warnings
    blockers = []
    warnings = []

    # Risk budget blocker
    if risk_budget.over_budget:
        blockers.append(PortfolioBlocker(
            rule="risk_budget_exceeded",
            message=f"Risk budget exceeded: {risk_budget.utilization_pct:.1f}% utilized "
                    f"({risk_budget.total_risk:,.0f} / {risk_budget.risk_budget:,.0f})",
            severity="error",
        ))

    # Concentration blockers
    for v in concentration_violations:
        if v.severity == "error":
            blockers.append(PortfolioBlocker(
                rule=v.rule,
                message=v.message,
                severity="error",
            ))
        else:
            warnings.append(PortfolioBlocker(
                rule=v.rule,
                message=v.message,
                severity="warning",
            ))

    # Stress test blockers
    for sr in stress_results:
        if sr.breaches_drawdown_limit:
            blockers.append(PortfolioBlocker(
                rule="stress_drawdown_breach",
                message=f"Scenario '{sr.scenario_name}' causes {sr.total_loss_pct:.1f}% loss, "
                        f"exceeding {policy.max_drawdown_pct:.0f}% drawdown limit",
                severity="error",
            ))

    # Candidate blockers
    if candidates:
        passing = [c for c in candidate_rankings if c.passes_watchlist]
        if not passing and candidates:
            warnings.append(PortfolioBlocker(
                rule="no_passing_candidates",
                message=f"None of the {len(candidates)} candidate(s) pass the watchlist filter",
                severity="warning",
            ))

    return PortfolioEvaluation(
        exposure_report=exposure_report,
        concentration_violations=concentration_violations,
        risk_budget=risk_budget,
        candidate_rankings=candidate_rankings,
        stress_results=stress_results,
        blockers=blockers,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Markdown Renderer
# ---------------------------------------------------------------------------

def render_portfolio_markdown(eval_result: PortfolioEvaluation) -> str:
    """Render portfolio evaluation as Markdown."""
    lines: List[str] = []
    er = eval_result.exposure_report

    lines.append("# Portfolio Risk Report")
    lines.append("")

    # Summary
    lines.append("## Portfolio Summary")
    lines.append(f"- **Total Value:** {er.total_value:,.2f}")
    lines.append(f"- **Cash:** {er.cash:,.2f} ({_pct(er.cash, er.total_value):.1f}%)")
    lines.append(f"- **Invested:** {er.invested_value:,.2f} ({er.invested_pct:.1f}%)")
    lines.append(f"- **Total Risk:** {er.total_risk:,.2f} ({er.total_risk_pct:.1f}% of portfolio)")
    lines.append("")

    # Positions
    if er.positions:
        lines.append("## Position Exposures")
        lines.append("")
        lines.append("| Code | Name | Sector | Value | Exposure % | P&L % | Risk % |")
        lines.append("|------|------|--------|-------|------------|-------|--------|")
        for p in er.positions:
            pnl_sign = "+" if p.unrealized_pnl_pct >= 0 else ""
            lines.append(
                f"| {p.code} | {p.name} | {p.sector} "
                f"| {p.market_value:,.0f} | {p.exposure_pct:.1f}% "
                f"| {pnl_sign}{p.unrealized_pnl_pct:.1f}% | {p.risk_pct:.1f}% |")
        lines.append("")

    # Sectors
    if er.sectors:
        lines.append("## Sector Exposures")
        lines.append("")
        lines.append("| Sector | Value | Exposure % | Positions |")
        lines.append("|--------|-------|------------|-----------|")
        for s in er.sectors:
            lines.append(
                f"| {s.sector} | {s.market_value:,.0f} "
                f"| {s.exposure_pct:.1f}% | {s.position_count} |")
        lines.append("")

    # Risk Budget
    rb = eval_result.risk_budget
    lines.append("## Risk Budget")
    lines.append(f"- **Budget:** {rb.risk_budget:,.2f} ({rb.risk_budget_pct:.1f}% of portfolio)")
    lines.append(f"- **Used:** {rb.total_risk:,.2f} ({rb.total_risk_pct:.1f}%)")
    lines.append(f"- **Remaining:** {rb.remaining_budget:,.2f} ({rb.remaining_budget_pct:.1f}%)")
    lines.append(f"- **Utilization:** {rb.utilization_pct:.1f}%")
    if rb.over_budget:
        lines.append("- **STATUS: OVER BUDGET**")
    lines.append("")

    # Concentration violations
    if eval_result.concentration_violations:
        lines.append("## Concentration Violations")
        for v in eval_result.concentration_violations:
            marker = "ERROR" if v.severity == "error" else "WARNING"
            lines.append(f"- [{marker}] {v.message}")
        lines.append("")

    # Candidate Rankings
    if eval_result.candidate_rankings:
        lines.append("## Candidate Watchlist")
        lines.append("")
        lines.append("| Rank | Code | Score | Direction | Sector | Exp Ret % | Passes |")
        lines.append("|------|------|-------|-----------|--------|-----------|--------|")
        for c in eval_result.candidate_rankings:
            pass_mark = "YES" if c.passes_watchlist else "NO"
            lines.append(
                f"| {c.rank} | {c.code} | {c.signal_score:.0f} "
                f"| {c.direction} | {c.sector} "
                f"| {c.expected_return_pct:+.1f}% | {pass_mark} |")
        lines.append("")
        for c in eval_result.candidate_rankings:
            if c.blockers or c.warnings:
                lines.append(f"**{c.code}:**")
                for b in c.blockers:
                    lines.append(f"- BLOCKER: {b}")
                for w in c.warnings:
                    lines.append(f"- WARNING: {w}")
        lines.append("")

    # Stress Tests
    if eval_result.stress_results:
        lines.append("## Stress Test Results")
        lines.append("")
        for sr in eval_result.stress_results:
            lines.append(f"### {sr.scenario_name}")
            if sr.description:
                lines.append(f"*{sr.description}*")
                lines.append("")
            lines.append(f"- **Original Value:** {sr.original_portfolio_value:,.2f}")
            lines.append(f"- **Stressed Value:** {sr.shocked_portfolio_value:,.2f}")
            lines.append(f"- **Total Loss:** {sr.total_loss:,.2f} ({sr.total_loss_pct:.1f}%)")
            if sr.breaches_drawdown_limit:
                lines.append("- **BREACHES DRAWDOWN LIMIT**")
            if sr.positions:
                lines.append("")
                lines.append("| Code | Sector | Shock % | Loss | Loss % |")
                lines.append("|------|--------|---------|------|--------|")
                for p in sr.positions:
                    if p.applied_shock_pct != 0:
                        lines.append(
                            f"| {p.code} | {p.sector} | {p.applied_shock_pct:+.1f}% "
                            f"| {p.loss:,.0f} | {p.loss_pct:.1f}% |")
            lines.append("")

    # Blockers
    if eval_result.blockers:
        lines.append("## Portfolio Blockers")
        for b in eval_result.blockers:
            lines.append(f"- **[{b.severity.upper()}]** {b.message}")
        lines.append("")

    if eval_result.warnings:
        lines.append("## Portfolio Warnings")
        for w in eval_result.warnings:
            lines.append(f"- [{w.severity.upper()}] {w.message}")
        lines.append("")

    # Clean slate
    if not eval_result.blockers and not eval_result.warnings:
        lines.append("## Status")
        lines.append("No portfolio-level blockers or warnings.")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by invest-signal-kit portfolio engine. Not investment advice.*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_holding(data: dict) -> Holding:
    """Load a Holding from a dict."""
    return Holding(
        code=data.get("code", ""),
        name=data.get("name", ""),
        asset_type=data.get("asset_type", "stock"),
        sector=data.get("sector", ""),
        shares=float(data.get("shares", 0)),
        entry_price=float(data.get("entry_price", 0)),
        current_price=float(data.get("current_price", 0)),
        stop_price=float(data.get("stop_price", 0)),
        direction=data.get("direction", "long"),
    )


def load_portfolio_policy(data: dict) -> PortfolioPolicy:
    """Load a PortfolioPolicy from a dict."""
    return PortfolioPolicy(
        max_position_pct=float(data.get("max_position_pct", 20)),
        max_sector_pct=float(data.get("max_sector_pct", 35)),
        max_risk_budget_pct=float(data.get("max_risk_budget_pct", 6)),
        max_drawdown_pct=float(data.get("max_drawdown_pct", 15)),
        watchlist_min_score=float(data.get("watchlist_min_score", 60)),
        max_candidate_risk_pct=float(data.get("max_candidate_risk_pct", 2)),
        sector_limits=data.get("sector_limits", {}),
    )


def load_candidate_signal(data: dict) -> CandidateSignal:
    """Load a CandidateSignal from a dict."""
    return CandidateSignal(
        code=data.get("code", ""),
        name=data.get("name", ""),
        direction=data.get("direction", "bullish"),
        asset_type=data.get("asset_type", "stock"),
        sector=data.get("sector", ""),
        expected_return_pct=float(data.get("expected_return_pct", 0)),
        risk_pct=float(data.get("risk_pct", 0)),
        position_size_pct=float(data.get("position_size_pct", 0)),
        signal_score=float(data.get("signal_score", 0)),
        action_level=data.get("action_level", "information"),
        thesis_quality=float(data.get("thesis_quality", 0)),
        market_confirmation=float(data.get("market_confirmation", 0)),
        risk_execution=float(data.get("risk_execution", 0)),
        ev_quality=data.get("ev_quality", "negative_ev"),
    )


def load_stress_scenario(data: dict) -> StressScenario:
    """Load a StressScenario from a dict."""
    return StressScenario(
        name=data.get("name", ""),
        description=data.get("description", ""),
        market_shock_pct=float(data.get("market_shock_pct", 0)),
        sector_shocks=data.get("sector_shocks", {}),
        single_name_shocks=data.get("single_name_shocks", {}),
        liquidity_haircut_pct=float(data.get("liquidity_haircut_pct", 0)),
    )


def load_portfolio_state(data: dict) -> Tuple[List[Holding], float, PortfolioPolicy,
                                               List[CandidateSignal], List[StressScenario]]:
    """Load full portfolio state from a dict.

    Expected format:
    {
        "holdings": [...],
        "cash": 100000,
        "policy": {...},
        "candidates": [...],
        "scenarios": [...]
    }
    """
    holdings = [load_holding(h) for h in data.get("holdings", [])]
    cash = float(data.get("cash", 0))
    policy = load_portfolio_policy(data.get("policy", {}))
    candidates = [load_candidate_signal(c) for c in data.get("candidates", [])]
    scenarios = [load_stress_scenario(s) for s in data.get("scenarios", [])]

    return holdings, cash, policy, candidates, scenarios


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


def run_portfolio_analysis(data: dict) -> dict:
    """Run full portfolio analysis from a JSON dict.

    Convenience function that loads, evaluates, and serializes.
    """
    holdings, cash, policy, candidates, scenarios = load_portfolio_state(data)
    result = evaluate_portfolio(holdings, cash, policy, candidates, scenarios)
    return _result_to_dict(result)


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _pct(value: float, total: float) -> float:
    """Percentage, safe against division by zero."""
    return (value / total * 100) if total else 0.0
