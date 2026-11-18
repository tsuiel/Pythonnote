"""考题一测试：正常用例 + 人工核对 + 边界/异常用例。"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import Workbook

from src.task1_excel.make_sample_data import make_sample
from src.task1_excel.sales_report import (
    SHEET_NAMES,
    ReportInputError,
    generate_report,
)

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BY_SALES = {"张三": 14400, "李四": 5400, "王五": 3000, "赵六": 900}
EXPECTED_BY_REGION = {"华东": 15300, "华北": 5400, "华南": 3000}
EXPECTED_MONTHLY = {"2026-10": 19600, "2026-11": 4100}
EXPECTED_TOTAL = 23700


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    return make_sample(tmp_path / "sales_raw.xlsx")


def _write_xlsx(path: Path, headers: list[str], rows: list[list]) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    wb.save(path)
    return path


def test_normal_report_and_manual_reconciliation(sample_file: Path, tmp_path: Path) -> None:
    """正常用例：一键生成四表，所有统计数值与人工核算一致。"""
    out = tmp_path / "report.xlsx"
    before = hashlib.sha256(sample_file.read_bytes()).hexdigest()

    stats = generate_report(sample_file, out)

    assert hashlib.sha256(sample_file.read_bytes()).hexdigest() == before, "原始文件被修改了"
    assert stats["原始行数"] == 16
    assert stats["有效行数"] == 8
    assert stats["缺失/非法关键字段剔除"] == 3
    assert stats["数量<=0 剔除"] == 2
    assert stats["单价<=0 剔除"] == 0
    assert stats["重复行剔除"] == 2
    assert stats["日期无法解析剔除"] == 1

    assert out.exists()
    sheets = pd.ExcelFile(out).sheet_names
    assert sheets == SHEET_NAMES

    detail = pd.read_excel(out, sheet_name="明细清洗后")
    assert len(detail) == 8
    assert list(detail["销售额"]) == [10000, 400, 3600, 600, 5000, 2400, 800, 900]
    assert detail["销售额"].sum() == EXPECTED_TOTAL

    by_sales = pd.read_excel(out, sheet_name="按销售员").set_index("销售员")["销售额"].to_dict()
    assert by_sales == pytest.approx(EXPECTED_BY_SALES)
    by_region = pd.read_excel(out, sheet_name="按地区").set_index("地区")["销售额"].to_dict()
    assert by_region == pytest.approx(EXPECTED_BY_REGION)
    assert sum(by_sales.values()) == sum(by_region.values()) == EXPECTED_TOTAL

    overview = pd.read_excel(out, sheet_name="总览").set_index("项目")["数值"].to_dict()
    for month, value in EXPECTED_MONTHLY.items():
        assert overview[f"月度总额 {month}"] == pytest.approx(value)
    assert overview["月度总额（合计）"] == pytest.approx(EXPECTED_TOTAL)


def test_missing_required_columns(tmp_path: Path) -> None:
    """边界 1：缺少必需字段 -> 明确报错，列出缺哪些。"""
    path = _write_xlsx(
        tmp_path / "missing_cols.xlsx",
        ["日期", "销售员", "数量", "单价"],
        [["2026-10-01", "张三", 2, 100]],
    )
    with pytest.raises(ReportInputError) as exc:
        generate_report(path, tmp_path / "out.xlsx")
    assert "缺少必需字段" in str(exc.value)
    assert "产品" in str(exc.value) and "地区" in str(exc.value)
    assert not (tmp_path / "out.xlsx").exists(), "报错时不应产生半成品报表"


def test_empty_zero_byte_file(tmp_path: Path) -> None:
    """边界 2：0 字节空文件 -> 明确报错。"""
    path = tmp_path / "empty.xlsx"
    path.write_bytes(b"")
    with pytest.raises(ReportInputError, match="为空"):
        generate_report(path, tmp_path / "out.xlsx")


def test_header_only_file(tmp_path: Path) -> None:
    """边界 3：只有表头、没有数据行 -> 明确报错。"""
    path = _write_xlsx(
        tmp_path / "header_only.xlsx",
        ["日期", "销售员", "产品", "数量", "单价", "地区"],
        [],
    )
    with pytest.raises(ReportInputError, match="没有数据行"):
        generate_report(path, tmp_path / "out.xlsx")


def test_no_valid_rows_after_cleaning(tmp_path: Path) -> None:
    """边界 4：全是脏数据 -> 明确提示「无有效数据」，不崩溃、不产出空报表。"""
    path = _write_xlsx(
        tmp_path / "all_dirty.xlsx",
        ["日期", "销售员", "产品", "数量", "单价", "地区"],
        [
            ["2026-10-01", None, "鼠标", 2, 100, "华东"],
            ["2026-10-02", "张三", "鼠标", -5, 100, "华东"],
            ["2026-10-03", "张三", "鼠标", 0, 100, "华东"],
        ],
    )
    with pytest.raises(ReportInputError, match="没有任何有效数据行"):
        generate_report(path, tmp_path / "out.xlsx")


def test_file_not_found(tmp_path: Path) -> None:
    """边界 5：输入路径不存在 -> 明确报错。"""
    with pytest.raises(ReportInputError, match="找不到原始文件"):
        generate_report(tmp_path / "nope.xlsx", tmp_path / "out.xlsx")


def test_nonpositive_unit_price_rows_are_dropped(tmp_path: Path) -> None:
    """边界 6（人工审查补充）：单价<=0 必须剔除，避免 0/负销售额污染统计。"""
    path = _write_xlsx(
        tmp_path / "bad_price.xlsx",
        ["日期", "销售员", "产品", "数量", "单价", "地区"],
        [
            ["2026-10-01", "张三", "笔记本", 2, 5000, "华东"],  # 有效：10000
            ["2026-10-02", "李四", "鼠标", 3, -80, "华北"],     # 负单价
            ["2026-10-03", "王五", "键盘", 4, 0, "华南"],       # 零单价
        ],
    )
    out = tmp_path / "out.xlsx"
    stats = generate_report(path, out)
    assert stats["单价<=0 剔除"] == 2
    assert stats["有效行数"] == 1
    detail = pd.read_excel(out, sheet_name="明细清洗后")
    assert list(detail["销售额"]) == [10000]


def test_cli_returns_readable_error_not_traceback() -> None:
    """异常输入经命令行调用时，退出码 2 且给出可读中文提示，无栈回溯。"""
    script = ROOT / "src" / "task1_excel" / "sales_report.py"
    proc = subprocess.run(
        [sys.executable, str(script), "-i", str(ROOT / "不存在的表.xlsx")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 2
    assert "[错误]" in proc.stderr
    assert "Traceback" not in proc.stderr
