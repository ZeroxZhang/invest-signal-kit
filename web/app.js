/* Invest Signal Kit — Workstation Application
   All framework logic ported to client-side JS. No build step, no dependencies. */

'use strict';

// ---------------------------------------------------------------------------
// Framework Logic (mirrors invest_signal_kit/framework.py)
// ---------------------------------------------------------------------------

function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

function gradeFromScore(score) {
  if (score >= 85) return 'A';
  if (score >= 70) return 'B';
  if (score >= 50) return 'C';
  if (score >= 30) return 'D';
  return 'F';
}

function weightedScore(items) {
  // items: [[score_0_10, weight], ...]
  let tw = 0, sum = 0;
  for (const [s, w] of items) { tw += w; sum += s * w; }
  return tw === 0 ? 0 : sum / tw;
}

function scoreTo100(s) { return clamp(s * 10, 0, 100); }

// --- Thesis Quality ---
function scoreThesisQuality(inp) {
  const weights = {
    evidence_strength: 0.25,
    source_diversity: 0.20,
    thesis_clarity: 0.25,
    catalyst_specificity: 0.15,
    time_horizon_fit: 0.15,
  };
  const factors = {};
  for (const k of Object.keys(weights)) {
    factors[k] = clamp(inp[k] || 0, 0, 10);
  }
  const blockers = [];
  if (factors.evidence_strength < 3) blockers.push('Thesis lacks sufficient evidence (score < 3)');
  if (factors.thesis_clarity < 3) blockers.push('Thesis is too vague to evaluate (score < 3)');

  const items = Object.keys(weights).map(k => [factors[k], weights[k]]);
  let total = scoreTo100(weightedScore(items));
  if (blockers.length) total = Math.min(total, 40);

  return { total: round1(total), grade: gradeFromScore(total), factors, weights, blockers };
}

// --- Market Confirmation ---
function scoreMarketConfirmation(inp) {
  const weights = {
    trend_alignment: 0.30,
    momentum: 0.20,
    volume_liquidity: 0.20,
    relative_strength: 0.15,
    regime_alignment: 0.15,
  };
  const factors = {};
  for (const k of Object.keys(weights)) {
    factors[k] = clamp(inp[k] || 0, 0, 10);
  }
  const blockers = [];
  if (factors.trend_alignment < 2) blockers.push('Price trend contradicts thesis direction');

  const items = Object.keys(weights).map(k => [factors[k], weights[k]]);
  let total = scoreTo100(weightedScore(items));
  if (blockers.length) total = Math.min(total, 30);

  return { total: round1(total), grade: gradeFromScore(total), factors, weights, blockers };
}

// --- Risk / Execution ---
function scoreRiskExecution(inp) {
  const weights = {
    invalidation_clarity: 0.25,
    max_loss_defined: 0.20,
    position_sizing_discipline: 0.20,
    liquidity_slippage_risk: 0.15,
    concentration_risk: 0.10,
    time_stop: 0.10,
  };
  const factors = {};
  for (const k of Object.keys(weights)) {
    factors[k] = clamp(inp[k] || 0, 0, 10);
  }
  const blockers = [];
  if (factors.invalidation_clarity < 3) blockers.push('No clear invalidation/stop condition defined');
  if (factors.max_loss_defined < 2) blockers.push('Maximum loss is not defined');

  const items = Object.keys(weights).map(k => [factors[k], weights[k]]);
  let total = scoreTo100(weightedScore(items));
  if (blockers.length) total = Math.min(total, 35);

  return { total: round1(total), grade: gradeFromScore(total), factors, weights, blockers };
}

// --- Expected Value ---
function calculateExpectedValue(inp) {
  const raw = inp.bull_probability + inp.base_probability + inp.bear_probability;
  if (raw <= 0) return { expected_return_pct: 0, max_drawdown_pct: 0, payoff_asymmetry: 0, quality: 'negative_ev', scenario_details: {} };

  const bp = inp.bull_probability / raw;
  const sp = inp.base_probability / raw;
  const rp = inp.bear_probability / raw;

  const expected = bp * inp.bull_return_pct + sp * inp.base_return_pct + rp * inp.bear_return_pct;
  const maxDd = Math.min(inp.bear_return_pct, 0);

  // Payoff asymmetry
  const upParts = [], downParts = [];
  if (inp.bull_return_pct > 0) upParts.push(bp * inp.bull_return_pct);
  if (inp.base_return_pct > 0) upParts.push(sp * inp.base_return_pct);
  if (inp.bull_return_pct < 0) downParts.push(bp * inp.bull_return_pct);
  if (inp.base_return_pct < 0) downParts.push(sp * inp.base_return_pct);
  if (inp.bear_return_pct < 0) downParts.push(rp * inp.bear_return_pct);
  if (inp.bear_return_pct > 0) upParts.push(rp * inp.bear_return_pct);

  const avgUp = upParts.reduce((a, b) => a + b, 0);
  const avgDown = Math.abs(downParts.reduce((a, b) => a + b, 0));
  const asymmetry = avgDown > 0 ? avgUp / avgDown : (avgUp > 0 ? 999 : 0);

  let quality;
  if (expected > 3) quality = 'positive_ev';
  else if (expected > 0) quality = 'marginal';
  else quality = 'negative_ev';

  return {
    expected_return_pct: round2(expected),
    max_drawdown_pct: round2(maxDd),
    payoff_asymmetry: round2(Math.min(asymmetry, 999)),
    normalized_probabilities: { bull: round3(bp), base: round3(sp), bear: round3(rp) },
    scenario_details: {
      bull: { probability: round3(bp), return_pct: inp.bull_return_pct },
      base: { probability: round3(sp), return_pct: inp.base_return_pct },
      bear: { probability: round3(rp), return_pct: inp.bear_return_pct },
    },
    quality,
  };
}

// --- Position Sizing ---
function calculatePositionSize(inp, targetReturnPct) {
  const notes = [];
  if (inp.portfolio_value <= 0) return { notes: ['Portfolio value must be positive'] };
  if (inp.entry_price <= 0) return { notes: ['Entry price must be positive'] };
  if (inp.stop_distance_pct <= 0) return { notes: ['Stop distance must be positive'] };

  const riskAmount = inp.portfolio_value * (inp.max_risk_pct / 100);
  const perUnitRisk = inp.entry_price * (inp.stop_distance_pct / 100);
  const rawShares = riskAmount / perUnitRisk;
  const confFactor = clamp(inp.confidence / 100, 0.1, 1.0);
  const adjShares = Math.round(rawShares * confFactor);
  const posValue = adjShares * inp.entry_price;
  const posPct = inp.portfolio_value > 0 ? (posValue / inp.portfolio_value * 100) : 0;
  const rr = (targetReturnPct > 0 && inp.stop_distance_pct > 0) ? targetReturnPct / inp.stop_distance_pct : 0;

  if (posPct > 20) notes.push(`Position is ${posPct.toFixed(1)}% of portfolio — consider reducing`);
  if (rr > 0 && rr < 1.5) notes.push(`Risk/reward ratio ${rr.toFixed(1)}:1 is below 1.5:1 — marginal setup`);
  if (confFactor < 0.5) notes.push('Low confidence haircut applied — size reduced significantly');

  return {
    risk_amount: round2(riskAmount),
    raw_position_size: Math.round(rawShares),
    adjusted_position_size: adjShares,
    confidence_factor: round3(confFactor),
    position_value: round2(posValue),
    position_pct_of_portfolio: round2(posPct),
    risk_reward_at_target: round2(rr),
    notes,
  };
}

// --- Decision Readiness ---
function assessDecisionReadiness(inp) {
  const checklist = {};
  const blockers = [];

  // G1: INFORMATION -> WATCH
  const g1 = inp.thesis_quality_score >= 30;
  checklist.thesis_quality_30 = inp.thesis_quality_score >= 30;

  // G2: WATCH -> CANDIDATE
  const g2c = {
    thesis_quality_50: inp.thesis_quality_score >= 50,
    market_confirmation_40: inp.market_confirmation_score >= 40,
    has_invalidation: !!inp.has_invalidation,
    has_trigger: !!inp.has_trigger,
  };
  const g2 = Object.values(g2c).every(Boolean);
  Object.assign(checklist, g2c);

  // G3: CANDIDATE -> ACTION
  const evOk = inp.ev_quality === 'positive_ev' || inp.ev_quality === 'marginal';
  const g3c = {
    thesis_quality_65: inp.thesis_quality_score >= 65,
    market_confirmation_55: inp.market_confirmation_score >= 55,
    risk_execution_60: inp.risk_execution_score >= 60,
    ev_positive_or_marginal: evOk,
    has_max_loss: !!inp.has_max_loss,
    has_position_sizing: !!inp.has_position_sizing,
    no_scorecard_blockers: (inp.scorecard_blockers || []).length === 0,
  };
  const g3 = Object.values(g3c).every(Boolean);
  Object.assign(checklist, g3c);

  let recommended;
  if (g3) recommended = 'action';
  else if (g2) recommended = 'candidate';
  else if (g1) recommended = 'watch';
  else recommended = 'information';

  if (!g1) {
    if (inp.thesis_quality_score < 30) blockers.push('Thesis quality too low for WATCH (need ≥ 30)');
  } else if (!g2) {
    for (const [k, v] of Object.entries(g2c)) {
      if (!v) blockers.push(`WATCH→CANDIDATE gate failed: ${k.replace(/_/g, ' ')}`);
    }
  } else if (!g3) {
    for (const [k, v] of Object.entries(g3c)) {
      if (!v) blockers.push(`CANDIDATE→ACTION gate failed: ${k.replace(/_/g, ' ')}`);
    }
  }
  if (inp.scorecard_blockers) blockers.push(...inp.scorecard_blockers);

  return { current_level: 'information', recommended_level: recommended, can_promote: g3, checklist, blockers };
}

// --- Helpers ---
function round1(v) { return Math.round(v * 10) / 10; }
function round2(v) { return Math.round(v * 100) / 100; }
function round3(v) { return Math.round(v * 1000) / 1000; }
function formatNum(n) { return n.toLocaleString('en-US'); }
function formatPct(n) { return (n >= 0 ? '+' : '') + n.toFixed(2) + '%'; }

// ---------------------------------------------------------------------------
// Embedded Examples
// ---------------------------------------------------------------------------

const EXAMPLES = {
  etf_signal: {
    name: 'ETF Candidate Signal',
    type: 'signal',
    description: 'Semiconductor ETF breakout candidate with A/B evidence, trigger/invalidation, and risk controls.',
    data: {
      signal: {
        id: '2026-05-20-semiconductor-etf-001',
        title: 'Semiconductor ETF breakout watch',
        summary: 'Semiconductor sector showing strength with policy tailwinds and volume expansion. ETF 512480 approaching key resistance with institutional inflow confirmation.',
        source_task: 'ETF pre-market analysis',
        signal_type: 'ETF',
        instrument: { code: '512480', name: 'Semiconductor ETF', asset_type: 'ETF' },
        evidence: [
          { source: 'Shanghai Stock Exchange fund flow data', date: '2026-05-19', quote_or_data: 'Net inflow 120M CNY over 3 days', evidence_level: 'A' },
          { source: 'National IC Fund announcement', date: '2026-05-18', quote_or_data: 'Phase III fund allocation details released', evidence_level: 'A' },
          { source: 'Financial media sector analysis', date: '2026-05-19', quote_or_data: 'Semiconductor index outperformed CSI 300 by 2.3% this week', evidence_level: 'B' },
        ],
        direction: 'bullish',
        impact_horizon: '1-3 months',
        confidence: 75,
        data_quality: 'verified',
        action_level: 'candidate',
        suggested_action: 'Watch for volume confirmation above 1.2x 20-day average',
        trigger_condition: 'Price breaks above 1.05 with volume > 1.2x 20-day avg and holds for 2 consecutive days',
        invalidation_condition: 'Price falls below 0.98 or sector index breaks below 20-day MA',
        max_risk: '8% drawdown from entry to stop-loss',
        risk_note: 'Semiconductor is cyclical; global demand recovery timing uncertain. Single-sector concentration risk.',
      },
    },
  },
  stock_shift: {
    name: 'Stock Shift / Watch Signal',
    type: 'signal',
    description: 'Event-driven stock signal at INFORMATION/WATCH level with mixed evidence.',
    data: {
      signal: {
        id: '2026-05-19-ev-maker-002',
        title: 'EV maker capacity expansion rumor',
        summary: 'Unconfirmed reports of new gigafactory site selection. Single-source media report with no official confirmation.',
        source_task: 'News monitoring',
        signal_type: 'stock',
        instrument: { code: 'TSLA', name: 'Tesla Inc', asset_type: 'stock' },
        evidence: [
          { source: 'Tech blog report', date: '2026-05-19', quote_or_data: 'Sources say new factory site narrowed to 3 candidates', evidence_level: 'C' },
        ],
        direction: 'bullish',
        impact_horizon: '3-6 months',
        confidence: 35,
        data_quality: 'unverified',
        action_level: 'information',
        suggested_action: 'Monitor for official announcement or regulatory filings',
        trigger_condition: '',
        invalidation_condition: '',
        max_risk: '',
        risk_note: '',
      },
    },
  },
  professional: {
    name: 'Professional Full Analysis',
    type: 'signal + framework',
    description: 'Complete signal with framework scorecard inputs, scenario model, and position sizing.',
    data: {
      signal: {
        id: '2026-05-20-semiconductor-etf-001',
        title: 'Semiconductor ETF breakout watch',
        summary: 'Semiconductor sector showing strength with policy tailwinds and volume expansion. ETF 512480 approaching key resistance with institutional inflow confirmation. National IC Fund Phase III allocation provides structural catalyst.',
        source_task: 'ETF pre-market analysis',
        signal_type: 'ETF',
        instrument: { code: '512480', name: 'Semiconductor ETF', asset_type: 'ETF' },
        evidence: [
          { source: 'Shanghai Stock Exchange fund flow data', date: '2026-05-19', quote_or_data: 'Net inflow 120M CNY over 3 days', evidence_level: 'A' },
          { source: 'National IC Fund announcement', date: '2026-05-18', quote_or_data: 'Phase III fund allocation details released', evidence_level: 'A' },
          { source: 'Financial media sector analysis', date: '2026-05-19', quote_or_data: 'Semiconductor index outperformed CSI 300 by 2.3% this week', evidence_level: 'B' },
        ],
        direction: 'bullish',
        impact_horizon: '1-3 months',
        confidence: 75,
        data_quality: 'verified',
        action_level: 'candidate',
        suggested_action: 'Watch for volume confirmation above 1.2x 20-day average',
        trigger_condition: 'Price breaks above 1.05 with volume > 1.2x 20-day avg and holds for 2 consecutive days',
        invalidation_condition: 'Price falls below 0.98 or sector index breaks below 20-day MA',
        max_risk: '8% drawdown from entry to stop-loss',
        risk_note: 'Semiconductor is cyclical; global demand recovery timing uncertain. Single-sector concentration risk.',
      },
      framework: {
        thesis_quality: { evidence_strength: 8, source_diversity: 7, thesis_clarity: 7, catalyst_specificity: 6, time_horizon_fit: 7 },
        market_confirmation: { trend_alignment: 7, momentum: 6, volume_liquidity: 7, relative_strength: 7, regime_alignment: 6 },
        risk_execution: { invalidation_clarity: 8, max_loss_defined: 7, position_sizing_discipline: 6, liquidity_slippage_risk: 7, concentration_risk: 4, time_stop: 5 },
        scenario: { bull_probability: 0.30, bull_return_pct: 15, base_probability: 0.45, base_return_pct: 5, bear_probability: 0.25, bear_return_pct: -8 },
        position_sizing: { portfolio_value: 500000, max_risk_pct: 2, entry_price: 1.02, stop_distance_pct: 4, confidence: 75, target_return_pct: 15 },
      },
    },
  },
  macro_context: {
    name: 'Macro Context',
    type: 'macro',
    description: 'Macro environment context (no trade action fields). Demonstrates macro validation.',
    data: {
      macro_context: {
        date: '2026-05-20',
        source_task: 'Daily macro scan',
        risk_appetite: 'rising',
        market_regime: 'risk-on with rotation into growth',
        key_variables: [
          { name: '10Y Treasury Yield', change: '-3bp to 4.28%', confidence: 85, data_quality: 'verified', possible_affected_themes: ['duration', 'growth stocks'], source: 'Bloomberg' },
          { name: 'CNY/USD', change: 'Stable at 7.22', confidence: 70, data_quality: 'verified', possible_affected_themes: ['exporters', 'commodities'], source: 'PBOC' },
        ],
        notes_for_tasks: [
          { theme: 'Semiconductor', background: 'Policy tailwinds from National IC Fund Phase III', what_to_verify: 'Actual allocation amounts and timeline' },
        ],
        summary: 'Risk appetite rising. Growth rotation underway. Rates stable.',
      },
    },
  },
  invalid_action: {
    name: 'Invalid Action Signal',
    type: 'signal (invalid)',
    description: 'Intentionally invalid action-level signal: D-only evidence, low confidence, missing risk fields.',
    data: {
      signal: {
        id: '2026-05-18-bad-signal-001',
        title: 'Hot tip buy now',
        summary: 'Someone on social media says this stock will double.',
        source_task: 'Social media monitoring',
        signal_type: 'stock',
        instrument: { code: 'XYZ', name: 'XYZ Corp', asset_type: 'stock' },
        evidence: [
          { source: 'Twitter post', date: '2026-05-18', quote_or_data: 'This stock is going to the moon!!!', evidence_level: 'D' },
        ],
        direction: 'bullish',
        impact_horizon: '1 week',
        confidence: 40,
        data_quality: 'unverified',
        action_level: 'action',
        suggested_action: 'Buy immediately',
        trigger_condition: '',
        invalidation_condition: '',
        max_risk: '',
        risk_note: '',
      },
    },
  },
};

// ---------------------------------------------------------------------------
// Validation (mirrors validators.py)
// ---------------------------------------------------------------------------

function validateSignal(sig) {
  const issues = [];
  const required = ['id', 'title', 'summary', 'source_task', 'signal_type', 'impact_horizon', 'suggested_action'];
  for (const f of required) {
    if (!sig[f]) issues.push({ rule: `required_${f}`, message: `signal requires ${f}`, severity: 'error' });
  }
  if (!sig.instrument) {
    issues.push({ rule: 'required_instrument', message: 'signal requires instrument', severity: 'error' });
  } else {
    if (!sig.instrument.code) issues.push({ rule: 'required_instrument_code', message: 'instrument requires code', severity: 'error' });
    if (!sig.instrument.name) issues.push({ rule: 'required_instrument_name', message: 'instrument requires name', severity: 'error' });
  }
  if (!sig.evidence || sig.evidence.length === 0) {
    issues.push({ rule: 'required_evidence', message: 'signal requires at least one evidence item', severity: 'error' });
  }
  if (sig.confidence !== undefined && (sig.confidence < 0 || sig.confidence > 100)) {
    issues.push({ rule: 'confidence_range', message: `confidence must be 0-100, got ${sig.confidence}`, severity: 'error' });
  }
  if (sig.action_level === 'action') {
    if (sig.confidence < 70) issues.push({ rule: 'action_confidence', message: `action-level requires confidence >= 70, got ${sig.confidence}`, severity: 'error' });
    if (sig.evidence) {
      const hasAB = sig.evidence.some(e => e.evidence_level === 'A' || e.evidence_level === 'B');
      if (!hasAB) issues.push({ rule: 'action_evidence_ab', message: 'action-level requires at least one A or B evidence', severity: 'error' });
      if (sig.evidence[0] && sig.evidence[0].evidence_level === 'D') issues.push({ rule: 'action_no_d_primary', message: 'D evidence cannot be primary support for action', severity: 'error' });
      const allD = sig.evidence.every(e => e.evidence_level === 'D');
      if (allD) issues.push({ rule: 'd_only_evidence', message: 'D-only evidence cannot justify action signal', severity: 'error' });
    }
    if (!sig.trigger_condition) issues.push({ rule: 'action_trigger', message: 'action-level requires trigger_condition', severity: 'error' });
    if (!sig.invalidation_condition) issues.push({ rule: 'action_invalidation', message: 'action-level requires invalidation_condition', severity: 'error' });
    if (!sig.max_risk) issues.push({ rule: 'action_max_risk', message: 'action-level requires max_risk', severity: 'error' });
    if (!sig.risk_note) issues.push({ rule: 'action_risk_note', message: 'action-level requires risk_note', severity: 'error' });
    if (sig.data_quality === 'missing' || sig.data_quality === 'unverified') {
      issues.push({ rule: 'action_data_quality', message: `action-level requires data_quality not missing/unverified, got ${sig.data_quality}`, severity: 'error' });
    }
  }
  if (sig.action_level === 'candidate' || sig.action_level === 'action') {
    if (!sig.trigger_condition) issues.push({ rule: 'candidate_trigger', message: `${sig.action_level}-level requires trigger_condition`, severity: 'error' });
    if (!sig.invalidation_condition) issues.push({ rule: 'candidate_invalidation', message: `${sig.action_level}-level requires invalidation_condition`, severity: 'error' });
    if (sig.evidence) {
      const allD = sig.evidence.every(e => e.evidence_level === 'D');
      if (allD) issues.push({ rule: 'd_only_evidence', message: 'D-only evidence cannot justify candidate/action', severity: 'error' });
    }
  }
  return issues;
}

function validateMacro(ctx) {
  const issues = [];
  const forbidden = ['suggested_action', 'action_level', 'trigger_condition', 'max_risk'];
  for (const f of forbidden) {
    if (ctx[f]) issues.push({ rule: 'macro_action_field', message: `MacroContext must not contain trade action field '${f}'`, severity: 'error' });
  }
  return issues;
}

// ---------------------------------------------------------------------------
// Scoring (mirrors scoring.py)
// ---------------------------------------------------------------------------

function scoreSignal(sig) {
  // Confidence: 30 pts
  const confPts = Math.round((sig.confidence || 0) * 30 / 100);

  // Evidence: 30 pts
  let evPts = 5;
  if (sig.evidence && sig.evidence.length > 0) {
    const levels = new Set(sig.evidence.map(e => e.evidence_level));
    if (levels.has('A')) evPts = 25;
    else if (levels.has('B')) evPts = 20;
    else if (levels.has('C')) evPts = 10;
    else evPts = 0;
    const abCount = sig.evidence.filter(e => e.evidence_level === 'A' || e.evidence_level === 'B').length;
    if (abCount >= 2) evPts += 5;
    evPts = Math.min(30, evPts);
  }

  // Data quality: 20 pts
  const dqMap = { verified: 20, estimated: 14, mixed: 10, stale: 6, missing: 0, unverified: 0 };
  const dqPts = dqMap[sig.data_quality] || 0;

  // Risk completeness: 20 pts
  let riskPts = 0;
  if (sig.trigger_condition) riskPts += 5;
  if (sig.invalidation_condition) riskPts += 5;
  if (sig.max_risk) riskPts += 5;
  if (sig.risk_note) riskPts += 5;

  const total = Math.max(0, Math.min(100, confPts + evPts + dqPts + riskPts));
  return {
    score: total,
    grade: gradeFromScore(total),
    breakdown: { confidence: confPts, evidence_strength: evPts, data_quality: dqPts, risk_completeness: riskPts },
  };
}

// ---------------------------------------------------------------------------
// Render Markdown (mirrors render.py)
// ---------------------------------------------------------------------------

function renderSignalMarkdown(sig) {
  const lines = [];
  lines.push(`# Signal: ${sig.title || sig.id || '(untitled)'}`);
  lines.push('');
  if (sig.id) lines.push(`**ID:** ${sig.id}`);
  if (sig.source_task) lines.push(`**Source:** ${sig.source_task}`);
  if (sig.signal_type) lines.push(`**Type:** ${sig.signal_type}`);
  lines.push(`**Action Level:** ${sig.action_level || 'information'}`);
  lines.push(`**Confidence:** ${sig.confidence || 0}/100`);
  lines.push(`**Direction:** ${sig.direction || 'uncertain'}`);
  if (sig.impact_horizon) lines.push(`**Impact Horizon:** ${sig.impact_horizon}`);
  lines.push(`**Data Quality:** ${sig.data_quality || 'unverified'}`);
  if (sig.suggested_action) lines.push(`**Suggested Action:** ${sig.suggested_action}`);
  lines.push('');
  if (sig.summary) { lines.push('## Summary'); lines.push(sig.summary); lines.push(''); }
  if (sig.instrument) {
    lines.push('## Instrument');
    lines.push(`- **Code:** ${sig.instrument.code}`);
    if (sig.instrument.name) lines.push(`- **Name:** ${sig.instrument.name}`);
    lines.push(`- **Asset Type:** ${sig.instrument.asset_type || 'other'}`);
    lines.push('');
  }
  if (sig.evidence && sig.evidence.length) {
    lines.push('## Evidence');
    sig.evidence.forEach((e, i) => {
      lines.push(`### Evidence ${i + 1} [${e.evidence_level}]`);
      lines.push(`- **Source:** ${e.source}`);
      if (e.date) lines.push(`- **Date:** ${e.date}`);
      if (e.quote_or_data) lines.push(`- **Data:** ${e.quote_or_data}`);
      if (e.note) lines.push(`- **Note:** ${e.note}`);
      lines.push('');
    });
  }
  if (sig.trigger_condition || sig.invalidation_condition || sig.max_risk || sig.risk_note) {
    lines.push('## Risk & Conditions');
    if (sig.trigger_condition) lines.push(`- **Trigger:** ${sig.trigger_condition}`);
    if (sig.invalidation_condition) lines.push(`- **Invalidation:** ${sig.invalidation_condition}`);
    if (sig.max_risk) lines.push(`- **Max Risk:** ${sig.max_risk}`);
    if (sig.risk_note) lines.push(`- **Risk Note:** ${sig.risk_note}`);
    lines.push('');
  }
  lines.push('---');
  lines.push('*Generated by invest-signal-kit. Not investment advice.*');
  return lines.join('\n');
}

// ---------------------------------------------------------------------------
// Memo Generator
// ---------------------------------------------------------------------------

function generateMemo(sigData, tq, mc, re, ev, ps, targetRet) {
  const lines = [];
  const sig = sigData.signal || sigData;

  lines.push(`# Decision Memo: ${sig.title || '(untitled)'}`);
  lines.push('');
  if (sig.instrument) lines.push(`**Instrument:** ${sig.instrument.code} — ${sig.instrument.name}`);
  if (sig.direction) lines.push(`**Direction:** ${sig.direction}`);
  if (sig.impact_horizon) lines.push(`**Horizon:** ${sig.impact_horizon}`);
  lines.push('');

  if (sig.summary) { lines.push('## Thesis Summary'); lines.push(sig.summary); lines.push(''); }

  // Thesis Quality
  lines.push('## Thesis Quality');
  lines.push(`**Score: ${tq.total}/100 (${tq.grade})**`);
  lines.push('');
  lines.push('| Factor | Score | Weight |');
  lines.push('|--------|-------|--------|');
  for (const [k, v] of Object.entries(tq.factors)) {
    const w = tq.weights[k] || 0;
    lines.push(`| ${k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())} | ${v}/10 | ${(w * 100).toFixed(0)}% |`);
  }
  if (tq.blockers.length) { lines.push(''); lines.push('**Blockers:**'); tq.blockers.forEach(b => lines.push(`- ${b}`)); }
  lines.push('');

  // Market Confirmation
  lines.push('## Market / Price Confirmation');
  lines.push(`**Score: ${mc.total}/100 (${mc.grade})**`);
  lines.push('');
  lines.push('| Factor | Score | Weight |');
  lines.push('|--------|-------|--------|');
  for (const [k, v] of Object.entries(mc.factors)) {
    const w = mc.weights[k] || 0;
    lines.push(`| ${k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())} | ${v}/10 | ${(w * 100).toFixed(0)}% |`);
  }
  if (mc.blockers.length) { lines.push(''); lines.push('**Blockers:**'); mc.blockers.forEach(b => lines.push(`- ${b}`)); }
  lines.push('');

  // Risk / Execution
  lines.push('## Risk & Execution Discipline');
  lines.push(`**Score: ${re.total}/100 (${re.grade})**`);
  lines.push('');
  lines.push('| Factor | Score | Weight |');
  lines.push('|--------|-------|--------|');
  for (const [k, v] of Object.entries(re.factors)) {
    const w = re.weights[k] || 0;
    lines.push(`| ${k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())} | ${v}/10 | ${(w * 100).toFixed(0)}% |`);
  }
  if (re.blockers.length) { lines.push(''); lines.push('**Blockers:**'); re.blockers.forEach(b => lines.push(`- ${b}`)); }
  lines.push('');

  // Expected Value
  lines.push('## Expected Value / Scenario Analysis');
  lines.push(`**Expected Return: ${formatPct(ev.expected_return_pct)}** (${ev.quality.replace(/_/g, ' ')})`);
  lines.push(`**Max Drawdown: ${ev.max_drawdown_pct.toFixed(2)}%**`);
  lines.push(`**Payoff Asymmetry: ${ev.payoff_asymmetry.toFixed(2)}x**`);
  lines.push('');
  lines.push('| Scenario | Probability | Return |');
  lines.push('|----------|-------------|--------|');
  for (const [name, d] of Object.entries(ev.scenario_details)) {
    lines.push(`| ${name.charAt(0).toUpperCase() + name.slice(1)} | ${(d.probability * 100).toFixed(1)}% | ${d.return_pct >= 0 ? '+' : ''}${d.return_pct}% |`);
  }
  lines.push('');

  // Position Sizing
  lines.push('## Position Sizing');
  lines.push(`- **Risk Budget:** ${formatNum(ps.risk_amount)}`);
  lines.push(`- **Raw Shares:** ${formatNum(ps.raw_position_size)}`);
  lines.push(`- **Adjusted Shares:** ${formatNum(ps.adjusted_position_size)} (confidence factor: ${ps.confidence_factor.toFixed(2)})`);
  lines.push(`- **Position Value:** ${formatNum(ps.position_value)} (${ps.position_pct_of_portfolio.toFixed(1)}% of portfolio)`);
  if (ps.risk_reward_at_target > 0) lines.push(`- **Risk/Reward at Target:** ${ps.risk_reward_at_target.toFixed(2)}:1`);
  if (ps.notes.length) { lines.push(''); lines.push('**Notes:**'); ps.notes.forEach(n => lines.push(`- ${n}`)); }
  lines.push('');

  // Decision Readiness
  const allBlockers = [...tq.blockers, ...mc.blockers, ...re.blockers];
  const hasInv = re.factors.invalidation_clarity >= 3;
  const hasTrig = tq.factors.catalyst_specificity >= 3;
  const hasMaxLoss = re.factors.max_loss_defined >= 2;
  const hasSizing = ps.portfolio_value > 0;

  const dr = assessDecisionReadiness({
    thesis_quality_score: tq.total,
    market_confirmation_score: mc.total,
    risk_execution_score: re.total,
    ev_quality: ev.quality,
    has_invalidation: hasInv,
    has_trigger: hasTrig,
    has_max_loss: hasMaxLoss,
    has_position_sizing: hasSizing,
    scorecard_blockers: allBlockers,
  });

  lines.push('## Decision Readiness');
  lines.push(`**Recommended Level: ${dr.recommended_level.toUpperCase()}**`);
  if (dr.can_promote) lines.push('**Status: All gates passed — ready for action**');
  else lines.push(`**Status: ${dr.blockers.length} blocker(s) remaining**`);
  lines.push('');
  lines.push('### Checklist');
  for (const [k, v] of Object.entries(dr.checklist)) {
    lines.push(`- [${v ? 'x' : ' '}] ${k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}`);
  }
  if (dr.blockers.length) {
    lines.push('');
    lines.push('### Blockers');
    dr.blockers.forEach(b => lines.push(`- ${b}`));
  }
  lines.push('');
  lines.push('---');
  lines.push('*Generated by invest-signal-kit framework. Not investment advice.*');
  return lines.join('\n');
}

// ---------------------------------------------------------------------------
// JSON Syntax Highlighting
// ---------------------------------------------------------------------------

function highlightJSON(json) {
  if (typeof json !== 'string') json = JSON.stringify(json, null, 2);
  return json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"([^"]+)"(?=\s*:)/g, '<span class="json-key">"$1"</span>')
    .replace(/:\s*"([^"]*)"/g, ': <span class="json-string">"$1"</span>')
    .replace(/:\s*(-?\d+\.?\d*)/g, ': <span class="json-number">$1</span>')
    .replace(/:\s*(true|false|null)/g, ': <span class="json-bool">$1</span>');
}

// ---------------------------------------------------------------------------
// Rebalance / Trade Plan Engine (mirrors invest_signal_kit/rebalance.py)
// ---------------------------------------------------------------------------

function rebalanceRoundLots(shares, lotSize) {
  if (lotSize <= 0) return shares;
  return Math.floor(shares / lotSize) * lotSize;
}

function rebalanceEstimateCost(orderValue, costs) {
  const commission = Math.max(costs.commission_per_order || 0, costs.min_commission || 0);
  const slippage = orderValue * ((costs.slippage_bps || 0) / 10000);
  return { commission: round2(commission), slippage: round2(slippage), total: round2(commission + slippage) };
}

function rebalanceCheckCandidateGates(candidate, minScore) {
  const blockers = [];
  if ((candidate.signal_score || 0) < minScore)
    blockers.push(`Signal score ${(candidate.signal_score || 0).toFixed(0)} below minimum ${minScore.toFixed(0)}`);
  if (!['candidate', 'action'].includes(candidate.action_level || ''))
    blockers.push(`Action level '${candidate.action_level || ''}' not yet candidate/action`);
  if (candidate.ev_quality === 'negative_ev')
    blockers.push('Expected value is negative');
  if ((candidate.proposed_shares || 0) <= 0 && (candidate.proposed_value || 0) <= 0)
    blockers.push('No proposed position size');
  return blockers;
}

function rebalanceGenerateOrders(holdings, cash, policy, targets, candidates, costs) {
  if (!costs) costs = { commission_per_order: 0, slippage_bps: 5, min_commission: 0 };

  const posMap = {};
  for (const h of holdings) { if (h.code) posMap[h.code] = h; }

  const totalValue = holdings.reduce((s, h) => s + h.shares * h.current_price, 0) + cash;
  const posWeights = {};
  for (const h of holdings) { if (h.code) posWeights[h.code] = pct(h.shares * h.current_price, totalValue); }

  const targetMap = {};
  for (const t of targets) { if (t.code) targetMap[t.code] = t.target_pct; }

  const orders = [];
  const threshold = policy.rebalance_threshold_pct || 2;
  const minOrder = policy.min_order_value || 500;
  const lotSize = policy.lot_size || 1;
  const maxOrderPct = policy.max_single_order_pct || 10;
  const maxOrderVal = totalValue * (maxOrderPct / 100);

  // Phase 1: existing holdings
  for (const h of holdings) {
    if (!h.code) continue;
    const currentWt = posWeights[h.code] || 0;
    const targetWt = targetMap[h.code];
    const order = {
      action: 'HOLD', code: h.code, name: h.name, sector: h.sector, asset_type: h.asset_type,
      direction: h.direction, price: h.current_price, shares: 0, order_value: 0,
      estimated_commission: 0, estimated_slippage: 0, estimated_total_cost: 0,
      current_weight_pct: round2(currentWt), target_weight_pct: round2(currentWt),
      new_weight_pct: round2(currentWt), drift_pct: 0, rationale: '', blockers: [], warnings: [],
      phase: 'immediate', priority: 0,
    };

    if (targetWt === undefined) {
      order.rationale = 'No target allocation specified; maintaining position.';
      orders.push(order);
      continue;
    }

    const drift = currentWt - targetWt;
    order.target_weight_pct = round2(targetWt);
    order.drift_pct = round2(drift);

    if (Math.abs(drift) < threshold) {
      order.rationale = `Current weight ${currentWt.toFixed(1)}% is within ${threshold.toFixed(1)}% of target ${targetWt.toFixed(1)}%. Drift ${drift >= 0 ? '+' : ''}${drift.toFixed(2)}% is below threshold.`;
      orders.push(order);
      continue;
    }

    if (drift > 0) {
      // Overweight — trim or sell
      let excessValue = (drift / 100) * totalValue;
      let excessShares = h.current_price > 0 ? excessValue / h.current_price : 0;
      excessShares = rebalanceRoundLots(excessShares, lotSize);

      if (excessShares <= 0 || excessValue < minOrder) {
        order.action = 'SKIP';
        order.rationale = `Calculated trim of ${excessShares.toFixed(0)} shares ($${excessValue.toLocaleString()}) below minimum order $${minOrder.toLocaleString()}.`;
        order.phase = 'blocked';
        orders.push(order);
        continue;
      }

      if (excessShares >= h.shares) {
        order.action = 'SELL';
        order.shares = -h.shares;
        order.order_value = round2(h.shares * h.current_price);
        order.rationale = `Selling entire position. Current ${currentWt.toFixed(1)}% drifts +${drift.toFixed(1)}% from target ${targetWt.toFixed(1)}%.`;
      } else {
        order.action = 'TRIM';
        order.shares = -excessShares;
        order.order_value = round2(excessShares * h.current_price);
        order.rationale = `Trimming ${excessShares.toFixed(0)} shares to reduce weight from ${currentWt.toFixed(1)}% toward target ${targetWt.toFixed(1)}%.`;
      }

      const cost = rebalanceEstimateCost(order.order_value, costs);
      order.estimated_commission = cost.commission;
      order.estimated_slippage = cost.slippage;
      order.estimated_total_cost = cost.total;
      const newShares = h.shares + order.shares;
      order.new_weight_pct = round2(pct(newShares * h.current_price, totalValue));
      order.phase = 'immediate';
      order.priority = 1;
    } else {
      // Underweight — add
      let deficitValue = (-drift / 100) * totalValue;
      let deficitShares = h.current_price > 0 ? deficitValue / h.current_price : 0;
      deficitShares = rebalanceRoundLots(deficitShares, lotSize);

      if (deficitShares <= 0 || deficitValue < minOrder) {
        order.action = 'SKIP';
        order.rationale = `Calculated add of ${deficitShares.toFixed(0)} shares ($${deficitValue.toLocaleString()}) below minimum order $${minOrder.toLocaleString()}.`;
        order.phase = 'blocked';
        orders.push(order);
        continue;
      }

      if (deficitValue > maxOrderVal) {
        deficitShares = rebalanceRoundLots(maxOrderVal / h.current_price, lotSize);
        deficitValue = deficitShares * h.current_price;
        order.warnings.push(`Order capped at $${maxOrderVal.toLocaleString()} (${maxOrderPct}% of portfolio).`);
      }

      order.action = 'ADD';
      order.shares = deficitShares;
      order.order_value = round2(deficitValue);
      const cost = rebalanceEstimateCost(order.order_value, costs);
      order.estimated_commission = cost.commission;
      order.estimated_slippage = cost.slippage;
      order.estimated_total_cost = cost.total;
      const newShares = h.shares + deficitShares;
      order.new_weight_pct = round2(pct(newShares * h.current_price, totalValue));
      order.rationale = `Adding ${deficitShares.toFixed(0)} shares to increase weight from ${currentWt.toFixed(1)}% toward target ${targetWt.toFixed(1)}%.`;
      order.phase = 'immediate';
      order.priority = 2;
    }
    orders.push(order);
  }

  // Phase 2: candidate signals
  const minScore = policy.watchlist_min_score || 60;
  for (const c of (candidates || [])) {
    const order = {
      action: 'BUY', code: c.code, name: c.name, sector: c.sector, asset_type: c.asset_type,
      direction: c.direction || 'bullish', price: c.current_price, shares: 0, order_value: 0,
      estimated_commission: 0, estimated_slippage: 0, estimated_total_cost: 0,
      current_weight_pct: 0, target_weight_pct: 0, new_weight_pct: 0, drift_pct: 0,
      rationale: '', blockers: [], warnings: [], phase: 'immediate', priority: 0,
    };

    const gateBlockers = rebalanceCheckCandidateGates(c, minScore);
    if (gateBlockers.length) {
      order.action = 'SKIP';
      order.blockers = gateBlockers;
      order.rationale = `Candidate ${c.code} does not pass readiness gates: ${gateBlockers.join('; ')}`;
      order.phase = 'blocked';
      orders.push(order);
      continue;
    }

    let buyShares = (c.proposed_shares || 0) > 0
      ? rebalanceRoundLots(c.proposed_shares, lotSize)
      : (c.proposed_value || 0) > 0 && c.current_price > 0
        ? rebalanceRoundLots(c.proposed_value / c.current_price, lotSize)
        : 0;

    if (buyShares <= 0) {
      order.action = 'SKIP';
      order.rationale = 'No valid proposed position size.';
      order.phase = 'blocked';
      orders.push(order);
      continue;
    }

    let buyValue = buyShares * c.current_price;
    if (buyValue < minOrder) {
      order.action = 'SKIP';
      order.rationale = `Order value $${buyValue.toLocaleString()} below minimum $${minOrder.toLocaleString()}.`;
      order.phase = 'blocked';
      orders.push(order);
      continue;
    }

    if (buyValue > maxOrderVal) {
      buyShares = rebalanceRoundLots(maxOrderVal / c.current_price, lotSize);
      buyValue = buyShares * c.current_price;
      order.warnings.push(`Order capped at $${maxOrderVal.toLocaleString()} (${maxOrderPct}% of portfolio).`);
    }

    order.action = 'BUY';
    order.shares = buyShares;
    order.order_value = round2(buyValue);
    const cost = rebalanceEstimateCost(order.order_value, costs);
    order.estimated_commission = cost.commission;
    order.estimated_slippage = cost.slippage;
    order.estimated_total_cost = cost.total;
    order.new_weight_pct = round2(pct(buyValue, totalValue));
    order.target_weight_pct = targetMap[c.code] !== undefined ? round2(targetMap[c.code]) : order.new_weight_pct;
    order.rationale = `Candidate signal passes gates (score=${(c.signal_score || 0).toFixed(0)}, level=${c.action_level}, ev=${c.ev_quality}). Buying ${buyShares.toFixed(0)} shares at $${c.current_price.toFixed(2)}.`;

    if ((c.signal_score || 0) >= 70 && c.action_level === 'action') {
      order.phase = 'immediate';
      order.priority = 4;
    } else {
      order.phase = 'wait-for-trigger';
      order.priority = 5;
      order.warnings.push('Consider waiting for stronger signal confirmation.');
    }
    orders.push(order);
  }

  // Build result
  return rebalanceBuildResult(orders, holdings, cash, policy, totalValue, costs);
}

function rebalanceBuildResult(orders, holdings, cash, policy, totalValue, costs) {
  const result = {
    before_total_value: round2(totalValue), before_cash: round2(cash),
    before_invested: round2(totalValue - cash),
    before_positions: [], before_sectors: [],
    after_total_value: 0, after_cash: 0, after_invested: 0,
    after_positions: [], after_sectors: [],
    orders, buy_count: 0, sell_count: 0, trim_count: 0, add_count: 0, hold_count: 0, skip_count: 0,
    total_commission: 0, total_slippage: 0, total_cost: 0, turnover_value: 0, turnover_pct: 0,
    guardrails: [], guardrail_breaches: 0, execution_phases: [], blockers: [], warnings: [],
  };

  // Before positions
  const sectorVals = {};
  for (const h of holdings) {
    if (!h.code) continue;
    const mv = h.shares * h.current_price;
    result.before_positions.push({
      code: h.code, name: h.name, sector: h.sector, shares: h.shares,
      market_value: round2(mv), weight_pct: round2(pct(mv, totalValue)),
    });
    const s = h.sector || 'Unknown';
    sectorVals[s] = (sectorVals[s] || 0) + mv;
  }
  for (const [s, v] of Object.entries(sectorVals).sort()) {
    result.before_sectors.push({ sector: s, market_value: round2(v), weight_pct: round2(pct(v, totalValue)) });
  }

  // Count actions
  for (const o of orders) {
    if (o.action === 'BUY') result.buy_count++;
    else if (o.action === 'SELL') result.sell_count++;
    else if (o.action === 'TRIM') result.trim_count++;
    else if (o.action === 'ADD') result.add_count++;
    else if (o.action === 'HOLD') result.hold_count++;
    else if (o.action === 'SKIP') result.skip_count++;
  }

  // Costs
  for (const o of orders) {
    if (o.phase !== 'blocked' && o.action !== 'HOLD' && o.action !== 'SKIP') {
      result.total_commission += o.estimated_commission;
      result.total_slippage += o.estimated_slippage;
      result.total_cost += o.estimated_total_cost;
      result.turnover_value += o.order_value;
    }
  }
  result.total_commission = round2(result.total_commission);
  result.total_slippage = round2(result.total_slippage);
  result.total_cost = round2(result.total_cost);
  result.turnover_value = round2(result.turnover_value);
  result.turnover_pct = round2(pct(result.turnover_value, totalValue));

  // After state
  const afterPos = {};
  for (const h of holdings) {
    if (h.code) afterPos[h.code] = { code: h.code, name: h.name, sector: h.sector, shares: h.shares, price: h.current_price };
  }
  let afterCash = cash;
  for (const o of orders) {
    if (o.phase === 'blocked' || o.action === 'HOLD' || o.action === 'SKIP') continue;
    if (afterPos[o.code]) afterPos[o.code].shares += o.shares;
    if (o.action === 'BUY' || o.action === 'ADD') afterCash -= o.order_value + o.estimated_total_cost;
    else if (o.action === 'SELL' || o.action === 'TRIM') afterCash += o.order_value - o.estimated_total_cost;
  }

  const afterInvested = Object.values(afterPos).reduce((s, p) => s + p.shares * p.price, 0);
  const afterTotal = afterInvested + afterCash;
  result.after_total_value = round2(afterTotal);
  result.after_cash = round2(afterCash);
  result.after_invested = round2(afterInvested);

  const afterSectorVals = {};
  for (const p of Object.values(afterPos)) {
    const mv = p.shares * p.price;
    result.after_positions.push({
      code: p.code, name: p.name, sector: p.sector, shares: round2(p.shares),
      market_value: round2(mv), weight_pct: round2(pct(mv, afterTotal)),
    });
    const s = p.sector || 'Unknown';
    afterSectorVals[s] = (afterSectorVals[s] || 0) + mv;
  }
  for (const [s, v] of Object.entries(afterSectorVals).sort()) {
    result.after_sectors.push({ sector: s, market_value: round2(v), weight_pct: round2(pct(v, afterTotal)) });
  }

  // Guardrails
  const guardrails = [];
  for (const p of result.after_positions) {
    guardrails.push({
      rule: 'max_position', description: `Position ${p.code} weight after rebalance`,
      current_value: p.weight_pct, limit_value: policy.max_position_pct,
      passes: p.weight_pct <= policy.max_position_pct,
      severity: p.weight_pct <= policy.max_position_pct ? 'warning' : 'error',
    });
  }
  for (const s of result.after_sectors) {
    const limit = (policy.sector_limits && policy.sector_limits[s.sector]) || policy.max_sector_pct;
    guardrails.push({
      rule: 'max_sector', description: `Sector '${s.sector}' weight after rebalance`,
      current_value: s.weight_pct, limit_value: limit,
      passes: s.weight_pct <= limit,
      severity: s.weight_pct <= limit ? 'warning' : 'error',
    });
  }
  const cashPct = round2(pct(afterCash, afterTotal));
  guardrails.push({
    rule: 'min_cash_reserve', description: 'Cash reserve after rebalance',
    current_value: cashPct, limit_value: policy.min_cash_reserve_pct,
    passes: cashPct >= policy.min_cash_reserve_pct,
    severity: cashPct >= policy.min_cash_reserve_pct ? 'warning' : 'error',
  });
  guardrails.push({
    rule: 'max_turnover', description: 'Total turnover as % of portfolio',
    current_value: result.turnover_pct, limit_value: policy.max_turnover_pct,
    passes: result.turnover_pct <= policy.max_turnover_pct,
    severity: result.turnover_pct <= policy.max_turnover_pct ? 'warning' : 'error',
  });
  result.guardrails = guardrails;
  result.guardrail_breaches = guardrails.filter(g => !g.passes).length;

  // Execution phases
  const phaseDescs = {
    immediate: 'Orders that can execute now without constraint violations.',
    'wait-for-trigger': 'Orders pending a trigger condition (price, cash, or signal).',
    'reduce-risk-first': 'Orders that require reducing existing risk before execution.',
    blocked: 'Orders blocked by guardrail or readiness constraints.',
  };
  const phaseMap = {};
  for (const o of orders) { (phaseMap[o.phase] = phaseMap[o.phase] || []).push(o); }
  for (const pn of ['immediate', 'wait-for-trigger', 'reduce-risk-first', 'blocked']) {
    const po = phaseMap[pn];
    if (!po || !po.length) continue;
    po.sort((a, b) => a.priority - b.priority);
    result.execution_phases.push({
      phase: pn, description: phaseDescs[pn] || '',
      orders: po, total_value: round2(po.reduce((s, o) => s + o.order_value, 0)),
    });
  }

  // Aggregate blockers/warnings
  for (const o of orders) {
    for (const b of o.blockers) result.blockers.push(`${o.code}: ${b}`);
    for (const w of o.warnings) result.warnings.push(`${o.code}: ${w}`);
  }

  return result;
}

function rebalanceAnalyze(data) {
  const holdings = (data.holdings || []).map(h => ({
    code: h.code || '', name: h.name || '', asset_type: h.asset_type || 'stock',
    sector: h.sector || '', shares: +(h.shares || 0), entry_price: +(h.entry_price || 0),
    current_price: +(h.current_price || 0), stop_price: +(h.stop_price || 0), direction: h.direction || 'long',
  }));
  const cash = +(data.cash || 0);
  const p = data.policy || {};
  const policy = {
    max_position_pct: +(p.max_position_pct || 20), max_sector_pct: +(p.max_sector_pct || 35),
    max_risk_budget_pct: +(p.max_risk_budget_pct || 6), min_cash_reserve_pct: +(p.min_cash_reserve_pct || 5),
    max_turnover_pct: +(p.max_turnover_pct || 50), max_single_order_pct: +(p.max_single_order_pct || 10),
    min_order_value: +(p.min_order_value || 500), lot_size: +(p.lot_size || 1),
    rebalance_threshold_pct: +(p.rebalance_threshold_pct || 2), watchlist_min_score: +(p.watchlist_min_score || 60),
    sector_limits: p.sector_limits || {},
  };
  const targets = (data.targets || []).map(t => ({ code: t.code || '', sector: t.sector || '', target_pct: +(t.target_pct || 0) }));
  const candidates = (data.candidates || []).map(c => ({
    code: c.code || '', name: c.name || '', direction: c.direction || 'bullish',
    asset_type: c.asset_type || 'stock', sector: c.sector || '',
    current_price: +(c.current_price || 0), stop_price: +(c.stop_price || 0),
    signal_score: +(c.signal_score || 0), action_level: c.action_level || 'information',
    thesis_quality: +(c.thesis_quality || 0), market_confirmation: +(c.market_confirmation || 0),
    risk_execution: +(c.risk_execution || 0), ev_quality: c.ev_quality || 'negative_ev',
    proposed_shares: +(c.proposed_shares || 0), proposed_value: +(c.proposed_value || 0),
  }));
  const costs = data.costs ? {
    commission_per_order: +(data.costs.commission_per_order || 0),
    slippage_bps: +(data.costs.slippage_bps || 5),
    min_commission: +(data.costs.min_commission || 0),
  } : { commission_per_order: 0, slippage_bps: 5, min_commission: 0 };

  return rebalanceGenerateOrders(holdings, cash, policy, targets, candidates, costs);
}

// Rebalance Example Data
const REBALANCE_EXAMPLE = {
  holdings: [
    { code: 'NVDA', name: 'NVIDIA Corp', asset_type: 'stock', sector: 'Technology', shares: 150, entry_price: 450, current_price: 820, stop_price: 720, direction: 'long' },
    { code: 'AAPL', name: 'Apple Inc', asset_type: 'stock', sector: 'Technology', shares: 200, entry_price: 170, current_price: 195, stop_price: 175, direction: 'long' },
    { code: 'JPM', name: 'JPMorgan Chase', asset_type: 'stock', sector: 'Financials', shares: 100, entry_price: 180, current_price: 210, stop_price: 190, direction: 'long' },
    { code: 'UNH', name: 'UnitedHealth Group', asset_type: 'stock', sector: 'Healthcare', shares: 50, entry_price: 520, current_price: 540, stop_price: 490, direction: 'long' },
    { code: 'AMZN', name: 'Amazon.com', asset_type: 'stock', sector: 'Consumer', shares: 80, entry_price: 150, current_price: 185, stop_price: 160, direction: 'long' },
  ],
  cash: 75000,
  policy: {
    max_position_pct: 25, max_sector_pct: 40, max_risk_budget_pct: 8,
    min_cash_reserve_pct: 10, max_turnover_pct: 60, max_single_order_pct: 12,
    min_order_value: 1000, lot_size: 1, rebalance_threshold_pct: 3, watchlist_min_score: 60,
    sector_limits: { Technology: 35 },
  },
  targets: [
    { code: 'NVDA', target_pct: 18 }, { code: 'AAPL', target_pct: 15 },
    { code: 'JPM', target_pct: 12 }, { code: 'UNH', target_pct: 15 },
    { code: 'AMZN', target_pct: 12 },
  ],
  candidates: [
    { code: 'LLY', name: 'Eli Lilly & Co', direction: 'bullish', asset_type: 'stock', sector: 'Healthcare', current_price: 780, stop_price: 700, signal_score: 78, action_level: 'action', thesis_quality: 72, market_confirmation: 68, risk_execution: 65, ev_quality: 'positive_ev', proposed_shares: 20 },
    { code: 'COIN', name: 'Coinbase Global', direction: 'bullish', asset_type: 'stock', sector: 'Financials', current_price: 220, stop_price: 180, signal_score: 42, action_level: 'watch', thesis_quality: 35, market_confirmation: 40, risk_execution: 30, ev_quality: 'negative_ev', proposed_shares: 50 },
  ],
  costs: { commission_per_order: 1, slippage_bps: 5, min_commission: 1 },
};

function renderRebalanceUI(result) {
  const fmt = v => v.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  const fmtp = v => v.toFixed(1) + '%';

  // Before summary
  document.getElementById('rb-before-total').textContent = fmt(result.before_total_value);
  document.getElementById('rb-before-cash').textContent = fmt(result.before_cash) + ' (' + fmtp(pct(result.before_cash, result.before_total_value)) + ')';
  document.getElementById('rb-before-invested').textContent = fmt(result.before_invested) + ' (' + fmtp(pct(result.before_invested, result.before_total_value)) + ')';

  // After summary
  document.getElementById('rb-after-total').textContent = fmt(result.after_total_value);
  document.getElementById('rb-after-cash').textContent = fmt(result.after_cash) + ' (' + fmtp(pct(result.after_cash, result.after_total_value)) + ')';
  document.getElementById('rb-after-invested').textContent = fmt(result.after_invested) + ' (' + fmtp(pct(result.after_invested, result.after_total_value)) + ')';

  // Costs
  document.getElementById('rb-commission').textContent = fmt(result.total_commission);
  document.getElementById('rb-slippage').textContent = fmt(result.total_slippage);
  document.getElementById('rb-total-cost').textContent = fmt(result.total_cost);
  document.getElementById('rb-turnover').textContent = fmt(result.turnover_value) + ' (' + fmtp(result.turnover_pct) + ')';

  // Orders table
  const ordersTbody = document.getElementById('rebal-orders-tbody');
  const activeOrders = result.orders.filter(o => !['HOLD', 'SKIP'].includes(o.action));
  const holdOrders = result.orders.filter(o => o.action === 'HOLD');
  const skipOrders = result.orders.filter(o => o.action === 'SKIP');

  ordersTbody.innerHTML = activeOrders.map(o => {
    const actionCls = o.action === 'BUY' ? 'positive' : o.action === 'SELL' || o.action === 'TRIM' ? 'negative' : '';
    return `<tr>
      <td class="${actionCls}"><strong>${escHtml(o.action)}</strong></td>
      <td>${escHtml(o.code)}</td><td>${escHtml(o.name)}</td>
      <td>${o.shares >= 0 ? '+' : ''}${o.shares.toLocaleString()}</td>
      <td>${fmt(o.order_value)}</td><td>${fmt(o.estimated_total_cost)}</td>
      <td>${fmtp(o.current_weight_pct)}</td><td>${fmtp(o.target_weight_pct)}</td>
      <td>${escHtml(o.phase)}</td>
    </tr>`;
  }).join('');

  // Rationale
  const rationaleDiv = document.getElementById('rebal-rationale');
  let ratHtml = '';
  for (const o of activeOrders) {
    ratHtml += `<div class="note-item"><strong>${escHtml(o.action)} ${escHtml(o.code)}</strong> (${escHtml(o.name)}): ${escHtml(o.rationale)}`;
    for (const b of o.blockers) ratHtml += `<br><span class="blocker-item">BLOCKER: ${escHtml(b)}</span>`;
    for (const w of o.warnings) ratHtml += `<br><span style="color:var(--yellow)">WARNING: ${escHtml(w)}</span>`;
    ratHtml += '</div>';
  }
  if (holdOrders.length) {
    ratHtml += '<div class="note-item"><strong>Hold Positions:</strong><br>';
    for (const o of holdOrders) ratHtml += `${escHtml(o.code)} (${escHtml(o.name)}): ${escHtml(o.rationale)}<br>`;
    ratHtml += '</div>';
  }
  if (skipOrders.length) {
    ratHtml += '<div class="note-item"><strong>Skipped Orders:</strong><br>';
    for (const o of skipOrders) {
      ratHtml += `${escHtml(o.code)} (${escHtml(o.name)}): ${escHtml(o.rationale)}`;
      for (const b of o.blockers) ratHtml += `<br><span class="blocker-item">BLOCKER: ${escHtml(b)}</span>`;
      ratHtml += '<br>';
    }
    ratHtml += '</div>';
  }
  rationaleDiv.innerHTML = ratHtml;

  // Guardrails
  const guardTbody = document.getElementById('rebal-guardrails-tbody');
  guardTbody.innerHTML = result.guardrails.map(g => {
    const statusCls = g.passes ? 'positive' : 'negative';
    return `<tr>
      <td>${escHtml(g.rule)}</td><td>${escHtml(g.description)}</td>
      <td>${fmtp(g.current_value)}</td><td>${fmtp(g.limit_value)}</td>
      <td class="${statusCls}">${g.passes ? 'PASS' : 'BREACH'}</td>
    </tr>`;
  }).join('');

  // Execution plan
  const execDiv = document.getElementById('rebal-execution');
  execDiv.innerHTML = result.execution_phases.map(phase => {
    const phaseTitle = phase.phase.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    let html = `<h3>${escHtml(phaseTitle)}</h3><p class="section-desc">${escHtml(phase.description)}</p>`;
    if (phase.orders.length) {
      html += '<div class="table-container"><table class="data-table"><thead><tr><th>Action</th><th>Code</th><th>Shares</th><th>Value</th><th>Phase</th></tr></thead><tbody>';
      for (const o of phase.orders) {
        html += `<tr><td>${escHtml(o.action)}</td><td>${escHtml(o.code)}</td><td>${o.shares >= 0 ? '+' : ''}${o.shares.toLocaleString()}</td><td>${fmt(o.order_value)}</td><td>${escHtml(o.phase)}</td></tr>`;
      }
      html += `</tbody></table></div><p style="margin-top:8px;color:var(--text-secondary)">Phase Total: ${fmt(phase.total_value)}</p>`;
    }
    return html;
  }).join('');

  // Blockers & Warnings
  const blockersDiv = document.getElementById('rebal-blockers');
  const warningsDiv = document.getElementById('rebal-warnings');
  blockersDiv.innerHTML = result.blockers.length
    ? result.blockers.map(b => `<div class="blocker-item">${escHtml(b)}</div>`).join('')
    : '<div class="note-item" style="color:var(--green)">No blockers.</div>';
  warningsDiv.innerHTML = result.warnings.length
    ? result.warnings.map(w => `<div class="note-item">${escHtml(w)}</div>`).join('')
    : '';

  // Before/After positions
  const beforeTbody = document.getElementById('rebal-before-pos-tbody');
  beforeTbody.innerHTML = result.before_positions.map(p =>
    `<tr><td>${escHtml(p.code)}</td><td>${escHtml(p.name)}</td><td>${escHtml(p.sector)}</td><td>${p.shares.toLocaleString()}</td><td>${fmt(p.market_value)}</td><td>${fmtp(p.weight_pct)}</td></tr>`
  ).join('');

  const afterTbody = document.getElementById('rebal-after-pos-tbody');
  afterTbody.innerHTML = result.after_positions.map(p =>
    `<tr><td>${escHtml(p.code)}</td><td>${escHtml(p.name)}</td><td>${escHtml(p.sector)}</td><td>${p.shares.toLocaleString()}</td><td>${fmt(p.market_value)}</td><td>${fmtp(p.weight_pct)}</td></tr>`
  ).join('');
}

function runRebalanceAnalysis() {
  const editor = document.getElementById('rebal-editor');
  let data;
  try { data = JSON.parse(editor.value); } catch (e) { alert('Invalid JSON: ' + e.message); return; }
  const result = rebalanceAnalyze(data);
  renderRebalanceUI(result);
  window._lastRebalResult = result;
}

// ---------------------------------------------------------------------------
// UI Wiring
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
  // --- Tab Navigation ---
  const navBtns = document.querySelectorAll('.nav-btn');
  const panels = document.querySelectorAll('.tab-panel');

  navBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      navBtns.forEach(b => b.classList.remove('active'));
      panels.forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(btn.dataset.tab).classList.add('active');
    });
  });

  // --- Scorecard Sliders ---
  const sliderContainers = ['thesis-factors', 'market-factors', 'risk-factors'];
  sliderContainers.forEach(id => {
    const container = document.getElementById(id);
    if (!container) return;
    container.querySelectorAll('.factor-row').forEach(row => {
      const slider = row.querySelector('input[type="range"]');
      const valueSpan = row.querySelector('.factor-value');
      slider.addEventListener('input', () => {
        valueSpan.textContent = parseFloat(slider.value).toFixed(1);
        updateScorecards();
      });
    });
  });

  // --- Scenario & Sizing Inputs ---
  const evInputs = ['ev-bull-prob', 'ev-bull-ret', 'ev-base-prob', 'ev-base-ret', 'ev-bear-prob', 'ev-bear-ret'];
  const szInputs = ['sz-portfolio', 'sz-max-risk', 'sz-entry', 'sz-stop', 'sz-confidence', 'sz-target'];
  [...evInputs, ...szInputs].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', updateScenarioSizing);
  });

  // --- Signal Lab Buttons ---
  document.getElementById('btn-validate').addEventListener('click', () => runSignalAction('validate'));
  document.getElementById('btn-score').addEventListener('click', () => runSignalAction('score'));
  document.getElementById('btn-render').addEventListener('click', () => runSignalAction('render'));
  document.getElementById('btn-framework').addEventListener('click', () => runSignalAction('framework'));
  document.getElementById('btn-copy-output').addEventListener('click', copyOutput);
  document.getElementById('btn-clear-output').addEventListener('click', clearOutput);
  document.getElementById('btn-generate-memo').addEventListener('click', generateMemoFromScorecards);
  document.getElementById('btn-copy-memo').addEventListener('click', copyMemo);

  // --- Example Gallery ---
  populateExamples();

  // Initial calculations
  updateScorecards();
  updateScenarioSizing();
});

// ---------------------------------------------------------------------------
// Scorecard Updates
// ---------------------------------------------------------------------------

function getSliderValues(containerId) {
  const result = {};
  document.getElementById(containerId).querySelectorAll('.factor-row').forEach(row => {
    const factor = row.dataset.factor;
    const value = parseFloat(row.querySelector('input[type="range"]').value);
    result[factor] = value;
  });
  return result;
}

function updateScorecards() {
  // Thesis Quality
  const tqInp = getSliderValues('thesis-factors');
  const tq = scoreThesisQuality(tqInp);
  document.getElementById('thesis-score').textContent = tq.total.toFixed(1);
  setGrade('thesis-grade', tq.grade);
  renderBlockers('thesis-blockers', tq.blockers);

  // Market Confirmation
  const mcInp = getSliderValues('market-factors');
  const mc = scoreMarketConfirmation(mcInp);
  document.getElementById('market-score').textContent = mc.total.toFixed(1);
  setGrade('market-grade', mc.grade);
  renderBlockers('market-blockers', mc.blockers);

  // Risk / Execution
  const reInp = getSliderValues('risk-factors');
  const re = scoreRiskExecution(reInp);
  document.getElementById('risk-score').textContent = re.total.toFixed(1);
  setGrade('risk-grade', re.grade);
  renderBlockers('risk-blockers', re.blockers);

  // Decision Readiness
  const allBlockers = [...tq.blockers, ...mc.blockers, ...re.blockers];
  const hasInv = reInp.invalidation_clarity >= 3;
  const hasTrig = tqInp.catalyst_specificity >= 3;
  const hasMaxLoss = reInp.max_loss_defined >= 2;

  // For sizing: check if we have portfolio value in the sizing tab
  const portfolioVal = parseFloat(document.getElementById('sz-portfolio')?.value || 0);

  const dr = assessDecisionReadiness({
    thesis_quality_score: tq.total,
    market_confirmation_score: mc.total,
    risk_execution_score: re.total,
    ev_quality: getCurrentEvQuality(),
    has_invalidation: hasInv,
    has_trigger: hasTrig,
    has_max_loss: hasMaxLoss,
    has_position_sizing: portfolioVal > 0,
    scorecard_blockers: allBlockers,
  });

  updateDecisionLadder(dr);
  renderChecklist('decision-checklist', dr.checklist);
  renderBlockers('decision-blockers', dr.blockers);
}

function getCurrentEvQuality() {
  const ev = getEvInputs();
  const result = calculateExpectedValue(ev);
  return result.quality;
}

function setGrade(elemId, grade) {
  const el = document.getElementById(elemId);
  el.textContent = grade;
  el.className = 'score-grade grade-' + grade.toLowerCase();
}

function renderBlockers(containerId, blockers) {
  const el = document.getElementById(containerId);
  el.innerHTML = blockers.map(b => `<div class="blocker-item">${escHtml(b)}</div>`).join('');
}

function renderChecklist(containerId, checklist) {
  const el = document.getElementById(containerId);
  el.innerHTML = Object.entries(checklist).map(([k, v]) =>
    `<div class="check-item ${v ? 'passed' : 'failed'}"><span class="check-mark">${v ? '✓' : '✗'}</span> ${k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</div>`
  ).join('');
}

function updateDecisionLadder(dr) {
  const order = ['information', 'watch', 'candidate', 'action'];
  const recIdx = order.indexOf(dr.recommended_level);

  document.querySelectorAll('.ladder-step').forEach(step => {
    const level = step.dataset.level;
    const idx = order.indexOf(level);
    step.classList.remove('reached', 'current', 'blocked');
    if (idx < recIdx) step.classList.add('reached');
    else if (idx === recIdx) step.classList.add('current');
    // Mark the step after recommended as blocked if not promotable
  });
}

// ---------------------------------------------------------------------------
// Scenario & Sizing Updates
// ---------------------------------------------------------------------------

function getEvInputs() {
  return {
    bull_probability: parseFloat(document.getElementById('ev-bull-prob').value) || 0,
    bull_return_pct: parseFloat(document.getElementById('ev-bull-ret').value) || 0,
    base_probability: parseFloat(document.getElementById('ev-base-prob').value) || 0,
    base_return_pct: parseFloat(document.getElementById('ev-base-ret').value) || 0,
    bear_probability: parseFloat(document.getElementById('ev-bear-prob').value) || 0,
    bear_return_pct: parseFloat(document.getElementById('ev-bear-ret').value) || 0,
  };
}

function getSzInputs() {
  return {
    portfolio_value: parseFloat(document.getElementById('sz-portfolio').value) || 0,
    max_risk_pct: parseFloat(document.getElementById('sz-max-risk').value) || 2,
    entry_price: parseFloat(document.getElementById('sz-entry').value) || 0,
    stop_distance_pct: parseFloat(document.getElementById('sz-stop').value) || 5,
    confidence: parseFloat(document.getElementById('sz-confidence').value) || 50,
  };
}

function updateScenarioSizing() {
  // Expected Value
  const evInp = getEvInputs();
  const ev = calculateExpectedValue(evInp);

  document.getElementById('ev-expected').textContent = formatPct(ev.expected_return_pct);
  document.getElementById('ev-expected').className = 'metric-value ' + (ev.expected_return_pct > 0 ? 'positive' : ev.expected_return_pct < 0 ? 'negative' : '');
  document.getElementById('ev-drawdown').textContent = ev.max_drawdown_pct.toFixed(2) + '%';
  document.getElementById('ev-drawdown').className = 'metric-value negative';
  document.getElementById('ev-asymmetry').textContent = ev.payoff_asymmetry.toFixed(2) + 'x';
  const qualityMap = { positive_ev: 'Positive EV', marginal: 'Marginal', negative_ev: 'Negative EV' };
  const qualityEl = document.getElementById('ev-quality');
  qualityEl.textContent = qualityMap[ev.quality] || ev.quality;
  qualityEl.className = 'metric-value ' + (ev.quality === 'positive_ev' ? 'positive' : ev.quality === 'marginal' ? 'marginal' : 'negative');

  // Position Sizing
  const szInp = getSzInputs();
  const targetRet = parseFloat(document.getElementById('sz-target').value) || 0;
  const ps = calculatePositionSize(szInp, targetRet);

  document.getElementById('sz-risk-amount').textContent = formatNum(ps.risk_amount || 0);
  document.getElementById('sz-raw-shares').textContent = formatNum(ps.raw_position_size || 0);
  document.getElementById('sz-adj-shares').textContent = formatNum(ps.adjusted_position_size || 0);
  document.getElementById('sz-position-value').textContent = formatNum(ps.position_value || 0);
  document.getElementById('sz-position-pct').textContent = (ps.position_pct_of_portfolio || 0).toFixed(1) + '%';
  document.getElementById('sz-rr').textContent = (ps.risk_reward_at_target || 0).toFixed(2) + ':1';

  // Sizing notes
  const notesEl = document.getElementById('sizing-notes');
  notesEl.innerHTML = (ps.notes || []).map(n => `<div class="note-item">${escHtml(n)}</div>`).join('');
}

// ---------------------------------------------------------------------------
// Signal Lab Actions
// ---------------------------------------------------------------------------

function runSignalAction(action) {
  const editor = document.getElementById('signal-editor');
  const output = document.getElementById('signal-output');
  let data;

  try {
    data = JSON.parse(editor.value);
  } catch (e) {
    output.innerHTML = `<span class="output-invalid">Invalid JSON: ${escHtml(e.message)}</span>`;
    return;
  }

  const sigData = data.signal || data;
  const isMacro = !!data.macro_context || (!data.signal && (data.risk_appetite || data.key_variables));

  switch (action) {
    case 'validate': {
      const issues = isMacro ? validateMacro(data.macro_context || data) : validateSignal(sigData);
      if (issues.length === 0) {
        output.innerHTML = `<span class="output-valid">VALID — ${isMacro ? 'macro' : 'signal'} passed all validation rules.</span>`;
      } else {
        output.innerHTML = `<span class="output-invalid">INVALID — ${issues.length} issue(s) found:</span>\n\n` +
          issues.map(i => `  [${i.severity}] ${i.rule}: ${i.message}`).join('\n');
      }
      break;
    }
    case 'score': {
      if (isMacro) {
        output.innerHTML = '<span class="output-invalid">Error: scoring only supports signals, not macro context.</span>';
        return;
      }
      const result = scoreSignal(sigData);
      output.innerHTML = `<pre class="output-json">${highlightJSON(JSON.stringify(result, null, 2))}</pre>`;
      break;
    }
    case 'render': {
      const md = isMacro ? renderMacroMD(data.macro_context || data) : renderSignalMarkdown(sigData);
      output.textContent = md;
      break;
    }
    case 'framework': {
      if (isMacro) {
        output.innerHTML = '<span class="output-invalid">Error: framework analysis only supports signals.</span>';
        return;
      }
      const fw = data.framework || {};
      const tqRaw = fw.thesis_quality || {};
      const mcRaw = fw.market_confirmation || {};
      const reRaw = fw.risk_execution || {};
      const evRaw = fw.scenario || {};
      const psRaw = fw.position_sizing || {};

      const tq = scoreThesisQuality(tqRaw);
      const mc = scoreMarketConfirmation(mcRaw);
      const re = scoreRiskExecution(reRaw);
      const ev = calculateExpectedValue(evRaw);
      const ps = calculatePositionSize(psRaw, psRaw.target_return_pct || evRaw.bull_return_pct || 10);

      const allBlockers = [...tq.blockers, ...mc.blockers, ...re.blockers];
      const dr = assessDecisionReadiness({
        thesis_quality_score: tq.total,
        market_confirmation_score: mc.total,
        risk_execution_score: re.total,
        ev_quality: ev.quality,
        has_invalidation: reRaw.invalidation_clarity >= 3,
        has_trigger: tqRaw.catalyst_specificity >= 3,
        has_max_loss: reRaw.max_loss_defined >= 2,
        has_position_sizing: psRaw.portfolio_value > 0,
        scorecard_blockers: allBlockers,
      });

      const result = {
        thesis_quality: tq,
        market_confirmation: mc,
        risk_execution: re,
        expected_value: ev,
        position_sizing: ps,
        decision_readiness: dr,
      };
      output.innerHTML = `<pre class="output-json">${highlightJSON(JSON.stringify(result, null, 2))}</pre>`;
      break;
    }
  }
}

function renderMacroMD(ctx) {
  const lines = [];
  lines.push(`# Macro Context: ${ctx.date || '(no date)'}`);
  lines.push('');
  if (ctx.source_task) lines.push(`**Source:** ${ctx.source_task}`);
  if (ctx.risk_appetite) lines.push(`**Risk Appetite:** ${ctx.risk_appetite}`);
  if (ctx.market_regime) lines.push(`**Market Regime:** ${ctx.market_regime}`);
  lines.push('');
  if (ctx.summary) { lines.push('## Summary'); lines.push(ctx.summary); lines.push(''); }
  if (ctx.key_variables && ctx.key_variables.length) {
    lines.push('## Key Variables');
    ctx.key_variables.forEach(v => {
      lines.push(`### ${v.name}`);
      if (v.change) lines.push(`- **Change:** ${v.change}`);
      lines.push(`- **Confidence:** ${v.confidence}/100`);
      lines.push(`- **Data Quality:** ${v.data_quality}`);
      if (v.possible_affected_themes) lines.push(`- **Affected Themes:** ${v.possible_affected_themes.join(', ')}`);
      if (v.source) lines.push(`- **Source:** ${v.source}`);
      lines.push('');
    });
  }
  lines.push('---');
  lines.push('*Generated by invest-signal-kit. Not investment advice.*');
  return lines.join('\n');
}

// ---------------------------------------------------------------------------
// Memo Generation
// ---------------------------------------------------------------------------

function generateMemoFromScorecards() {
  const tqInp = getSliderValues('thesis-factors');
  const mcInp = getSliderValues('market-factors');
  const reInp = getSliderValues('risk-factors');
  const evInp = getEvInputs();
  const szInp = getSzInputs();
  const targetRet = parseFloat(document.getElementById('sz-target').value) || 0;

  const tq = scoreThesisQuality(tqInp);
  const mc = scoreMarketConfirmation(mcInp);
  const re = scoreRiskExecution(reInp);
  const ev = calculateExpectedValue(evInp);
  const ps = calculatePositionSize(szInp, targetRet);

  // Try to get signal info from editor
  let sigData = { signal: { title: '(manual entry)', summary: '' } };
  try {
    const editorVal = document.getElementById('signal-editor').value;
    if (editorVal.trim()) sigData = JSON.parse(editorVal);
  } catch (e) { /* use default */ }

  const memo = generateMemo(sigData, tq, mc, re, ev, ps, targetRet);
  document.getElementById('memo-output').textContent = memo;
}

// ---------------------------------------------------------------------------
// Example Gallery
// ---------------------------------------------------------------------------

function populateExamples() {
  const gallery = document.getElementById('example-gallery');
  gallery.innerHTML = '';

  for (const [key, ex] of Object.entries(EXAMPLES)) {
    const card = document.createElement('div');
    card.className = 'example-card';
    card.innerHTML = `
      <span class="example-type">${escHtml(ex.type)}</span>
      <h3>${escHtml(ex.name)}</h3>
      <p>${escHtml(ex.description)}</p>
    `;
    card.addEventListener('click', () => {
      // Portfolio examples load into Portfolio tab
      if (ex.type === 'portfolio') {
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
        document.querySelector('[data-tab="portfolio"]').classList.add('active');
        document.getElementById('portfolio').classList.add('active');
        document.getElementById('portfolio-editor').value = JSON.stringify(ex.data, null, 2);
        runPortfolioAnalysis();
        return;
      }

      // Journal examples load into Journal tab
      if (ex.type === 'journal') {
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
        document.querySelector('[data-tab="journal"]').classList.add('active');
        document.getElementById('journal').classList.add('active');
        document.getElementById('journal-editor').value = JSON.stringify(ex.data, null, 2);
        runJournalAnalysis();
        return;
      }

      // Rebalance examples load into Rebalance tab
      if (ex.type === 'rebalance') {
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
        document.querySelector('[data-tab="rebalance"]').classList.add('active');
        document.getElementById('rebalance').classList.add('active');
        document.getElementById('rebal-editor').value = JSON.stringify(ex.data, null, 2);
        runRebalanceAnalysis();
        return;
      }

      // Switch to Signal Lab
      document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      document.querySelector('[data-tab="signal-lab"]').classList.add('active');
      document.getElementById('signal-lab').classList.add('active');

      // Load data into editor
      document.getElementById('signal-editor').value = JSON.stringify(ex.data, null, 2);

      // If it has framework data, also load into scorecards
      const fw = ex.data.framework;
      if (fw) {
        loadFrameworkIntoUI(fw);
      }

      // Auto-validate
      runSignalAction('validate');
    });
    gallery.appendChild(card);
  }
}

function loadFrameworkIntoUI(fw) {
  // Load thesis quality sliders
  if (fw.thesis_quality) {
    loadSliders('thesis-factors', fw.thesis_quality);
  }
  if (fw.market_confirmation) {
    loadSliders('market-factors', fw.market_confirmation);
  }
  if (fw.risk_execution) {
    loadSliders('risk-factors', fw.risk_execution);
  }
  if (fw.scenario) {
    const s = fw.scenario;
    setVal('ev-bull-prob', s.bull_probability);
    setVal('ev-bull-ret', s.bull_return_pct);
    setVal('ev-base-prob', s.base_probability);
    setVal('ev-base-ret', s.base_return_pct);
    setVal('ev-bear-prob', s.bear_probability);
    setVal('ev-bear-ret', s.bear_return_pct);
  }
  if (fw.position_sizing) {
    const p = fw.position_sizing;
    setVal('sz-portfolio', p.portfolio_value);
    setVal('sz-max-risk', p.max_risk_pct);
    setVal('sz-entry', p.entry_price);
    setVal('sz-stop', p.stop_distance_pct);
    setVal('sz-confidence', p.confidence);
    setVal('sz-target', p.target_return_pct);
  }
  updateScorecards();
  updateScenarioSizing();
}

function loadSliders(containerId, values) {
  const container = document.getElementById(containerId);
  container.querySelectorAll('.factor-row').forEach(row => {
    const factor = row.dataset.factor;
    if (values[factor] !== undefined) {
      const slider = row.querySelector('input[type="range"]');
      const valueSpan = row.querySelector('.factor-value');
      slider.value = values[factor];
      valueSpan.textContent = parseFloat(values[factor]).toFixed(1);
    }
  });
}

function setVal(id, val) {
  const el = document.getElementById(id);
  if (el && val !== undefined) el.value = val;
}

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

function copyOutput() {
  const output = document.getElementById('signal-output');
  navigator.clipboard.writeText(output.textContent).catch(() => {});
}

function clearOutput() {
  const output = document.getElementById('signal-output');
  output.innerHTML = '<p class="placeholder-text">Load an example or paste JSON, then click an action button.</p>';
}

function copyMemo() {
  const memo = document.getElementById('memo-output');
  navigator.clipboard.writeText(memo.textContent).catch(() => {});
}

function escHtml(s) {
  if (typeof s !== 'string') return '';
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ---------------------------------------------------------------------------
// Portfolio Risk Engine (mirrors invest_signal_kit/portfolio.py)
// ---------------------------------------------------------------------------

function pct(value, total) { return total > 0 ? (value / total * 100) : 0; }

function portfolioCalculateExposures(holdings, cash) {
  const investedValue = holdings.reduce((s, h) => s + h.shares * h.current_price, 0);
  const totalValue = investedValue + cash;

  const positions = holdings.map(h => {
    const mv = h.shares * h.current_price;
    const cb = h.shares * h.entry_price;
    const pnl = h.direction === 'short'
      ? (h.entry_price - h.current_price) * h.shares
      : (h.current_price - h.entry_price) * h.shares;
    const pnlPct = cb > 0 ? (pnl / cb * 100) : 0;
    const riskPerShare = h.stop_price > 0 ? Math.abs(h.current_price - h.stop_price) : 0;
    const posRisk = h.shares * riskPerShare;
    return {
      code: h.code, name: h.name, sector: h.sector || 'Unknown', asset_type: h.asset_type,
      market_value: round2(mv), exposure_pct: round2(pct(mv, totalValue)),
      unrealized_pnl: round2(pnl), unrealized_pnl_pct: round2(pnlPct),
      position_risk: round2(posRisk), risk_pct: round2(pct(posRisk, totalValue)),
    };
  });

  // Sector aggregation
  const sectorMap = {};
  for (const h of holdings) {
    const s = h.sector || 'Unknown';
    if (!sectorMap[s]) sectorMap[s] = { value: 0, count: 0, codes: [] };
    sectorMap[s].value += h.shares * h.current_price;
    sectorMap[s].count++;
    sectorMap[s].codes.push(h.code);
  }
  const sectors = Object.entries(sectorMap).map(([s, info]) => ({
    sector: s, market_value: round2(info.value),
    exposure_pct: round2(pct(info.value, totalValue)),
    position_count: info.count, position_codes: info.codes,
  }));

  const totalRisk = holdings.reduce((s, h) => {
    const rps = h.stop_price > 0 ? Math.abs(h.current_price - h.stop_price) : 0;
    return s + h.shares * rps;
  }, 0);

  return {
    total_value: round2(totalValue), cash: round2(cash),
    invested_value: round2(investedValue), invested_pct: round2(pct(investedValue, totalValue)),
    positions, sectors,
    total_risk: round2(totalRisk), total_risk_pct: round2(pct(totalRisk, totalValue)),
  };
}

function portfolioCheckConcentration(holdings, policy, totalValue) {
  const violations = [];
  if (totalValue <= 0) return violations;

  for (const h of holdings) {
    const mv = h.shares * h.current_price;
    const posPct = pct(mv, totalValue);
    if (posPct > policy.max_position_pct) {
      violations.push({
        rule: 'position_concentration', severity: 'warning',
        message: `${h.code} is ${posPct.toFixed(1)}% of portfolio, limit ${policy.max_position_pct}%`,
        actual_pct: round2(posPct), limit_pct: policy.max_position_pct,
      });
    }
  }

  const sectorValues = {};
  for (const h of holdings) {
    const s = h.sector || 'Unknown';
    sectorValues[s] = (sectorValues[s] || 0) + h.shares * h.current_price;
  }
  for (const [sector, value] of Object.entries(sectorValues)) {
    const sp = pct(value, totalValue);
    const limit = (policy.sector_limits && policy.sector_limits[sector]) || policy.max_sector_pct;
    if (sp > limit) {
      violations.push({
        rule: 'sector_concentration', severity: 'warning',
        message: `Sector '${sector}' is ${sp.toFixed(1)}%, limit ${limit}%`,
        actual_pct: round2(sp), limit_pct: limit,
      });
    }
  }

  for (const h of holdings) {
    const rps = h.stop_price > 0 ? Math.abs(h.current_price - h.stop_price) : 0;
    const rp = pct(h.shares * rps, totalValue);
    if (rp > policy.max_candidate_risk_pct) {
      violations.push({
        rule: 'position_risk_limit', severity: 'error',
        message: `${h.code} risk is ${rp.toFixed(1)}%, limit ${policy.max_candidate_risk_pct}%`,
        actual_pct: round2(rp), limit_pct: policy.max_candidate_risk_pct,
      });
    }
  }
  return violations;
}

function portfolioCheckRiskBudget(holdings, totalValue, policy) {
  const budget = totalValue * (policy.max_risk_budget_pct / 100);
  const totalRisk = holdings.reduce((s, h) => {
    const rps = h.stop_price > 0 ? Math.abs(h.current_price - h.stop_price) : 0;
    return s + h.shares * rps;
  }, 0);
  const remaining = Math.max(0, budget - totalRisk);
  const utilization = pct(totalRisk, budget);
  const posRisks = {};
  for (const h of holdings) {
    const rps = h.stop_price > 0 ? Math.abs(h.current_price - h.stop_price) : 0;
    posRisks[h.code] = round2(h.shares * rps);
  }
  return {
    total_risk: round2(totalRisk), total_risk_pct: round2(pct(totalRisk, totalValue)),
    risk_budget: round2(budget), risk_budget_pct: policy.max_risk_budget_pct,
    remaining_budget: round2(remaining), remaining_budget_pct: round2(pct(remaining, totalValue)),
    utilization_pct: round2(utilization), over_budget: totalRisk > budget,
    position_risks: posRisks,
  };
}

function portfolioRankCandidates(candidates, holdings, policy, totalValue) {
  const sectorValues = {};
  for (const h of holdings) {
    const s = h.sector || 'Unknown';
    sectorValues[s] = (sectorValues[s] || 0) + h.shares * h.current_price;
  }

  return candidates.map((c, i) => {
    const blockers = [];
    const warnings = [];

    if (c.signal_score < policy.watchlist_min_score)
      blockers.push(`Score ${c.signal_score} below min ${policy.watchlist_min_score}`);
    if (c.ev_quality === 'negative_ev')
      blockers.push('Expected value is negative');
    if (c.position_size_pct > 0 && c.position_size_pct > policy.max_position_pct)
      blockers.push(`Size ${c.position_size_pct}% exceeds limit ${policy.max_position_pct}%`);
    if (c.sector) {
      const existing = sectorValues[c.sector] || 0;
      const added = totalValue * (c.position_size_pct / 100);
      const newPct = pct(existing + added, totalValue);
      const limit = (policy.sector_limits && policy.sector_limits[c.sector]) || policy.max_sector_pct;
      if (newPct > limit)
        blockers.push(`Sector '${c.sector}' would be ${newPct.toFixed(1)}%, limit ${limit}%`);
    }
    if (c.risk_pct > policy.max_candidate_risk_pct)
      blockers.push(`Risk ${c.risk_pct}% exceeds per-trade limit ${policy.max_candidate_risk_pct}%`);
    if (['information', 'watch'].includes(c.action_level) && c.signal_score >= policy.watchlist_min_score)
      warnings.push(`Signal at '${c.action_level}' level`);
    if (c.thesis_quality > 0 && c.thesis_quality < 50)
      warnings.push(`Low thesis quality (${c.thesis_quality})`);

    return {
      code: c.code, name: c.name, direction: c.direction, sector: c.sector,
      signal_score: c.signal_score, action_level: c.action_level,
      expected_return_pct: c.expected_return_pct, risk_pct: c.risk_pct,
      position_size_pct: c.position_size_pct, passes_watchlist: blockers.length === 0,
      blockers, warnings, rank: 0,
    };
  }).sort((a, b) => {
    if (a.passes_watchlist !== b.passes_watchlist) return a.passes_watchlist ? -1 : 1;
    if (a.signal_score !== b.signal_score) return b.signal_score - a.signal_score;
    return b.expected_return_pct - a.expected_return_pct;
  }).map((r, i) => { r.rank = i + 1; return r; });
}

function portfolioRunStressTest(holdings, cash, scenario, maxDrawdownPct) {
  const investedValue = holdings.reduce((s, h) => s + h.shares * h.current_price, 0);
  const totalValue = investedValue + cash;

  const positions = [];
  let totalShocked = 0;
  for (const h of holdings) {
    let shock = scenario.market_shock_pct || 0;
    if (h.sector && scenario.sector_shocks && scenario.sector_shocks[h.sector])
      shock += scenario.sector_shocks[h.sector];
    if (scenario.single_name_shocks && scenario.single_name_shocks[h.code])
      shock += scenario.single_name_shocks[h.code];

    let sv = h.shares * h.current_price * (1 + shock / 100);
    if (scenario.liquidity_haircut_pct > 0)
      sv *= (1 - scenario.liquidity_haircut_pct / 100);

    const loss = h.shares * h.current_price - sv;
    const lossPct = h.shares * h.current_price > 0 ? pct(loss, h.shares * h.current_price) : 0;
    positions.push({
      code: h.code, name: h.name, sector: h.sector || 'Unknown',
      original_value: round2(h.shares * h.current_price), shocked_value: round2(sv),
      loss: round2(loss), loss_pct: round2(lossPct), applied_shock_pct: round2(shock),
    });
    totalShocked += sv;
  }

  totalShocked += cash;
  const totalLoss = totalValue - totalShocked;
  const totalLossPct = pct(totalLoss, totalValue);

  return {
    scenario_name: scenario.name, description: scenario.description || '',
    original_portfolio_value: round2(totalValue), shocked_portfolio_value: round2(totalShocked),
    total_loss: round2(totalLoss), total_loss_pct: round2(totalLossPct), positions,
    breaches_drawdown_limit: totalLossPct > maxDrawdownPct,
  };
}

function portfolioEvaluate(data) {
  const holdings = (data.holdings || []).map(h => ({
    code: h.code || '', name: h.name || '', asset_type: h.asset_type || 'stock',
    sector: h.sector || '', shares: Number(h.shares) || 0,
    entry_price: Number(h.entry_price) || 0, current_price: Number(h.current_price) || 0,
    stop_price: Number(h.stop_price) || 0, direction: h.direction || 'long',
  }));
  const cash = Number(data.cash) || 0;
  const policy = {
    max_position_pct: Number(data.policy?.max_position_pct) || 20,
    max_sector_pct: Number(data.policy?.max_sector_pct) || 35,
    max_risk_budget_pct: Number(data.policy?.max_risk_budget_pct) || 6,
    max_drawdown_pct: Number(data.policy?.max_drawdown_pct) || 15,
    watchlist_min_score: Number(data.policy?.watchlist_min_score) || 60,
    max_candidate_risk_pct: Number(data.policy?.max_candidate_risk_pct) || 2,
    sector_limits: data.policy?.sector_limits || {},
  };
  const candidates = (data.candidates || []).map(c => ({
    code: c.code || '', name: c.name || '', direction: c.direction || 'bullish',
    asset_type: c.asset_type || 'stock', sector: c.sector || '',
    expected_return_pct: Number(c.expected_return_pct) || 0,
    risk_pct: Number(c.risk_pct) || 0, position_size_pct: Number(c.position_size_pct) || 0,
    signal_score: Number(c.signal_score) || 0, action_level: c.action_level || 'information',
    thesis_quality: Number(c.thesis_quality) || 0,
    market_confirmation: Number(c.market_confirmation) || 0,
    risk_execution: Number(c.risk_execution) || 0,
    ev_quality: c.ev_quality || 'negative_ev',
  }));
  const scenarios = (data.scenarios || []).map(s => ({
    name: s.name || '', description: s.description || '',
    market_shock_pct: Number(s.market_shock_pct) || 0,
    sector_shocks: s.sector_shocks || {},
    single_name_shocks: s.single_name_shocks || {},
    liquidity_haircut_pct: Number(s.liquidity_haircut_pct) || 0,
  }));

  const exposureReport = portfolioCalculateExposures(holdings, cash);
  const totalValue = exposureReport.total_value;
  const concentrationViolations = portfolioCheckConcentration(holdings, policy, totalValue);
  const riskBudget = portfolioCheckRiskBudget(holdings, totalValue, policy);
  const candidateRankings = candidates.length > 0
    ? portfolioRankCandidates(candidates, holdings, policy, totalValue) : [];
  const stressResults = scenarios.map(sc =>
    portfolioRunStressTest(holdings, cash, sc, policy.max_drawdown_pct));

  const blockers = [];
  const warnings = [];
  if (riskBudget.over_budget)
    blockers.push({ rule: 'risk_budget_exceeded', severity: 'error',
      message: `Risk budget exceeded: ${riskBudget.utilization_pct.toFixed(1)}% utilized` });
  for (const v of concentrationViolations) {
    if (v.severity === 'error') blockers.push(v);
    else warnings.push(v);
  }
  for (const sr of stressResults) {
    if (sr.breaches_drawdown_limit)
      blockers.push({ rule: 'stress_drawdown_breach', severity: 'error',
        message: `'${sr.scenario_name}' causes ${sr.total_loss_pct.toFixed(1)}% loss, exceeds limit` });
  }

  return { exposure_report: exposureReport, concentration_violations: concentrationViolations,
    risk_budget: riskBudget, candidate_rankings: candidateRankings,
    stress_results: stressResults, blockers, warnings };
}

// ---------------------------------------------------------------------------
// Decision Journal Engine (mirrors invest_signal_kit/journal.py)
// ---------------------------------------------------------------------------

const JOURNAL_VALID_STATUSES = new Set(['planned', 'active', 'exited', 'invalidated', 'reviewed']);

function journalLoadDecision(raw) {
  return {
    id: raw.id || '',
    instrument_code: raw.instrument_code || '',
    instrument_name: raw.instrument_name || '',
    direction: raw.direction || 'bullish',
    sector: raw.sector || '',
    status: raw.status || 'planned',
    decision_date: raw.decision_date || '',
    entry_date: raw.entry_date || '',
    exit_date: raw.exit_date || '',
    thesis_snapshot: raw.thesis_snapshot || '',
    thesis_quality_score: parseFloat(raw.thesis_quality_score) || 0,
    market_confirmation_score: parseFloat(raw.market_confirmation_score) || 0,
    risk_execution_score: parseFloat(raw.risk_execution_score) || 0,
    signal_score: parseFloat(raw.signal_score) || 0,
    ev_quality: raw.ev_quality || '',
    entry_price: parseFloat(raw.entry_price) || 0,
    exit_price: parseFloat(raw.exit_price) || 0,
    target_price: parseFloat(raw.target_price) || 0,
    stop_price: parseFloat(raw.stop_price) || 0,
    risk_budget_pct: parseFloat(raw.risk_budget_pct) || 0,
    position_size_pct: parseFloat(raw.position_size_pct) || 0,
    decision_level: raw.decision_level || 'information',
    tags: Array.isArray(raw.tags) ? raw.tags : [],
    review_date: raw.review_date || '',
    time_stop_date: raw.time_stop_date || '',
    exit_reason: raw.exit_reason || '',
    actual_return_pct: parseFloat(raw.actual_return_pct) || 0,
    r_multiple: parseFloat(raw.r_multiple) || 0,
    outcome_category: raw.outcome_category || '',
    process_score: parseFloat(raw.process_score) || 0,
    review_notes: raw.review_notes || '',
    market_move_pct: parseFloat(raw.market_move_pct) || 0,
    sector_move_pct: parseFloat(raw.sector_move_pct) || 0,
    idiosyncratic_move_pct: parseFloat(raw.idiosyncratic_move_pct) || 0,
    sizing_contribution_pct: parseFloat(raw.sizing_contribution_pct) || 0,
    attribution_notes: raw.attribution_notes || '',
  };
}

function journalLoadJournal(data) {
  const list = Array.isArray(data) ? data : (data.decisions || []);
  return list.map(journalLoadDecision);
}

function journalValidateLifecycle(decisions) {
  const today = new Date().toISOString().slice(0, 10);
  const alerts = [];

  for (const d of decisions) {
    if (!JOURNAL_VALID_STATUSES.has(d.status)) {
      alerts.push({ rule: 'invalid_status', message: `Decision ${d.id}: invalid status '${d.status}'`, severity: 'error', decision_id: d.id });
      continue;
    }

    if (d.status === 'active') {
      if (!d.exit_date && !d.time_stop_date)
        alerts.push({ rule: 'active_decision_missing_exit', message: `Decision ${d.id} (${d.instrument_code}): active with no exit or time-stop date`, severity: 'warning', decision_id: d.id });
      if (d.stop_price > 0 && d.entry_price > 0 && d.direction === 'bullish' && d.entry_price > d.stop_price && d.exit_price > 0 && d.exit_price < d.stop_price)
        alerts.push({ rule: 'stop_breached_not_exited', message: `Decision ${d.id} (${d.instrument_code}): exit price ${d.exit_price} is below stop ${d.stop_price}`, severity: 'error', decision_id: d.id });
      if (!d.thesis_snapshot)
        alerts.push({ rule: 'missing_thesis', message: `Decision ${d.id} (${d.instrument_code}): active decision has no thesis snapshot`, severity: 'warning', decision_id: d.id });
    }

    if (d.status === 'exited' || d.status === 'invalidated') {
      if (!d.outcome_category)
        alerts.push({ rule: 'missing_review', message: `Decision ${d.id} (${d.instrument_code}): ${d.status} but no outcome review`, severity: 'warning', decision_id: d.id });
      if (!d.thesis_snapshot)
        alerts.push({ rule: 'missing_thesis', message: `Decision ${d.id} (${d.instrument_code}): ${d.status} decision has no thesis snapshot`, severity: 'warning', decision_id: d.id });
    }

    if (d.status === 'invalidated' && !d.exit_date)
      alerts.push({ rule: 'thesis_invalidated_not_exited', message: `Decision ${d.id} (${d.instrument_code}): invalidated but no exit date recorded`, severity: 'warning', decision_id: d.id });

    if (d.review_date && d.review_date < today && d.status !== 'reviewed')
      alerts.push({ rule: 'expired_review', message: `Decision ${d.id} (${d.instrument_code}): review date ${d.review_date} has passed`, severity: 'warning', decision_id: d.id });

    if (d.risk_budget_pct > 5.0)
      alerts.push({ rule: 'oversized_risk', message: `Decision ${d.id} (${d.instrument_code}): risk budget ${d.risk_budget_pct.toFixed(1)}% exceeds 5% threshold`, severity: 'warning', decision_id: d.id });

    if (d.status === 'planned' && d.decision_date) {
      try {
        const dd = new Date(d.decision_date);
        const days = Math.floor((new Date(today) - dd) / 86400000);
        if (days > 90)
          alerts.push({ rule: 'stale_thesis', message: `Decision ${d.id} (${d.instrument_code}): planned for ${days} days — thesis may be stale`, severity: 'warning', decision_id: d.id });
      } catch (e) { /* ignore */ }
    }
  }
  return alerts;
}

const JOURNAL_BUCKET_EDGES = [[0, 30], [30, 50], [50, 65], [65, 80], [80, 101]];
const JOURNAL_BUCKET_LABELS = ['0-29 (F/D)', '30-49 (D/C)', '50-64 (C)', '65-79 (B)', '80-100 (A)'];

function journalEffectiveScore(d) {
  if (d.signal_score > 0) return d.signal_score;
  const scores = [d.thesis_quality_score, d.market_confirmation_score, d.risk_execution_score].filter(s => s > 0);
  return scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;
}

function journalCalibrateScores(decisions) {
  const reviewed = decisions.filter(d =>
    (d.status === 'reviewed' || d.status === 'exited') && d.outcome_category);

  const buckets = JOURNAL_BUCKET_EDGES.map(([lo, hi], i) => {
    const bucketDecisions = reviewed.filter(d => {
      const s = journalEffectiveScore(d);
      return s >= lo && s < hi;
    });
    if (bucketDecisions.length === 0) return { score_range: JOURNAL_BUCKET_LABELS[i], decision_count: 0, win_count: 0, loss_count: 0, win_rate: 0, avg_return_pct: 0, avg_r_multiple: 0, total_return_pct: 0, process_error_count: 0 };

    const n = bucketDecisions.length;
    const wins = bucketDecisions.filter(d => d.actual_return_pct > 0).length;
    const returns = bucketDecisions.map(d => d.actual_return_pct);
    const rMults = bucketDecisions.filter(d => d.r_multiple !== 0).map(d => d.r_multiple);

    return {
      score_range: JOURNAL_BUCKET_LABELS[i],
      decision_count: n,
      win_count: wins,
      loss_count: n - wins,
      win_rate: round1(wins / n * 100),
      avg_return_pct: round2(returns.reduce((a, b) => a + b, 0) / n),
      avg_r_multiple: rMults.length > 0 ? round2(rMults.reduce((a, b) => a + b, 0) / rMults.length) : 0,
      total_return_pct: round2(returns.reduce((a, b) => a + b, 0)),
      process_error_count: 0,
    };
  });

  const nR = reviewed.length;
  const allReturns = reviewed.map(d => d.actual_return_pct);
  const allR = reviewed.filter(d => d.r_multiple !== 0).map(d => d.r_multiple);
  const overallWins = reviewed.filter(d => d.actual_return_pct > 0).length;

  return {
    total_decisions: decisions.length,
    reviewed_decisions: nR,
    buckets,
    overall_win_rate: nR > 0 ? round1(overallWins / nR * 100) : 0,
    overall_avg_return: nR > 0 ? round2(allReturns.reduce((a, b) => a + b, 0) / nR) : 0,
    overall_avg_r_multiple: allR.length > 0 ? round2(allR.reduce((a, b) => a + b, 0) / allR.length) : 0,
  };
}

function journalComputeAttribution(decisions) {
  return decisions
    .filter(d => (d.status === 'reviewed' || d.status === 'exited') && d.outcome_category)
    .map(d => {
      const decomposed = d.market_move_pct + d.sector_move_pct + d.idiosyncratic_move_pct;
      const residual = round2(d.actual_return_pct - decomposed);
      const sizing = d.position_size_pct > 0 ? round2(d.actual_return_pct * (d.position_size_pct / 100)) : 0;
      return {
        decision_id: d.id,
        instrument_code: d.instrument_code,
        total_return_pct: round2(d.actual_return_pct),
        market_move_pct: round2(d.market_move_pct),
        sector_move_pct: round2(d.sector_move_pct),
        idiosyncratic_move_pct: round2(d.idiosyncratic_move_pct),
        sizing_contribution_pct: sizing,
        residual_pct: residual,
        notes: d.attribution_notes,
      };
    });
}

function journalAnalyze(data) {
  const decisions = journalLoadJournal(data);
  const alerts = journalValidateLifecycle(decisions);
  const calibration = journalCalibrateScores(decisions);
  const attribution = journalComputeAttribution(decisions);
  return { decisions, alerts, calibration, attribution };
}

// ---------------------------------------------------------------------------
// Portfolio UI
// ---------------------------------------------------------------------------

const PORTFOLIO_EXAMPLE = {
  holdings: [
    { code: '512480', name: 'Semiconductor ETF', asset_type: 'ETF', sector: 'Technology', shares: 50000, entry_price: 1.02, current_price: 1.08, stop_price: 0.96, direction: 'long' },
    { code: '300750', name: 'CATL', asset_type: 'stock', sector: 'New Energy', shares: 800, entry_price: 210, current_price: 225.5, stop_price: 195, direction: 'long' },
    { code: '600519', name: 'Kweichow Moutai', asset_type: 'stock', sector: 'Consumer', shares: 200, entry_price: 1680, current_price: 1620, stop_price: 1550, direction: 'long' },
    { code: '510300', name: 'CSI 300 ETF', asset_type: 'ETF', sector: 'Broad Market', shares: 30000, entry_price: 3.85, current_price: 3.92, stop_price: 3.70, direction: 'long' },
    { code: '601318', name: 'Ping An Insurance', asset_type: 'stock', sector: 'Financials', shares: 1500, entry_price: 45, current_price: 48.2, stop_price: 42, direction: 'long' },
  ],
  cash: 150000,
  policy: { max_position_pct: 25, max_sector_pct: 40, max_risk_budget_pct: 8, max_drawdown_pct: 15, watchlist_min_score: 55, max_candidate_risk_pct: 2, sector_limits: { Technology: 30 } },
  candidates: [
    { code: '688981', name: 'SMIC', direction: 'bullish', sector: 'Technology', expected_return_pct: 12, risk_pct: 5, position_size_pct: 8, signal_score: 72, action_level: 'candidate', thesis_quality: 68, market_confirmation: 55, risk_execution: 62, ev_quality: 'positive_ev' },
    { code: '002594', name: 'BYD', direction: 'bullish', sector: 'New Energy', expected_return_pct: 8, risk_pct: 4, position_size_pct: 6, signal_score: 65, action_level: 'candidate', thesis_quality: 60, market_confirmation: 50, risk_execution: 58, ev_quality: 'marginal' },
    { code: '600036', name: 'China Merchants Bank', direction: 'bullish', sector: 'Financials', expected_return_pct: 5, risk_pct: 3, position_size_pct: 5, signal_score: 58, action_level: 'watch', thesis_quality: 52, market_confirmation: 45, risk_execution: 48, ev_quality: 'marginal' },
    { code: '000001', name: 'PetroChina', direction: 'bearish', sector: 'Energy', expected_return_pct: -2, risk_pct: 3, position_size_pct: 4, signal_score: 42, action_level: 'information', thesis_quality: 38, market_confirmation: 30, risk_execution: 25, ev_quality: 'negative_ev' },
  ],
  scenarios: [
    { name: 'Market Crash (-15%)', description: 'Broad market selloff', market_shock_pct: -15 },
    { name: 'Tech Sector Shock', description: 'Tech selloff with spillover', market_shock_pct: -5, sector_shocks: { Technology: -20, 'New Energy': -10 } },
    { name: 'Single-Name Crash (Moutai)', description: 'Moutai regulatory crackdown', market_shock_pct: 0, single_name_shocks: { '600519': -25 } },
    { name: 'Liquidity Crisis', description: 'Market-wide liquidity dry-up', market_shock_pct: -8, liquidity_haircut_pct: 10 },
  ],
};

function renderPortfolioUI(result) {
  const er = result.exposure_report;
  const rb = result.risk_budget;

  // Summary
  document.getElementById('pf-total-value').textContent = formatNum(er.total_value);
  document.getElementById('pf-cash').textContent = formatNum(er.cash);
  document.getElementById('pf-invested').textContent = formatNum(er.invested_value);
  const riskEl = document.getElementById('pf-total-risk');
  riskEl.textContent = formatNum(er.total_risk) + ' (' + er.total_risk_pct.toFixed(1) + '%)';
  riskEl.className = 'metric-value ' + (er.total_risk_pct > 5 ? 'negative' : er.total_risk_pct > 3 ? 'marginal' : 'positive');

  // Risk budget
  document.getElementById('rb-budget').textContent = formatNum(rb.risk_budget);
  document.getElementById('rb-used').textContent = formatNum(rb.total_risk);
  document.getElementById('rb-remaining').textContent = formatNum(rb.remaining_budget);
  document.getElementById('rb-utilization').textContent = rb.utilization_pct.toFixed(1) + '%';
  const fill = document.getElementById('risk-budget-fill');
  fill.style.width = Math.min(100, rb.utilization_pct) + '%';
  fill.className = 'risk-budget-fill' + (rb.over_budget ? ' danger' : rb.utilization_pct > 75 ? ' warning' : '');
  document.getElementById('risk-budget-label').textContent = rb.utilization_pct.toFixed(1) + '%';

  // Positions table
  const ptb = document.getElementById('positions-tbody');
  ptb.innerHTML = er.positions.map(p => {
    const pnlCls = p.unrealized_pnl_pct >= 0 ? 'positive' : 'negative';
    const riskCls = p.risk_pct > 2 ? 'negative' : p.risk_pct > 1 ? 'warning-text' : '';
    return `<tr>
      <td>${escHtml(p.code)}</td><td>${escHtml(p.name)}</td><td>${escHtml(p.sector)}</td>
      <td>${formatNum(p.market_value)}</td><td>${p.exposure_pct.toFixed(1)}%</td>
      <td class="${pnlCls}">${p.unrealized_pnl_pct >= 0 ? '+' : ''}${p.unrealized_pnl_pct.toFixed(1)}%</td>
      <td class="${riskCls}">${p.risk_pct.toFixed(1)}%</td>
    </tr>`;
  }).join('');

  // Sectors table
  const stb = document.getElementById('sectors-tbody');
  stb.innerHTML = er.sectors.map(s => `<tr>
    <td>${escHtml(s.sector)}</td><td>${formatNum(s.market_value)}</td>
    <td>${s.exposure_pct.toFixed(1)}%</td><td>${s.position_count}</td>
    <td>${escHtml(s.position_codes.join(', '))}</td>
  </tr>`).join('');

  // Candidates table
  const ctb = document.getElementById('candidates-tbody');
  if (result.candidate_rankings.length === 0) {
    ctb.innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--text-muted)">No candidates</td></tr>';
  } else {
    ctb.innerHTML = result.candidate_rankings.map(c => {
      const passCls = c.passes_watchlist ? 'pass' : 'fail';
      const issues = [...c.blockers.map(b => 'BLOCK: ' + b), ...c.warnings.map(w => 'WARN: ' + w)];
      return `<tr>
        <td>${c.rank}</td><td>${escHtml(c.code)}</td><td>${c.signal_score}</td>
        <td>${escHtml(c.direction)}</td><td>${escHtml(c.sector)}</td>
        <td class="${c.expected_return_pct >= 0 ? 'positive' : 'negative'}">${c.expected_return_pct >= 0 ? '+' : ''}${c.expected_return_pct.toFixed(1)}%</td>
        <td class="${passCls}">${c.passes_watchlist ? 'PASS' : 'FAIL'}</td>
        <td style="font-size:11px;color:var(--text-secondary)">${escHtml(issues.join('; '))}</td>
      </tr>`;
    }).join('');
  }

  // Stress tests
  const stressDiv = document.getElementById('stress-results');
  if (result.stress_results.length === 0) {
    stressDiv.innerHTML = '<p class="placeholder-text">No stress scenarios defined.</p>';
  } else {
    stressDiv.innerHTML = result.stress_results.map(sr => {
      const breachCls = sr.breaches_drawdown_limit ? ' breach' : '';
      const lossColor = sr.total_loss_pct > 10 ? 'negative' : sr.total_loss_pct > 5 ? 'marginal' : '';
      const posRows = sr.positions.filter(p => p.applied_shock_pct !== 0).map(p =>
        `<tr><td>${escHtml(p.code)}</td><td>${escHtml(p.sector)}</td>
         <td>${p.applied_shock_pct >= 0 ? '+' : ''}${p.applied_shock_pct.toFixed(1)}%</td>
         <td class="negative">${formatNum(p.loss)}</td><td class="negative">${p.loss_pct.toFixed(1)}%</td></tr>`
      ).join('');
      return `<div class="stress-scenario${breachCls}">
        <h3>${escHtml(sr.scenario_name)}</h3>
        ${sr.description ? `<p class="stress-desc">${escHtml(sr.description)}</p>` : ''}
        <div class="stress-summary">
          <div class="stress-metric"><span class="metric-label">Original</span><span class="metric-value">${formatNum(sr.original_portfolio_value)}</span></div>
          <div class="stress-metric"><span class="metric-label">Stressed</span><span class="metric-value ${lossColor}">${formatNum(sr.shocked_portfolio_value)}</span></div>
          <div class="stress-metric"><span class="metric-label">Loss</span><span class="metric-value negative">${formatNum(sr.total_loss)} (${sr.total_loss_pct.toFixed(1)}%)</span></div>
        </div>
        ${posRows ? `<table class="data-table"><thead><tr><th>Code</th><th>Sector</th><th>Shock</th><th>Loss</th><th>Loss %</th></tr></thead><tbody>${posRows}</tbody></table>` : ''}
        ${sr.breaches_drawdown_limit ? '<p style="color:var(--red);font-weight:600;margin-top:8px">BREACHES DRAWDOWN LIMIT</p>' : ''}
      </div>`;
    }).join('');
  }

  // Blockers & Warnings
  const blkDiv = document.getElementById('portfolio-blockers');
  blkDiv.innerHTML = result.blockers.map(b =>
    `<div class="blocker-item">${escHtml(b.message)}</div>`).join('');

  const wrnDiv = document.getElementById('portfolio-warnings');
  wrnDiv.innerHTML = result.warnings.map(w =>
    `<div class="note-item">${escHtml(w.message)}</div>`).join('');

  // Show issues panel only if there are issues
  document.getElementById('portfolio-issues-panel').style.display =
    (result.blockers.length > 0 || result.warnings.length > 0) ? '' : 'none';
}

function runPortfolioAnalysis() {
  const editor = document.getElementById('portfolio-editor');
  let data;
  try {
    data = JSON.parse(editor.value);
  } catch (e) {
    alert('Invalid JSON: ' + e.message);
    return;
  }
  const result = portfolioEvaluate(data);
  renderPortfolioUI(result);
  window._lastPortfolioResult = result;
}

// Wire portfolio tab
document.addEventListener('DOMContentLoaded', () => {
  const btnLoad = document.getElementById('btn-portfolio-load');
  const btnAnalyze = document.getElementById('btn-portfolio-analyze');
  const btnCopy = document.getElementById('btn-portfolio-copy');

  if (btnLoad) {
    btnLoad.addEventListener('click', () => {
      document.getElementById('portfolio-editor').value = JSON.stringify(PORTFOLIO_EXAMPLE, null, 2);
      runPortfolioAnalysis();
    });
  }
  if (btnAnalyze) {
    btnAnalyze.addEventListener('click', runPortfolioAnalysis);
  }
  if (btnCopy) {
    btnCopy.addEventListener('click', () => {
      if (window._lastPortfolioResult)
        navigator.clipboard.writeText(JSON.stringify(window._lastPortfolioResult, null, 2)).catch(() => {});
    });
  }

  // Add portfolio example to EXAMPLES gallery
  if (typeof EXAMPLES !== 'undefined') {
    EXAMPLES.portfolio_workflow = {
      name: 'Portfolio Risk Workflow',
      type: 'portfolio',
      description: 'Multi-asset portfolio with 5 holdings, sector limits, risk budget, 4 candidate signals, and 4 stress scenarios.',
      data: PORTFOLIO_EXAMPLE,
    };
    populateExamples();
  }
});

// ---------------------------------------------------------------------------
// Journal UI
// ---------------------------------------------------------------------------

const JOURNAL_EXAMPLE = {
  decisions: [
    { id: 'DJ-2026-001', instrument_code: '510300', instrument_name: 'CSI 300 ETF', direction: 'bullish', sector: 'Index', status: 'reviewed', decision_date: '2026-01-15', entry_date: '2026-01-20', exit_date: '2026-03-10', thesis_snapshot: 'Policy-driven recovery with improving PMI and credit impulse turning positive.', thesis_quality_score: 72, market_confirmation_score: 65, risk_execution_score: 70, signal_score: 75, ev_quality: 'positive_ev', entry_price: 3.85, exit_price: 4.28, target_price: 4.30, stop_price: 3.60, risk_budget_pct: 2.0, position_size_pct: 8.0, decision_level: 'action', tags: ['macro', 'policy', 'etf'], review_date: '2026-04-01', time_stop_date: '2026-04-20', exit_reason: 'hit_target', actual_return_pct: 11.17, r_multiple: 1.72, outcome_category: 'hit_target', process_score: 9.0, review_notes: 'Clean execution. Target hit.', market_move_pct: 7.5, sector_move_pct: 3.2, idiosyncratic_move_pct: 0.47, sizing_contribution_pct: 0.89, attribution_notes: 'Bulk from broad market rally.' },
    { id: 'DJ-2026-002', instrument_code: '600519', instrument_name: 'Kweichow Moutai', direction: 'bullish', sector: 'Consumer', status: 'reviewed', decision_date: '2026-02-01', entry_date: '2026-02-05', exit_date: '2026-02-28', thesis_snapshot: 'Premium consumer demand resilient. Spring festival sales data strong.', thesis_quality_score: 68, market_confirmation_score: 55, risk_execution_score: 60, signal_score: 62, ev_quality: 'marginal', entry_price: 1680, exit_price: 1580, target_price: 1850, stop_price: 1590, risk_budget_pct: 1.5, position_size_pct: 5.0, decision_level: 'action', tags: ['consumer', 'single-stock'], review_date: '2026-03-15', time_stop_date: '2026-04-05', exit_reason: 'hit_stop', actual_return_pct: -5.95, r_multiple: -1.0, outcome_category: 'hit_stop', process_score: 7.0, review_notes: 'Stop hit on sector sell-off. Disciplined.', market_move_pct: -2.0, sector_move_pct: -3.5, idiosyncratic_move_pct: -0.45, sizing_contribution_pct: -0.30, attribution_notes: 'Sector rotation driver.' },
    { id: 'DJ-2026-003', instrument_code: 'NVDA', instrument_name: 'NVIDIA Corp', direction: 'bullish', sector: 'Technology', status: 'reviewed', decision_date: '2026-01-25', entry_date: '2026-01-28', exit_date: '2026-04-15', thesis_snapshot: 'AI capex cycle accelerating. Data center revenue visibility through 2027.', thesis_quality_score: 82, market_confirmation_score: 78, risk_execution_score: 75, signal_score: 80, ev_quality: 'positive_ev', entry_price: 142.50, exit_price: 168.00, target_price: 170.00, stop_price: 125.00, risk_budget_pct: 2.5, position_size_pct: 10.0, decision_level: 'action', tags: ['ai', 'tech', 'semiconductor'], review_date: '2026-03-01', time_stop_date: '2026-05-01', exit_reason: 'hit_target', actual_return_pct: 17.89, r_multiple: 1.49, outcome_category: 'hit_target', process_score: 8.0, review_notes: 'Strong thesis execution.', market_move_pct: 5.0, sector_move_pct: 8.0, idiosyncratic_move_pct: 4.89, sizing_contribution_pct: 1.79, attribution_notes: 'Idiosyncratic alpha from earnings beat.' },
    { id: 'DJ-2026-004', instrument_code: '518880', instrument_name: 'Gold ETF', direction: 'bullish', sector: 'Commodity', status: 'exited', decision_date: '2026-03-01', entry_date: '2026-03-05', exit_date: '2026-04-20', thesis_snapshot: 'Geopolitical risk premium underpricing. Central bank buying trend intact.', thesis_quality_score: 58, market_confirmation_score: 50, risk_execution_score: 45, signal_score: 52, ev_quality: 'marginal', entry_price: 5.80, exit_price: 5.95, target_price: 6.50, stop_price: 5.50, risk_budget_pct: 1.0, position_size_pct: 4.0, decision_level: 'candidate', tags: ['gold', 'hedge'], review_date: '2026-05-01', time_stop_date: '2026-06-01', exit_reason: 'time_stop', actual_return_pct: 2.59, r_multiple: 0.50, outcome_category: '', process_score: 0, review_notes: '', market_move_pct: 1.5, sector_move_pct: 1.0, idiosyncratic_move_pct: 0.09, sizing_contribution_pct: 0.10, attribution_notes: 'Modest return.' },
    { id: 'DJ-2026-005', instrument_code: 'BABA', instrument_name: 'Alibaba Group', direction: 'bullish', sector: 'Technology', status: 'invalidated', decision_date: '2026-02-10', entry_date: '2026-02-15', exit_date: '2026-03-20', thesis_snapshot: 'Regulatory overhang lifting. Cloud revenue re-accelerating.', thesis_quality_score: 55, market_confirmation_score: 42, risk_execution_score: 50, signal_score: 50, ev_quality: 'marginal', entry_price: 85.00, exit_price: 72.00, target_price: 105.00, stop_price: 75.00, risk_budget_pct: 2.0, position_size_pct: 6.0, decision_level: 'candidate', tags: ['china', 'tech', 'regulatory'], review_date: '2026-04-01', time_stop_date: '2026-05-15', exit_reason: 'thesis_broken', actual_return_pct: -15.29, r_multiple: -1.30, outcome_category: 'thesis_broken', process_score: 4.0, review_notes: 'Regulatory thesis invalidated. Held through stop.', market_move_pct: -3.0, sector_move_pct: -5.0, idiosyncratic_move_pct: -7.29, sizing_contribution_pct: -0.92, attribution_notes: 'Idiosyncratic risk dominated.' },
    { id: 'DJ-2026-006', instrument_code: '510050', instrument_name: 'SSE 50 ETF', direction: 'bullish', sector: 'Index', status: 'active', decision_date: '2026-04-15', entry_date: '2026-04-18', exit_date: '', thesis_snapshot: 'SOE reform catalyst accelerating. Valuation discount at 2-sigma.', thesis_quality_score: 70, market_confirmation_score: 62, risk_execution_score: 68, signal_score: 68, ev_quality: 'positive_ev', entry_price: 2.95, exit_price: 0, target_price: 3.35, stop_price: 2.75, risk_budget_pct: 2.0, position_size_pct: 7.0, decision_level: 'action', tags: ['soe', 'reform', 'dividend', 'etf'], review_date: '2026-06-15', time_stop_date: '2026-07-18', exit_reason: '', actual_return_pct: 0, r_multiple: 0, outcome_category: '', process_score: 0, review_notes: '', market_move_pct: 0, sector_move_pct: 0, idiosyncratic_move_pct: 0, sizing_contribution_pct: 0, attribution_notes: '' },
    { id: 'DJ-2026-007', instrument_code: 'TSLA', instrument_name: 'Tesla Inc', direction: 'bearish', sector: 'Automotive', status: 'active', decision_date: '2026-04-20', entry_date: '2026-04-22', exit_date: '', thesis_snapshot: 'Margin compression continuing. EV competition intensifying.', thesis_quality_score: 62, market_confirmation_score: 48, risk_execution_score: 55, signal_score: 55, ev_quality: 'marginal', entry_price: 245.00, exit_price: 0, target_price: 200.00, stop_price: 270.00, risk_budget_pct: 1.5, position_size_pct: 4.0, decision_level: 'candidate', tags: ['ev', 'short', 'automotive'], review_date: '2026-06-01', time_stop_date: '2026-07-20', exit_reason: '', actual_return_pct: 0, r_multiple: 0, outcome_category: '', process_score: 0, review_notes: '', market_move_pct: 0, sector_move_pct: 0, idiosyncratic_move_pct: 0, sizing_contribution_pct: 0, attribution_notes: '' },
    { id: 'DJ-2026-008', instrument_code: '000858', instrument_name: 'Wuliangye Yibin', direction: 'bullish', sector: 'Consumer', status: 'planned', decision_date: '2026-05-01', entry_date: '', exit_date: '', thesis_snapshot: 'Premium baijiu demand structural. Channel inventory destocked.', thesis_quality_score: 60, market_confirmation_score: 45, risk_execution_score: 40, signal_score: 0, ev_quality: 'marginal', entry_price: 145.00, exit_price: 0, target_price: 170.00, stop_price: 130.00, risk_budget_pct: 6.5, position_size_pct: 0, decision_level: 'watch', tags: ['consumer', 'baijiu'], review_date: '2026-06-01', time_stop_date: '', exit_reason: '', actual_return_pct: 0, r_multiple: 0, outcome_category: '', process_score: 0, review_notes: '', market_move_pct: 0, sector_move_pct: 0, idiosyncratic_move_pct: 0, sizing_contribution_pct: 0, attribution_notes: '' },
    { id: 'DJ-2026-009', instrument_code: 'AMZN', instrument_name: 'Amazon.com Inc', direction: 'bullish', sector: 'Technology', status: 'reviewed', decision_date: '2026-01-10', entry_date: '2026-01-12', exit_date: '2026-03-25', thesis_snapshot: 'AWS re-acceleration on AI workload migration. Retail margin expansion.', thesis_quality_score: 78, market_confirmation_score: 72, risk_execution_score: 72, signal_score: 78, ev_quality: 'positive_ev', entry_price: 195.00, exit_price: 210.00, target_price: 220.00, stop_price: 178.00, risk_budget_pct: 2.0, position_size_pct: 8.0, decision_level: 'action', tags: ['cloud', 'ai', 'retail'], review_date: '2026-04-10', time_stop_date: '2026-05-12', exit_reason: 'time_stop', actual_return_pct: 7.69, r_multiple: 0.88, outcome_category: 'time_stop', process_score: 6.0, review_notes: 'Time stop triggered before thesis fully played out.', market_move_pct: 4.0, sector_move_pct: 2.5, idiosyncratic_move_pct: 1.19, sizing_contribution_pct: 0.62, attribution_notes: 'Positive return but R below 1.0 due to early exit.' },
    { id: 'DJ-2026-010', instrument_code: '002475', instrument_name: 'Luxshare Precision', direction: 'bullish', sector: 'Technology', status: 'exited', decision_date: '2026-03-10', entry_date: '2026-03-12', exit_date: '2026-04-30', thesis_snapshot: 'Apple supply chain share gains accelerating. New product categories.', thesis_quality_score: 65, market_confirmation_score: 58, risk_execution_score: 55, signal_score: 60, ev_quality: 'marginal', entry_price: 38.50, exit_price: 35.20, target_price: 45.00, stop_price: 35.00, risk_budget_pct: 2.0, position_size_pct: 5.0, decision_level: 'action', tags: ['apple-supply-chain', 'manufacturing'], review_date: '2026-05-15', time_stop_date: '2026-06-12', exit_reason: 'opportunity_cost', actual_return_pct: -8.57, r_multiple: -0.94, outcome_category: '', process_score: 0, review_notes: '', market_move_pct: -2.0, sector_move_pct: -3.0, idiosyncratic_move_pct: -3.57, sizing_contribution_pct: -0.43, attribution_notes: 'Rotated to better opportunity.' },
  ],
};

function renderJournalUI(result) {
  const { decisions, alerts, calibration, attribution } = result;

  // Summary counts
  const counts = { planned: 0, active: 0, exited: 0, invalidated: 0, reviewed: 0 };
  decisions.forEach(d => { if (counts.hasOwnProperty(d.status)) counts[d.status]++; });
  document.getElementById('jrn-total').textContent = decisions.length;
  document.getElementById('jrn-active').textContent = counts.active;
  document.getElementById('jrn-exited').textContent = counts.exited;
  document.getElementById('jrn-reviewed').textContent = counts.reviewed;
  document.getElementById('jrn-invalidated').textContent = counts.invalidated;
  document.getElementById('jrn-planned').textContent = counts.planned;

  // Calibration summary
  document.getElementById('jrn-win-rate').textContent = calibration.overall_win_rate.toFixed(1) + '%';
  const avgRetEl = document.getElementById('jrn-avg-return');
  avgRetEl.textContent = (calibration.overall_avg_return >= 0 ? '+' : '') + calibration.overall_avg_return.toFixed(2) + '%';
  avgRetEl.className = 'metric-value ' + (calibration.overall_avg_return > 0 ? 'positive' : calibration.overall_avg_return < 0 ? 'negative' : '');
  document.getElementById('jrn-avg-r').textContent = calibration.overall_avg_r_multiple.toFixed(2);

  // Calibration table
  const calTbody = document.getElementById('calibration-tbody');
  calTbody.innerHTML = calibration.buckets.map(b => {
    if (b.decision_count === 0) return `<tr><td>${escHtml(b.score_range)}</td><td>0</td><td>-</td><td>-</td><td>-</td><td>-</td></tr>`;
    const rStr = b.avg_r_multiple !== 0 ? b.avg_r_multiple.toFixed(2) : '-';
    return `<tr>
      <td>${escHtml(b.score_range)}</td><td>${b.decision_count}</td>
      <td>${b.win_rate.toFixed(1)}%</td>
      <td class="${b.avg_return_pct > 0 ? 'positive' : b.avg_return_pct < 0 ? 'negative' : ''}">${b.avg_return_pct >= 0 ? '+' : ''}${b.avg_return_pct.toFixed(2)}%</td>
      <td>${rStr}</td><td>${b.process_error_count}</td>
    </tr>`;
  }).join('');

  // Alerts
  const alertsDiv = document.getElementById('journal-alerts');
  if (alerts.length === 0) {
    alertsDiv.innerHTML = '<div class="note-item" style="color:var(--green)">No lifecycle alerts — all decisions are clean.</div>';
  } else {
    alertsDiv.innerHTML = alerts.map(a => {
      const cls = a.severity === 'error' ? 'blocker-item' : 'note-item';
      return `<div class="${cls}">[${a.severity.toUpperCase()}] ${escHtml(a.message)}</div>`;
    }).join('');
  }

  // Decisions table
  const decTbody = document.getElementById('decisions-tbody');
  decTbody.innerHTML = decisions.map(d => {
    const retStr = d.actual_return_pct !== 0 ? (d.actual_return_pct >= 0 ? '+' : '') + d.actual_return_pct.toFixed(2) + '%' : '-';
    const rStr = d.r_multiple !== 0 ? d.r_multiple.toFixed(2) : '-';
    const scoreStr = d.signal_score > 0 ? d.signal_score.toFixed(0) : '-';
    const retCls = d.actual_return_pct > 0 ? 'positive' : d.actual_return_pct < 0 ? 'negative' : '';
    const statusCls = d.status === 'active' ? 'status-active' : d.status === 'reviewed' ? 'status-reviewed' : d.status === 'invalidated' ? 'status-invalidated' : '';
    return `<tr>
      <td>${escHtml(d.id)}</td><td>${escHtml(d.instrument_code)}</td>
      <td class="${statusCls}">${escHtml(d.status)}</td><td>${escHtml(d.direction)}</td>
      <td>${d.entry_price > 0 ? d.entry_price.toFixed(2) : '-'}</td>
      <td>${d.exit_price > 0 ? d.exit_price.toFixed(2) : '-'}</td>
      <td class="${retCls}">${retStr}</td><td>${rStr}</td><td>${scoreStr}</td>
      <td style="font-size:11px;color:var(--text-secondary)">${escHtml(d.tags.join(', '))}</td>
    </tr>`;
  }).join('');

  // Attribution table
  const attrPanel = document.getElementById('journal-attribution-panel');
  if (attribution.length === 0) {
    attrPanel.style.display = 'none';
  } else {
    attrPanel.style.display = '';
    const attrTbody = document.getElementById('attribution-tbody');
    attrTbody.innerHTML = attribution.map(a => {
      const fmt = v => (v >= 0 ? '+' : '') + v.toFixed(2) + '%';
      const cls = v => v > 0 ? 'positive' : v < 0 ? 'negative' : '';
      return `<tr>
        <td>${escHtml(a.decision_id)}</td><td>${escHtml(a.instrument_code)}</td>
        <td class="${cls(a.total_return_pct)}">${fmt(a.total_return_pct)}</td>
        <td class="${cls(a.market_move_pct)}">${fmt(a.market_move_pct)}</td>
        <td class="${cls(a.sector_move_pct)}">${fmt(a.sector_move_pct)}</td>
        <td class="${cls(a.idiosyncratic_move_pct)}">${fmt(a.idiosyncratic_move_pct)}</td>
        <td class="${cls(a.sizing_contribution_pct)}">${fmt(a.sizing_contribution_pct)}</td>
        <td class="${cls(a.residual_pct)}">${fmt(a.residual_pct)}</td>
      </tr>`;
    }).join('');
  }
}

function runJournalAnalysis() {
  const editor = document.getElementById('journal-editor');
  let data;
  try {
    data = JSON.parse(editor.value);
  } catch (e) {
    alert('Invalid JSON: ' + e.message);
    return;
  }
  const result = journalAnalyze(data);
  renderJournalUI(result);
  window._lastJournalResult = result;
}

// Wire journal tab
document.addEventListener('DOMContentLoaded', () => {
  const btnLoad = document.getElementById('btn-journal-load');
  const btnAnalyze = document.getElementById('btn-journal-analyze');
  const btnCopy = document.getElementById('btn-journal-copy');

  if (btnLoad) {
    btnLoad.addEventListener('click', () => {
      document.getElementById('journal-editor').value = JSON.stringify(JOURNAL_EXAMPLE, null, 2);
      runJournalAnalysis();
    });
  }
  if (btnAnalyze) {
    btnAnalyze.addEventListener('click', runJournalAnalysis);
  }
  if (btnCopy) {
    btnCopy.addEventListener('click', () => {
      if (window._lastJournalResult)
        navigator.clipboard.writeText(JSON.stringify(window._lastJournalResult, null, 2)).catch(() => {});
    });
  }

  // Add journal example to EXAMPLES gallery
  if (typeof EXAMPLES !== 'undefined') {
    EXAMPLES.decision_journal = {
      name: 'Decision Journal',
      type: 'journal',
      description: 'Multi-decision journal with 10 decisions across active/exited/invalidated/reviewed/planned states. Demonstrates calibration buckets and attribution.',
      data: JOURNAL_EXAMPLE,
    };
    populateExamples();
  }

  // Wire rebalance tab
  const btnRebalLoad = document.getElementById('btn-rebal-load');
  const btnRebalAnalyze = document.getElementById('btn-rebal-analyze');
  const btnRebalCopy = document.getElementById('btn-rebal-copy');

  if (btnRebalLoad) {
    btnRebalLoad.addEventListener('click', () => {
      document.getElementById('rebal-editor').value = JSON.stringify(REBALANCE_EXAMPLE, null, 2);
      runRebalanceAnalysis();
    });
  }
  if (btnRebalAnalyze) {
    btnRebalAnalyze.addEventListener('click', runRebalanceAnalysis);
  }
  if (btnRebalCopy) {
    btnRebalCopy.addEventListener('click', () => {
      if (window._lastRebalResult)
        navigator.clipboard.writeText(JSON.stringify(window._lastRebalResult, null, 2)).catch(() => {});
    });
  }

  // Add rebalance example to EXAMPLES gallery
  if (typeof EXAMPLES !== 'undefined') {
    EXAMPLES.rebalance_plan = {
      name: 'Rebalance Trade Plan',
      type: 'rebalance',
      description: 'Portfolio rebalance with 5 holdings, target allocations, 2 candidate signals (one passing, one blocked), and cost assumptions. Demonstrates trim, add, buy, hold, and skip.',
      data: REBALANCE_EXAMPLE,
    };
    populateExamples();
  }
});
