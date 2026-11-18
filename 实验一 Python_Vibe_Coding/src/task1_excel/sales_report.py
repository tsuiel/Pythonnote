#!/usr/bin/env python3
"""考题一：Excel 销售报表生成脚本。

读取 sales_raw.xlsx -> 清洗 -> 统计 -> 输出 report.xlsx（四个工作表）。

设计要点（对应验收标准）：
* 原始文件只读，全程不写回；可用 sha256 前后比对验证。
* 所有可预期的输入异常统一抛 ReportInputError，由 main 转成可读提示 + 退出码 2，
  不向使用者抛栈回溯、不生成半成品报表。
* 统计口径单一：销售额 = 数量 × 单价，各维度与总览都从同一份清洗结果派生，
  保证「人工核对一致」。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

REQUIRED_COLUMNS = ["日期", "销售员", "产品", "数量", "单价", "地区"]
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "data" / "sales_raw.xlsx"
DEFAULT_OUTPUT = ROOT / "data" / "report.xlsx"
SHEET_NAMES = ["明细清洗后", "按销售员", "按地区", "总览"]


class ReportInputError(Exception):
    """输入数据不合规，需要以可读方式告知使用者。"""


def read_raw(path: Path) -> pd.DataFrame:
    """只读加载原始表，并做结构级校验。"""
    path = Path(path)
    if not path.exists():
        raise ReportInputError(f"找不到原始文件：{path}")
    if path.is_dir():
        raise ReportInputError(f"输入路径是文件夹，不是 Excel 文件：{path}")
    if path.stat().st_size == 0:
        raise ReportInputError(f"原始文件为空（0 字节）：{path}")
    try:
        df = pd.read_excel(path, engine="openpyxl")
    except Exception as exc:  # 文件损坏、格式不对、加密等
        raise ReportInputError(f"无法读取 Excel 文件 {path.name}：{exc}") from exc
    if df.empty:
        raise ReportInputError("原始文件没有数据行（空表），无法生成报表。")
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ReportInputError(
            "原始文件缺少必需字段："
            + "、".join(missing)
            + "；实际字段为："
            + "、".join(str(c) for c in df.columns)
        )
    return df


def clean_data(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """清洗脏数据，返回（清洗后明细, 各步骤剔除行数）。

    规则严格按题目：删除关键字段缺失行 -> 剔除数量<=0 -> 全字段去重。
    人工审查后补充两条防护（详见 01_AI协作过程记录.md 的 Code Review 段）：
    * 单价<=0 同样剔除，否则会产生 0 或负销售额，污染统计口径；
    * 无法解析的日期视为无效行，否则无法计算月度总额。
    两类剔除都在统计里如实记录，不静默丢弃。
    """
    work = df.loc[:, REQUIRED_COLUMNS].copy()
    stats: dict[str, int] = {"原始行数": len(work)}

    # 文本字段去首尾空格，空串统一成缺失值
    for col in ["日期", "销售员", "产品", "地区"]:
        work[col] = work[col].astype("string").str.strip().replace("", pd.NA)
    # 数量、单价统一成数值；非数值（含空串）转成 NaN，随后按「关键字段缺失」剔除
    work["数量"] = pd.to_numeric(work["数量"], errors="coerce")
    work["单价"] = pd.to_numeric(work["单价"], errors="coerce")

    before = len(work)
    work = work.dropna(subset=REQUIRED_COLUMNS)
    stats["缺失/非法关键字段剔除"] = before - len(work)

    before = len(work)
    work = work[work["数量"] > 0]
    stats["数量<=0 剔除"] = before - len(work)

    before = len(work)
    work = work[work["单价"] > 0]
    stats["单价<=0 剔除"] = before - len(work)

    before = len(work)
    work = work.drop_duplicates(subset=REQUIRED_COLUMNS, keep="first")
    stats["重复行剔除"] = before - len(work)

    work["日期"] = pd.to_datetime(work["日期"], errors="coerce")
    before = len(work)
    work = work.dropna(subset=["日期"])
    stats["日期无法解析剔除"] = before - len(work)

    if work.empty:
        raise ReportInputError(
            "清洗后没有任何有效数据行，无法生成报表。"
            + "；".join(f"{k}={v}" for k, v in stats.items())
        )

    work["销售额"] = (work["数量"] * work["单价"]).round(2)
    work["月份"] = work["日期"].dt.strftime("%Y-%m")
    stats["有效行数"] = len(work)
    return work.reset_index(drop=True), stats


def build_sheets(clean: pd.DataFrame, stats: dict[str, int]) -> dict[str, pd.DataFrame]:
    """由同一份清洗结果派生四个工作表。"""
    detail = clean[["日期", "销售员", "产品", "数量", "单价", "地区", "销售额"]].copy()
    detail["日期"] = detail["日期"].dt.strftime("%Y-%m-%d")

    def group_by(col: str) -> pd.DataFrame:
        out = (
            clean.groupby(col, as_index=False)
            .agg(销售额=("销售额", "sum"), 数量合计=("数量", "sum"), 记录数=("销售额", "size"))
            .sort_values(["销售额", col], ascending=[False, True])
            .reset_index(drop=True)
        )
        out["销售额"] = out["销售额"].round(2)
        return out

    by_sales = group_by("销售员")
    by_region = group_by("地区")

    monthly = clean.groupby("月份", as_index=False)["销售额"].sum().sort_values("月份")
    rows = [
        ("有效记录数", stats["有效行数"], "清洗后参与统计的明细行数"),
        ("总数量", int(clean["数量"].sum()), "清洗后数量字段合计"),
    ]
    for _, r in monthly.iterrows():
        rows.append((f"月度总额 {r['月份']}", round(float(r["销售额"]), 2), "该月销售额合计"))
    rows.append(("月度总额（合计）", round(float(clean["销售额"].sum()), 2), "全部月份销售额合计"))
    rows.append(("原始行数", stats["原始行数"], "原始表数据行数"))
    for key in ["缺失/非法关键字段剔除", "数量<=0 剔除", "单价<=0 剔除",
                "重复行剔除", "日期无法解析剔除"]:
        rows.append((key, stats[key], "清洗阶段剔除行数"))
    overview = pd.DataFrame(rows, columns=["项目", "数值", "说明"])

    return dict(zip(SHEET_NAMES, [detail, by_sales, by_region, overview]))


def write_report(sheets: dict[str, pd.DataFrame], output: Path) -> Path:
    """写出 xlsx，并做最基本的版式处理。"""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name, index=False)
        for ws in writer.book.worksheets:
            ws.freeze_panes = "A2"
            for cell in ws[1]:
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal="center")
            for col in ws.columns:
                width = max(
                    (len(str(c.value)) if c.value is not None else 0) for c in col
                )
                ws.column_dimensions[get_column_letter(col[0].column)].width = min(
                    max(width * 1.7 + 3, 12), 30
                )
    return output


def generate_report(input_path: Path | str = DEFAULT_INPUT,
                    output_path: Path | str = DEFAULT_OUTPUT) -> dict[str, int]:
    """供脚本与测试共用的完整流程；出错时抛 ReportInputError。"""
    raw = read_raw(Path(input_path))
    clean, stats = clean_data(raw)
    sheets = build_sheets(clean, stats)
    write_report(sheets, Path(output_path))
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="销售数据清洗与报表生成")
    parser.add_argument("-i", "--input", default=str(DEFAULT_INPUT), help="原始 sales_raw.xlsx 路径")
    parser.add_argument("-o", "--output", default=str(DEFAULT_OUTPUT), help="输出 report.xlsx 路径")
    args = parser.parse_args(argv)
    try:
        stats = generate_report(args.input, args.output)
    except ReportInputError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 2
    print(f"[完成] 已生成报表：{args.output}")
    print(f"  原始行数 {stats['原始行数']} -> 有效行数 {stats['有效行数']}")
    for key in ["缺失/非法关键字段剔除", "数量<=0 剔除", "单价<=0 剔除",
                "重复行剔除", "日期无法解析剔除"]:
        print(f"  {key}：{stats[key]} 行")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
