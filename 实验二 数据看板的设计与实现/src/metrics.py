"""看板指标层：所有图表、KPI 卡片、预警、导出报告共用同一套纯函数。

设计原则：
1. 单一口径 —— 销售额 / 利润 / 订单量只统计『已完成』订单，退款率基于全部有效订单；
2. 恒等式 —— 各维度汇总、时间序列、KPI 全部由同一份筛选结果派生，合计必然相等；
3. 无副作用 —— 不读文件、不写文件、不依赖 Streamlit，方便单元测试直接断言。
"""
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import DATE_END, DATE_START, REFUND_ALERT, SALES_TARGET, TARGET_ALERT

WEEKDAY_ORDER = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def completed(df: pd.DataFrame) -> pd.DataFrame:
    """只保留已完成订单（销售额 / 利润 / 订单量的统计口径）。"""
    return df.loc[~df["是否退款"]].copy()


def apply_filters(df: pd.DataFrame, *, start=None, end=None,
                  categories=None, regions=None, channels=None,
                  products=None, keyword: str = "") -> pd.DataFrame:
    """按日期 + 分类维度 + 关键词筛选；None / 空列表表示不限制。"""
    out = df
    if start is not None:
        out = out[out["日期_dt"] >= pd.Timestamp(start)]
    if end is not None:
        out = out[out["日期_dt"] <= pd.Timestamp(end)]
    for col, values in (("商品品类", categories), ("销售区域", regions),
                        ("销售渠道", channels), ("商品名称", products)):
        if values:
            out = out[out[col].isin(list(values))]
    if keyword:
        kw = str(keyword).strip()
        if kw:
            mask = out["订单号"].str.contains(kw, case=False, na=False) | \
                   out["商品名称"].str.contains(kw, case=False, na=False)
            out = out[mask]
    return out.copy()


def prorated_target(start, end, target: float = SALES_TARGET) -> float:
    """按所选日期区间占整个数据集天数的比例折算销售目标。"""
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    total_days = (pd.Timestamp(DATE_END) - pd.Timestamp(DATE_START)).days + 1
    days = max((e - s).days + 1, 1)
    return target * days / total_days


def kpis(view: pd.DataFrame, scope: pd.DataFrame, *, start, end,
         target: float = SALES_TARGET,
         refund_alert: float = REFUND_ALERT,
         target_alert: float = TARGET_ALERT) -> dict:
    """计算核心指标。scope = 只按分类维度筛选的全量数据（用于计算环比）。"""
    cur = completed(view)
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    span = (e - s).days + 1
    prev_start, prev_end = s - timedelta(days=span), s - timedelta(days=1)
    prev = scope[(scope["日期_dt"] >= prev_start) & (scope["日期_dt"] <= prev_end)]
    prev_sales = float(completed(prev)["销售额"].sum())
    sales = float(cur["销售额"].sum())
    profit = float(cur["利润"].sum())
    orders = int(len(cur))
    growth = ((sales - prev_sales) / prev_sales * 100) if prev_sales > 0 else None
    p_target = prorated_target(s, e, target)
    refund_rate = float(view["是否退款"].mean() * 100) if len(view) else 0.0
    result = {
        "销售额": round(sales, 2),
        "订单量": orders,
        "客单价": round(sales / orders, 2) if orders else 0.0,
        "利润": round(profit, 2),
        "利润率": round(profit / sales * 100, 2) if sales else 0.0,
        "平均评分": round(float(cur["客户评分"].mean()), 2) if orders else 0.0,
        "退款率": round(refund_rate, 2),
        "有效订单数": int(len(view)),
        "上期销售额": round(prev_sales, 2),
        "环比增长率": round(growth, 2) if growth is not None else None,
        "区间目标": round(p_target, 2),
        "目标达成率": round(sales / p_target * 100, 2) if p_target else 0.0,
        "区间": f"{s.date()} ~ {e.date()}",
        "区间天数": span,
    }
    result["预警"] = alerts(result, refund_alert=refund_alert, target_alert=target_alert)
    return result


def alerts(k: dict, *, refund_alert: float = REFUND_ALERT,
           target_alert: float = TARGET_ALERT) -> list[dict]:
    """扩展2 · 阈值预警：退款率过高 / 目标达成不足 / 环比大幅下滑。"""
    out: list[dict] = []
    if k["退款率"] > refund_alert:
        out.append({"级别": "danger", "指标": "退款率",
                    "消息": f"退款率 {k['退款率']:.2f}% 已超过阈值 {refund_alert:.1f}%，建议排查售后与商品质量"})
    if k["目标达成率"] < target_alert:
        out.append({"级别": "warning", "指标": "目标达成率",
                    "消息": f"目标达成率 {k['目标达成率']:.2f}% 低于阈值 {target_alert:.1f}%，需关注销售进度"})
    if k["环比增长率"] is not None and k["环比增长率"] < -10:
        out.append({"级别": "warning", "指标": "环比增长率",
                    "消息": f"销售额环比下降 {abs(k['环比增长率']):.2f}%，较上一周期明显回落"})
    if not out:
        out.append({"级别": "ok", "指标": "整体",
                    "消息": "全部核心指标处于正常范围，未触发预警"})
    return out


def by_dimension(df: pd.DataFrame, col: str) -> pd.DataFrame:
    cur = completed(df)
    if cur.empty:
        return pd.DataFrame(columns=[col, "销售额", "订单量", "利润", "占比(%)"])
    g = (cur.groupby(col, as_index=False)
         .agg(销售额=("销售额", "sum"), 订单量=("订单号", "count"), 利润=("利润", "sum"))
         .sort_values("销售额", ascending=False))
    g["销售额"] = g["销售额"].round(2)
    g["利润"] = g["利润"].round(2)
    g["占比(%)"] = (g["销售额"] / g["销售额"].sum() * 100).round(2)
    return g.reset_index(drop=True)


def time_series(df: pd.DataFrame, freq: str = "D") -> pd.DataFrame:
    """freq: D=按日 / W=按周 / M=按月；返回销售额、订单量、利润与 7 日均线。"""
    cur = completed(df)
    if cur.empty:
        return pd.DataFrame(columns=["日期", "销售额", "订单量", "利润", "7日均线"])
    rule = {"D": "D", "W": "W-MON", "M": "MS"}[freq]
    g = (cur.set_index("日期_dt")
         .resample(rule)
         .agg(销售额=("销售额", "sum"), 订单量=("订单号", "count"), 利润=("利润", "sum"))
         .reset_index()
         .rename(columns={"日期_dt": "日期"}))
    g["销售额"] = g["销售额"].round(2)
    g["利润"] = g["利润"].round(2)
    g["7日均线"] = g["销售额"].rolling(7, min_periods=1).mean().round(2) if freq == "D" else np.nan
    return g


def weekday_category_heatmap(df: pd.DataFrame) -> pd.DataFrame:
    """扩展3 · 星期 × 品类 销售额热力图。"""
    cur = completed(df)
    if cur.empty:
        return pd.DataFrame()
    p = cur.pivot_table(index="星期", columns="商品品类", values="销售额",
                        aggfunc="sum", fill_value=0).round(0)
    return p.reindex([w for w in WEEKDAY_ORDER if w in p.index])


def radar_data(df: pd.DataFrame) -> pd.DataFrame:
    """扩展3 · 品类五维雷达：销售额 / 订单量 / 客单价 / 利润率 / 客户评分，归一化到 0~100。"""
    cur = completed(df)
    if cur.empty:
        return pd.DataFrame()
    g = cur.groupby("商品品类").agg(
        销售额=("销售额", "sum"), 订单量=("订单号", "count"),
        利润=("利润", "sum"), 评分=("客户评分", "mean"))
    g["客单价"] = g["销售额"] / g["订单量"]
    g["利润率"] = g["利润"] / g["销售额"] * 100
    cols = ["销售额", "订单量", "客单价", "利润率", "评分"]
    norm = g[cols].copy()
    for c in cols:
        mx = norm[c].max()
        norm[c] = (norm[c] / mx * 100).round(1) if mx and mx > 0 else 0.0
    return norm.reset_index()


def ranking(df: pd.DataFrame, col: str = "商品名称", topn: int = 8) -> pd.DataFrame:
    return by_dimension(df, col).head(topn)


def detail_table(df: pd.DataFrame) -> pd.DataFrame:
    """明细数据区展示用表（含退款单，状态列保留真实业务含义）。"""
    cols = ["订单号", "日期", "商品品类", "商品名称", "销售区域", "销售渠道",
            "数量", "单价", "销售额", "利润", "订单状态", "客户评分"]
    return df[cols].sort_values("日期", ascending=False).reset_index(drop=True)


def consistency_check(df: pd.DataFrame) -> dict:
    """数据准确性自检：三处合计必须相等，供测试与一键运行核对。"""
    cur = completed(df)
    total = round(float(cur["销售额"].sum()), 2)
    return {
        "明细销售额合计": total,
        "按品类合计": round(float(by_dimension(df, "商品品类")["销售额"].sum()), 2),
        "按区域合计": round(float(by_dimension(df, "销售区域")["销售额"].sum()), 2),
        "按月合计": round(float(time_series(df, "M")["销售额"].sum()), 2),
        "按日合计": round(float(time_series(df, "D")["销售额"].sum()), 2),
        "是否一致": all(abs(total - v) < 0.05 for v in [
            round(float(by_dimension(df, "商品品类")["销售额"].sum()), 2),
            round(float(by_dimension(df, "销售区域")["销售额"].sum()), 2),
            round(float(time_series(df, "M")["销售额"].sum()), 2),
            round(float(time_series(df, "D")["销售额"].sum()), 2),
        ]),
    }
