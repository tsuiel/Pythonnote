"""实验2 · 星云商城经营数据看板（Streamlit + Pandas + Plotly）

四大模块：① 数据概览区 ② 维度统计区 ③ 趋势分析区 ④ 明细数据区
覆盖基础任务 1~5、进阶 1~3、扩展 1~5（详见 README / 实验报告）。

启动：streamlit run src/dashboard.py --server.port 8501
"""
from __future__ import annotations

import inspect
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

sys.path.insert(0, str(Path(__file__).resolve().parent))

import charts
import metrics
import realtime_feed
from config import (CHANNELS, CATEGORIES, CLEANING_REPORT, PALETTE, REFUND_ALERT,
                    REGIONS, SALES_TARGET, TARGET_ALERT, THEMES)
from export_report import build_html_report, save_report
from preprocess import DataCleaningError, load_clean

st.set_page_config(page_title="星云商城 · 经营数据看板", page_icon="📊",
                   layout="wide", initial_sidebar_state="expanded")

HAS_ON_SELECT = "on_select" in inspect.signature(st.plotly_chart).parameters
# Streamlit 1.5x 起 use_container_width 被 width="stretch" 取代；按版本自适应，避免弃用告警
STRETCH = ({"width": "stretch"}
           if "width" in inspect.signature(st.plotly_chart).parameters
           else {"use_container_width": True})

# ------------------------------------------------------------------ 样式
CSS_TEMPLATE = """
<style>
:root{
 --bg:__BG__; --panel:__PANEL__; --panel2:__PANEL2__; --text:__TEXT__;
 --muted:__MUTED__; --border:__BORDER__; --primary:__PRIMARY__;
}
.stApp{background:
 radial-gradient(1200px 600px at 12% -10%, rgba(34,211,238,.10), transparent 60%),
 radial-gradient(900px 500px at 92% 0%, rgba(167,139,250,.10), transparent 60%),
 var(--bg);}
.stApp::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;
 background-image:linear-gradient(var(--border) 1px,transparent 1px),
 linear-gradient(90deg,var(--border) 1px,transparent 1px);
 background-size:52px 52px;opacity:.16;}
.block-container{position:relative;z-index:1;padding-top:1.4rem;max-width:1900px}
[data-testid="stHeader"]{background:transparent!important}
[data-testid="stToolbar"],#MainMenu,footer,[data-testid="stDecoration"]{visibility:hidden}
[data-testid="stSidebar"]{background:#111C2E;border-right:1px solid #23395A}
[data-testid="stSidebar"] *{color:#E8F1FF}
[data-testid="stSidebar"] [data-baseweb="select"]>div,
[data-testid="stSidebar"] [data-baseweb="input"]{background:#16243A!important;color:#E8F1FF!important}
h1,h2,h3,h4,.stMarkdown p{color:var(--text)}
/* 覆盖 Streamlit 内置 base=dark 的文字色，保证亮色主题下标题/说明/指标是深字 */
.stApp [data-testid="stMarkdownContainer"] p,
.stApp [data-testid="stMarkdownContainer"] h1,
.stApp [data-testid="stMarkdownContainer"] h2,
.stApp [data-testid="stMarkdownContainer"] h3,
.stApp [data-testid="stMarkdownContainer"] h4,
.stApp [data-testid="stMetricValue"],
.stApp [data-testid="stMetricLabel"],
.stApp [data-testid="stWidgetLabel"] p{color:var(--text)}
.stApp [data-testid="stCaptionContainer"],
.stApp [data-testid="stCaptionContainer"] p{color:var(--muted)}
/* 侧边栏恒为深色，避免亮色主题下被上面的通用规则染成深字（深底深字不可读） */
.stApp [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
.stApp [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
.stApp [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p{color:#E8F1FF}
.hero{display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:12px;
 padding:18px 22px;border:1px solid var(--border);border-radius:16px;
 background:linear-gradient(120deg,var(--panel),var(--panel2));margin-bottom:8px;
 box-shadow:0 8px 30px rgba(0,0,0,.18)}
.hero h1{margin:0;font-size:28px;letter-spacing:2px;font-weight:800}
.hero .sub{color:var(--muted);font-size:12px;margin-top:6px;letter-spacing:.5px}
.hero .live{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:12px}
.dot{width:9px;height:9px;border-radius:50%;background:__SUCCESS__;
 box-shadow:0 0 10px __SUCCESS__;animation:pulse 1.6s infinite}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.45;transform:scale(.75)}}
.ticker{height:34px;overflow:hidden;border:1px solid var(--border);border-radius:10px;
 background:var(--panel);margin:10px 0 4px;padding:0 14px;display:flex;align-items:center;gap:12px}
.ticker .tag{font-size:11px;color:__ACCENT__;font-weight:700;white-space:nowrap;letter-spacing:1px}
.ticker .roll{height:34px;overflow:hidden;flex:1}
.ticker .roll-inner{animation:roll 16s linear infinite}
.ticker .roll-inner div{height:34px;line-height:34px;font-size:12px;color:var(--muted);
 white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
@keyframes roll{0%,22%{transform:translateY(0)}27%,47%{transform:translateY(-34px)}
 52%,72%{transform:translateY(-68px)}77%,97%{transform:translateY(-102px)}
 100%{transform:translateY(0)}}
.section{display:flex;align-items:center;gap:12px;margin:26px 0 12px}
.section .no{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;
 border-radius:8px;background:var(--primary);color:#04121E;font-weight:800;font-size:14px}
.section h3{margin:0;font-size:17px;letter-spacing:1px}
.section .line{flex:1;height:1px;background:linear-gradient(90deg,var(--border),transparent)}
.section .en{font-size:10px;color:var(--muted);letter-spacing:2px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(178px,1fr));gap:12px}
.kpi-card{background:linear-gradient(145deg,var(--panel),var(--panel2));
 border:1px solid var(--border);border-radius:14px;padding:15px 17px;position:relative;overflow:hidden;
 animation:rise .65s cubic-bezier(.2,.8,.2,1) both}
.kpi-card::after{content:"";position:absolute;right:-24px;top:-24px;width:80px;height:80px;
 border-radius:50%;background:var(--primary);opacity:.07}
.kpi-card .lab{font-size:12px;color:var(--muted);letter-spacing:.5px}
.kpi-card .val{font-size:25px;font-weight:800;margin-top:8px;letter-spacing:.5px;
 animation:rollnum .8s cubic-bezier(.2,.8,.2,1) both}
.kpi-card .sub{font-size:11px;color:var(--muted);margin-top:6px}
.kpi-card.alert{border-color:__DANGER__;box-shadow:0 0 0 1px __DANGER__ inset}
.kpi-card.alert .val{color:__DANGER__!important}
@keyframes rise{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}
@keyframes rollnum{from{opacity:0;transform:translateY(14px) scale(.94);filter:blur(3px)}
 to{opacity:1;transform:none;filter:none}}
.panel{background:var(--panel);border:1px solid var(--border);border-radius:14px;
 padding:12px 16px;animation:rise .7s ease both}
[data-testid="stPlotlyChart"]{background:var(--panel);border:1px solid var(--border);
 border-radius:14px;padding:8px 6px 2px;margin-bottom:10px;
 animation:rise .7s ease both;box-shadow:0 6px 22px rgba(0,0,0,.12)}
.cap{font-size:11px;color:var(--muted);padding:0 4px 8px;line-height:1.7}
.blink{animation:blink 1.1s ease-in-out infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.52}}
.alertbar{border-radius:10px;padding:10px 14px;margin:6px 0;font-size:13px;
 border:1px solid var(--border);background:var(--panel)}
.alertbar.danger{border-color:__DANGER__;color:__DANGER__}
.alertbar.warning{border-color:__ACCENT__;color:__ACCENT__}
.alertbar.ok{border-color:__SUCCESS__;color:__SUCCESS__}
.particle{position:fixed;width:4px;height:4px;border-radius:50%;background:var(--primary);
 opacity:.35;pointer-events:none;z-index:0;animation:float 14s linear infinite}
@keyframes float{from{transform:translateY(105vh)}to{transform:translateY(-10vh)}}
.foot{margin-top:30px;padding:16px 0;border-top:1px solid var(--border);
 color:var(--muted);font-size:11px;line-height:1.9}
@media(max-width:900px){
 .hero h1{font-size:21px}.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
 .kpi-card .val{font-size:20px}.block-container{padding:0 10px}}
@media(min-width:2000px){.block-container{max-width:2300px}.kpi-card .val{font-size:29px}}
</style>
"""


def inject_css(theme: dict) -> None:
    css = (CSS_TEMPLATE
           .replace("__BG__", theme["bg"]).replace("__PANEL__", theme["panel"])
           .replace("__PANEL2__", theme["panel2"]).replace("__TEXT__", theme["text"])
           .replace("__MUTED__", theme["muted"]).replace("__BORDER__", theme["border"])
           .replace("__PRIMARY__", PALETTE["primary"]).replace("__ACCENT__", PALETTE["accent"])
           .replace("__SUCCESS__", PALETTE["success"]).replace("__DANGER__", PALETTE["danger"]))
    st.markdown(css, unsafe_allow_html=True)
    st.markdown(
        "".join(f'<div class="particle" style="left:{x}%;animation-delay:{d}s;'
                f'animation-duration:{t}s"></div>'
                for x, d, t in [(7, 0, 15), (23, 3, 19), (48, 6, 17), (71, 2, 21), (89, 8, 16)]),
        unsafe_allow_html=True)


def section(no: str, zh: str, en: str, desc: str = "") -> None:
    st.markdown(
        f'<div class="section"><span class="no">{no}</span><h3>{zh}</h3>'
        f'<span class="en">{en}</span><span class="line"></span>'
        f'<span style="font-size:11px;color:var(--muted)">{desc}</span></div>',
        unsafe_allow_html=True)


def show(fig, key: str | None = None, selectable: bool = False):
    kwargs: dict = dict(STRETCH)
    if key:
        kwargs["key"] = key
    if selectable and HAS_ON_SELECT:
        kwargs["on_select"] = "rerun"
    try:
        return st.plotly_chart(fig, **kwargs)
    except TypeError:
        kwargs.pop("on_select", None)
        return st.plotly_chart(fig, **kwargs)


@st.cache_data(ttl=2, show_spinner=False)
def load_data(_tick: int = 0) -> pd.DataFrame:
    """读清洗结果并合并实时订单流；ttl=2s 保证自动刷新能取到新订单。"""
    return realtime_feed.merge_feed(load_clean())


def fmt_money(v: float) -> str:
    return f"¥{v / 10000:,.1f}万" if abs(v) >= 10000 else f"¥{v:,.0f}"


def kpi_cards(k: dict) -> None:
    growth = k["环比增长率"]
    gtxt = "上期无可比数据" if growth is None else f"较上一周期 {growth:+.2f}%"
    items = [
        ("销售额", fmt_money(k["销售额"]), gtxt, PALETTE["primary"], False),
        ("有效订单量", f"{k['订单量']:,}", f"有效记录 {k['有效订单数']:,} 条", PALETTE["secondary"], False),
        ("客单价", fmt_money(k["客单价"]), "销售额 / 已完成订单", PALETTE["primary"], False),
        ("利润", fmt_money(k["利润"]), f"利润率 {k['利润率']:.2f}%", PALETTE["success"], False),
        ("退款率", f"{k['退款率']:.2f}%", f"预警阈值 {st.session_state.get('refund_th', REFUND_ALERT):.1f}%",
         PALETTE["danger"] if k["退款率"] > st.session_state.get("refund_th", REFUND_ALERT) else PALETTE["accent"],
         k["退款率"] > st.session_state.get("refund_th", REFUND_ALERT)),
        ("目标达成率", f"{k['目标达成率']:.2f}%", f"区间目标 {fmt_money(k['区间目标'])}",
         PALETTE["danger"] if k["目标达成率"] < st.session_state.get("target_th", TARGET_ALERT) else PALETTE["accent"],
         k["目标达成率"] < st.session_state.get("target_th", TARGET_ALERT)),
    ]
    html = '<div class="kpis">' + "".join(
        f'<div class="kpi-card{" alert" if alert else ""}" style="animation-delay:{i * .06}s">'
        f'<div class="lab">{lab}</div><div class="val" style="color:{color}">{val}</div>'
        f'<div class="sub">{sub}</div></div>'
        for i, (lab, val, sub, color, alert) in enumerate(items)
    ) + "</div>"
    st.markdown(html, unsafe_allow_html=True)


def main() -> None:
    theme_name = st.session_state.get("theme", "暗色科技风")
    theme = THEMES[theme_name]
    inject_css(theme)

    try:
        df = load_data()
    except DataCleaningError as exc:
        st.error(f"数据未就绪：{exc}\n\n请先在项目根目录运行 `python run_all.py`。")
        st.stop()

    min_d, max_d = df["日期_dt"].min().date(), df["日期_dt"].max().date()

    # ---------------------------------------------------------- 侧边栏
    with st.sidebar:
        st.markdown("## ⚙️ 看板控制台")
        st.caption("筛选条件对所有图表 / KPI / 明细表同步生效")
        st.selectbox("🎨 主题", list(THEMES), key="theme")
        if st.session_state["theme"] != theme_name:   # 主题变更后立即用新配色重绘整页
            st.rerun()
        theme_name = st.session_state["theme"]
        theme = THEMES[theme_name]

        st.divider()
        dr = st.date_input("📅 统计日期区间", value=(min_d, max_d),
                           min_value=min_d, max_value=max_d, format="YYYY-MM-DD")
        if isinstance(dr, (list, tuple)) and len(dr) == 2:
            start, end = dr
        elif isinstance(dr, (list, tuple)) and len(dr) == 1:
            start = end = dr[0]
        else:
            start = end = min_d
        st.caption(f"区间 {start} ~ {end}（{(pd.Timestamp(end) - pd.Timestamp(start)).days + 1} 天）")

        # 图表点击联动：在 widget 实例化之前把待联动值写入 session_state
        pending = st.session_state.pop("_pending_category", None)
        if pending:
            st.session_state["f_category"] = pending
        cats = st.multiselect("🏷️ 商品品类", CATEGORIES, key="f_category",
                              on_change=lambda: st.session_state.pop("_linked", None))
        regs = st.multiselect("🗺️ 销售区域", REGIONS, key="f_region")
        chs = st.multiselect("🛒 销售渠道", CHANNELS, key="f_channel")
        kw = st.text_input("🔍 订单号 / 商品名关键词", key="f_keyword")
        freq_label = st.radio("📈 趋势粒度", ["按日", "按周", "按月"], horizontal=True)
        freq = {"按日": "D", "按周": "W", "按月": "M"}[freq_label]

        st.divider()
        st.markdown("##### 🔴 扩展：实时与预警")
        live = st.checkbox("启用模拟实时数据流", value=False, key="live")
        interval = st.slider("自动刷新间隔（秒）", 5, 60, 15, 5, key="interval")
        auto = st.checkbox("启用页面自动刷新", value=False, key="auto")
        target = st.number_input("全周期销售目标（元）", value=float(SALES_TARGET),
                                 step=100000.0, min_value=10000.0)
        refund_th = st.slider("退款率预警阈值（%）", 0.0, 30.0, REFUND_ALERT, 0.5)
        target_th = st.slider("目标达成率预警阈值（%）", 0.0, 120.0, TARGET_ALERT, 5.0)
        st.session_state["refund_th"], st.session_state["target_th"] = refund_th, target_th

        if st.button("🔄 立即刷新数据", **STRETCH):
            st.cache_data.clear()
            st.rerun()
        if live:
            now = time.time()
            if now - st.session_state.get("_last_feed", 0) >= interval:
                realtime_feed.append_batch(2)
                st.session_state["_last_feed"] = now
                st.cache_data.clear()
            if st.button("清空实时订单流", **STRETCH):
                realtime_feed.reset_feed()
                st.session_state.pop("_last_feed", None)
                st.cache_data.clear()
                st.rerun()
        if st.session_state.get("_linked"):
            if st.button("✖ 清除图表联动", **STRETCH):
                st.session_state.pop("_linked", None)
                st.session_state["f_category"] = []
                st.rerun()

    if auto:
        components.html(
            f"<script>setTimeout(function(){{window.parent.location.reload();}},{int(interval) * 1000});</script>",
            height=1)

    # ---------------------------------------------------------- 计算
    scope = metrics.apply_filters(df, categories=cats, regions=regs,
                                  channels=chs, keyword=kw)
    view = metrics.apply_filters(scope, start=start, end=end)
    if view.empty:
        st.warning("当前筛选条件下没有数据，请放宽日期区间或清除筛选条件。")
        st.stop()
    k = metrics.kpis(view, scope, start=start, end=end, target=target,
                     refund_alert=refund_th, target_alert=target_th)

    # ---------------------------------------------------------- 头部
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    live_txt = "实时数据流 · ON" if live else "静态数据集 · 可切换实时"
    growth_txt = "—" if k["环比增长率"] is None else f'{k["环比增长率"]:+.2f}%'
    st.markdown(
        f'<div class="hero"><div><h1>📊 星云商城 · 经营数据看板</h1>'
        f'<div class="sub">实验2 数据看板的设计与实现 ｜ Streamlit + Pandas + Plotly ｜ '
        f'统计区间 {k["区间"]}</div></div>'
        f'<div class="live"><span class="dot"></span><span>{live_txt}<br>'
        f'最近刷新 {now_str}</span></div></div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="ticker"><span class="tag">实时快讯</span><div class="roll"><div class="roll-inner">'
        f'<div>▸ 本期销售额 {fmt_money(k["销售额"])}，已完成订单 {k["订单量"]:,} 单</div>'
        f'<div>▸ 客单价 {fmt_money(k["客单价"])}，利润率 {k["利润率"]:.2f}%，环比 {growth_txt}</div>'
        f'<div>▸ 点击「品类销售额」柱体可联动全页图表；左侧筛选器支持多维组合</div>'
        f'<div>▸ 数据更新于 {now_str}</div></div></div></div>', unsafe_allow_html=True)

    # ---------------------------------------------------------- ① 数据概览区
    section("1", "数据概览区", "OVERVIEW", "核心指标 / 目标达成 / 预警监控")
    kpi_cards(k)
    st.write("")
    c1, c2 = st.columns([1, 1.35])
    with c1:
        # 图表容器由全局 CSS（[data-testid="stPlotlyChart"]）统一渲染为面板
        show(charts.gauge_target(k["目标达成率"], theme), key="gauge")
        st.markdown(
            f'<div class="cap">区间折算目标 {fmt_money(k["区间目标"])}（全周期目标按 '
            f'{k["区间天数"]} 天占比折算）；虚线为 100% 达标线。</div>',
            unsafe_allow_html=True)
    with c2:
        alert_rows = ""
        for a in k["预警"]:
            cls = "blink" if a["级别"] == "danger" else ""
            icon = {"danger": "🔴", "warning": "🟡", "ok": "🟢"}[a["级别"]]
            alert_rows += (f'<div class="alertbar {a["级别"]} {cls}">{icon} '
                           f'<b>{a["指标"]}</b>：{a["消息"]}</div>')
        st.markdown(
            '<div class="panel"><div style="font-size:14px;font-weight:700;margin-bottom:10px">'
            '🚨 数据预警与异常监控</div>' + alert_rows +
            f'<div class="cap" style="margin-top:12px;line-height:1.9">'
            f'口径：销售额 / 利润 / 订单量仅统计「已完成」订单；退款率 = 退款单数 / 有效订单数；'
            f'环比对比上一等长周期（上期 {fmt_money(k["上期销售额"])}）。<br>'
            f'阈值可在左侧控制台实时调整，超阈值时指标卡变红并闪烁。</div></div>',
            unsafe_allow_html=True)

    # ---------------------------------------------------------- ② 维度统计区
    section("2", "维度统计区", "DIMENSIONS", "品类 / 渠道 / 区域 / 商品排行 · 点击柱体联动")
    cat_g = metrics.by_dimension(view, "商品品类")
    ch_g = metrics.by_dimension(view, "销售渠道")
    reg_g = metrics.by_dimension(view, "销售区域")
    rank_g = metrics.ranking(view, "商品名称", 8)
    radar = metrics.radar_data(view)

    c1, c2 = st.columns(2)
    with c1:
        # 图表容器由全局 CSS（[data-testid="stPlotlyChart"]）统一渲染为面板
        event = show(charts.bar_comparison(cat_g, "商品品类", "各品类销售额对比（点击柱体联动）", theme),
                     key="bar_cat", selectable=True)
        st.markdown('<div class="cap">💡 点击任一柱体，下方趋势 / 热力图 / 雷达图 / 明细表同步切换到该品类</div>',
                    unsafe_allow_html=True)
        if HAS_ON_SELECT and event is not None:
            pts = getattr(getattr(event, "selection", None), "points", None) or []
            if pts:
                p0 = pts[0]
                x = p0.get("x") if isinstance(p0, dict) else getattr(p0, "x", None)
                if x in CATEGORIES and st.session_state.get("_linked") != x:
                    st.session_state["_linked"] = x
                    st.session_state["_pending_category"] = [x]
                    st.rerun()
    with c2:
        # 图表容器由全局 CSS（[data-testid="stPlotlyChart"]）统一渲染为面板
        show(charts.donut_share(ch_g, "销售渠道", "销售渠道销售额占比", theme), key="donut_ch")
        # /panel（由全局 CSS 收口，无需手写闭合标签）

    c3, c4 = st.columns(2)
    with c3:
        # 图表容器由全局 CSS（[data-testid="stPlotlyChart"]）统一渲染为面板
        show(charts.ranking_bar(rank_g, "商品名称", "商品销售额 TOP8 排行榜", theme), key="rank")
        # /panel（由全局 CSS 收口，无需手写闭合标签）
    with c4:
        # 图表容器由全局 CSS（[data-testid="stPlotlyChart"]）统一渲染为面板
        show(charts.radar_category(radar, theme) if not radar.empty
             else charts.bar_comparison(reg_g, "销售区域", "区域销售额", theme), key="radar")
        # /panel（由全局 CSS 收口，无需手写闭合标签）

    # ---------------------------------------------------------- ③ 趋势分析区
    section("3", "趋势分析区", "TRENDS", f"时间趋势 / 热力分布 / 多维分析（{freq_label}）")
    ts = metrics.time_series(view, freq)
    # 图表容器由全局 CSS（[data-testid="stPlotlyChart"]）统一渲染为面板
    show(charts.line_trend(ts, f"销售额时间趋势（{freq_label}，含 7 日均线）", theme, freq), key="trend")

    c5, c6 = st.columns(2)
    heat = metrics.weekday_category_heatmap(view)
    with c5:
        # 图表容器由全局 CSS（[data-testid="stPlotlyChart"]）统一渲染为面板
        show(charts.heatmap_weekday(heat, theme) if not heat.empty
             else charts.bar_comparison(reg_g, "销售区域", "区域销售额", theme), key="heat")
        # /panel（由全局 CSS 收口，无需手写闭合标签）
    with c6:
        # 图表容器由全局 CSS（[data-testid="stPlotlyChart"]）统一渲染为面板
        show(charts.profit_scatter(cat_g, theme), key="scatter")
        # /panel（由全局 CSS 收口，无需手写闭合标签）

    # ---------------------------------------------------------- ④ 明细数据区
    section("4", "明细数据区", "DETAILS", "筛选结果 / 数据校验 / 导出报告")
    detail = metrics.detail_table(view)
    check = metrics.consistency_check(view)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("筛选后明细行数", f"{len(detail):,}")
    m2.metric("明细销售额合计", fmt_money(check["明细销售额合计"]))
    m3.metric("各维度合计校验", "✅ 一致" if check["是否一致"] else "❌ 不一致")
    m4.metric("平均客户评分", f"{k['平均评分']:.2f} / 5.00")

    st.dataframe(detail, **STRETCH, height=340,
                 column_config={
                     "销售额": st.column_config.NumberColumn("销售额", format="¥%.2f"),
                     "利润": st.column_config.NumberColumn("利润", format="¥%.2f"),
                     "单价": st.column_config.NumberColumn("单价", format="¥%.2f"),
                     "客户评分": st.column_config.NumberColumn("客户评分", format="%.1f"),
                 })

    e1, e2, e3, e4 = st.columns([1, 1, 1.4, 1])
    csv_bytes = detail.to_csv(index=False).encode("utf-8-sig")
    e1.download_button("⬇ 导出明细 CSV", csv_bytes, "看板筛选明细.csv", "text/csv",
                       **STRETCH)
    e2.download_button("⬇ 导出清洗日志", Path(CLEANING_REPORT).read_bytes(),
                       "cleaning_report.json", "application/json", **STRETCH)
    if e3.button("📄 一键生成可视化数据报告", **STRETCH):
        with st.spinner("正在汇总全部图表并生成离线 HTML 报告…"):
            html = build_html_report(view, k, start, end, theme_name=theme_name)
            p = save_report(view, k, start, end)
        st.success(f"报告已生成：{p.name}")
        st.download_button("⬇ 下载 HTML 报告", html.encode("utf-8"), p.name,
                           "text/html", **STRETCH)
    if e4.button("📊 导出图表 PNG", **STRETCH):
        try:
            from config import EVIDENCE_DIR
            p = EVIDENCE_DIR / f"趋势图_{datetime.now():%Y%m%d_%H%M%S}.png"
            charts.line_trend(ts, "销售额趋势", theme, freq).write_image(str(p), scale=2)
            st.success(f"已导出：{p.name}")
        except Exception as exc:                                   # noqa: BLE001
            st.info("PNG 导出需要 kaleido；已提供离线 HTML 报告（可用浏览器打印为 PDF / 截图）。")

    st.markdown(
        f'<div class="foot">数据源：data/sales_raw.csv（1272 行原始订单）→ 9 条清洗规则 → '
        f'data/sales_clean.csv（1200 行有效订单）→ 看板筛选（{len(detail):,} 行）。'
        f'{"已合并实时订单流。" if realtime_feed.load_feed().shape[0] else ""}<br>'
        f'准确性自检：品类合计 {fmt_money(check["按品类合计"])} ＝ 区域合计 '
        f'{fmt_money(check["按区域合计"])} ＝ 月度合计 {fmt_money(check["按月合计"])} '
        f'＝ 明细合计 {fmt_money(check["明细销售额合计"])}。<br>'
        f'实验2 · 数据看板的设计与实现 ｜ 基础任务 1~5 + 进阶 1~3 + 扩展 1~5 ｜ '
        f'生成时间 {now_str}</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
