"""任务3/5 · 指标层验收用例（口径一致、恒等式、筛选联动、预警、报告输出）"""
from __future__ import annotations

import pandas as pd
import pytest

import metrics
from config import CATEGORIES, DATE_END, DATE_START, SALES_TARGET


@pytest.fixture(scope="module")
def bounds(clean_df):
    return clean_df["日期_dt"].min(), clean_df["日期_dt"].max()


def test_consistency_four_ways(clean_df):
    """明细 / 品类 / 区域 / 月度 / 日度合计必须完全相等。"""
    c = metrics.consistency_check(clean_df)
    assert c["是否一致"] is True
    for key in ["按品类合计", "按区域合计", "按月合计", "按日合计"]:
        assert abs(c[key] - c["明细销售额合计"]) < 0.05


def test_kpis_full_period(clean_df, bounds):
    s, e = bounds
    k = metrics.kpis(clean_df, clean_df, start=s, end=e)
    completed = metrics.completed(clean_df)
    assert k["订单量"] == len(completed)
    assert abs(k["销售额"] - completed["销售额"].sum()) < 0.05
    assert abs(k["利润"] - completed["利润"].sum()) < 0.05
    assert abs(k["客单价"] - k["销售额"] / k["订单量"]) < 0.05
    assert abs(k["利润率"] - k["利润"] / k["销售额"] * 100) < 0.05
    assert k["有效订单数"] == len(clean_df)
    assert abs(k["退款率"] - clean_df["是否退款"].mean() * 100) < 0.05
    assert k["环比增长率"] is None            # 全周期无上一等长周期
    assert abs(k["区间目标"] - SALES_TARGET) < 1
    assert abs(k["目标达成率"] - k["销售额"] / SALES_TARGET * 100) < 0.05


def test_kpis_sub_period_has_growth(clean_df):
    s, e = pd.Timestamp("2026-10-01"), pd.Timestamp("2026-10-31")
    scope = clean_df
    view = metrics.apply_filters(scope, start=s, end=e)
    k = metrics.kpis(view, scope, start=s, end=e)
    assert k["上期销售额"] > 0
    assert k["环比增长率"] is not None
    assert abs(k["区间目标"] - SALES_TARGET * 31 / (
        (pd.Timestamp(DATE_END) - pd.Timestamp(DATE_START)).days + 1)) < 1


def test_by_dimension_totals(clean_df):
    total = metrics.completed(clean_df)["销售额"].sum()
    for col in ["商品品类", "销售区域", "销售渠道", "商品名称", "星期"]:
        g = metrics.by_dimension(clean_df, col)
        assert abs(g["销售额"].sum() - total) < 0.5
        assert abs(g["占比(%)"].sum() - 100) < 0.05
        assert (g["销售额"] <= g["销售额"].shift().fillna(g["销售额"].iloc[0])).all()


def test_time_series_totals(clean_df):
    total = metrics.completed(clean_df)["销售额"].sum()
    for freq in ["D", "W", "M"]:
        ts = metrics.time_series(clean_df, freq)
        assert abs(ts["销售额"].sum() - total) < 0.5
        assert ts["订单量"].sum() == len(metrics.completed(clean_df))
    daily = metrics.time_series(clean_df, "D")
    assert daily["7日均线"].notna().all()


def test_filters_are_consistent(clean_df):
    cat = CATEGORIES[0]
    filtered = metrics.apply_filters(clean_df, categories=[cat])
    assert set(filtered["商品品类"]) == {cat}
    expected = metrics.by_dimension(clean_df, "商品品类").set_index("商品品类").loc[cat, "销售额"]
    assert abs(metrics.completed(filtered)["销售额"].sum() - expected) < 0.5

    s, e = pd.Timestamp("2026-06-01"), pd.Timestamp("2026-06-30")
    dated = metrics.apply_filters(clean_df, start=s, end=e)
    assert dated["日期_dt"].between(s, e).all()
    assert len(dated) < len(clean_df)

    kw = metrics.apply_filters(clean_df, keyword="耳机")
    assert kw["商品名称"].str.contains("耳机").all()


def test_alerts_threshold(clean_df, bounds):
    s, e = bounds
    k_ok = metrics.kpis(clean_df, clean_df, start=s, end=e,
                        refund_alert=99.0, target_alert=0.0)
    assert k_ok["预警"][0]["级别"] == "ok"
    k_bad = metrics.kpis(clean_df, clean_df, start=s, end=e,
                         refund_alert=0.0, target_alert=999.0)
    levels = {a["级别"] for a in k_bad["预警"]}
    assert "danger" in levels and "warning" in levels


def test_heatmap_radar_ranking(clean_df):
    heat = metrics.weekday_category_heatmap(clean_df)
    assert heat.shape[0] <= 7 and heat.shape[1] == len(CATEGORIES)
    assert abs(heat.values.sum() - metrics.completed(clean_df)["销售额"].sum()) < 5
    radar = metrics.radar_data(clean_df)
    assert len(radar) == len(CATEGORIES)
    assert radar[["销售额", "订单量", "客单价", "利润率", "评分"]].max().max() <= 100.01
    assert radar[["销售额", "订单量", "客单价", "利润率", "评分"]].min().min() >= 0
    assert len(metrics.ranking(clean_df, "商品名称", 5)) == 5


def test_detail_table(clean_df):
    d = metrics.detail_table(clean_df)
    assert len(d) == len(clean_df)
    assert "订单状态" in d.columns and "销售额" in d.columns
    assert d["日期"].is_monotonic_decreasing


def test_export_report_offline(clean_df, bounds, tmp_path):
    """扩展4：生成的离线报告必须内联 Plotly.js 且包含核心 KPI。"""
    pytest.importorskip("plotly")
    from export_report import build_html_report
    s, e = bounds
    k = metrics.kpis(clean_df, clean_df, start=s, end=e)
    html = build_html_report(clean_df, k, s, e)
    assert "<!DOCTYPE html>" in html
    assert "plotly" in html.lower()               # 内联 Plotly.js，断网可用
    assert "核心指标" in html and "明细数据" in html
    assert len(html) > 1_000_000                 # plotly.js 内联后 > 1MB
