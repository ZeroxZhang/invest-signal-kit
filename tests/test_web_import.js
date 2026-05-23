#!/usr/bin/env node
// Smoke test: extract import functions from web/app.js and exercise them in Node VM.
// Run: node tests/test_web_import.js

'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const appPath = path.join(__dirname, '..', 'web', 'app.js');
const code = fs.readFileSync(appPath, 'utf8');

// Extract the Import & Scenario Builder section from the DOMContentLoaded closure.
// This section contains: IMPORT_PRICES_EXAMPLE, IMPORT_SIGNALS_EXAMPLE,
// IMPORT_BENCH_EXAMPLE, parseCsv, parseCsvFloat, importPricesCsv,
// importSignalsCsv, buildScenario — all self-contained with no DOM dependencies.
const sectionStart = code.indexOf('const IMPORT_PRICES_EXAMPLE');
const sectionEnd = code.indexOf('function setStatus');
if (sectionStart === -1 || sectionEnd === -1) {
  console.error('Cannot locate import section in web/app.js');
  process.exit(1);
}
const importCode = code.substring(sectionStart, sectionEnd);

const ctx = vm.createContext({});
vm.runInContext(importCode, ctx);

// ---- helpers -----------------------------------------------------------
let passed = 0;
let failed = 0;
function assert(cond, msg) {
  if (cond) { passed++; console.log('  PASS: ' + msg); }
  else      { failed++; console.log('  FAIL: ' + msg); }
}

// ---- Test 1: multi-asset price CSV import ------------------------------
console.log('\n=== Test 1: importPricesCsv multi-asset ===');
const pricesCsv = [
  'date,asset,open,high,low,close,volume',
  '2026-01-02,AAPL,180,183,179,182,50000000',
  '2026-01-03,AAPL,182,185,181,184,48000000',
  '2026-01-06,AAPL,184,188,183,187,52000000',
  '2026-01-07,AAPL,187,190,186,189,47000000',
  '2026-01-08,AAPL,189,192,188,191,51000000',
  '2026-01-09,AAPL,191,193,190,192,46000000',
  '2026-01-12,AAPL,192,195,191,194,49000000',
  '2026-01-13,AAPL,194,196,193,195,45000000',
  '2026-01-14,AAPL,195,197,194,196,44000000',
  '2026-01-15,AAPL,196,198,195,197,47000000',
  '2026-01-02,MSFT,365,368,363,366,30000000',
  '2026-01-03,MSFT,366,370,365,369,28000000',
  '2026-01-06,MSFT,369,375,368,373,32000000',
  '2026-01-07,MSFT,373,378,372,376,29000000',
  '2026-01-08,MSFT,376,382,375,379,31000000',
  '2026-01-09,MSFT,379,384,378,382,27000000',
  '2026-01-12,MSFT,382,388,381,386,33000000',
  '2026-01-13,MSFT,386,390,384,388,26000000',
  '2026-01-14,MSFT,388,392,387,390,28000000',
  '2026-01-15,MSFT,390,394,389,392,30000000',
  '2026-01-02,TSLA,245,250,243,248,40000000',
  '2026-01-03,TSLA,248,253,246,251,38000000',
  '2026-01-06,TSLA,251,256,249,254,42000000',
  '2026-01-07,TSLA,254,260,253,258,39000000',
  '2026-01-08,TSLA,258,264,257,262,41000000',
  '2026-01-09,TSLA,262,267,260,265,37000000',
  '2026-01-12,TSLA,265,270,263,268,43000000',
  '2026-01-13,TSLA,268,272,266,270,36000000',
  '2026-01-14,TSLA,270,274,268,272,38000000',
  '2026-01-15,TSLA,272,276,270,274,40000000',
].join('\n');

const pRes = ctx.importPricesCsv(pricesCsv);
assert(pRes.errors.length === 0, 'no import errors');
assert(pRes.data.length === 30, '30 price rows imported (3 assets x 10 days)');

const aaplRows = pRes.data.filter(r => r.asset === 'AAPL');
const msftRows = pRes.data.filter(r => r.asset === 'MSFT');
const tslaRows = pRes.data.filter(r => r.asset === 'TSLA');
assert(aaplRows.length === 10, '10 AAPL rows');
assert(msftRows.length === 10, '10 MSFT rows');
assert(tslaRows.length === 10, '10 TSLA rows');
assert(pRes.data.every(r => r.asset), 'every row has asset field');
assert(aaplRows[0].close === 182, 'first AAPL close = 182');

// ---- Test 2: duplicate date per asset is rejected ----------------------
console.log('\n=== Test 2: duplicate date per asset rejected ===');
const dupCsv = 'date,asset,close\n2026-01-02,AAPL,100\n2026-01-02,AAPL,200\n';
const dupRes = ctx.importPricesCsv(dupCsv);
assert(dupRes.errors.length === 1, 'duplicate (asset,date) produces 1 error');
assert(dupRes.errors[0].includes('duplicate date'), 'error mentions duplicate date');

// ---- Test 3: same date different assets allowed ------------------------
console.log('\n=== Test 3: same date different assets allowed ===');
const multiCsv = 'date,asset,close\n2026-01-02,AAPL,100\n2026-01-02,MSFT,200\n2026-01-02,TSLA,300\n';
const multiRes = ctx.importPricesCsv(multiCsv);
assert(multiRes.errors.length === 0, 'no errors for same date, different assets');
assert(multiRes.data.length === 3, '3 rows imported');

// ---- Test 4: single-asset CSV (no asset column) still works -----------
console.log('\n=== Test 4: single-asset CSV (no asset column) ===');
const singleDupCsv = 'date,close\n2026-01-02,100\n2026-01-03,101\n2026-01-02,102\n';
const singleDupRes = ctx.importPricesCsv(singleDupCsv);
assert(singleDupRes.errors.length === 1, 'duplicate date without asset column is still rejected');
assert(singleDupRes.data === null, 'data is null when errors exist');

const singleCsv = 'date,close\n2026-01-02,100\n2026-01-03,101\n';
const singleRes = ctx.importPricesCsv(singleCsv);
assert(singleRes.data.length === 2, 'single-asset CSV imports correctly');
assert(!singleRes.data[0].asset, 'no asset field when column absent');

// ---- Test 5: signals CSV import ----------------------------------------
console.log('\n=== Test 5: importSignalsCsv ===');
const signalsCsv = [
  'date,asset,action,quantity,price,reason,confidence,stop_price,target_price,time_stop_days',
  '2026-01-02,AAPL,enter,100,,Breakout above resistance with volume confirmation,80,175,200,15',
  '2026-01-06,MSFT,enter,50,,Earnings momentum play with sector tailwind,75,360,400,20',
  '2026-01-07,TSLA,enter,,,Low confidence speculative entry,35,240,280,',
  '2026-01-08,MSFT,add,25,,Adding on confirmed breakout,70,,,',
  '2026-01-09,AAPL,exit,,,Taking profits ahead of macro event,0,,,',
].join('\n');
const sRes = ctx.importSignalsCsv(signalsCsv);
assert(sRes.errors.length === 0, 'no signal import errors');
assert(sRes.data.length === 5, '5 signal events');

// ---- Test 6: buildScenario multi-asset ----------------------------------
console.log('\n=== Test 6: buildScenario multi-asset ===');
const scenario = ctx.buildScenario(
  pRes.data, sRes.data, [],
  { capital: 100000, commission: 1, slippage: 5, maxPos: 25, maxDd: 20, minConf: 60, assetName: 'IMPORTED' }
);
const assetKeys = Object.keys(scenario.price_series);
assert(assetKeys.length === 3, 'scenario has 3 assets');
assert(assetKeys.includes('AAPL'), 'price_series includes AAPL');
assert(assetKeys.includes('MSFT'), 'price_series includes MSFT');
assert(assetKeys.includes('TSLA'), 'price_series includes TSLA');
assert(scenario.price_series['AAPL'].length === 10, 'AAPL has 10 bars');
assert(scenario.price_series['MSFT'].length === 10, 'MSFT has 10 bars');
assert(scenario.price_series['TSLA'].length === 10, 'TSLA has 10 bars');
assert(scenario.signal_events.length === 5, '5 signal events in scenario');
assert(scenario.initial_capital === 100000, 'initial capital 100000');
assert(!scenario.price_series['AAPL'][0].asset, 'asset field stripped from price_series entries');

// ---- Test 7: embedded example matches fixture CSV ----------------------
console.log('\n=== Test 7: embedded example equals fixture CSV ===');
// const/let declarations don't leak to vm context, so re-evaluate with var.
// Replace const/let with var so declarations become context properties in vm.
const evalCode = importCode.replace(/\bconst /g, 'var ').replace(/\blet /g, 'var ');
const ctx2 = vm.createContext({});
vm.runInContext(evalCode, ctx2);

const fixturePrices = fs.readFileSync(path.join(__dirname, '..', 'examples', 'prices.csv'), 'utf8').replace(/\s+$/, '');
const fixtureSignals = fs.readFileSync(path.join(__dirname, '..', 'examples', 'signals.csv'), 'utf8').replace(/\s+$/, '');
const embeddedPrices = ctx2.IMPORT_PRICES_EXAMPLE.replace(/\s+$/, '');
const embeddedSignals = ctx2.IMPORT_SIGNALS_EXAMPLE.replace(/\s+$/, '');
assert(embeddedPrices === fixturePrices, 'IMPORT_PRICES_EXAMPLE matches examples/prices.csv');
assert(embeddedSignals === fixtureSignals, 'IMPORT_SIGNALS_EXAMPLE matches examples/signals.csv');

// ---- Test 8: syntax check ----------------------------------------------
console.log('\n=== Test 8: syntax check ===');
try {
  new Function(code);
  assert(true, 'app.js passes syntax check');
} catch (e) {
  assert(false, 'app.js syntax error: ' + e.message);
}

// ---- Summary -----------------------------------------------------------
console.log('\n' + '='.repeat(50));
console.log('Results: ' + passed + ' passed, ' + failed + ' failed');
if (failed > 0) process.exit(1);
