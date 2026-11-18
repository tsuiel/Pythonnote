"""任务2 · 数据预处理验收用例（清洗规则、边界、数据完整性、原文件保护）"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from config import (CLEANING_REPORT, DATE_END, DATE_START, RAW_COLUMNS,
                    RAW_CSV)
from preprocess import (DataCleaningError, clean_dataframe, load_clean,
                        read_raw, run)


def sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def test_raw_dataset_baseline(raw_df):
    """原始数据集固定 1272 行、11 列，可通过固定种子完全复现。"""
    assert len(raw_df) == 1272
    assert list(raw_df.columns) == RAW_COLUMNS
    # 数据集中确实注入了空值 / 负数 / 非法日期等脏数据
    assert raw_df.eq("").any().any()
    assert raw_df["数量"].astype(str).str.startswith("-").any()


def test_clean_keeps_exactly_1200_rows(raw_df):
    done, report = clean_dataframe(raw_df)
    assert len(done) == 1200
    assert report["原始行数"] == 1272
    assert report["剔除总行数"] == 72
    assert len(report["清洗步骤"]) == 9
    assert sum(s["剔除行数"] for s in report["清洗步骤"]) == 72


def test_no_dirty_value_survives(clean_df):
    """清洗结果中不得残留任何一类脏数据。"""
    assert not clean_df[RAW_COLUMNS].isna().any().any()
    assert (clean_df["数量"] > 0).all()
    assert (clean_df["单价"] > 0).all()
    assert (clean_df["成本单价"] > 0).all()
    assert (clean_df["成本单价"] <= clean_df["单价"]).all()
    assert clean_df["订单状态"].isin(["已完成", "已退款"]).all()
    assert clean_df["客户评分"].between(0, 5).all()
    assert clean_df["订单号"].is_unique
    assert clean_df["日期"].str.match(r"^\d{4}-\d{2}-\d{2}$").all()
    assert clean_df["日期"].between(DATE_START, DATE_END).all()
    assert not clean_df["商品品类"].astype(str).str.strip().eq("").any()


def test_derived_fields_are_consistent(clean_df):
    assert ((clean_df["数量"] * clean_df["单价"] - clean_df["销售额"]).abs() < 0.02).all()
    assert ((clean_df["销售额"] - clean_df["成本"] - clean_df["利润"]).abs() < 0.02).all()
    assert ((clean_df["利润"] / clean_df["销售额"] * 100 - clean_df["利润率"]).abs() < 0.02).all()
    assert (clean_df["月份"] == clean_df["日期"].str[:7]).all()
    assert clean_df["星期"].isin(["周一", "周二", "周三", "周四", "周五", "周六", "周日"]).all()
    assert (clean_df["是否退款"] == clean_df["订单状态"].eq("已退款")).all()


def test_report_baseline_and_json(clean_df):
    report = json.loads(Path(CLEANING_REPORT).read_text(encoding="utf-8"))
    completed = clean_df.loc[~clean_df["是否退款"]]
    assert report["有效行数"] == 1200
    assert report["计入统计订单数"] == len(completed)
    assert report["退款订单数"] == int(clean_df["是否退款"].sum())
    assert abs(report["销售额合计(元)"] - completed["销售额"].sum()) < 0.05
    assert abs(report["利润合计(元)"] - completed["利润"].sum()) < 0.05
    assert abs(report["退款率(%)"] - clean_df["是否退款"].mean() * 100) < 0.05


def test_run_never_modifies_raw_file(tmp_path):
    """清洗必须只读原始文件，不得写回（sha256 前后一致）。"""
    before = sha256(RAW_CSV)
    run(output_path=tmp_path / "clean.csv", report_path=tmp_path / "report.json")
    assert sha256(RAW_CSV) == before
    assert (tmp_path / "clean.csv").is_file()
    assert json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))["有效行数"] == 1200


def test_missing_file_raises(tmp_path):
    with pytest.raises(DataCleaningError, match="不存在"):
        read_raw(tmp_path / "nope.csv")


def test_empty_file_raises(tmp_path):
    p = tmp_path / "empty.csv"
    p.write_bytes(b"")
    with pytest.raises(DataCleaningError, match="为空"):
        read_raw(p)


def test_header_only_raises(tmp_path):
    p = tmp_path / "header.csv"
    p.write_text(",".join(RAW_COLUMNS) + "\n", encoding="utf-8-sig")
    with pytest.raises(DataCleaningError, match="没有数据行"):
        read_raw(p)


def test_missing_column_raises(tmp_path):
    p = tmp_path / "short.csv"
    pd.DataFrame([{c: "x" for c in RAW_COLUMNS[:-2]}]).to_csv(
        p, index=False, encoding="utf-8-sig")
    with pytest.raises(DataCleaningError, match="缺少必需字段"):
        read_raw(p)


def test_no_valid_row_raises(tmp_path):
    p = tmp_path / "all_dirty.csv"
    pd.DataFrame([{c: "" for c in RAW_COLUMNS} for _ in range(5)]).to_csv(
        p, index=False, encoding="utf-8-sig")
    with pytest.raises(DataCleaningError, match="没有任何有效数据行"):
        clean_dataframe(read_raw(p))


def test_load_clean_types():
    df = load_clean()
    assert pd.api.types.is_datetime64_any_dtype(df["日期_dt"])
    assert pd.api.types.is_bool_dtype(df["是否退款"])
    assert len(df) == 1200
