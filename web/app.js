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
