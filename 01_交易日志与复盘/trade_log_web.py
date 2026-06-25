"""A tiny local web form for maintaining the trade log.

This tool is intentionally simple and dependency-free. It runs only on
127.0.0.1 by default, writes submitted records to my_trade_log.csv, and is
for education / research review only.

Usage:
    python trade_log_web.py
"""

from __future__ import annotations

import csv
import html
import io
import subprocess
import sys
import urllib.parse
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "my_trade_log.csv"
ANALYZE_SCRIPT = BASE_DIR / "analyze_trades.py"
HOST = "127.0.0.1"
PORT = 8008

HEADERS = [
    "交易ID",
    "日期",
    "市场",
    "品种",
    "周期",
    "方向",
    "交易状态",
    "交易形态",
    "入场截图",
    "出场截图",
    "复盘截图",
    "入场理由",
    "失效条件",
    "入场价",
    "止损价",
    "出场价",
    "数量",
    "计划风险金额",
    "手续费滑点",
    "净盈亏",
    "R倍数",
    "是否按计划执行",
    "主要错误",
    "情绪标签",
    "备注",
]


def ensure_csv_exists() -> None:
    if CSV_PATH.exists():
        with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames == HEADERS:
                return

            rows = list(reader)

        with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=HEADERS)
            writer.writeheader()
            for row in rows:
                normalized_row = {header: row.get(header, "") for header in HEADERS}
                if not normalized_row["交易状态"]:
                    if normalized_row["R倍数"].strip() or normalized_row["净盈亏"].strip():
                        normalized_row["交易状态"] = "已出场"
                    else:
                        normalized_row["交易状态"] = "持仓中"
                writer.writerow(normalized_row)
        return

    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=HEADERS)
        writer.writeheader()


def read_rows() -> list[dict[str, str]]:
    ensure_csv_exists()
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return list(reader)


def next_trade_id(rows: list[dict[str, str]]) -> str:
    ids: list[int] = []
    for row in rows:
        value = row.get("交易ID", "").strip()
        if value.isdigit():
            ids.append(int(value))
    return str(max(ids, default=0) + 1)


def parse_float(value: str) -> float | None:
    value = value.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def format_number(value: float | None) -> str:
    if value is None:
        return ""
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text if text else "0"


def normalize_chart_path(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if "/" in value or "\\" in value:
        return value.replace("\\", "/")
    return f"charts/{value}"


def compute_fields(row: dict[str, str]) -> None:
    entry_price = parse_float(row["入场价"])
    stop_price = parse_float(row["止损价"])
    exit_price = parse_float(row["出场价"])
    quantity = parse_float(row["数量"])
    fees_slippage = parse_float(row["手续费滑点"]) or 0.0

    if not row["计划风险金额"].strip() and None not in (entry_price, stop_price, quantity):
        planned_risk = abs(entry_price - stop_price) * quantity  # type: ignore[operator]
        row["计划风险金额"] = format_number(planned_risk)

    if not row["净盈亏"].strip() and None not in (entry_price, exit_price, quantity):
        direction = row["方向"].strip()
        if direction in {"做空", "short", "空"}:
            gross_pnl = (entry_price - exit_price) * quantity  # type: ignore[operator]
        else:
            gross_pnl = (exit_price - entry_price) * quantity  # type: ignore[operator]
        row["净盈亏"] = format_number(gross_pnl - fees_slippage)

    planned_risk_amount = parse_float(row["计划风险金额"])
    net_pnl = parse_float(row["净盈亏"])
    if not row["R倍数"].strip() and planned_risk_amount and net_pnl is not None:
        row["R倍数"] = format_number(net_pnl / planned_risk_amount)


def append_row(row: dict[str, str]) -> None:
    ensure_csv_exists()
    with CSV_PATH.open("a", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=HEADERS)
        writer.writerow(row)


def field_value(params: dict[str, list[str]], name: str) -> str:
    return params.get(name, [""])[0].strip()


def build_row(params: dict[str, list[str]]) -> dict[str, str]:
    rows = read_rows()
    row = {header: field_value(params, header) for header in HEADERS}

    if not row["交易ID"]:
        row["交易ID"] = next_trade_id(rows)
    if not row["日期"]:
        row["日期"] = date.today().isoformat()
    if not row["交易状态"]:
        if row["出场价"] or row["净盈亏"] or row["R倍数"]:
            row["交易状态"] = "已出场"
        else:
            row["交易状态"] = "持仓中"

    row["入场截图"] = normalize_chart_path(row["入场截图"])
    row["出场截图"] = normalize_chart_path(row["出场截图"])
    row["复盘截图"] = normalize_chart_path(row["复盘截图"])

    compute_fields(row)
    return row


def escape(value: str) -> str:
    return html.escape(value, quote=True)


def option(value: str, selected: str = "") -> str:
    selected_attr = " selected" if value == selected else ""
    return f'<option value="{escape(value)}"{selected_attr}>{escape(value)}</option>'


def input_field(label: str, name: str, value: str = "", field_type: str = "text") -> str:
    step_attr = ' step="any"' if field_type == "number" else ""
    return (
        f'<label><span>{escape(label)}</span>'
        f'<input type="{field_type}" name="{escape(name)}" value="{escape(value)}"{step_attr}></label>'
    )


def textarea_field(label: str, name: str) -> str:
    return f'<label class="wide"><span>{escape(label)}</span><textarea name="{escape(name)}"></textarea></label>'


def select_field(label: str, name: str, values: list[str]) -> str:
    options = "".join(option(value) for value in values)
    return f'<label><span>{escape(label)}</span><select name="{escape(name)}">{options}</select></label>'


def render_recent_rows(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "<p class=\"muted\">还没有记录。先填第一笔，给未来的自己一点证据。</p>"

    lines = []
    for row in rows[-10:][::-1]:
        lines.append(
            "<tr>"
            f"<td>{escape(row.get('交易ID', ''))}</td>"
            f"<td>{escape(row.get('日期', ''))}</td>"
            f"<td>{escape(row.get('市场', ''))}</td>"
            f"<td>{escape(row.get('品种', ''))}</td>"
            f"<td>{escape(row.get('交易状态', ''))}</td>"
            f"<td>{escape(row.get('交易形态', ''))}</td>"
            f"<td>{escape(row.get('R倍数', ''))}</td>"
            f"<td>{escape(row.get('是否按计划执行', ''))}</td>"
            "</tr>"
        )

    return (
        "<table><thead><tr>"
        "<th>ID</th><th>日期</th><th>市场</th><th>品种</th>"
        "<th>状态</th><th>形态</th><th>R</th><th>执行</th>"
        "</tr></thead><tbody>"
        + "".join(lines)
        + "</tbody></table>"
    )


def run_analysis() -> str:
    ensure_csv_exists()
    completed = subprocess.run(
        [sys.executable, str(ANALYZE_SCRIPT), str(CSV_PATH)],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    output = completed.stdout
    if completed.stderr:
        output += "\n" + completed.stderr
    return output.strip()


def render_page(message: str = "") -> bytes:
    rows = read_rows()
    analysis = run_analysis() if rows else "还没有交易记录。"
    message_html = f'<div class="message">{escape(message)}</div>' if message else ""

    body = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>交易日志填写</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7fb;
      --card: #ffffff;
      --text: #182033;
      --muted: #667085;
      --line: #d8deea;
      --primary: #2854d8;
      --soft: #eef3ff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      padding: 28px;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
    }}
    main {{ max-width: 1180px; margin: 0 auto; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    h2 {{ margin-top: 0; }}
    p {{ line-height: 1.7; }}
    .muted {{ color: var(--muted); }}
    .grid {{ display: grid; grid-template-columns: 1.5fr 1fr; gap: 18px; align-items: start; }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 20px;
      box-shadow: 0 10px 28px rgba(30, 41, 59, 0.06);
    }}
    form {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }}
    label {{ display: flex; flex-direction: column; gap: 6px; font-size: 14px; color: var(--muted); }}
    label.wide {{ grid-column: span 3; }}
    input, select, textarea {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px 12px;
      font: inherit;
      color: var(--text);
      background: #fff;
    }}
    textarea {{ min-height: 76px; resize: vertical; }}
    .actions {{ grid-column: span 3; display: flex; gap: 10px; flex-wrap: wrap; }}
    button, .button {{
      border: 0;
      border-radius: 12px;
      padding: 11px 16px;
      background: var(--primary);
      color: #fff;
      font: inherit;
      cursor: pointer;
      text-decoration: none;
      display: inline-block;
    }}
    .button.secondary {{ background: var(--soft); color: var(--primary); }}
    .message {{
      margin: 16px 0;
      padding: 12px 14px;
      background: #ecfdf3;
      color: #027a48;
      border: 1px solid #abefc6;
      border-radius: 12px;
    }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 8px 6px; text-align: left; }}
    pre {{
      white-space: pre-wrap;
      background: #101828;
      color: #e4e7ec;
      border-radius: 14px;
      padding: 14px;
      overflow: auto;
      font-size: 13px;
      line-height: 1.55;
    }}
    .hint {{ background: var(--soft); border-radius: 14px; padding: 12px 14px; }}
    @media (max-width: 900px) {{
      body {{ padding: 16px; }}
      .grid {{ grid-template-columns: 1fr; }}
      form {{ grid-template-columns: 1fr; }}
      label.wide, .actions {{ grid-column: span 1; }}
    }}
  </style>
</head>
<body>
<main>
  <h1>交易日志填写</h1>
  <p class="muted">本页面只在本机运行，用来做学习、研究和复盘记录，不提供投资建议。</p>
  {message_html}

  <div class="grid">
    <section class="card">
      <h2>新增一笔交易</h2>
      <form method="post" action="/add">
        {input_field("日期", "日期", date.today().isoformat(), "date")}
        {select_field("市场", "市场", ["币圈", "美股", "A股", "其他"])}
        {input_field("品种", "品种", "", "text")}

        {select_field("周期", "周期", ["6小时", "4小时", "日线", "1小时", "30分钟", "周线", "其他"])}
        {select_field("方向", "方向", ["做多", "做空"])}
        {select_field("交易状态", "交易状态", ["持仓中", "已出场", "已取消"])}

        {select_field("交易形态", "交易形态", ["箱体突破", "杯柄突破", "均线回踩", "其他"])}
        <div></div>
        <div></div>

        {input_field("入场价", "入场价", "", "number")}
        {input_field("止损价", "止损价", "", "number")}
        {input_field("出场价", "出场价", "", "number")}

        {input_field("数量", "数量", "", "number")}
        {input_field("计划风险金额", "计划风险金额", "", "number")}
        {input_field("手续费滑点", "手续费滑点", "0", "number")}

        {input_field("净盈亏", "净盈亏", "", "number")}
        {input_field("R倍数", "R倍数", "", "number")}
        {select_field("是否按计划执行", "是否按计划执行", ["是", "否"])}

        {input_field("入场截图", "入场截图", "", "text")}
        {input_field("出场截图", "出场截图", "", "text")}
        {input_field("复盘截图", "复盘截图", "", "text")}

        {select_field("主要错误", "主要错误", ["", "无明显错误", "提前入场", "追高", "提前止盈", "止损变形", "报复交易", "无计划交易", "仓位过大", "其他"])}
        {select_field("情绪标签", "情绪标签", ["冷静", "FOMO", "恐惧", "贪婪", "犹豫", "冲动", "复仇", "其他"])}

        {textarea_field("入场理由", "入场理由")}
        {textarea_field("失效条件", "失效条件")}
        {textarea_field("备注", "备注")}

        <div class="actions">
          <button type="submit">保存到 CSV</button>
          <a class="button secondary" href="/csv">下载 CSV</a>
          <a class="button secondary" href="/analyze">只看统计</a>
        </div>
      </form>
    </section>

    <aside class="card">
      <h2>填写提示</h2>
      <div class="hint">
        <p>截图可以只填文件名，例如 <code>btc-entry.png</code>，系统会自动记录成 <code>charts/btc-entry.png</code>。</p>
        <p>如果你填写了入场价、止损价、出场价、数量，页面会在保存时自动补计划风险、净盈亏和 R 倍数。</p>
      </div>
      <h2>最近记录</h2>
      {render_recent_rows(rows)}
    </aside>
  </div>

  <section class="card" style="margin-top: 18px;">
    <h2>当前统计</h2>
    <pre>{escape(analysis)}</pre>
  </section>
</main>
</body>
</html>"""
    return body.encode("utf-8")


class TradeLogHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def send_bytes(self, content: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            params = urllib.parse.parse_qs(parsed.query)
            message = "保存成功，已经追加到 my_trade_log.csv。" if params.get("saved") else ""
            self.send_bytes(render_page(message), "text/html; charset=utf-8")
            return

        if parsed.path == "/csv":
            ensure_csv_exists()
            content = CSV_PATH.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="my_trade_log.csv"')
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        if parsed.path == "/analyze":
            content = f"<pre>{escape(run_analysis())}</pre>".encode("utf-8")
            self.send_bytes(content, "text/html; charset=utf-8")
            return

        self.send_bytes("Not Found".encode("utf-8"), "text/plain; charset=utf-8", HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/add":
            self.send_bytes("Not Found".encode("utf-8"), "text/plain; charset=utf-8", HTTPStatus.NOT_FOUND)
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length).decode("utf-8")
        params = urllib.parse.parse_qs(raw_body, keep_blank_values=True)
        row = build_row(params)
        append_row(row)
        self.redirect("/?saved=1")


def main() -> int:
    ensure_csv_exists()
    server = ThreadingHTTPServer((HOST, PORT), TradeLogHandler)
    print(f"交易日志页面已启动：http://{HOST}:{PORT}")
    print("按 Ctrl+C 停止。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
