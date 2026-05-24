# A股投资检查助手

`invest-signal-kit` 现在默认面向个人投资者使用：它是一个本地运行的 **A股投资检查助手**，帮助你在买入前或持仓中，把理由、资金占比、可承受亏损和放弃条件先说清楚。

默认 Web 页面只有三个入口：**买前检查**、**持仓体检**、**检查记录**。当前版本**只支持国内A股股票和场内ETF**，只做风险检查和信息完整性提醒，**不构成投资建议**，不会荐股、不会自动下单、不会承诺收益。检查记录只保存在你的本机浏览器。

## 这个工具适合谁

- 你是个人投资者，想在买 A 股或场内 ETF 前先冷静检查一次。
- 你能填写 6 位股票/ETF 代码、名称、准备投入金额、总资金和最多能接受亏多少。
- 你希望系统用普通中文指出：理由是否说清楚、仓位是否太集中、信息来源是否太弱、风险线是否明确。
- 你不需要专业终端、券商账户连接、实时行情、自动交易或收益预测。

## 你可以做什么

### 买前检查

用于准备买入前的检查。

你输入：

- 股票/ETF代码
- 名称
- 你为什么想买
- 消息从哪里来
- 准备投入多少钱
- 总投资资金
- 最多能接受亏多少
- 打算持有多久
- 什么情况你会放弃这次买入

系统输出：

- 结论：暂缓、继续观察、条件满足后再考虑、风险过高
- 主要原因：为什么给出这个结论
- 风险线：这次最多愿意亏多少、仓位占比大不大
- 需要补充的信息：哪些信息还不够可靠
- 下一步：先补信息、降低投入、继续观察或暂缓
- 风险提醒：结果只做风险检查，不构成投资建议

### 持仓体检

用于已经买入后的复查。

你输入：

- 持有代码/名称
- 买入成本
- 当前价格
- 持有金额
- 总投资资金
- 当初为什么买
- 现在还想继续持有的理由
- 最多还能接受亏多少

系统输出：

- 当前状态：正常观察、仓位偏重、亏损接近风险线、理由已经失效
- 仓位提醒：持仓金额占总资金的比例
- 亏损提醒：当前价格相对成本的变化和剩余风险承受空间
- 继续持有前要确认的事
- 可执行动作：继续观察、减小仓位、重新检查理由、停止加仓
- 风险提醒：这不是买卖建议

### 检查记录

你可以把一次买前检查或持仓体检保存为记录，方便以后回看当时的理由和风险线。

记录包含：

- 检查类型：买前检查或持仓体检
- 代码和名称
- 创建时间
- 结论或状态
- 主要原因
- 风险线
- 下一步

记录只保存在本机浏览器的本地存储里，不会上传服务器，不会同步到云端，也不会生成订单或交易记录。

## 快速开始

### 方式一：直接打开网页

在浏览器中打开：

```text
web/index.html
```

这是一个静态页面，不需要构建步骤。

### 方式二：启动本地服务

```bash
python3 -m invest_signal_kit serve --port 8765
```

然后打开：

```text
http://127.0.0.1:8765
```

页面打开后，默认进入“买前检查”。你可以先填一个 6 位 A 股或场内 ETF 代码，例如 `600519` 或 `510300`。

## 本地与隐私

- Web 页面在本机浏览器里运行。
- 不需要 API key。
- 不连接券商账户。
- 不读取你的真实账户。
- 不获取实时行情。
- 检查记录只保存在当前浏览器本地。
- 清理浏览器站点数据会删除本地检查记录。

## 产品边界

这个项目的输出是“风险检查”和“信息完整性提醒”，不是投资建议。

它会帮助你发现这些问题：

- 代码不是 6 位国内 A 股或场内 ETF 代码。
- 买入理由太空泛。
- 信息只来自朋友转述或社交平台。
- 单次投入占总资金比例太高。
- 没写清楚什么情况会放弃。
- 持仓亏损已经接近自己能承受的风险线。
- 继续持有的理由和当初买入理由不一致。

它不会做这些事：

- 不推荐具体买哪只股票或 ETF。
- 不告诉你一定可以买、卖或持有。
- 不预测收益。
- 不自动交易。
- 不替代你自己的判断。

## 安装

如果只想看 Web 页面，可以直接打开 `web/index.html`。如果想使用本地服务命令，先安装项目：

```bash
git clone https://github.com/ZeroxZhang/invest-signal-kit.git
cd invest-signal-kit
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install .
```

项目运行时只使用 Python 标准库。

## 文档入口

- [docs/ui.md](docs/ui.md)：面向普通用户的 Web 页面说明。
- [docs/usage.md](docs/usage.md)：命令行使用方式。
- [docs/framework.md](docs/framework.md)：保留的研究框架说明。
- [docs/portfolio.md](docs/portfolio.md)：组合风险工作流。
- [docs/rebalance.md](docs/rebalance.md)：再平衡和交易计划。
- [docs/backtest.md](docs/backtest.md)：回放和历史检验工作流。
- [docs/monte_carlo.md](docs/monte_carlo.md)：风险路径模拟。
- [docs/optimizer.md](docs/optimizer.md)：组合优化实验。

普通用户建议先看 [docs/ui.md](docs/ui.md)。后面的命令行和研究框架文档主要留给开发者或高级用户。

## 高级/开发者入口

仓库里仍保留原来的 Python 命令行能力，方便开发者做结构化研究、报告生成和批量测试。它们不是默认的消费者使用路径。

常用命令：

```bash
# 启动本地 Web 页面
python3 -m invest_signal_kit serve --port 8765

# 校验结构化研究文件
python3 -m invest_signal_kit validate examples/etf_signal.json

# 生成 Markdown 报告
python3 -m invest_signal_kit render examples/etf_signal.json --output out.md

# 运行保留的研究框架
python3 -m invest_signal_kit framework examples/professional_signal.json
```

安装后也可以使用 console script：

```bash
invest-signal-kit serve --port 8765
invest-signal-kit validate examples/etf_signal.json
```

## 开发与测试

运行消费者 Web UI smoke test：

```bash
node tests/test_consumer_ui.js
```

运行 Python unittest 包装测试：

```bash
python3 -m unittest tests.test_consumer_ui_runner -v
```

运行完整测试：

```bash
python3 -m unittest discover -s tests -v
```

## 免责声明

本项目只用于个人投资流程整理、风险检查和学习，不是投资顾问服务、证券研究报告、交易系统、收益承诺或任何形式的买卖建议。所有输出都应该被理解为“帮你检查自己是否把理由和风险说清楚”的提示。真实投资决策需要你独立判断，并自行承担风险。
