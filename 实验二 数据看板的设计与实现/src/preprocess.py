"""任务2 · 数据预处理：空值 / 异常值 / 重复 / 日期规范化 / 维度派生。

清洗顺序固定且不可颠倒，每一步的剔除行数都会写入 data/cleaning_report.json，
保证看板上的每个数字都能回溯到清洗日志。

运行：python src/preprocess.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (CLEAN_CSV, CLEANING_REPORT, DATE_END, DATE_START,
                    DERIVED_COLUMNS, RAW_COLUMNS, RAW_CSV, STATUSES)

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class DataCleaningError(Exception):
    """输入数据不可用（缺文件 / 空文件 / 缺列 / 清洗后无有效行）。"""


def read_raw(path: str | Path = RAW_CSV) -> pd.DataFrame:
    """以纯文本读入原始表，不依赖 pandas 的自动类型推断（避免脏值被静默转换）。"""
    p = Path(path)
    if not p.is_file():
        raise DataCleaningError(f"输入文件不存在：{p}")
    if p.stat().st_size == 0:
        raise DataCleaningError(f"输入文件为空：{p}")
    try:
        df = pd.read_csv(p, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except Exception as exc:                                  # noqa: BLE001
        raise DataCleaningError(f"无法解析 CSV：{exc}") from exc
    if len(df) == 0:
        raise DataCleaningError("输入文件只有表头，没有数据行")
    missing = [c for c in RAW_COLUMNS if c not in df.columns]
    if missing:
        raise DataCleaningError(f"缺少必需字段：{', '.join(missing)}")
    return df[RAW_COLUMNS]


def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """按固定规则清洗，返回 (清洗后 DataFrame, 清洗报告)。"""
    raw_count = len(df)
    work = df.copy()
    # 先统一去掉首尾空白；纯空白字符串视为缺失
    for col in RAW_COLUMNS:
        work[col] = work[col].astype(str).str.strip().replace(
            {"": None, "nan": None, "None": None, "NULL": None}
        )

    steps: list[dict] = []

    def drop(mask: pd.Series, reason: str) -> None:
        nonlocal work
        n = int(mask.sum())
        work = work.loc[~mask].copy()
        steps.append({"规则": reason, "剔除行数": n, "剩余行数": len(work)})

    # 1) 关键字段缺失
    drop(work[RAW_COLUMNS].isna().any(axis=1), "1. 任一关键字段为空 / 纯空白")

    # 2) 日期：严格 YYYY-MM-DD → 真实存在 → 落在数据集范围内
    date_text = work["日期"].astype(str)
    parsed = pd.to_datetime(date_text.where(date_text.str.match(DATE_RE), other=None),
                            format="%Y-%m-%d", errors="coerce")
    work["_日期"] = parsed
    drop(parsed.isna(), "2. 日期格式非法 / 不是真实日期（如 2026-02-30）")
    start, end = pd.Timestamp(DATE_START), pd.Timestamp(DATE_END)
    drop(~work["_日期"].between(start, end), "3. 日期超出数据集范围")

    # 3) 数值字段：必须为正数，且成本单价不高于单价
    numeric_cols = ["数量", "单价", "成本单价", "客户评分"]
    for col in numeric_cols:
        work[col] = pd.to_numeric(work[col], errors="coerce")
    work["数量"] = work["数量"].astype("Int64")
    drop(work[numeric_cols].isna().any(axis=1), "4. 数值字段无法解析为数字")
    drop((work["数量"] <= 0) | (work["单价"] <= 0) | (work["成本单价"] <= 0),
         "5. 数量 / 单价 / 成本单价 非正")
    drop(work["成本单价"] > work["单价"], "6. 成本单价高于单价（异常成本）")

    # 4) 枚举与评分区间
    drop(~work["订单状态"].isin(STATUSES), "7. 订单状态不在枚举内")
    drop(~work["客户评分"].between(0, 5), "8. 客户评分越界（应在 0~5）")

    # 5) 订单号重复：保留首次出现
    drop(work["订单号"].duplicated(keep="first"), "9. 订单号重复（保留首次）")

    if work.empty:
        raise DataCleaningError("清洗后没有任何有效数据行，请检查原始数据质量")

    # 6) 派生统计维度（时间 / 分类 / 数值三类维度全部落地）
    work = work.rename(columns={"_日期": "日期_dt"})
    work["数量"] = work["数量"].astype(int)
    work["销售额"] = (work["数量"] * work["单价"]).round(2)
    work["成本"] = (work["数量"] * work["成本单价"]).round(2)
    work["利润"] = (work["销售额"] - work["成本"]).round(2)
    work["利润率"] = (work["利润"] / work["销售额"] * 100).round(2)
    work["月份"] = work["日期_dt"].dt.strftime("%Y-%m")
    work["星期"] = work["日期_dt"].dt.day_of_week.map(
        {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
    )
    work["是否退款"] = work["订单状态"].eq("已退款")
    work = work.drop(columns=["日期_dt"]).reset_index(drop=True)

    done = work[RAW_COLUMNS + DERIVED_COLUMNS].copy()
    completed = done.loc[~done["是否退款"]]
    report = {
        "数据口径": "销售额 / 利润 / 订单量只统计『已完成』订单；退款率 = 退款单数 / 有效订单数",
        "原始行数": raw_count,
        "有效行数": len(done),
        "剔除总行数": raw_count - len(done),
        "计入统计订单数": len(completed),
        "退款订单数": int(done["是否退款"].sum()),
        "退款率(%)": round(done["是否退款"].mean() * 100, 2),
        "销售额合计(元)": round(float(completed["销售额"].sum()), 2),
        "利润合计(元)": round(float(completed["利润"].sum()), 2),
        "日期范围": f"{done['日期'].min()} ~ {done['日期'].max()}",
        "品类数": int(done["商品品类"].nunique()),
        "区域数": int(done["销售区域"].nunique()),
        "渠道数": int(done["销售渠道"].nunique()),
        "清洗步骤": steps,
    }
    return done, report


def run(input_path: str | Path = RAW_CSV,
        output_path: str | Path = CLEAN_CSV,
        report_path: str | Path = CLEANING_REPORT) -> tuple[pd.DataFrame, dict]:
    """完整流水线：读 → 清洗 → 落盘（清洗结果 + JSON 日志），不修改原始文件。"""
    raw = read_raw(input_path)
    done, report = clean_dataframe(raw)
    out, rep = Path(output_path), Path(report_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    done.to_csv(out, index=False, encoding="utf-8-sig")
    rep.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return done, report


def load_clean(path: str | Path = CLEAN_CSV) -> pd.DataFrame:
    """供看板 / 测试读取清洗结果，并还原正确的字段类型。"""
    p = Path(path)
    if not p.is_file():
        raise DataCleaningError(f"清洗结果不存在，请先运行 python src/preprocess.py：{p}")
    df = pd.read_csv(p, encoding="utf-8-sig")
    df["日期_dt"] = pd.to_datetime(df["日期"], format="%Y-%m-%d")
    df["是否退款"] = df["是否退款"].astype(str).str.lower().isin(["true", "1", "yes"])
    return df


def main() -> None:
    try:
        _, report = run()
    except DataCleaningError as exc:
        print(f"[错误] {exc}")
        sys.exit(2)
    print("=" * 68)
    print("任务2 · 数据预处理完成")
    print("=" * 68)
    print(f"原始行数 {report['原始行数']} → 有效行数 {report['有效行数']}，"
          f"共剔除 {report['剔除总行数']} 行")
    print("-" * 68)
    for s in report["清洗步骤"]:
        print(f"  {s['规则']:<42} -{s['剔除行数']:>3} 行，剩余 {s['剩余行数']:>4} 行")
    print("-" * 68)
    print(f"计入统计订单 : {report['计入统计订单数']} 单（退款 {report['退款订单数']} 单）")
    print(f"销售额合计   : {report['销售额合计(元)']:,.2f} 元")
    print(f"利润合计     : {report['利润合计(元)']:,.2f} 元")
    print(f"日期范围     : {report['日期范围']}")
    print(f"清洗结果     : {CLEAN_CSV}")
    print(f"清洗日志     : {CLEANING_REPORT}")
    print("=" * 68)


if __name__ == "__main__":
    main()
