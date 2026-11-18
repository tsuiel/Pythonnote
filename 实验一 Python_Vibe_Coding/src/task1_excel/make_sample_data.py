#!/usr/bin/env python3
"""生成考题一的样例原始数据 sales_raw.xlsx（刻意包含脏数据）。

8 条有效记录 + 8 条脏数据，数值经过人工核算，便于验收时逐项核对：
  按销售员：张三 14400 / 李四 5400 / 王五 3000 / 赵六 900
  按地区  ：华东 15300 / 华北 5400 / 华南 3000
  月度总额：2026-10 = 19600，2026-11 = 4100，合计 23700
"""
from __future__ import annotations

import argparse
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

HEADERS = ["日期", "销售员", "产品", "数量", "单价", "地区"]
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "data" / "sales_raw.xlsx"

VALID_ROWS = [
    ["2026-10-03", "张三", "笔记本", 2, 5000, "华东"],
    ["2026-10-05", "李四", "鼠标", 5, 80, "华北"],
    ["2026-10-08", "张三", "显示器", 3, 1200, "华东"],
    ["2026-10-12", "王五", "键盘", 4, 150, "华南"],
    ["2026-10-20", "李四", "笔记本", 1, 5000, "华北"],
    ["2026-11-02", "王五", "显示器", 2, 1200, "华南"],
    ["2026-11-06", "张三", "鼠标", 10, 80, "华东"],
    ["2026-11-15", "赵六", "键盘", 6, 150, "华东"],
]

DIRTY_ROWS = [
    ["2026-10-09", None, "鼠标", 3, 80, "华东"],          # 关键字段缺失：销售员
    ["2026-10-10", "王五", None, 2, 100, "华南"],          # 关键字段缺失：产品
    ["2026-10-14", "赵六", "键盘", 2, None, "华东"],       # 关键字段缺失：单价
    ["2026-10-11", "张三", "笔记本", -1, 5000, "华东"],    # 负数量
    ["2026-10-13", "李四", "鼠标", 0, 80, "华北"],         # 数量 = 0
    ["2026-10-03", "张三", "笔记本", 2, 5000, "华东"],     # 与第 1 行完全重复
    ["2026-11-02", "王五", "显示器", 2, 1200, "华南"],     # 与第 6 行完全重复
    ["2026-13-45", "赵六", "鼠标", 1, 80, "华东"],         # 日期无法解析
]

ALL_ROWS = [
    VALID_ROWS[0], DIRTY_ROWS[0], VALID_ROWS[1], DIRTY_ROWS[3],
    VALID_ROWS[2], DIRTY_ROWS[2], VALID_ROWS[3], DIRTY_ROWS[4],
    VALID_ROWS[4], DIRTY_ROWS[5], VALID_ROWS[5], DIRTY_ROWS[6],
    VALID_ROWS[6], DIRTY_ROWS[7], VALID_ROWS[7], DIRTY_ROWS[1],
]


def make_sample(output: Path | str = DEFAULT_OUTPUT) -> Path:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "销售明细"
    ws.append(HEADERS)
    for row in ALL_ROWS:
        ws.append(row)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for col, width in zip("ABCDEF", [14, 12, 12, 10, 10, 10]):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A2"
    wb.save(output)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="生成含脏数据的样例销售表")
    parser.add_argument("-o", "--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    path = make_sample(args.output)
    print(f"[完成] 已生成样例数据：{path}（{len(ALL_ROWS)} 行，其中 {len(DIRTY_ROWS)} 行脏数据）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
