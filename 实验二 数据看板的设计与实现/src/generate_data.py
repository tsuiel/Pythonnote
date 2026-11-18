"""任务2 · 生成模拟电商销售数据集（含可控脏数据），输出 CSV + Excel。

数据可复现：固定随机种子 config.RANDOM_SEED，任何机器生成结果完全一致。
运行：python src/generate_data.py
"""
from __future__ import annotations

import random
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

# 兼容 "python src/xxx.py" 与 "pytest 从根目录导入 src.xxx" 两种运行方式
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (CHANNELS, CATEGORIES, CLEAN_CSV, CLEANING_REPORT, DATE_END,
                    DATE_START, MARGIN_RATE, N_DIRTY, N_NORMAL, PRICE_RANGE,
                    PRODUCTS, RANDOM_SEED, RAW_COLUMNS, RAW_CSV, RAW_XLSX,
                    REALTIME_CSV, REGIONS, STATUSES)

DIRTY_TYPES = [
    "日期缺失", "关键字段空值", "数量非正", "单价非正", "成本高于售价",
    "日期格式非法", "日期超出范围", "订单号重复", "评分/状态越界", "纯空白脏值",
]


def _date_span() -> list[date]:
    start = date.fromisoformat(DATE_START)
    end = date.fromisoformat(DATE_END)
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def _season_factor(d: date) -> float:
    """给趋势图注入真实的业务波动：周末上扬、月末冲量、11 月大促峰值。"""
    f = 1.0
    if d.weekday() >= 5:
        f *= 1.18
    if d.day >= 26:
        f *= 1.12
    if d.month == 6:
        f *= 1.25          # 618
    if d.month == 11 and d.day <= 8:
        f *= 1.85          # 双 11 预热
    if d.month == 5 and d.day <= 5:
        f *= 1.15          # 五一
    f *= 1.0 + 0.035 * (d - date.fromisoformat(DATE_START)).days / 30  # 缓慢增长
    return f


def _normal_rows(rng: random.Random) -> list[dict]:
    days = _date_span()
    weights = [_season_factor(d) for d in days]
    rows: list[dict] = []
    for i in range(N_NORMAL):
        d = rng.choices(days, weights=weights, k=1)[0]
        cat = rng.choices(CATEGORIES, weights=[0.24, 0.18, 0.16, 0.15, 0.17, 0.10], k=1)[0]
        lo, hi = PRICE_RANGE[cat]
        price = round(rng.uniform(lo, hi), 2)
        cost = round(price * (1 - MARGIN_RATE[cat]), 2)
        qty = rng.choices([1, 2, 3, 4, 5], weights=[52, 26, 13, 6, 3], k=1)[0]
        status = rng.choices(STATUSES, weights=[92, 8], k=1)[0]
        score = round(rng.uniform(3.4, 5.0), 1)
        rows.append({
            "订单号": f"SO{d.strftime('%Y%m%d')}{i + 1:05d}",
            "日期": d.isoformat(),
            "商品品类": cat,
            "商品名称": rng.choice(PRODUCTS[cat]),
            "销售区域": rng.choices(REGIONS, weights=[0.28, 0.21, 0.18, 0.14, 0.11, 0.08], k=1)[0],
            "销售渠道": rng.choices(CHANNELS, weights=[0.30, 0.25, 0.20, 0.15, 0.10], k=1)[0],
            "数量": str(qty),
            "单价": f"{price:.2f}",
            "成本单价": f"{cost:.2f}",
            "订单状态": status,
            "客户评分": f"{score:.1f}",
        })
    return rows


def _dirty_rows(rng: random.Random, normal: list[dict]) -> list[dict]:
    dirty: list[dict] = []
    for i in range(N_DIRTY):
        row = dict(rng.choice(normal))
        kind = DIRTY_TYPES[i % len(DIRTY_TYPES)]
        row["订单号"] = f"BX{i + 1:05d}"       # 脏行独立编号，便于核对
        if kind == "日期缺失":
            row["日期"] = ""
        elif kind == "关键字段空值":
            row[rng.choice(["商品品类", "销售区域", "单价", "商品名称"])] = ""
        elif kind == "数量非正":
            row["数量"] = rng.choice(["0", "-2", "-1"])
        elif kind == "单价非正":
            row["单价"] = rng.choice(["0", "-99.9", "0.00"])
        elif kind == "成本高于售价":
            row["成本单价"] = f"{float(row['单价']) * 1.6:.2f}"
        elif kind == "日期格式非法":
            row["日期"] = rng.choice(["2026/13/45", "未知", "2026-02-30", "20261108"])
        elif kind == "日期超出范围":
            row["日期"] = rng.choice(["2027-01-01", "2026-04-30", "2025-12-31"])
        elif kind == "订单号重复":
            row["订单号"] = rng.choice(normal)["订单号"]
        elif kind == "评分/状态越界":
            row["客户评分"] = rng.choice(["6.8", "-1", "9.9"])
        elif kind == "纯空白脏值":
            row["商品品类"] = "   "
            row["销售渠道"] = "\t"
        dirty.append(row)
    return dirty


def generate() -> pd.DataFrame:
    rng = random.Random(RANDOM_SEED)
    normal = _normal_rows(rng)
    rows = normal + _dirty_rows(rng, normal)
    rng.shuffle(rows)
    df = pd.DataFrame(rows, columns=RAW_COLUMNS)
    RAW_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(RAW_CSV, index=False, encoding="utf-8-sig")
    df.to_excel(RAW_XLSX, index=False, sheet_name="原始订单")
    return df


def main() -> None:
    # 重跑时清掉下游产物，避免出现"新原始数据 + 旧清洗结果"的错配
    for p in (CLEAN_CSV, CLEANING_REPORT, REALTIME_CSV):
        if p.exists():
            p.unlink()
    df = generate()
    print("=" * 68)
    print("任务2 · 模拟数据集生成完成")
    print("=" * 68)
    print(f"随机种子            : {RANDOM_SEED}（结果完全可复现）")
    print(f"日期范围            : {DATE_START} ~ {DATE_END}")
    print(f"原始行数            : {len(df)}（有效 {N_NORMAL} + 脏数据 {N_DIRTY}）")
    print(f"字段                : {', '.join(RAW_COLUMNS)}")
    print(f"脏数据类型（{len(DIRTY_TYPES)} 类）: {', '.join(DIRTY_TYPES)}")
    print(f"CSV                 : {RAW_CSV}")
    print(f"Excel               : {RAW_XLSX}")
    print("=" * 68)


if __name__ == "__main__":
    main()
