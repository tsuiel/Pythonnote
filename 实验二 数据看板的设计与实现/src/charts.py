"""任务3/进阶3/扩展3 · Plotly 图表工厂。

所有图表只接收 metrics 层算好的 DataFrame，不自行读数据、不自行改口径；
统一由 apply_theme 注入明暗主题，保证整页视觉一致。
"""
from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import PALETTE, THEMES

FONT = "Microsoft YaHei, PingFang SC, Segoe UI, sans-serif"


def apply_theme(fig: go.Figure, theme: dict, height: int = 330) -> go.Figure:
    fig.update_layout(
        template=theme["plotly_template"],
        height=height,
        font=dict(family=FONT, size=12, color=theme["text"]),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=12, r=12, t=38, b=12),
        hoverlabel=dict(bgcolor=theme["panel2"], font_size=12,
                        font_family=FONT, font_color=theme["text"]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                    font=dict(size=11, color=theme["muted"])),
        title=dict(font=dict(size=14, color=theme["text"]), x=0.01, y=0.97),
    )
    fig.update_xaxes(gridcolor=theme["grid"], zerolinecolor=theme["grid"],
                     linecolor=theme["border"], tickfont=dict(color=theme["muted"]))
    fig.update_yaxes(gridcolor=theme["grid"], zerolinecolor=theme["grid"],
                     linecolor=theme["border"], tickfont=dict(color=theme["muted"]))
    return fig


def bar_comparison(g, col: str, title: str, theme: dict, height: int = 330) -> go.Figure:
    """柱状图：分类数据对比（基础图表 ②）。"""
    fig = go.Figure(go.Bar(
        x=g[col], y=g["销售额"],
        marker=dict(color=g["销售额"], colorscale=[
            [0, PALETTE["secondary"]], [1, PALETTE["primary"]]],
            line=dict(width=0), cornerradius=6),
        text=[f"{v / 10000:.1f}万" for v in g["销售额"]],
        textposition="outside", textfont=dict(size=11, color=theme["text"]),
        customdata=g[["订单量", "利润"]],
        hovertemplate=f"<b>%{{x}}</b><br>销售额 ¥%{{y:,.0f}}<br>订单量 %{{customdata[0]}}<br>利润 ¥%{{customdata[1]:,.0f}}<extra></extra>",
    ))
    fig.update_layout(title=title, showlegend=False,
                      yaxis_title="销售额（元）", clickmode="event+select")
    return apply_theme(fig, theme, height)


def donut_share(g, col: str, title: str, theme: dict, height: int = 330) -> go.Figure:
    """环形图：占比结构（基础图表 ④）。"""
    fig = go.Figure(go.Pie(
        labels=g[col], values=g["销售额"], hole=0.58,
        marker=dict(colors=PALETTE["series"], line=dict(color=theme["bg"], width=2)),
        textinfo="label+percent", textfont=dict(size=11, color=theme["text"]),
        hovertemplate="<b>%{label}</b><br>销售额 ¥%{value:,.0f}<br>占比 %{percent}<extra></extra>",
    ))
    fig.update_layout(title=title, showlegend=False,
                      annotations=[dict(text="销售额<br>结构", x=0.5, y=0.5,
                                        font=dict(size=13, color=theme["muted"]),
                                        showarrow=False)])
    return apply_theme(fig, theme, height)


def line_trend(ts, title: str, theme: dict, freq: str = "D", height: int = 340) -> go.Figure:
    """折线图：时间趋势 + 7 日均线（基础图表 ③）。"""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=ts["日期"], y=ts["销售额"], name="销售额", mode="lines",
        line=dict(color=PALETTE["primary"], width=2.2, shape="spline", smoothing=0.4),
        fill="tozeroy", fillcolor="rgba(34,211,238,0.12)",
        hovertemplate="%{x|%Y-%m-%d}<br>销售额 ¥%{y:,.0f}<extra></extra>",
    ))
    if freq == "D" and "7日均线" in ts and ts["7日均线"].notna().any():
        fig.add_trace(go.Scatter(
            x=ts["日期"], y=ts["7日均线"], name="7 日均线", mode="lines",
            line=dict(color=PALETTE["accent"], width=2, dash="dot"),
            hovertemplate="%{x|%Y-%m-%d}<br>7 日均线 ¥%{y:,.0f}<extra></extra>",
        ))
    fig.update_layout(title=title, yaxis_title="销售额（元）", hovermode="x unified")
    return apply_theme(fig, theme, height)


def heatmap_weekday(pivot, theme: dict, height: int = 340) -> go.Figure:
    """热力图：星期 × 品类 销售分布（进阶3）。"""
    fig = go.Figure(go.Heatmap(
        z=pivot.values, x=list(pivot.columns), y=list(pivot.index),
        colorscale=[[0, theme["panel2"]], [0.35, "#1D6FA5"],
                    [0.7, PALETTE["primary"]], [1, PALETTE["accent"]]],
        hoverongaps=False, colorbar=dict(thickness=10, len=0.8,
                                         tickfont=dict(color=theme["muted"], size=10)),
        hovertemplate="%{y} · %{x}<br>销售额 ¥%{z:,.0f}<extra></extra>",
    ))
    fig.update_layout(title="星期 × 品类 销售热力图")
    return apply_theme(fig, theme, height)


def radar_category(norm, theme: dict, height: int = 340) -> go.Figure:
    """雷达图：品类五维能力对比（进阶3）。"""
    dims = ["销售额", "订单量", "客单价", "利润率", "评分"]
    labels = ["销售规模", "订单热度", "客单价", "盈利水平", "客户口碑"]
    fig = go.Figure()
    for i, row in norm.iterrows():
        vals = [float(row[d]) for d in dims]
        fig.add_trace(go.Scatterpolar(
            r=vals + [vals[0]], theta=labels + [labels[0]],
            fill="toself", fillcolor=f"rgba({_rgb(PALETTE['series'][i % len(PALETTE['series'])])},0.08)",
            line=dict(color=PALETTE["series"][i % len(PALETTE["series"])], width=2),
            name=str(row["商品品类"]),
            hovertemplate="%{theta}: %{r:.1f}<extra>" + str(row["商品品类"]) + "</extra>",
        ))
    fig.update_layout(
        title="品类五维能力雷达（归一化 0~100）",
        polar=dict(bgcolor="rgba(0,0,0,0)",
                   radialaxis=dict(visible=True, range=[0, 105],
                                   gridcolor=theme["grid"], tickfont=dict(size=9, color=theme["muted"])),
                   angularaxis=dict(gridcolor=theme["grid"], tickfont=dict(size=11, color=theme["text"]))),
        showlegend=True,
    )
    return apply_theme(fig, theme, height)


def gauge_target(rate: float, theme: dict, height: int = 260) -> go.Figure:
    """进度仪表盘：区间销售目标达成率（进阶3）。"""
    color = PALETTE["success"] if rate >= 80 else (PALETTE["accent"] if rate >= 60 else PALETTE["danger"])
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=min(rate, 150), number=dict(suffix="%", font=dict(size=30, color=theme["text"])),
        gauge=dict(axis=dict(range=[0, 150], tickwidth=1, tickcolor=theme["muted"],
                             tickfont=dict(color=theme["muted"], size=9)),
                   bar=dict(color=color, thickness=0.7),
                   bgcolor=theme["panel2"], borderwidth=0,
                   steps=[dict(range=[0, 60], color="rgba(248,113,113,0.16)"),
                          dict(range=[60, 100], color="rgba(245,158,11,0.14)"),
                          dict(range=[100, 150], color="rgba(52,211,153,0.16)")],
                   threshold=dict(line=dict(color=theme["text"], width=2), thickness=0.75, value=100)),
    ))
    fig.update_layout(title="销售目标达成率")
    return apply_theme(fig, theme, height)


def ranking_bar(g, col: str, title: str, theme: dict, height: int = 340) -> go.Figure:
    """排行榜：商品 / 区域 TOP N（进阶3）。"""
    d = g.sort_values("销售额")
    fig = go.Figure(go.Bar(
        x=d["销售额"], y=d[col], orientation="h",
        marker=dict(color=d["销售额"], colorscale=[
            [0, PALETTE["secondary"]], [1, PALETTE["primary"]]], cornerradius=5),
        text=[f"¥{v / 10000:.1f}万" for v in d["销售额"]],
        textposition="outside", textfont=dict(size=10, color=theme["text"]),
        hovertemplate="<b>%{y}</b><br>销售额 ¥%{x:,.0f}<extra></extra>",
    ))
    fig.update_layout(title=title, showlegend=False, xaxis_title="销售额（元）")
    return apply_theme(fig, theme, height)


def profit_scatter(g, theme: dict, height: int = 340) -> go.Figure:
    """散点图：品类销售额 vs 利润率，气泡大小表示订单量（扩展：多维度分析）。"""
    g = g.copy()
    if "利润率" not in g.columns:
        g["利润率"] = g["利润"] / g["销售额"] * 100
    fig = go.Figure(go.Scatter(
        x=g["销售额"], y=g["利润率"], mode="markers+text",
        marker=dict(size=g["订单量"] / g["订单量"].max() * 45 + 16,
                    color=g["利润"], colorscale="Tealgrn",
                    line=dict(color=theme["bg"], width=1.5), opacity=0.9),
        text=g["商品品类"], textposition="top center",
        textfont=dict(size=10, color=theme["text"]),
        customdata=g["订单量"],
        hovertemplate="<b>%{text}</b><br>销售额 ¥%{x:,.0f}<br>利润率 %{y:.2f}%<br>订单量 %{customdata}<extra></extra>",
    ))
    fig.update_layout(title="销售额 / 利润率 / 订单量 三维分析", showlegend=False,
                      xaxis_title="销售额（元）", yaxis_title="利润率（%）")
    return apply_theme(fig, theme, height)


def _rgb(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    return f"{int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)}"
