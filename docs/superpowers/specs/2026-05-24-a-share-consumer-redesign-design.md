# A-Share Consumer Redesign Design

Date: 2026-05-24

## Summary

Reposition the current project from a professional, JSON-first investment signal workstation into a clear consumer product for individual domestic A-share users. The product will become an "A股投资检查助手" that helps beginners check a buying idea or an existing holding with plain Chinese forms and plain Chinese results.

The product must not recommend stocks, automate trades, promise returns, or imply professional advisory service. Its job is to slow down impulsive decisions, make the user's reason and risk line explicit, and explain what information is missing before a user acts.

## Current Problem

The current web UI exposes professional concepts directly:

- Signal JSON input
- Signal Lab, Scorecards, Scenario & Sizing
- Portfolio, Rebalance, Backtest, Monte Carlo, Optimizer, Import & Build
- Internal labels such as action level, evidence level, invalidation condition, and framework analysis

This is useful for expert workflows but not understandable for a beginner personal investor. The user's stated requirement is that a normal consumer should clearly understand what to input, what the system outputs, and what each result means without seeing professional schema or JSON terminology.

## Target User

The target user is an individual domestic A-share investor with little or no investment process knowledge.

Assumptions:

- They understand stock and ETF codes, money amounts, and simple loss tolerance.
- They do not understand JSON, schemas, scorecards, Monte Carlo, optimizer, or backtest terminology.
- They want help deciding whether an A-share or listed ETF idea is worth watching, pausing, or checking further.
- They need clear warnings that the tool is not investment advice.

## Product Positioning

Product name in the UI: A股投资检查助手.

Primary promise:

> 填几项你能说清楚的信息，系统帮你检查这次买入或持仓有没有明显风险、缺什么信息、下一步该看什么。

Non-goals:

- Do not recommend a specific stock to buy.
- Do not connect to brokerage accounts.
- Do not fetch live quotes in the first version.
- Do not support non-mainland markets in the consumer UI.
- Do not expose JSON editing in the main consumer workflow.

## Recommended Product Shape

Use a consumer-first interface with three visible main entries:

1. 买前检查
2. 持仓体检
3. 检查记录

Professional tools may remain in the codebase, but they must not appear in the default consumer navigation. If retained in the web UI, they must be hidden behind an explicitly secondary "高级工具" entry that is collapsed or visually subordinate by default.

## Main Navigation

Default navigation:

- 买前检查
- 持仓体检
- 检查记录

Removed from the default navigation:

- Signal Lab
- Scorecards
- Scenario & Sizing
- Portfolio
- Rebalance
- Backtest
- Monte Carlo
- Optimizer
- Import & Build
- Examples

The first page shown on load is 买前检查.

## Buy Check Flow

Purpose: help a user check a potential A-share stock or listed ETF before buying.

### User Inputs

The form uses plain labels:

- 股票/ETF代码
- 名称
- 你为什么想买
- 消息从哪里来
- 准备投入多少钱
- 这笔钱大概占你总资金多少
- 最多能接受亏多少
- 打算持有多久
- 什么情况你会放弃这次买入

The code field accepts a 6-digit domestic stock or listed ETF code. Obvious foreign tickers such as TSLA, AAPL, and MSFT are rejected in the consumer flow.

### Reason Choices

The "你为什么想买" field provides a short choice list plus an optional free-text explanation:

- 看到新闻
- 看了公告或财报
- 看了研报
- 朋友推荐
- 价格上涨想追
- 长期看好
- 其他

### Source Choices

The "消息从哪里来" field uses consumer-readable source options:

- 官方公告或财报
- 券商研报
- 财经媒体
- 社交平台
- 朋友转述
- 自己观察价格

### Output

The result must be split into clear sections:

- 结论
- 主要原因
- 风险线
- 需要补充的信息
- 下一步
- 风险提醒

Allowed conclusion labels:

- 暂缓
- 继续观察
- 条件满足后再考虑
- 风险过高

No output section should require the user to understand JSON, schema validation, evidence levels, scorecards, or action levels.

## Holding Check Flow

Purpose: help a user check whether an existing holding has obvious position or loss-risk issues.

### User Inputs

- 持有代码/名称
- 买入成本
- 当前价格
- 持有金额
- 总投资资金
- 当初为什么买
- 现在还想继续持有的理由
- 最多还能接受亏多少

### Output

The result must be split into clear sections:

- 当前状态
- 仓位提醒
- 亏损提醒
- 继续持有前要确认的事
- 可执行动作
- 风险提醒

Allowed status labels:

- 正常观察
- 仓位偏重
- 亏损接近风险线
- 理由已经失效

Allowed action labels:

- 继续观察
- 减小仓位
- 重新检查理由
- 停止加仓

## Check Records

The product stores recent checks in browser-local storage only.

Each record contains:

- Type: 买前检查 or 持仓体检
- Code and name
- Created time
- Conclusion or status
- Key reasons
- Risk line
- Next step

Records are for user review only. They do not create orders or portfolio transactions.

## Mapping From Existing Professional Concepts

Existing internal concepts can be reused, but only behind consumer wording:

| Internal concept | Consumer wording |
| --- | --- |
| signal | 这次检查 |
| evidence | 信息来源 |
| evidence level | 信息可靠度 |
| confidence | 把握程度 |
| trigger condition | 什么情况再考虑买 |
| invalidation condition | 什么情况说明想错了 |
| max risk | 最多愿意亏多少 |
| action level | 结论 |
| framework analysis | 检查结果 |
| blocker | 主要问题 |

Consumer UI must not display internal field names such as `action_level`, `trigger_condition`, `invalidation_condition`, `evidence_level`, or `signal JSON`.

## Rules

### A-Share Scope

The consumer UI only supports domestic A-share stocks and listed ETFs. The first version validates the code format with a 6-digit code. It does not need to identify every exchange rule or fetch market data.

If the user enters a foreign ticker or non-6-digit code, show:

> 当前版本只支持国内A股股票和场内ETF，请输入6位A股/ETF代码。

### Buy Check Decision Rules

The first version can use deterministic, explainable rules:

- Missing code or name: block result and ask for the missing input.
- Missing buy reason: block result and ask the user to write one sentence.
- Missing abandon condition: conclusion should not be "条件满足后再考虑"; risk line is unclear.
- Prepared investment greater than available total funds: block result.
- Position share above 30 percent: mark risk high.
- Position share above 15 percent: warn that the amount may be too concentrated for a beginner.
- Source is friend referral or social platform only: ask the user to verify with announcement, financial report, or reliable media.
- User cannot accept any loss: conclusion should be 暂缓.
- Clear reason, reliable source, defined loss tolerance, and defined abandon condition: conclusion can be 条件满足后再考虑.

### Holding Check Rules

- Holding value greater than total funds: block result.
- Position share above 30 percent: status includes 仓位偏重.
- Current loss is close to or beyond acceptable loss: status includes 亏损接近风险线.
- Current holding reason is empty or contradicts the original reason: status includes 理由已经失效.
- Otherwise status can be 正常观察.

## Error Handling

Errors must be written as direct user guidance, not developer diagnostics.

Examples:

- 请先填写股票或ETF代码。
- 请写一句你为什么想买，不然系统没法帮你检查理由。
- 投入金额不能大于你的总资金。
- 最多能接受亏损要大于 0。
- 请写清楚什么情况你会放弃买入，否则风险线不明确。

Avoid:

- schema invalid
- validation failed
- missing required field
- invalid signal
- JSON parse error

## Visual Design Direction

The interface should feel like a clear personal finance tool, not a professional trading terminal.

Design principles:

- Light or neutral interface is preferred over the current dense dark workstation.
- Form sections should be visually grouped by user task.
- Inputs should use labels, short helper text, selects, and numeric fields.
- Result cards should be easy to scan and use plain Chinese headings.
- Avoid marketing hero pages; the first screen is the actual tool.
- Avoid decorative gradients and oversized slogans.

Primary first-screen layout:

- Header: A股投资检查助手
- Short disclaimer line: 只做风险检查，不荐股，不承诺收益。
- Left/main form: 买前检查
- Right/result panel: 检查结果
- Secondary tabs or buttons: 持仓体检, 检查记录

## Documentation Changes

Documentation should be updated after implementation so the README and UI docs describe the consumer product first.

The old expert workflow can remain documented as advanced or developer-oriented, but it should not be the first path presented to a normal user.

## Testing And Verification

Implementation must include verification for:

- The default consumer page does not expose JSON as the primary input.
- Default navigation does not show Signal Lab, Monte Carlo, Optimizer, or other expert-only tools.
- Buy check can be completed with plain form fields.
- Buy check output includes conclusion, reasons, risk line, missing information, next step, and risk disclaimer.
- Holding check can be completed with plain form fields.
- Holding check output includes status, position warning, loss warning, confirmation items, action, and risk disclaimer.
- Foreign ticker examples such as TSLA, AAPL, and MSFT are absent from the consumer example path.
- A non-6-digit code produces the domestic A-share scope message.
- Existing baseline tests still pass unless intentionally replaced by consumer UI tests.

## Implementation Boundaries

This design is a single focused redesign of the web consumer experience. It does not require changing the Python CLI behavior in the first implementation step.

The implementation should avoid broad backend refactors. It can reuse or leave existing professional JavaScript engines in place, but the consumer entry point and visible UI must satisfy the target user experience.
