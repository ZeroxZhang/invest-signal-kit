#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.join(__dirname, '..');
const consumerPath = path.join(ROOT, 'web', 'consumer.js');
const indexPath = path.join(ROOT, 'web', 'index.html');

let passed = 0;
let failed = 0;

function assert(cond, msg) {
  if (cond) {
    passed += 1;
    console.log('  PASS: ' + msg);
  } else {
    failed += 1;
    console.log('  FAIL: ' + msg);
  }
}

function finish() {
  console.log('\n' + '='.repeat(50));
  console.log('Results: ' + passed + ' passed, ' + failed + ' failed');
  if (failed > 0) process.exit(1);
}

function valueAt(obj, pathParts) {
  let value = obj;
  for (const part of pathParts) {
    if (value === null || value === undefined) return undefined;
    value = value[part];
  }
  return value;
}

function hasArray(obj, pathParts) {
  const value = valueAt(obj, pathParts);
  return Array.isArray(value) && value.length > 0;
}

function hasString(obj, pathParts) {
  const value = valueAt(obj, pathParts);
  return typeof value === 'string' && value.length > 0;
}

function includesText(obj, pathParts, text) {
  const value = valueAt(obj, pathParts);
  return typeof value === 'string' && value.includes(text);
}

function arrayIncludesText(obj, pathParts, text) {
  const value = valueAt(obj, pathParts);
  return Array.isArray(value) && value.includes(text);
}

function loadConsumer() {
  try {
    const code = fs.readFileSync(consumerPath, 'utf8');
    const ctx = vm.createContext({ console });
    vm.runInContext(code, ctx);
    return { app: ctx.ConsumerApp, error: null };
  } catch (err) {
    return { app: null, error: err };
  }
}

console.log('\n=== Consumer rule module ===');
const loaded = loadConsumer();
if (loaded.error) {
  assert(false, 'consumer module could not be loaded: ' + loaded.error.message);
  finish();
}

const ConsumerApp = loaded.app;
assert(!!ConsumerApp, 'ConsumerApp is exposed for tests');
if (!ConsumerApp) finish();

assert(typeof ConsumerApp.isAshareCode === 'function', 'isAshareCode exists');
assert(typeof ConsumerApp.evaluateBuyCheck === 'function', 'evaluateBuyCheck exists');
assert(typeof ConsumerApp.evaluateHoldingCheck === 'function', 'evaluateHoldingCheck exists');
if (
  typeof ConsumerApp.isAshareCode !== 'function' ||
  typeof ConsumerApp.evaluateBuyCheck !== 'function' ||
  typeof ConsumerApp.evaluateHoldingCheck !== 'function'
) {
  finish();
}

assert(ConsumerApp.isAshareCode('600519') === true, '6-digit A-share stock code passes');
assert(ConsumerApp.isAshareCode('510300') === true, '6-digit listed ETF code passes');
assert(ConsumerApp.isAshareCode('TSLA') === false, 'foreign ticker fails');

const invalidCode = ConsumerApp.evaluateBuyCheck({
  code: 'TSLA',
  name: '特斯拉',
  reasonType: '朋友推荐',
  reasonText: '朋友说会涨',
  sourceType: '朋友转述',
  plannedAmount: 10000,
  totalFunds: 100000,
  maxLoss: 3000,
  holdingPeriod: '1-3个月',
  abandonCondition: '跌破关键位置',
});
assert(invalidCode.ok === false, 'foreign ticker blocks buy check');
assert(
  arrayIncludesText(invalidCode, ['errors'], '当前版本只支持国内A股股票和场内ETF，请输入6位A股/ETF代码。'),
  'foreign ticker gets domestic A-share scope message'
);

const goodBuy = ConsumerApp.evaluateBuyCheck({
  code: '600519',
  name: '贵州茅台',
  reasonType: '看了公告或财报',
  reasonText: '收入和利润保持增长，想等回调后观察。',
  sourceType: '官方公告或财报',
  plannedAmount: 20000,
  totalFunds: 200000,
  maxLoss: 3000,
  holdingPeriod: '3-6个月',
  abandonCondition: '业绩不及预期或跌破计划风险线',
});
assert(goodBuy.ok === true, 'complete A-share buy check succeeds');
assert(goodBuy.conclusion === '条件满足后再考虑', 'complete reliable buy check returns conditional conclusion');
assert(hasArray(goodBuy, ['sections', 'reasons']), 'buy check includes reasons');
assert(hasString(goodBuy, ['sections', 'riskLine']), 'buy check includes risk line');
assert(hasArray(goodBuy, ['sections', 'nextSteps']), 'buy check includes next steps');
assert(includesText(goodBuy, ['sections', 'disclaimer'], '不构成投资建议'), 'buy check includes plain disclaimer');

const concentratedBuy = ConsumerApp.evaluateBuyCheck({
  code: '510300',
  name: '沪深300ETF',
  reasonType: '长期看好',
  reasonText: '想长期配置宽基指数。',
  sourceType: '自己观察价格',
  plannedAmount: 80000,
  totalFunds: 200000,
  maxLoss: 10000,
  holdingPeriod: '一年以上',
  abandonCondition: '总资金安排变化或跌破能承受的风险线',
});
assert(concentratedBuy.conclusion === '风险过高', 'position share above 30 percent is high risk');

const holding = ConsumerApp.evaluateHoldingCheck({
  code: '600519',
  name: '贵州茅台',
  costPrice: 1800,
  currentPrice: 1620,
  holdingAmount: 70000,
  totalFunds: 200000,
  originalReason: '长期看好高端白酒',
  currentReason: '理由没有变化，但仓位较大',
  maxAdditionalLoss: 8000,
});
assert(holding.ok === true, 'holding check succeeds');
assert(holding.status === '仓位偏重', 'holding above 30 percent flags concentration');
assert(hasArray(holding, ['sections', 'positionWarning']), 'holding output includes position warning');
assert(hasArray(holding, ['sections', 'lossWarning']), 'holding output includes loss warning');
assert(hasArray(holding, ['sections', 'actions']), 'holding output includes actions');

console.log('\n=== Consumer page shell ===');
const html = fs.readFileSync(indexPath, 'utf8');
assert(html.includes('A股投资检查助手'), 'page shows consumer product name');
assert(html.includes('买前检查'), 'page exposes buy check');
assert(html.includes('持仓体检'), 'page exposes holding check');
assert(html.includes('检查记录'), 'page exposes records');
assert(html.includes('consumer.js'), 'page loads consumer.js');
assert(!html.includes('app.js'), 'page does not load expert app.js');

const forbiddenMainCopy = ['Signal Lab', 'Monte Carlo', 'Optimizer', 'signal JSON', 'action_level', 'trigger_condition'];
for (const term of forbiddenMainCopy) {
  assert(!html.includes(term), 'consumer page avoids expert term: ' + term);
}

finish();
