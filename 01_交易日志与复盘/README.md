# 01 交易日志与复盘

这个目录用于整理最近 30 笔交易，并把主观交易结果转成可以统计的样本。

## 文件

- `trade_log_template.csv`：交易日志模板。先复制一份再填写真实交易，避免覆盖原始模板。
- `analyze_trades.py`：读取交易日志并输出基础统计，包括总 R、平均 R、胜率、按 setup / market 拆分表现等。
- `trade_log_web.py`：本地填写页面。通过浏览器填表，并自动追加到 `my_trade_log.csv`。
- `charts/`：保存入场、出场和复盘标注后的 K 线截图。

## 推荐使用方式

### 方式一：用本地页面填写

1. 启动页面：

   ```powershell
   python trade_log_web.py
   ```

2. 打开浏览器访问：

   ```text
   http://127.0.0.1:8008
   ```

3. 在页面里填写交易记录并保存。记录会自动追加到 `my_trade_log.csv`。

### 方式二：手动编辑 CSV

1. 复制模板：

   ```powershell
   Copy-Item trade_log_template.csv my_trade_log.csv
   ```

2. 填写最近 30 笔交易。数据不完整时可以先估算，但要在 `notes` 字段说明。

3. 把 K 线截图放到 `charts/` 目录，并在 CSV 里填写相对路径，例如：

   ```text
   charts/2026-06-24_crypto_BTCUSDT_breakout_range_entry.png
   ```

4. 运行统计脚本：

   ```powershell
   python analyze_trades.py my_trade_log.csv
   ```

## 字段提醒

- `计划风险金额` 是这笔交易入场前计划最多亏损的金额。
- `净盈亏` 是扣除手续费、滑点等成本后的实际盈亏。
- `R倍数` 可以手动填写；如果留空，脚本会尝试用 `净盈亏 / 计划风险金额` 自动计算。
- `交易状态` 建议填写 `持仓中`、`已出场` 或 `已取消`。统计脚本默认只统计 `已出场` 的交易。
- `是否按计划执行` 建议填写 `是` 或 `否`。
- `入场截图` 是入场时或刚入场时的 K 线截图路径。
- `出场截图` 是出场时的 K 线截图路径。
- `复盘截图` 是复盘时标注过的截图路径，可以暂时留空。

脚本同时兼容旧版英文表头，例如 `planned_risk_amount`、`net_pnl`、`result_r`、`followed_plan`。

## 截图命名建议

建议使用这种格式：

```text
YYYY-MM-DD_市场_品种_setup_阶段.png
```

例如：

```text
charts/2026-06-24_crypto_BTCUSDT_breakout_range_entry.png
charts/2026-06-24_crypto_BTCUSDT_breakout_range_exit.png
charts/2026-06-24_crypto_BTCUSDT_breakout_range_review.png
```

入场图最好在交易当时保存，不要等结果出来后再补截图。这样能减少后视偏差。

## 风险提醒

这个目录只用于学习、研究和复盘，不构成投资建议。不要把少量样本的结果当成稳定优势，更不要因为短期结果扩大仓位或使用高杠杆。
