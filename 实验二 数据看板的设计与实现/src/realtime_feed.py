
from __future__ import annotations

import random
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (CHANNELS, DATE_END, DERIVED_COLUMNS, MARGIN_RATE,
                    PRICE_RANGE, PRODUCTS, RAW_COLUMNS, REALTIME_CSV, REGIONS)

WEEKDAY = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}


def _make_row(rng: random.Random, stamp: datetime, i: int) -> dict:
    cat = rng.choice(list(PRODUCTS))
    lo, hi = PRICE_RANGE[cat]
    price = round(rng.uniform(lo, hi), 2)
    cost = round(price * (1 - MARGIN_RATE[cat]), 2)
    qty = rng.randint(1, 4)
    d = min(stamp.date(), date.fromisoformat(DATE_END)).isoformat()
    dt = pd.Timestamp(d)
    sales, c = round(qty * price, 2), round(qty * cost, 2)
    profit = round(sales - c, 2)
    status = "已完成" if rng.random() > 0.07 else "已退款"
    return {
        "订单号": f"RT{stamp.strftime('%Y%m%d%H%M%S')}{i:02d}",
        "日期": d, "商品品类": cat, "商品名称": rng.choice(PRODUCTS[cat]),
        "销售区域": rng.choice(REGIONS), "销售渠道": rng.choice(CHANNELS),
        "数量": qty, "单价": price, "成本单价": cost,
        "订单状态": status,
        "客户评分": round(rng.uniform(3.6, 5.0), 1),
        "销售额": sales, "成本": c, "利润": profit,
        "利润率": round(profit / sales * 100, 2),
        "月份": dt.strftime("%Y-%m"), "星期": WEEKDAY[dt.day_of_week],
        "是否退款": status == "已退款",
    }


def append_batch(n: int = 2, max_rows: int = 60) -> pd.DataFrame:
    """追加 n 条新订单；feed 最多保留 max_rows 行，避免文件无限增长。"""
    rng = random.Random()
    now = datetime.now()
    cols = RAW_COLUMNS + DERIVED_COLUMNS
    fresh = pd.DataFrame([_make_row(rng, now, i) for i in range(n)], columns=cols)
    REALTIME_CSV.parent.mkdir(parents=True, exist_ok=True)
    if REALTIME_CSV.is_file():
        old = pd.read_csv(REALTIME_CSV, encoding="utf-8-sig")
        all_rows = pd.concat([old, fresh], ignore_index=True)
    else:
        all_rows = fresh
    all_rows = all_rows.drop_duplicates(subset=["订单号"], keep="last").tail(max_rows)
    all_rows.to_csv(REALTIME_CSV, index=False, encoding="utf-8-sig")
    return fresh


def load_feed() -> pd.DataFrame:
    if not REALTIME_CSV.is_file():
        return pd.DataFrame()
    df = pd.read_csv(REALTIME_CSV, encoding="utf-8-sig")
    df["日期_dt"] = pd.to_datetime(df["日期"], format="%Y-%m-%d")
    df["是否退款"] = df["是否退款"].astype(str).str.lower().isin(["true", "1", "yes"])
    return df


def merge_feed(clean: pd.DataFrame) -> pd.DataFrame:
    feed = load_feed()
    if feed.empty:
        return clean
    out = pd.concat([clean, feed], ignore_index=True)
    out = out.drop_duplicates(subset=["订单号"], keep="last")
    return out.reset_index(drop=True)


def reset_feed() -> None:
    if REALTIME_CSV.is_file():
        REALTIME_CSV.unlink()


if __name__ == "__main__":
    df = append_batch(3)
    print(f"已向 {REALTIME_CSV} 追加 {len(df)} 条实时订单：")
    print(df[["订单号", "日期", "商品品类", "销售额"]].to_string(index=False))
