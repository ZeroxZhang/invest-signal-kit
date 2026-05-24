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
    const estimatedLossAmount = currentPrice > 0 ? holdingAmount * Math.max(0, costPrice / currentPrice - 1) : 0;

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
      lossWarning.push('当前估算亏损距离你设置的风险线还有一定空间，但仍要按计划复查。');
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

  function getStorage(storage) {
    if (storage) return storage;
    try {
      return root.localStorage || null;
    } catch (_) {
      return null;
    }
  }

  function loadRecords(storage) {
    const store = getStorage(storage);
    if (!store) return [];
    try {
      const raw = store.getItem('aShareCheckRecords');
      return raw ? JSON.parse(raw) : [];
    } catch (_) {
      return [];
    }
  }

  function saveRecord(record, storage) {
    const store = getStorage(storage);
    if (!store || !record) return [];
    const records = loadRecords(store);
    const next = [{ ...record, createdAt: new Date().toISOString() }, ...records].slice(0, 20);
    try {
      store.setItem('aShareCheckRecords', JSON.stringify(next));
    } catch (_) {
      return records;
    }
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
