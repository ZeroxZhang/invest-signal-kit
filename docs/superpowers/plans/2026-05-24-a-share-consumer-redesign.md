# A-Share Consumer Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the default web workstation with a beginner-friendly domestic A-share investment check assistant.

**Architecture:** Add a focused `web/consumer.js` module for consumer rules, DOM rendering, and browser-local records, and make `web/index.html` load that module instead of the old expert `web/app.js`. Keep the existing professional engines in the repository for now, but remove them from the default consumer navigation and visible first-run path.

**Tech Stack:** Static HTML/CSS/JavaScript, browser localStorage, Node VM smoke tests, existing Python unittest suite.

---

## Files

- Create: `web/consumer.js`
  - Owns consumer-facing validation, buy-check rules, holding-check rules, rendering helpers, and localStorage record helpers.
  - Exposes `ConsumerApp` on `window` in the browser and on `globalThis` for Node VM tests.
- Replace: `web/index.html`
  - Becomes the consumer UI shell with three visible entries: 买前检查, 持仓体检, 检查记录.
  - Loads `consumer.js`, not `app.js`.
- Replace: `web/styles.css`
  - Becomes a light, form-first consumer interface.
- Create: `tests/test_consumer_ui.js`
  - Node-based tests for consumer rules and default page copy.
- Modify: `README.md`
  - Put the consumer product path first and move professional workflow language down as advanced/developer context.
- Modify: `docs/ui.md`
  - Describe the new consumer UI and A-share-only scope.

## Task 1: Consumer Rule Tests

**Files:**
- Create: `tests/test_consumer_ui.js`
- Create in Task 2: `web/consumer.js`

- [ ] **Step 1: Write the failing test**

Create `tests/test_consumer_ui.js` with:

```javascript
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

function loadConsumer() {
  const code = fs.readFileSync(consumerPath, 'utf8');
  const ctx = vm.createContext({ console });
  vm.runInContext(code, ctx);
  return ctx.ConsumerApp;
}

console.log('\n=== Consumer rule module ===');
const ConsumerApp = loadConsumer();
assert(!!ConsumerApp, 'ConsumerApp is exposed for tests');
assert(typeof ConsumerApp.isAshareCode === 'function', 'isAshareCode exists');
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
  invalidCode.errors.includes('当前版本只支持国内A股股票和场内ETF，请输入6位A股/ETF代码。'),
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
assert(goodBuy.sections.reasons.length > 0, 'buy check includes reasons');
assert(goodBuy.sections.riskLine.length > 0, 'buy check includes risk line');
assert(goodBuy.sections.nextSteps.length > 0, 'buy check includes next steps');
assert(goodBuy.sections.disclaimer.includes('不构成投资建议'), 'buy check includes plain disclaimer');

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
assert(holding.sections.positionWarning.length > 0, 'holding output includes position warning');
assert(holding.sections.lossWarning.length > 0, 'holding output includes loss warning');
assert(holding.sections.actions.length > 0, 'holding output includes actions');

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

console.log('\n' + '='.repeat(50));
console.log('Results: ' + passed + ' passed, ' + failed + ' failed');
if (failed > 0) process.exit(1);
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
node tests/test_consumer_ui.js
```

Expected: FAIL because `web/consumer.js` does not exist yet, or `ConsumerApp` is not exposed.

- [ ] **Step 3: Commit the failing test**

```bash
git add tests/test_consumer_ui.js
git commit -m "test: add consumer A-share UI expectations"
```

## Task 2: Consumer Rule Module

**Files:**
- Create: `web/consumer.js`
- Test: `tests/test_consumer_ui.js`

- [ ] **Step 1: Implement the minimal rule module**

Create `web/consumer.js` with:

```javascript
/* A股投资检查助手 — consumer-facing rules and UI glue. */
'use strict';

(function(root) {
  const ASHARE_SCOPE_MESSAGE = '当前版本只支持国内A股股票和场内ETF，请输入6位A股/ETF代码。';
  const DISCLAIMER = '本结果只做风险检查，不构成投资建议，不承诺收益。';
  const RELIABLE_SOURCES = new Set(['官方公告或财报', '券商研报', '财经媒体']);
  const WEAK_SOURCES = new Set(['社交平台', '朋友转述']);

  function isAshareCode(code) {
    return /^\d{6}$/.test(String(code || '').trim());
  }

  function toNumber(value) {
    const n = Number(value);
    return Number.isFinite(n) ? n : 0;
  }

  function money(value) {
    return Math.round(toNumber(value)).toLocaleString('zh-CN');
  }

  function percent(value) {
    return `${Math.round(toNumber(value) * 10) / 10}%`;
  }

  function cleanText(value) {
    return String(value || '').trim();
  }

  function validateCommonCode(input) {
    const errors = [];
    if (!cleanText(input.code)) errors.push('请先填写股票或ETF代码。');
    else if (!isAshareCode(input.code)) errors.push(ASHARE_SCOPE_MESSAGE);
    if (!cleanText(input.name)) errors.push('请填写股票或ETF名称，方便你之后回看记录。');
    return errors;
  }

  function evaluateBuyCheck(input) {
    const data = input || {};
    const errors = validateCommonCode(data);
    const plannedAmount = toNumber(data.plannedAmount);
    const totalFunds = toNumber(data.totalFunds);
    const maxLoss = toNumber(data.maxLoss);
    const reasonText = cleanText(data.reasonText);
    const abandonCondition = cleanText(data.abandonCondition);
    const sourceType = cleanText(data.sourceType);
    const positionPct = totalFunds > 0 ? plannedAmount / totalFunds * 100 : 0;

    if (!cleanText(data.reasonType) && !reasonText) errors.push('请写一句你为什么想买，不然系统没法帮你检查理由。');
    if (plannedAmount <= 0) errors.push('请填写准备投入多少钱。');
    if (totalFunds <= 0) errors.push('请填写你的总投资资金。');
    if (plannedAmount > totalFunds && totalFunds > 0) errors.push('投入金额不能大于你的总资金。');
    if (maxLoss <= 0) errors.push('最多能接受亏损要大于 0。');
    if (!abandonCondition) errors.push('请写清楚什么情况你会放弃买入，否则风险线不明确。');

    if (errors.length) return { ok: false, errors };

    const reasons = [];
    const missing = [];
    const nextSteps = [];
    let conclusion = '继续观察';

    if (positionPct > 30) {
      conclusion = '风险过高';
      reasons.push(`这次计划投入约占总资金 ${percent(positionPct)}，对普通个人用户来说过于集中。`);
      nextSteps.push('先把计划投入金额降下来，再重新检查。');
    } else if (positionPct > 15) {
      conclusion = '暂缓';
      reasons.push(`这次计划投入约占总资金 ${percent(positionPct)}，仓位偏高，建议先降低金额。`);
      nextSteps.push('把单次投入控制在更容易承受的范围内。');
    } else {
      reasons.push(`这次计划投入约占总资金 ${percent(positionPct)}，仓位压力相对可控。`);
    }

    if (WEAK_SOURCES.has(sourceType)) {
      if (conclusion !== '风险过高') conclusion = '暂缓';
      reasons.push('当前信息来源偏弱，容易受到情绪或传闻影响。');
      missing.push('请用官方公告、财报、交易所信息或可靠财经媒体交叉验证。');
      nextSteps.push('先补充可靠来源，再考虑是否继续观察。');
    } else if (RELIABLE_SOURCES.has(sourceType)) {
      reasons.push('信息来源相对可靠，但仍需要结合价格和风险线。');
    } else {
      missing.push('请补充一个更明确的信息来源。');
    }

    if (maxLoss >= plannedAmount) {
      conclusion = '风险过高';
      reasons.push('你能接受的亏损已经接近或超过本次投入金额，风险边界不合理。');
      nextSteps.push('重新设置本次最多能亏多少钱。');
    } else {
      reasons.push(`你为这次检查设置的最大可承受亏损约为 ${money(maxLoss)} 元。`);
    }

    if (reasonText.length < 8) {
      if (conclusion !== '风险过高') conclusion = '暂缓';
      missing.push('买入理由还太短，请写清楚你期待它变好的具体原因。');
    }

    if (conclusion === '继续观察' && RELIABLE_SOURCES.has(sourceType) && abandonCondition) {
      conclusion = '条件满足后再考虑';
      nextSteps.push('只在你写下的条件出现后再考虑买入，不要因为短期波动临时加码。');
    }

    if (!nextSteps.length) nextSteps.push('先观察，不急着买；补齐缺失信息后再检查一次。');
    if (!missing.length) missing.push('暂时没有必须补充的信息，但买入前仍要核对公告、价格位置和风险线。');

    return {
      ok: true,
      conclusion,
      sections: {
        reasons,
        riskLine: `本次最多可承受亏损：${money(maxLoss)} 元；放弃条件：${abandonCondition}`,
        missing,
        nextSteps,
        disclaimer: DISCLAIMER,
      },
      record: {
        type: '买前检查',
        code: cleanText(data.code),
        name: cleanText(data.name),
        conclusion,
        riskLine: `最多亏 ${money(maxLoss)} 元`,
        nextStep: nextSteps[0],
      },
    };
  }

  function evaluateHoldingCheck(input) {
    const data = input || {};
    const errors = validateCommonCode(data);
    const costPrice = toNumber(data.costPrice);
    const currentPrice = toNumber(data.currentPrice);
    const holdingAmount = toNumber(data.holdingAmount);
    const totalFunds = toNumber(data.totalFunds);
    const maxAdditionalLoss = toNumber(data.maxAdditionalLoss);
    const originalReason = cleanText(data.originalReason);
    const currentReason = cleanText(data.currentReason);
    const positionPct = totalFunds > 0 ? holdingAmount / totalFunds * 100 : 0;
    const lossPct = costPrice > 0 ? Math.max(0, (costPrice - currentPrice) / costPrice * 100) : 0;
    const estimatedLossAmount = holdingAmount * (lossPct / 100);

    if (costPrice <= 0) errors.push('请填写买入成本。');
    if (currentPrice <= 0) errors.push('请填写当前价格。');
    if (holdingAmount <= 0) errors.push('请填写当前持有金额。');
    if (totalFunds <= 0) errors.push('请填写你的总投资资金。');
    if (holdingAmount > totalFunds && totalFunds > 0) errors.push('持有金额不能大于你的总资金。');
    if (!originalReason) errors.push('请写一句当初为什么买。');
    if (!currentReason) errors.push('请写一句现在还想继续持有的理由。');
    if (maxAdditionalLoss <= 0) errors.push('最多还能接受亏损要大于 0。');

    if (errors.length) return { ok: false, errors };

    let status = '正常观察';
    const positionWarning = [];
    const lossWarning = [];
    const confirmations = [];
    const actions = [];

    if (positionPct > 30) {
      status = '仓位偏重';
      positionWarning.push(`这只标的约占总资金 ${percent(positionPct)}，仓位明显偏重。`);
      actions.push('先停止加仓，必要时把仓位降到更容易承受的范围。');
    } else if (positionPct > 15) {
      positionWarning.push(`这只标的约占总资金 ${percent(positionPct)}，需要持续关注集中度。`);
      actions.push('继续观察，但不要因为短期上涨继续加仓。');
    } else {
      positionWarning.push(`这只标的约占总资金 ${percent(positionPct)}，仓位暂时不算集中。`);
    }

    if (estimatedLossAmount >= maxAdditionalLoss * 0.8) {
      if (status === '正常观察') status = '亏损接近风险线';
      lossWarning.push(`按当前价格估算，亏损已经接近你还能承受的 ${money(maxAdditionalLoss)} 元风险线。`);
      actions.push('重新检查是否需要减小仓位或停止加仓。');
    } else {
      lossWarning.push(`当前估算亏损距离你设置的风险线还有一定空间，但仍要按计划复查。`);
    }

    if (currentReason.length < 8 || currentReason === originalReason && originalReason.length < 8) {
      if (status === '正常观察') status = '理由已经失效';
      confirmations.push('继续持有的理由还不够清楚，请重新写下你愿意继续持有的依据。');
      actions.push('重新检查理由。');
    } else {
      confirmations.push('确认当前理由仍然成立，并定期核对公告、业绩和风险线。');
    }

    if (!actions.length) actions.push('继续观察。');

    return {
      ok: true,
      status,
      sections: {
        positionWarning,
        lossWarning,
        confirmations,
        actions: Array.from(new Set(actions)),
        disclaimer: DISCLAIMER,
      },
      record: {
        type: '持仓体检',
        code: cleanText(data.code),
        name: cleanText(data.name),
        conclusion: status,
        riskLine: `最多再亏 ${money(maxAdditionalLoss)} 元`,
        nextStep: actions[0],
      },
    };
  }

  function loadRecords(storage) {
    const store = storage || (root.localStorage || null);
    if (!store) return [];
    try {
      const raw = store.getItem('aShareCheckRecords');
      return raw ? JSON.parse(raw) : [];
    } catch (_) {
      return [];
    }
  }

  function saveRecord(record, storage) {
    const store = storage || (root.localStorage || null);
    if (!store || !record) return [];
    const records = loadRecords(store);
    const next = [{ ...record, createdAt: new Date().toISOString() }, ...records].slice(0, 20);
    store.setItem('aShareCheckRecords', JSON.stringify(next));
    return next;
  }

  root.ConsumerApp = {
    ASHARE_SCOPE_MESSAGE,
    DISCLAIMER,
    isAshareCode,
    evaluateBuyCheck,
    evaluateHoldingCheck,
    loadRecords,
    saveRecord,
  };
})(typeof window !== 'undefined' ? window : globalThis);
```

- [ ] **Step 2: Run the consumer test**

Run:

```bash
node tests/test_consumer_ui.js
```

Expected: still FAIL because `web/index.html` has not been converted to the consumer shell yet.

- [ ] **Step 3: Commit the rule module**

```bash
git add web/consumer.js
git commit -m "feat: add consumer A-share check rules"
```

## Task 3: Consumer HTML Shell

**Files:**
- Replace: `web/index.html`
- Test: `tests/test_consumer_ui.js`

- [ ] **Step 1: Replace the default HTML shell**

Replace `web/index.html` with:

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>A股投资检查助手</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header class="app-header">
    <div>
      <h1>A股投资检查助手</h1>
      <p>只做风险检查，不荐股，不承诺收益。</p>
    </div>
    <nav class="top-nav" aria-label="主导航">
      <button class="nav-btn active" data-view="buy-check" type="button">买前检查</button>
      <button class="nav-btn" data-view="holding-check" type="button">持仓体检</button>
      <button class="nav-btn" data-view="records" type="button">检查记录</button>
    </nav>
  </header>

  <main class="app-shell">
    <section class="view active" id="buy-check" aria-labelledby="buy-title">
      <div class="work-area">
        <form class="tool-panel" id="buy-form">
          <div class="section-heading">
            <span>买前检查</span>
            <h2 id="buy-title">准备买之前，先把理由和风险说清楚</h2>
            <p>适用于国内A股股票和场内ETF。输入你已经知道的信息，系统会告诉你哪里还不清楚。</p>
          </div>

          <div class="form-grid two-cols">
            <label>股票/ETF代码
              <input name="code" inputmode="numeric" maxlength="6" placeholder="例如 600519 或 510300">
            </label>
            <label>名称
              <input name="name" placeholder="例如 贵州茅台 / 沪深300ETF">
            </label>
          </div>

          <label>你为什么想买
            <select name="reasonType">
              <option value="">请选择一个最接近的原因</option>
              <option>看到新闻</option>
              <option>看了公告或财报</option>
              <option>看了研报</option>
              <option>朋友推荐</option>
              <option>价格上涨想追</option>
              <option>长期看好</option>
              <option>其他</option>
            </select>
          </label>

          <label>用一句话写清楚你的理由
            <textarea name="reasonText" rows="3" placeholder="例如：公司最新财报收入增长，我想等价格回调后再观察。"></textarea>
          </label>

          <label>消息从哪里来
            <select name="sourceType">
              <option value="">请选择信息来源</option>
              <option>官方公告或财报</option>
              <option>券商研报</option>
              <option>财经媒体</option>
              <option>社交平台</option>
              <option>朋友转述</option>
              <option>自己观察价格</option>
            </select>
          </label>

          <div class="form-grid two-cols">
            <label>准备投入多少钱
              <input name="plannedAmount" type="number" min="0" step="100" placeholder="例如 20000">
            </label>
            <label>总投资资金
              <input name="totalFunds" type="number" min="0" step="100" placeholder="例如 200000">
            </label>
            <label>最多能接受亏多少
              <input name="maxLoss" type="number" min="0" step="100" placeholder="例如 3000">
            </label>
            <label>打算持有多久
              <input name="holdingPeriod" placeholder="例如 1-3个月 / 一年以上">
            </label>
          </div>

          <label>什么情况你会放弃这次买入
            <textarea name="abandonCondition" rows="3" placeholder="例如：业绩不及预期，或跌破我能承受的风险线。"></textarea>
          </label>

          <div class="form-actions">
            <button class="primary-btn" type="submit">开始检查</button>
            <button class="ghost-btn" type="reset">清空</button>
          </div>
        </form>

        <aside class="result-panel" id="buy-result" aria-live="polite">
          <div class="empty-state">
            <h2>检查结果</h2>
            <p>填写左侧表单后，这里会显示结论、主要原因、风险线和下一步。</p>
          </div>
        </aside>
      </div>
    </section>

    <section class="view" id="holding-check" aria-labelledby="holding-title">
      <div class="work-area">
        <form class="tool-panel" id="holding-form">
          <div class="section-heading">
            <span>持仓体检</span>
            <h2 id="holding-title">已经买了，也要定期检查理由还在不在</h2>
            <p>输入成本、当前价格和仓位，检查是否太集中、亏损是否接近风险线。</p>
          </div>

          <div class="form-grid two-cols">
            <label>持有代码
              <input name="code" inputmode="numeric" maxlength="6" placeholder="例如 600519">
            </label>
            <label>名称
              <input name="name" placeholder="例如 贵州茅台">
            </label>
            <label>买入成本
              <input name="costPrice" type="number" min="0" step="0.01" placeholder="例如 1800">
            </label>
            <label>当前价格
              <input name="currentPrice" type="number" min="0" step="0.01" placeholder="例如 1620">
            </label>
            <label>持有金额
              <input name="holdingAmount" type="number" min="0" step="100" placeholder="例如 70000">
            </label>
            <label>总投资资金
              <input name="totalFunds" type="number" min="0" step="100" placeholder="例如 200000">
            </label>
          </div>

          <label>当初为什么买
            <textarea name="originalReason" rows="3" placeholder="例如：长期看好高端白酒需求。"></textarea>
          </label>
          <label>现在还想继续持有的理由
            <textarea name="currentReason" rows="3" placeholder="例如：业绩逻辑还在，但仓位已经偏高。"></textarea>
          </label>
          <label>最多还能接受亏多少
            <input name="maxAdditionalLoss" type="number" min="0" step="100" placeholder="例如 8000">
          </label>

          <div class="form-actions">
            <button class="primary-btn" type="submit">开始体检</button>
            <button class="ghost-btn" type="reset">清空</button>
          </div>
        </form>

        <aside class="result-panel" id="holding-result" aria-live="polite">
          <div class="empty-state">
            <h2>体检结果</h2>
            <p>填写左侧表单后，这里会显示当前状态、仓位提醒、亏损提醒和可执行动作。</p>
          </div>
        </aside>
      </div>
    </section>

    <section class="view" id="records" aria-labelledby="records-title">
      <div class="records-panel">
        <div class="section-heading">
          <span>检查记录</span>
          <h2 id="records-title">回看每一次检查，不靠临时情绪做决定</h2>
          <p>记录只保存在当前浏览器里，不会上传，也不会生成交易订单。</p>
        </div>
        <div id="records-list" class="records-list"></div>
      </div>
    </section>
  </main>

  <script src="consumer.js"></script>
</body>
</html>
```

- [ ] **Step 2: Run the consumer test**

Run:

```bash
node tests/test_consumer_ui.js
```

Expected: PASS for rule and page-shell assertions.

- [ ] **Step 3: Commit the HTML shell**

```bash
git add web/index.html
git commit -m "feat: replace workstation shell with consumer UI"
```

## Task 4: Consumer DOM Rendering

**Files:**
- Modify: `web/consumer.js`
- Test: `tests/test_consumer_ui.js`

- [ ] **Step 1: Extend the failing test for records and render helpers**

Append this block before the final summary in `tests/test_consumer_ui.js`:

```javascript
console.log('\n=== Consumer record helpers ===');
const fakeStorage = {
  value: null,
  getItem(key) { return key === 'aShareCheckRecords' ? this.value : null; },
  setItem(key, value) { if (key === 'aShareCheckRecords') this.value = value; },
};
const saved = ConsumerApp.saveRecord({ type: '买前检查', code: '600519', name: '贵州茅台', conclusion: '继续观察' }, fakeStorage);
assert(saved.length === 1, 'saveRecord stores one item');
const loaded = ConsumerApp.loadRecords(fakeStorage);
assert(loaded[0].code === '600519', 'loadRecords returns stored item');
assert(typeof ConsumerApp.renderBuyResultHtml === 'function', 'renderBuyResultHtml exists');
assert(typeof ConsumerApp.renderHoldingResultHtml === 'function', 'renderHoldingResultHtml exists');
assert(ConsumerApp.renderBuyResultHtml(goodBuy).includes('结论'), 'buy result renderer includes conclusion heading');
assert(ConsumerApp.renderHoldingResultHtml(holding).includes('当前状态'), 'holding result renderer includes status heading');
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
node tests/test_consumer_ui.js
```

Expected: FAIL because `renderBuyResultHtml` and `renderHoldingResultHtml` are not exposed yet.

- [ ] **Step 3: Implement render helpers and DOM initialization**

Add these functions inside `web/consumer.js` before `root.ConsumerApp = { ... }`, then add them to the exported object:

```javascript
  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function listHtml(items) {
    return `<ul>${(items || []).map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`;
  }

  function errorHtml(result) {
    return `
      <div class="result-card danger">
        <span class="eyebrow">需要先补充</span>
        <h2>现在还不能检查</h2>
        ${listHtml(result.errors)}
      </div>
    `;
  }

  function renderBuyResultHtml(result) {
    if (!result.ok) return errorHtml(result);
    return `
      <div class="result-card">
        <span class="eyebrow">结论</span>
        <h2>${escapeHtml(result.conclusion)}</h2>
        <section><h3>主要原因</h3>${listHtml(result.sections.reasons)}</section>
        <section><h3>风险线</h3><p>${escapeHtml(result.sections.riskLine)}</p></section>
        <section><h3>需要补充的信息</h3>${listHtml(result.sections.missing)}</section>
        <section><h3>下一步</h3>${listHtml(result.sections.nextSteps)}</section>
        <p class="disclaimer">${escapeHtml(result.sections.disclaimer)}</p>
        <button class="secondary-btn" type="button" data-save-record="buy">保存这次检查</button>
      </div>
    `;
  }

  function renderHoldingResultHtml(result) {
    if (!result.ok) return errorHtml(result);
    return `
      <div class="result-card">
        <span class="eyebrow">当前状态</span>
        <h2>${escapeHtml(result.status)}</h2>
        <section><h3>仓位提醒</h3>${listHtml(result.sections.positionWarning)}</section>
        <section><h3>亏损提醒</h3>${listHtml(result.sections.lossWarning)}</section>
        <section><h3>继续持有前要确认的事</h3>${listHtml(result.sections.confirmations)}</section>
        <section><h3>可执行动作</h3>${listHtml(result.sections.actions)}</section>
        <p class="disclaimer">${escapeHtml(result.sections.disclaimer)}</p>
        <button class="secondary-btn" type="button" data-save-record="holding">保存这次体检</button>
      </div>
    `;
  }

  function formDataObject(form) {
    const out = {};
    new FormData(form).forEach((value, key) => { out[key] = value; });
    return out;
  }

  function renderRecords() {
    const list = root.document && root.document.getElementById('records-list');
    if (!list) return;
    const records = loadRecords();
    if (!records.length) {
      list.innerHTML = '<div class="empty-state"><h2>还没有检查记录</h2><p>完成一次买前检查或持仓体检后，可以保存到这里。</p></div>';
      return;
    }
    list.innerHTML = records.map(record => `
      <article class="record-item">
        <span>${escapeHtml(record.type || '检查')}</span>
        <h3>${escapeHtml(record.code)} ${escapeHtml(record.name)}</h3>
        <p><strong>结论：</strong>${escapeHtml(record.conclusion)}</p>
        <p><strong>风险线：</strong>${escapeHtml(record.riskLine || '')}</p>
        <p><strong>下一步：</strong>${escapeHtml(record.nextStep || '')}</p>
      </article>
    `).join('');
  }

  function initConsumerUI() {
    if (!root.document) return;
    const navButtons = Array.from(root.document.querySelectorAll('.nav-btn'));
    const views = Array.from(root.document.querySelectorAll('.view'));
    navButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        navButtons.forEach(item => item.classList.remove('active'));
        views.forEach(view => view.classList.remove('active'));
        btn.classList.add('active');
        const target = root.document.getElementById(btn.dataset.view);
        if (target) target.classList.add('active');
        if (btn.dataset.view === 'records') renderRecords();
      });
    });

    let lastBuyResult = null;
    let lastHoldingResult = null;
    const buyForm = root.document.getElementById('buy-form');
    const buyResult = root.document.getElementById('buy-result');
    if (buyForm && buyResult) {
      buyForm.addEventListener('submit', event => {
        event.preventDefault();
        lastBuyResult = evaluateBuyCheck(formDataObject(buyForm));
        buyResult.innerHTML = renderBuyResultHtml(lastBuyResult);
      });
      buyResult.addEventListener('click', event => {
        if (event.target && event.target.dataset.saveRecord === 'buy' && lastBuyResult && lastBuyResult.ok) {
          saveRecord(lastBuyResult.record);
          renderRecords();
        }
      });
    }

    const holdingForm = root.document.getElementById('holding-form');
    const holdingResult = root.document.getElementById('holding-result');
    if (holdingForm && holdingResult) {
      holdingForm.addEventListener('submit', event => {
        event.preventDefault();
        lastHoldingResult = evaluateHoldingCheck(formDataObject(holdingForm));
        holdingResult.innerHTML = renderHoldingResultHtml(lastHoldingResult);
      });
      holdingResult.addEventListener('click', event => {
        if (event.target && event.target.dataset.saveRecord === 'holding' && lastHoldingResult && lastHoldingResult.ok) {
          saveRecord(lastHoldingResult.record);
          renderRecords();
        }
      });
    }

    renderRecords();
  }

  if (root.document) {
    root.document.addEventListener('DOMContentLoaded', initConsumerUI);
  }
```

Also export the added helpers:

```javascript
    renderBuyResultHtml,
    renderHoldingResultHtml,
    initConsumerUI,
```

- [ ] **Step 4: Run the consumer test**

Run:

```bash
node tests/test_consumer_ui.js
```

Expected: PASS.

- [ ] **Step 5: Commit DOM rendering**

```bash
git add web/consumer.js tests/test_consumer_ui.js
git commit -m "feat: render consumer check results and records"
```

## Task 5: Consumer Styling

**Files:**
- Replace: `web/styles.css`
- Test: `tests/test_consumer_ui.js`

- [ ] **Step 1: Add CSS expectations to the test**

Append this block before the final summary in `tests/test_consumer_ui.js`:

```javascript
console.log('\n=== Consumer styles ===');
const css = fs.readFileSync(path.join(ROOT, 'web', 'styles.css'), 'utf8');
assert(css.includes('.app-shell'), 'styles define app shell');
assert(css.includes('.tool-panel'), 'styles define tool panel');
assert(css.includes('.result-panel'), 'styles define result panel');
assert(css.includes('@media'), 'styles include responsive rules');
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
node tests/test_consumer_ui.js
```

Expected: FAIL if the old stylesheet does not define the consumer classes.

- [ ] **Step 3: Replace `web/styles.css`**

Replace `web/styles.css` with:

```css
:root {
  --bg: #f6f7f9;
  --surface: #ffffff;
  --surface-soft: #eef3f7;
  --text: #17202a;
  --muted: #617080;
  --border: #d8e0e8;
  --primary: #1f7a5c;
  --primary-dark: #155f47;
  --danger: #b42318;
  --warning: #a15c00;
  --shadow: 0 12px 30px rgba(22, 34, 51, 0.08);
  --radius: 8px;
  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font-family: var(--font);
  line-height: 1.5;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 20px 32px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 10;
}

.app-header h1 {
  margin: 0;
  font-size: 24px;
}

.app-header p {
  margin: 4px 0 0;
  color: var(--muted);
}

.top-nav {
  display: flex;
  gap: 8px;
}

.nav-btn,
.primary-btn,
.secondary-btn,
.ghost-btn {
  min-height: 40px;
  border-radius: 6px;
  border: 1px solid var(--border);
  padding: 0 16px;
  background: var(--surface);
  color: var(--text);
  font: inherit;
  cursor: pointer;
}

.nav-btn.active,
.primary-btn {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}

.primary-btn:hover {
  background: var(--primary-dark);
}

.secondary-btn {
  border-color: var(--primary);
  color: var(--primary);
}

.ghost-btn {
  background: transparent;
}

.app-shell {
  width: min(1180px, calc(100vw - 32px));
  margin: 24px auto 48px;
}

.view {
  display: none;
}

.view.active {
  display: block;
}

.work-area {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(360px, 0.9fr);
  gap: 20px;
  align-items: start;
}

.tool-panel,
.result-panel,
.records-panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 24px;
}

.section-heading span,
.eyebrow {
  color: var(--primary);
  font-size: 13px;
  font-weight: 700;
}

.section-heading h2,
.empty-state h2,
.result-card h2 {
  margin: 4px 0 8px;
  font-size: 22px;
}

.section-heading p,
.empty-state p,
.disclaimer {
  margin: 0 0 20px;
  color: var(--muted);
}

.form-grid {
  display: grid;
  gap: 16px;
}

.two-cols {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

label {
  display: grid;
  gap: 6px;
  margin-bottom: 16px;
  font-weight: 700;
}

input,
select,
textarea {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px 12px;
  color: var(--text);
  background: #fff;
  font: inherit;
}

textarea {
  resize: vertical;
}

input:focus,
select:focus,
textarea:focus {
  outline: 2px solid rgba(31, 122, 92, 0.18);
  border-color: var(--primary);
}

.form-actions {
  display: flex;
  gap: 10px;
  margin-top: 8px;
}

.result-card section {
  border-top: 1px solid var(--border);
  padding-top: 14px;
  margin-top: 14px;
}

.result-card h3 {
  margin: 0 0 8px;
  font-size: 15px;
}

.result-card ul {
  margin: 0;
  padding-left: 20px;
}

.result-card li + li {
  margin-top: 6px;
}

.result-card.danger {
  border-left: 4px solid var(--danger);
}

.disclaimer {
  margin-top: 18px;
  padding: 12px;
  border-radius: 6px;
  background: var(--surface-soft);
}

.records-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.record-item {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
  background: #fff;
}

.record-item span {
  color: var(--primary);
  font-size: 13px;
  font-weight: 700;
}

.record-item h3 {
  margin: 4px 0 10px;
}

.record-item p {
  margin: 6px 0;
  color: var(--muted);
}

@media (max-width: 860px) {
  .app-header {
    align-items: stretch;
    flex-direction: column;
    padding: 18px;
  }

  .top-nav {
    overflow-x: auto;
  }

  .app-shell {
    width: min(100vw - 20px, 1180px);
    margin-top: 12px;
  }

  .work-area,
  .two-cols,
  .records-list {
    grid-template-columns: 1fr;
  }

  .tool-panel,
  .result-panel,
  .records-panel {
    padding: 18px;
  }
}
```

- [ ] **Step 4: Run the consumer test**

Run:

```bash
node tests/test_consumer_ui.js
```

Expected: PASS.

- [ ] **Step 5: Commit styling**

```bash
git add web/styles.css tests/test_consumer_ui.js
git commit -m "style: add consumer A-share assistant layout"
```

## Task 6: Documentation Update

**Files:**
- Modify: `README.md`
- Modify: `docs/ui.md`

- [ ] **Step 1: Write a failing documentation check**

Add this block before the final summary in `tests/test_consumer_ui.js`:

```javascript
console.log('\n=== Consumer documentation ===');
const readme = fs.readFileSync(path.join(ROOT, 'README.md'), 'utf8');
const uiDoc = fs.readFileSync(path.join(ROOT, 'docs', 'ui.md'), 'utf8');
assert(readme.includes('A股投资检查助手'), 'README presents consumer product');
assert(readme.includes('买前检查'), 'README documents buy check');
assert(readme.includes('持仓体检'), 'README documents holding check');
assert(uiDoc.includes('A股投资检查助手'), 'UI docs present consumer UI');
assert(uiDoc.includes('当前版本只支持国内A股股票和场内ETF'), 'UI docs document A-share-only scope');
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
node tests/test_consumer_ui.js
```

Expected: FAIL because README and UI docs still describe the professional workstation first.

- [ ] **Step 3: Update README introduction and quick start**

Modify the top of `README.md` so it starts with this consumer-first copy:

```markdown
# A股投资检查助手

一个完全本地运行的个人投资风险检查工具，面向国内 A 股股票和场内 ETF。它不荐股、不自动交易、不承诺收益；它只帮你在买入前或持仓中把理由、仓位、亏损承受范围和下一步检查项说清楚。

## 最快开始

```bash
python3 -m invest_signal_kit serve --port 8765
```

打开：

```text
http://127.0.0.1:8765
```

第一次使用建议从三个入口开始：

1. **买前检查**：输入股票/ETF代码、名称、买入理由、信息来源、准备投入金额、总资金、最多能接受亏损和放弃条件。
2. **持仓体检**：输入已持有代码、成本价、当前价、持有金额和继续持有理由，检查仓位和亏损风险。
3. **检查记录**：回看保存在当前浏览器里的检查结果，避免只靠临时情绪做决定。

当前消费者页面只面向国内 A 股股票和场内 ETF。旧的 JSON、回测、蒙特卡洛、组合优化等能力属于高级/开发者工具，不是普通用户的默认入口。
```

Keep existing install and CLI documentation below an "高级与开发者说明" heading.

- [ ] **Step 4: Replace `docs/ui.md` with consumer UI documentation**

Replace `docs/ui.md` with:

```markdown
# A股投资检查助手 Web UI

这个 Web UI 面向国内 A 股个人用户。它不是交易软件，不荐股，不承诺收益，也不连接券商账户。它只帮助用户把一次买入想法或一次持仓复查整理成清晰的风险检查。

## 入口

- **买前检查**：准备买某只 A 股股票或场内 ETF 前使用。
- **持仓体检**：已经持有某只 A 股股票或场内 ETF 时使用。
- **检查记录**：查看保存在当前浏览器里的最近检查。

## 买前检查

用户需要填写：

- 股票/ETF代码
- 名称
- 你为什么想买
- 消息从哪里来
- 准备投入多少钱
- 总投资资金
- 最多能接受亏多少
- 打算持有多久
- 什么情况你会放弃这次买入

输出包括：

- 结论
- 主要原因
- 风险线
- 需要补充的信息
- 下一步
- 风险提醒

## 持仓体检

用户需要填写：

- 持有代码
- 名称
- 买入成本
- 当前价格
- 持有金额
- 总投资资金
- 当初为什么买
- 现在还想继续持有的理由
- 最多还能接受亏多少

输出包括：

- 当前状态
- 仓位提醒
- 亏损提醒
- 继续持有前要确认的事
- 可执行动作
- 风险提醒

## 市场范围

当前版本只支持国内A股股票和场内ETF。消费者页面使用 6 位代码作为基础检查；如果输入 TSLA、AAPL、MSFT 等非国内市场代码，会提示用户输入 6 位 A股/ETF 代码。

## 数据与隐私

检查记录只保存在当前浏览器 localStorage 中，不会上传，也不会生成交易订单。
```

- [ ] **Step 5: Run tests**

Run:

```bash
node tests/test_consumer_ui.js
python3 -m unittest tests.test_all
node tests/test_web_import.js
```

Expected: all PASS.

- [ ] **Step 6: Commit docs**

```bash
git add README.md docs/ui.md tests/test_consumer_ui.js
git commit -m "docs: describe consumer A-share workflow"
```

## Task 7: Browser Verification And Final Check

**Files:**
- No production file expected unless verification finds a defect.

- [ ] **Step 1: Start the local server**

Run:

```bash
python3 -m invest_signal_kit serve --port 8765
```

Expected: server prints `Serving web UI at http://127.0.0.1:8765`.

- [ ] **Step 2: Open the page in the browser**

Use the Browser plugin or Playwright-equivalent local browser automation to open:

```text
http://127.0.0.1:8765
```

Expected visual checks:

- First screen shows `A股投资检查助手`.
- First visible workflow is `买前检查`.
- Navigation shows `买前检查`, `持仓体检`, `检查记录`.
- Main page does not show `JSON`, `Signal Lab`, `Monte Carlo`, or `Optimizer`.

- [ ] **Step 3: Exercise buy-check interaction**

Fill:

- 股票/ETF代码: `600519`
- 名称: `贵州茅台`
- 你为什么想买: `看了公告或财报`
- 理由: `收入和利润保持增长，想等回调后观察。`
- 消息来源: `官方公告或财报`
- 准备投入: `20000`
- 总投资资金: `200000`
- 最多能接受亏损: `3000`
- 持有多久: `3-6个月`
- 放弃条件: `业绩不及预期或跌破计划风险线`

Click `开始检查`.

Expected: result shows `结论`, `主要原因`, `风险线`, `需要补充的信息`, `下一步`, and the disclaimer.

- [ ] **Step 4: Exercise A-share scope error**

Change code to `TSLA` and submit.

Expected: result shows `当前版本只支持国内A股股票和场内ETF，请输入6位A股/ETF代码。`

- [ ] **Step 5: Exercise holding-check interaction**

Open `持仓体检` and fill:

- 持有代码: `600519`
- 名称: `贵州茅台`
- 买入成本: `1800`
- 当前价格: `1620`
- 持有金额: `70000`
- 总投资资金: `200000`
- 当初为什么买: `长期看好高端白酒`
- 现在还想继续持有的理由: `理由没有变化，但仓位较大`
- 最多还能接受亏损: `8000`

Click `开始体检`.

Expected: result shows `当前状态`, `仓位提醒`, `亏损提醒`, `继续持有前要确认的事`, `可执行动作`, and disclaimer.

- [ ] **Step 6: Run full verification**

Run:

```bash
node tests/test_consumer_ui.js
node tests/test_web_import.js
python3 -m unittest tests.test_all
git status --short
```

Expected:

- All tests PASS.
- `git status --short` only shows intentional uncommitted changes, or is clean after final commit.

- [ ] **Step 7: Final commit if verification fixes were needed**

If browser verification required fixes:

```bash
git add web/index.html web/styles.css web/consumer.js tests/test_consumer_ui.js README.md docs/ui.md
git commit -m "fix: polish consumer A-share assistant"
```

If no fixes were needed, do not create an empty commit.

## Plan Self-Review

Spec coverage:

- Consumer positioning: Task 3, Task 5, Task 6.
- Clear buy-check UI: Task 3 and Task 4.
- Clear holding-check UI: Task 3 and Task 4.
- No JSON primary workflow: Task 1 page-shell assertions and Task 3.
- Domestic A-share-only scope: Task 1 rule assertions, Task 2 implementation, Task 6 docs.
- Hide redundant professional functions from default UI: Task 1 assertions and Task 3 removing `app.js` from default page.
- Records: Task 3 and Task 4.
- Testing and browser verification: Task 1 through Task 7.

Placeholder scan:

- No deferred-detail instructions are present. HTML `placeholder` attributes in code samples are intentional user-facing input hints.
- Each task has exact files, commands, and expected results.

Type consistency:

- The plan consistently uses `ConsumerApp`, `evaluateBuyCheck`, `evaluateHoldingCheck`, `renderBuyResultHtml`, `renderHoldingResultHtml`, `loadRecords`, and `saveRecord`.
