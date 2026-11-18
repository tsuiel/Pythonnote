"""扩展4 · 一键生成离线可视化数据报告（单文件 HTML，可直接打印为 PDF）。

报告与看板共用 metrics / charts，口径完全一致；Plotly.js 内联，断网也能打开。
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from plotly.offline import get_plotlyjs

sys.path.insert(0, str(Path(__file__).resolve().parent))

import charts
import metrics
from config import EXPORT_DIR, PALETTE, THEMES

_CSS = """
:root{--bg:#0B1424;--panel:#111F34;--text:#E8F1FF;--muted:#8FA6C4;--line:#23395A}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
 font-family:"Microsoft YaHei","PingFang SC",Segoe UI,sans-serif;padding:32px 5vw 60px}
.wrap{max-width:1440px;margin:0 auto}
header{border-bottom:1px solid var(--line);padding-bottom:20px;margin-bottom:26px}
h1{font-size:28px;margin:0 0 8px;letter-spacing:1px}
.sub{color:var(--muted);font-size:13px}
h2{font-size:18px;margin:34px 0 14px;padding-left:12px;border-left:4px solid #22D3EE}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px}
.kpi .lab{color:var(--muted);font-size:12px}
.kpi .val{font-size:26px;font-weight:700;margin-top:8px;color:#22D3EE}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(520px,1fr));gap:16px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:10px;overflow:hidden}
table{width:100%;border-collapse:collapse;font-size:12px}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{color:var(--muted);background:#16243A}
tbody tr:hover{background:#16243A}
.note{margin-top:34px;color:var(--muted);font-size:12px;line-height:1.9;
 border-top:1px solid var(--line);padding-top:16px}
@media print{body{background:#fff;color:#111}.kpi,.card,th{background:#fff;color:#111}
 .kpi .val{color:#0B6E9E}h2{border-color:#0B6E9E}}
"""


def _fig_html(fig) -> str:
    return fig.to_html(full_html=False, include_plotlyjs=False,
                       config={"displayModeBar": False, "responsive": True})


def build_html_report(view: pd.DataFrame, k: dict, start, end,
                      *, theme_name: str = "暗色科技风") -> str:
    theme = THEMES[theme_name]
    cat = metrics.by_dimension(view, "商品品类")
    ch = metrics.by_dimension(view, "销售渠道")
    reg = metrics.by_dimension(view, "销售区域")
    ts = metrics.time_series(view, "D")
    heat = metrics.weekday_category_heatmap(view)
    radar = metrics.radar_data(view)
    rank = metrics.ranking(view, "商品名称", 8)

    figures = [
        charts.line_trend(ts, "日销售额趋势与 7 日均线", theme),
        charts.bar_comparison(cat, "商品品类", "各品类销售额对比", theme),
        charts.donut_share(ch, "销售渠道", "渠道销售额占比", theme),
        charts.ranking_bar(rank, "商品名称", "商品销售额 TOP8 排行榜", theme),
        charts.heatmap_weekday(heat, theme) if not heat.empty else charts.bar_comparison(reg, "销售区域", "区域销售额", theme),
        charts.radar_category(radar, theme) if not radar.empty else charts.profit_scatter(cat, theme),
        charts.gauge_target(k["目标达成率"], theme),
        charts.profit_scatter(cat, theme),
    ]
    cards = "\n".join(f'<div class="card">{_fig_html(f)}</div>' for f in figures)

    kpi_items = [
        ("销售额", f"¥{k['销售额']:,.0f}"), ("有效订单", f"{k['订单量']:,}"),
        ("客单价", f"¥{k['客单价']:,.0f}"), ("利润", f"¥{k['利润']:,.0f}"),
        ("利润率", f"{k['利润率']:.2f}%"), ("退款率", f"{k['退款率']:.2f}%"),
        ("环比增长", "—" if k["环比增长率"] is None else f"{k['环比增长率']:+.2f}%"),
        ("目标达成率", f"{k['目标达成率']:.2f}%"),
    ]
    kpi_html = "\n".join(
        f'<div class="kpi"><div class="lab">{lab}</div><div class="val">{val}</div></div>'
        for lab, val in kpi_items
    )
    detail = metrics.detail_table(view).head(30).copy()
    detail["销售额"] = detail["销售额"].map(lambda v: f"{v:,.2f}")
    detail["利润"] = detail["利润"].map(lambda v: f"{v:,.2f}")
    table_html = detail.to_html(index=False, escape=False, border=0)

    warn_html = "".join(
        f'<li>{a["指标"]}：{a["消息"]}</li>' for a in k["预警"]
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>星云商城经营数据报告 {k['区间']}</title>
<style>{_CSS}</style><script>{get_plotlyjs()}</script></head>
<body><div class="wrap">
<header><h1>星云商城 · 经营数据可视化报告</h1>
<div class="sub">统计区间：{k['区间']} ｜ 生成时间：{datetime.now():%Y-%m-%d %H:%M:%S} ｜ 数据源：sales_clean.csv（含实时订单流）</div></header>
<h2>一、核心指标</h2><div class="kpis">{kpi_html}</div>
<h2>二、图表分析</h2><div class="grid">{cards}</div>
<h2>三、预警结论</h2><ul style="color:var(--muted);font-size:13px;line-height:2">{warn_html}</ul>
<h2>四、明细数据（最近 30 条）</h2><div class="card" style="overflow-x:auto">{table_html}</div>
<div class="note">
数据口径：销售额 / 利润 / 订单量仅统计「已完成」订单；退款率 = 退款单数 / 有效订单数；
环比对比上一等长周期；区间销售目标按天数比例折算。<br>
原始 1272 行数据经 9 条清洗规则剔除 72 行脏数据后得到 1200 行有效订单，清洗日志见 data/cleaning_report.json。<br>
本报告由实验2工程 src/export_report.py 自动生成，与 Streamlit 看板共用同一套指标函数，数值完全一致。
</div></div></body></html>"""


def save_report(view: pd.DataFrame, k: dict, start, end,
                path: Path | None = None) -> Path:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    p = Path(path) if path else EXPORT_DIR / f"可视化数据报告_{datetime.now():%Y%m%d_%H%M%S}.html"
    p.write_text(build_html_report(view, k, start, end), encoding="utf-8")
    return p


if __name__ == "__main__":
    from preprocess import load_clean
    df = load_clean()
    s, e = df["日期_dt"].min(), df["日期_dt"].max()
    kk = metrics.kpis(df, df, start=s, end=e)
    out = save_report(df, kk, s, e, EXPORT_DIR / "可视化数据报告_全量.html")
    print(f"报告已生成：{out}（{out.stat().st_size / 1024 / 1024:.2f} MB）")
