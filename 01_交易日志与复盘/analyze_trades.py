"""Analyze a simple trade log.

This script is for education and research only. It does not provide
investment advice, trading signals, or return promises.

Usage:
    python analyze_trades.py my_trade_log.csv
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean


REQUIRED_COLUMNS = {
    "trade_id",
    "date",
    "market",
    "setup",
    "planned_risk_amount",
    "net_pnl",
    "result_r",
    "followed_plan",
}

FIELD_ALIASES = {
    "trade_id": ("trade_id", "交易ID", "交易编号"),
    "date": ("date", "日期"),
    "market": ("market", "市场"),
    "status": ("status", "交易状态", "状态"),
    "setup": ("setup", "交易形态", "形态", "Setup"),
    "planned_risk_amount": ("planned_risk_amount", "计划风险金额", "计划风险"),
    "net_pnl": ("net_pnl", "净盈亏", "实际盈亏"),
    "result_r": ("result_r", "R倍数", "R 倍数"),
    "followed_plan": ("followed_plan", "是否按计划执行", "按计划执行"),
    "entry_chart_path": ("entry_chart_path", "入场截图", "入场图"),
    "exit_chart_path": ("exit_chart_path", "出场截图", "出场图"),
    "review_chart_path": ("review_chart_path", "复盘截图", "复盘图"),
}

CHART_PATH_COLUMNS = (
    "entry_chart_path",
    "exit_chart_path",
    "review_chart_path",
)


@dataclass(frozen=True)
class Trade:
    trade_id: str
    date: str
    market: str
    status: str
    setup: str
    planned_risk_amount: float
    net_pnl: float
    result_r: float
    result_r_available: bool
    followed_plan: str
    entry_chart_path: str = ""
    exit_chart_path: str = ""
    review_chart_path: str = ""


def parse_float(value: str, default: float = 0.0) -> float:
    value = value.strip()
    if not value:
        return default
    return float(value)


def normalize_text(value: str, fallback: str = "unknown") -> str:
    value = value.strip()
    return value if value else fallback


def build_header_map(fieldnames: list[str]) -> dict[str, str]:
    header_map: dict[str, str] = {}
    for canonical_name, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if alias in fieldnames:
                header_map[canonical_name] = alias
                break
    return header_map


def get_cell(row: dict[str, str], header_map: dict[str, str], canonical_name: str) -> str:
    actual_name = header_map.get(canonical_name)
    if actual_name is None:
        return ""
    return row.get(actual_name, "").strip()


def is_yes(value: str) -> bool:
    return value.strip().lower() in {"yes", "y", "true", "1", "是", "按计划", "执行"}


def is_no(value: str) -> bool:
    return value.strip().lower() in {"no", "n", "false", "0", "否", "未按计划", "没按计划"}


def infer_status(status_text: str, result_r_text: str, net_pnl_text: str) -> str:
    if status_text:
        return status_text
    if result_r_text or net_pnl_text:
        return "已出场"
    return "持仓中"


def is_closed(status: str) -> bool:
    return status.strip().lower() in {"已出场", "closed", "done", "完成", "结束"}


def is_open(status: str) -> bool:
    return status.strip().lower() in {"持仓中", "open", "holding", "进行中"}


def load_trades(path: Path) -> list[Trade]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError("CSV 文件为空，未找到表头。")

        header_map = build_header_map(reader.fieldnames)
        missing_columns = REQUIRED_COLUMNS - set(header_map)
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"CSV 缺少必要字段：{missing}")

        trades: list[Trade] = []
        for row_number, row in enumerate(reader, start=2):
            planned_risk_amount = parse_float(get_cell(row, header_map, "planned_risk_amount"))
            net_pnl_text = get_cell(row, header_map, "net_pnl")
            net_pnl = parse_float(net_pnl_text)
            status = infer_status(
                get_cell(row, header_map, "status"),
                get_cell(row, header_map, "result_r"),
                net_pnl_text,
            )

            result_r_text = get_cell(row, header_map, "result_r")
            result_r_available = bool(result_r_text or net_pnl_text)
            if result_r_text:
                result_r = parse_float(result_r_text)
            elif planned_risk_amount > 0 and net_pnl_text:
                result_r = net_pnl / planned_risk_amount
            else:
                result_r = 0.0

            if is_closed(status) and not result_r_available:
                print(f"提醒：第 {row_number} 行已出场但未填写净盈亏或R倍数，暂不进入R统计。")
            elif result_r_available and planned_risk_amount <= 0 and not result_r_text:
                print(f"提醒：第 {row_number} 行 planned_risk_amount <= 0，R 倍数可能无效。")

            trades.append(
                Trade(
                    trade_id=normalize_text(
                        get_cell(row, header_map, "trade_id"),
                        fallback=str(row_number - 1),
                    ),
                    date=normalize_text(get_cell(row, header_map, "date")),
                    market=normalize_text(get_cell(row, header_map, "market")),
                    status=status,
                    setup=normalize_text(get_cell(row, header_map, "setup")),
                    planned_risk_amount=planned_risk_amount,
                    net_pnl=net_pnl,
                    result_r=result_r,
                    result_r_available=result_r_available,
                    followed_plan=normalize_text(get_cell(row, header_map, "followed_plan")),
                    entry_chart_path=get_cell(row, header_map, "entry_chart_path"),
                    exit_chart_path=get_cell(row, header_map, "exit_chart_path"),
                    review_chart_path=get_cell(row, header_map, "review_chart_path"),
                )
            )

    return trades


def win_rate(trades: list[Trade]) -> float:
    if not trades:
        return 0.0
    wins = [trade for trade in trades if trade.result_r > 0]
    return len(wins) / len(trades)


def profit_factor(trades: list[Trade]) -> float | None:
    gross_profit = sum(trade.result_r for trade in trades if trade.result_r > 0)
    gross_loss = abs(sum(trade.result_r for trade in trades if trade.result_r < 0))
    if gross_loss == 0:
        return None
    return gross_profit / gross_loss


def max_drawdown_r(trades: list[Trade]) -> float:
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0

    for trade in trades:
        equity += trade.result_r
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)

    return max_drawdown


def group_by(trades: list[Trade], field_name: str) -> dict[str, list[Trade]]:
    grouped: dict[str, list[Trade]] = defaultdict(list)
    for trade in trades:
        grouped[getattr(trade, field_name)].append(trade)
    return dict(grouped)


def print_summary(title: str, trades: list[Trade]) -> None:
    if not trades:
        return

    total_r = sum(trade.result_r for trade in trades)
    average_r = mean(trade.result_r for trade in trades)
    worst_r = min(trade.result_r for trade in trades)
    best_r = max(trade.result_r for trade in trades)
    pf = profit_factor(trades)
    pf_text = "无亏损样本" if pf is None else f"{pf:.2f}"

    print(f"\n{title}")
    print("-" * len(title))
    print(f"交易笔数：{len(trades)}")
    print(f"总 R：{total_r:.2f}")
    print(f"平均 R：{average_r:.2f}")
    print(f"胜率：{win_rate(trades):.1%}")
    print(f"最好单笔：{best_r:.2f}R")
    print(f"最差单笔：{worst_r:.2f}R")
    print(f"最大回撤：{max_drawdown_r(trades):.2f}R")
    print(f"Profit Factor：{pf_text}")


def print_status_summary(trades: list[Trade]) -> None:
    closed = [trade for trade in trades if is_closed(trade.status)]
    open_trades = [trade for trade in trades if is_open(trade.status)]
    other = len(trades) - len(closed) - len(open_trades)

    print("\n交易状态")
    print("========")
    print(f"全部记录：{len(trades)} 笔")
    print(f"已出场：{len(closed)} 笔")
    print(f"持仓中：{len(open_trades)} 笔")
    if other:
        print(f"其他状态：{other} 笔")


def print_grouped_summary(trades: list[Trade], field_name: str, title: str) -> None:
    print(f"\n{title}")
    print("=" * len(title))

    for group_name, group_trades in sorted(group_by(trades, field_name).items()):
        total_r = sum(trade.result_r for trade in group_trades)
        average_r = mean(trade.result_r for trade in group_trades)
        print(
            f"{group_name}: "
            f"笔数={len(group_trades)}, "
            f"总R={total_r:.2f}, "
            f"平均R={average_r:.2f}, "
            f"胜率={win_rate(group_trades):.1%}"
        )


def print_execution_summary(trades: list[Trade]) -> None:
    followed = [trade for trade in trades if is_yes(trade.followed_plan)]
    not_followed = [trade for trade in trades if is_no(trade.followed_plan)]

    print("\n执行纪律")
    print("========")
    print(f"按计划执行：{len(followed)} 笔")
    print(f"未按计划执行：{len(not_followed)} 笔")

    if followed:
        print(f"按计划执行平均R：{mean(trade.result_r for trade in followed):.2f}")
    if not_followed:
        print(f"未按计划执行平均R：{mean(trade.result_r for trade in not_followed):.2f}")


def resolve_chart_path(csv_path: Path, chart_path: str) -> Path:
    path = Path(chart_path)
    if path.is_absolute():
        return path
    return csv_path.parent / path


def print_chart_path_summary(trades: list[Trade], csv_path: Path) -> None:
    total_expected = 0
    existing = 0
    missing: list[tuple[str, str, str]] = []

    for trade in trades:
        for column in CHART_PATH_COLUMNS:
            chart_path = getattr(trade, column)
            if not chart_path:
                continue

            total_expected += 1
            resolved_path = resolve_chart_path(csv_path, chart_path)
            if resolved_path.exists():
                existing += 1
            else:
                missing.append((trade.trade_id, column, chart_path))

    print("\nK线截图路径")
    print("==========")
    print(f"已填写截图路径：{total_expected}")
    print(f"可找到文件：{existing}")
    print(f"缺失文件：{len(missing)}")

    if missing:
        print("缺失明细：")
        for trade_id, column, chart_path in missing[:10]:
            print(f"- trade_id={trade_id}, {column}={chart_path}")
        if len(missing) > 10:
            print(f"- 还有 {len(missing) - 10} 个缺失路径未显示")


def main() -> int:
    if len(sys.argv) != 2:
        print("用法：python analyze_trades.py <trade_log.csv>")
        return 1

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"找不到文件：{path}")
        return 1

    try:
        trades = load_trades(path)
    except (OSError, ValueError) as error:
        print(f"读取失败：{error}")
        return 1

    if not trades:
        print("没有可统计的交易记录。")
        return 0

    closed_trades = [trade for trade in trades if is_closed(trade.status)]
    closed_trades_with_result = [
        trade for trade in closed_trades if trade.result_r_available
    ]
    closed_trades_missing_result = len(closed_trades) - len(closed_trades_with_result)

    print_status_summary(trades)
    if closed_trades_with_result:
        if closed_trades_missing_result:
            print(f"\n已出场但结果待补：{closed_trades_missing_result} 笔")
        print_summary("已出场交易统计", closed_trades_with_result)
        print_grouped_summary(closed_trades_with_result, "setup", "按 setup 拆分")
        print_grouped_summary(closed_trades_with_result, "market", "按 market 拆分")
        print_execution_summary(closed_trades_with_result)
    else:
        print("\n已出场交易统计")
        print("==============")
        print("还没有可统计R的已出场交易；当前持仓和结果待补记录不会进入胜率、平均 R 和回撤统计。")

    print_chart_path_summary(trades, path)

    print("\n提醒：这些统计只能帮助你发现问题，不能证明未来收益。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
