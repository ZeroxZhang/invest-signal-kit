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

class FakeClassList {
  constructor() {
    this.values = new Set();
  }

  add(value) {
    this.values.add(value);
  }

  remove(value) {
    this.values.delete(value);
  }

  contains(value) {
    return this.values.has(value);
  }
}

class FakeElement {
  constructor(id, options = {}) {
    this.id = id;
    this.dataset = options.dataset || {};
    this.fields = options.fields || {};
    this.listeners = {};
    this.classList = new FakeClassList();
    this.innerHTML = '';
  }

  addEventListener(type, handler) {
    this.listeners[type] = this.listeners[type] || [];
    this.listeners[type].push(handler);
  }

  dispatch(type, event = {}) {
    const evt = {
      target: this,
      preventDefault() {},
      ...event,
    };
    (this.listeners[type] || []).forEach(handler => handler(evt));
  }
}

class FakeDocument {
  constructor() {
    this.elements = {};
    this.listeners = {};
    this.navButtons = [
      new FakeElement('nav-buy', { dataset: { view: 'buy' } }),
      new FakeElement('nav-records', { dataset: { view: 'records' } }),
    ];
    this.views = [
      new FakeElement('buy'),
      new FakeElement('records'),
    ];
    this.register('buy-form', new FakeElement('buy-form'));
    this.register('buy-result', new FakeElement('buy-result'));
    this.register('holding-form', new FakeElement('holding-form'));
    this.register('holding-result', new FakeElement('holding-result'));
    this.register('records-list', new FakeElement('records-list'));
    this.views.forEach(element => this.register(element.id, element));
  }

  register(id, element) {
    this.elements[id] = element;
    return element;
  }

  getElementById(id) {
    return this.elements[id] || null;
  }

  querySelectorAll(selector) {
    if (selector === '.nav-btn') return this.navButtons;
    if (selector === '.view') return this.views;
    return [];
  }

  addEventListener(type, handler) {
    this.listeners[type] = this.listeners[type] || [];
    this.listeners[type].push(handler);
  }
}

class FakeFormData {
  constructor(form) {
    this.fields = form.fields || {};
  }

  forEach(callback) {
    Object.entries(this.fields).forEach(([key, value]) => callback(value, key));
  }
}

function createStorage() {
  return {
    value: null,
    getItem(key) { return key === 'aShareCheckRecords' ? this.value : null; },
    setItem(key, value) { if (key === 'aShareCheckRecords') this.value = value; },
  };
}

function loadConsumerWithDom(document, storage) {
  const code = fs.readFileSync(consumerPath, 'utf8');
  const root = { document, localStorage: storage, console, FormData: FakeFormData };
  root.globalThis = root;
  const ctx = vm.createContext(root);
  vm.runInContext(code, ctx);
  return ctx.ConsumerApp;
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

const deepLossHolding = ConsumerApp.evaluateHoldingCheck({
  code: '600519',
  name: '贵州茅台',
  costPrice: 100,
  currentPrice: 50,
  holdingAmount: 10000,
  totalFunds: 50000,
  originalReason: '长期看好公司基本面改善',
  currentReason: '继续持有是因为基本面仍需验证',
  maxAdditionalLoss: 9000,
});
assert(deepLossHolding.status === '亏损接近风险线', 'holding loss uses current value and price ratio');

const throwingStorage = {
  getItem() { throw new Error('storage blocked'); },
  setItem() { throw new Error('quota blocked'); },
};
assert(Array.isArray(ConsumerApp.loadRecords(throwingStorage)), 'loadRecords tolerates blocked storage');
assert(ConsumerApp.loadRecords(throwingStorage).length === 0, 'blocked storage loads as empty records');
assert(Array.isArray(ConsumerApp.saveRecord({ code: '600519' }, throwingStorage)), 'saveRecord tolerates blocked storage');

const malformedStorage = {
  value: '{"unexpected":true}',
  getItem() { return this.value; },
  setItem(_key, value) { this.value = value; },
};
assert(ConsumerApp.loadRecords(malformedStorage).length === 0, 'loadRecords ignores non-array stored data');
assert(ConsumerApp.saveRecord({ code: '600519' }, malformedStorage).length === 1, 'saveRecord recovers from non-array stored data');

const contradictedHolding = ConsumerApp.evaluateHoldingCheck({
  code: '600519',
  name: '贵州茅台',
  costPrice: 100,
  currentPrice: 98,
  holdingAmount: 5000,
  totalFunds: 100000,
  originalReason: '长期看好公司基本面改善',
  currentReason: '不再看好公司基本面改善',
  maxAdditionalLoss: 9000,
});
assert(contradictedHolding.status === '理由已经失效', 'contradicted holding reason invalidates status');
assert(hasArray(goodBuy, ['record', 'keyReasons']), 'buy record includes key reasons');
assert(hasArray(holding, ['record', 'keyReasons']), 'holding record includes key reasons');

console.log('\n=== Consumer page shell ===');
const html = fs.readFileSync(indexPath, 'utf8');
assert(html.includes('A股投资检查助手'), 'page shows consumer product name');
assert(html.includes('买前检查'), 'page exposes buy check');
assert(html.includes('持仓体检'), 'page exposes holding check');
assert(html.includes('检查记录'), 'page exposes records');
assert(html.includes('consumer.js'), 'page loads consumer.js');
assert(!html.includes('app.js'), 'page does not load expert app.js');
assert(/<body\b[^>]*class=["'][^"']*\bconsumer-app\b/.test(html), 'page scopes consumer UI with body class');

const forbiddenMainCopy = ['Signal Lab', 'Monte Carlo', 'Optimizer', 'signal JSON', 'action_level', 'trigger_condition'];
for (const term of forbiddenMainCopy) {
  assert(!html.includes(term), 'consumer page avoids expert term: ' + term);
}

console.log('\n=== Consumer record helpers ===');
const fakeStorage = {
  value: null,
  getItem(key) { return key === 'aShareCheckRecords' ? this.value : null; },
  setItem(key, value) { if (key === 'aShareCheckRecords') this.value = value; },
};
const saved = ConsumerApp.saveRecord({ type: '买前检查', code: '600519', name: '贵州茅台', conclusion: '继续观察' }, fakeStorage);
assert(saved.length === 1, 'saveRecord stores one item');
const loadedRecords = ConsumerApp.loadRecords(fakeStorage);
assert(loadedRecords[0].code === '600519', 'loadRecords returns stored item');
assert(typeof ConsumerApp.renderBuyResultHtml === 'function', 'renderBuyResultHtml exists');
assert(typeof ConsumerApp.renderHoldingResultHtml === 'function', 'renderHoldingResultHtml exists');
assert(ConsumerApp.renderBuyResultHtml(goodBuy).includes('结论'), 'buy result renderer includes conclusion heading');
assert(ConsumerApp.renderHoldingResultHtml(holding).includes('当前状态'), 'holding result renderer includes status heading');

const unsafeResultHtml = ConsumerApp.renderBuyResultHtml({
  ok: true,
  conclusion: '<script>alert("x")</script>',
  sections: {
    reasons: ['理由包含 <img src=x onerror=alert(1)> 标签'],
    riskLine: '跌破 <b>风险线</b>',
    missing: ['补充 <em>公告</em>'],
    nextSteps: ['不要点 <a href="#">链接</a>'],
    disclaimer: '普通提示',
  },
});
assert(!unsafeResultHtml.includes('<script>'), 'buy result renderer does not render raw script tags');
assert(!unsafeResultHtml.includes('<img'), 'buy result renderer escapes raw reason HTML');
assert(unsafeResultHtml.includes('&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;'), 'buy result renderer includes escaped script text');

console.log('\n=== Consumer DOM flow ===');
const domStorage = createStorage();
const domDocument = new FakeDocument();
const DomConsumerApp = loadConsumerWithDom(domDocument, domStorage);
domDocument.getElementById('buy-form').fields = {
  code: '600519',
  name: '贵州茅台<script>',
  reasonType: '看了公告或财报',
  reasonText: '收入和利润保持增长，想等回调后观察。',
  sourceType: '官方公告或财报',
  plannedAmount: 20000,
  totalFunds: 200000,
  maxLoss: 3000,
  holdingPeriod: '3-6个月',
  abandonCondition: '业绩不及预期或跌破计划风险线',
};
DomConsumerApp.initConsumerUI();
domDocument.getElementById('buy-form').dispatch('submit');
assert(domDocument.getElementById('buy-result').innerHTML.includes('保存这次检查'), 'submit renders buy save action');
domDocument.getElementById('buy-result').dispatch('click', { target: { dataset: { saveRecord: 'buy' } } });
const flowRecords = DomConsumerApp.loadRecords(domStorage);
assert(flowRecords.length === 1, 'save click stores one rendered buy record');
assert(flowRecords[0].name === '贵州茅台<script>', 'saved record keeps original user text');
assert(domDocument.getElementById('records-list').innerHTML.includes('主要原因'), 'records render key reason heading');
assert(!domDocument.getElementById('records-list').innerHTML.includes('<script>'), 'records escape saved name HTML');
assert(domDocument.getElementById('records-list').innerHTML.includes('&lt;script&gt;'), 'records include escaped saved name text');

const reasonStorage = createStorage();
reasonStorage.value = JSON.stringify([{
  type: '买前检查',
  code: '600519',
  name: '贵州茅台',
  conclusion: '继续观察',
  riskLine: '最多亏 3,000 元',
  nextStep: '继续观察',
  keyReasons: ['原因含 <strong>标签</strong>'],
}]);
const reasonDocument = new FakeDocument();
const ReasonConsumerApp = loadConsumerWithDom(reasonDocument, reasonStorage);
ReasonConsumerApp.initConsumerUI();
assert(reasonDocument.getElementById('records-list').innerHTML.includes('主要原因'), 'records show keyReasons section');
assert(!reasonDocument.getElementById('records-list').innerHTML.includes('<strong>标签</strong>'), 'records do not render raw keyReasons HTML');
assert(reasonDocument.getElementById('records-list').innerHTML.includes('&lt;strong&gt;标签&lt;/strong&gt;'), 'records include escaped keyReasons text');

const doubleInitStorage = createStorage();
const doubleInitDocument = new FakeDocument();
const DoubleInitConsumerApp = loadConsumerWithDom(doubleInitDocument, doubleInitStorage);
doubleInitDocument.getElementById('buy-form').fields = {
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
};
DoubleInitConsumerApp.initConsumerUI();
DoubleInitConsumerApp.initConsumerUI();
doubleInitDocument.getElementById('buy-form').dispatch('submit');
doubleInitDocument.getElementById('buy-result').dispatch('click', { target: { dataset: { saveRecord: 'buy' } } });
assert(DoubleInitConsumerApp.loadRecords(doubleInitStorage).length === 1, 'double init still saves only one record per click');

const malformedRecordStorage = createStorage();
malformedRecordStorage.value = JSON.stringify([
  { code: '600519', name: '<b>贵州茅台</b>', keyReasons: 'legacy <script>reason</script>' },
  null,
]);
const malformedRecordDocument = new FakeDocument();
const MalformedRecordConsumerApp = loadConsumerWithDom(malformedRecordDocument, malformedRecordStorage);
let malformedRenderError = null;
try {
  MalformedRecordConsumerApp.initConsumerUI();
} catch (err) {
  malformedRenderError = err;
}
const malformedRecordsHtml = malformedRecordDocument.getElementById('records-list').innerHTML;
assert(malformedRenderError === null, 'records render tolerates malformed stored items');
assert(malformedRecordsHtml.includes('主要原因'), 'records render legacy keyReasons heading');
assert(malformedRecordsHtml.includes('legacy &lt;script&gt;reason&lt;/script&gt;'), 'records escape legacy string keyReasons');
assert(!malformedRecordsHtml.includes('<script>reason</script>'), 'records do not render raw legacy keyReasons HTML');
assert(malformedRecordsHtml.includes('检查'), 'records render null legacy item with fallback type');

console.log('\n=== Consumer styles ===');
const css = fs.readFileSync(path.join(ROOT, 'web', 'styles.css'), 'utf8');

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function selectorRegex(selector) {
  const pattern = escapeRegExp(selector).replace(/\\ /g, '\\s+');
  return new RegExp('(^|[{},])\\s*' + pattern + '\\s*(?=,|\\{)', 'm');
}

function hasSelector(selector) {
  return selectorRegex(selector).test(css);
}

function mediaBlock(query) {
  const start = css.search(new RegExp('@media\\s*\\(' + escapeRegExp(query).replace(/\\ /g, '\\s*') + '\\)'));
  if (start < 0) return '';
  const open = css.indexOf('{', start);
  if (open < 0) return '';
  let depth = 0;
  for (let i = open; i < css.length; i += 1) {
    if (css[i] === '{') depth += 1;
    if (css[i] === '}') depth -= 1;
    if (depth === 0) return css.slice(open + 1, i);
  }
  return '';
}

assert(/:root\s*\{[\s\S]*--page-bg:\s*#[0-9a-f]{6};[\s\S]*--surface:\s*#[0-9a-f]{6};[\s\S]*--primary:\s*#[0-9a-f]{6};[\s\S]*--radius:\s*8px;/i.test(css), 'styles define consumer design tokens');

const scopedSelectors = [
  '.consumer-app .app-shell',
  '.consumer-app .work-area',
  '.consumer-app .tool-panel',
  '.consumer-app .result-panel',
  '.consumer-app .record-item',
  '.consumer-app .primary-btn',
  '.consumer-app .nav-btn',
  '.consumer-app .view.active',
  '.consumer-app label',
  '.consumer-app input',
  '.consumer-app select',
  '.consumer-app textarea',
];
for (const selector of scopedSelectors) {
  assert(hasSelector(selector), 'styles define scoped selector: ' + selector);
}

assert(!hasSelector('label'), 'styles do not style all labels globally');
assert(!hasSelector('input'), 'styles do not style all inputs globally');
assert(!hasSelector('select'), 'styles do not style all selects globally');
assert(!hasSelector('textarea'), 'styles do not style all textareas globally');
assert(!hasSelector('.nav-btn'), 'styles do not style nav buttons outside consumer app');
assert(!hasSelector('.primary-btn'), 'styles do not style primary buttons outside consumer app');

const mobile520 = mediaBlock('max-width: 520px');
assert(mobile520.length > 0, 'styles include max-width 520 mobile rules');
assert(
  /\.consumer-app\s+\.nav-btn\s*,\s*\.consumer-app\s+\.primary-btn\s*,\s*\.consumer-app\s+\.secondary-btn\s*,\s*\.consumer-app\s+\.ghost-btn\s*\{[^}]*min-height:\s*(?:4[4-9]|[5-9]\d)px/i.test(mobile520),
  'mobile consumer buttons keep at least 44px min-height'
);

finish();
