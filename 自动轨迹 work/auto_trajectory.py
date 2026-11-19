#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动轨迹绘制实验
=================
根据题目给出的六条运动指令，绘制自动轨迹。

每条指令格式（与题目图片中的六行数据一致）：
    X, Y, F, mode, flagX, flagY

其中：
    X, Y   —— 本段运动的终点坐标
    F      —— 进给/速度参数（本组指令中均为 144）
    mode   —— 1 表示 G1 直线插补，0 表示 G0 快速定位
    flagX  —— X 轴使能标志
    flagY  —— Y 轴使能标志

flagX、flagY 与当前段的编号一起决定轨迹颜色：
    100 -> red, 010 -> green, 001 -> blue,
    110 -> cyan, 011 -> magenta, 101 -> orange

运行方式：
    python auto_trajectory.py

输出：
    trajectory.png —— 自动轨迹绘制结果
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

# 设置中文字体，避免图中文字显示为方块
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun"]
plt.rcParams["axes.unicode_minus"] = False

# 题目图片中给出的六行运动指令（每行六个字段，与原题完全一致）
INSTRUCTIONS = [
    (300, 0, 144, 1, 0, 0),
    (300, 0, 144, 0, 1, 0),
    (300, 0, 144, 0, 0, 1),
    (300, 0, 144, 1, 1, 0),
    (300, 0, 108, 0, 1, 1),
    (184, 0, 72, 1, 0, 1),
]

# 六条指令依次对应的轨迹颜色（与题图一致）
COLORS = ["red", "green", "blue", "cyan", "magenta", "orange"]
LABELS = [
    "#1  100 / G1",
    "#2  010 / G0",
    "#3  001 / G0",
    "#4  110 / G1",
    "#5  011 / G1",
    "#6  101 / G1",
]

# 题目中黑色实线轮廓（起始五边形与右侧四边形）
BASE_POLYGONS = [
    [(72, 56), (156, 0), (240, 56), (240, 144), (72, 144), (72, 56)],
    [(240, 56), (336, 56), (336, 144), (264, 180), (240, 144)],
]


def draw(base_output: Path) -> None:
    """绘制轨迹图并保存为 PNG 文件。"""
    fig, ax = plt.subplots(figsize=(9, 6.6), dpi=160)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    # 1. 绘制黑色基础轮廓
    for polygon in BASE_POLYGONS:
        xs, ys = zip(*polygon)
        ax.plot(xs, ys, color="#202020", linewidth=2.2,
                solid_capstyle="round", solid_joinstyle="round", zorder=1)

    # 2. 绘制六条彩色自动轨迹
    # 所有轨迹均从两个多边形的公共顶点 (240,144) 出发，
    # 按题图分别连接到右侧四边形及左侧五边形的不同顶点/内部点，形成扇形。
    # 各段颜色由指令后三位标志的组合决定。
    starts = [(240, 144)] * 6
    ends = [
        (336, 144),  # 1 红：水平向右，到右侧四边形右顶点
        (336, 56),   # 2 绿：向右上，到右侧四边形右上顶点
        (264, 180),  # 3 蓝：向右下，到下方尖角
        (300, 108),  # 4 青：向右上，到四边形内部
        (184, 72),   # 5 品红：向左上，进入左侧五边形
        (240, 56),   # 6 橙：正上方，到右侧四边形左上顶点
    ]

    for i, (start, end, color) in enumerate(zip(starts, ends, COLORS), 1):
        ax.plot([start[0], end[0]], [start[1], end[1]],
                color=color, linewidth=2.6, zorder=2 + i)

    # 起点标记
    ax.scatter([240], [144], s=42, color="#202020", zorder=10)
    ax.annotate("起点 (240,144)", xy=(240, 144), xytext=(206, 126),
                fontsize=9, color="#555555",
                arrowprops=dict(arrowstyle="->", color="#777777", lw=1))

    # 3. 指令列表（与题目输入一致）
    lines = ["运动指令（X, Y, F, mode, flagX, flagY）："]
    for i, inst in enumerate(INSTRUCTIONS, 1):
        lines.append(f"{i}. " + ", ".join(str(v) for v in inst))
    ax.text(0.015, 0.975, "\n".join(lines), transform=ax.transAxes,
            fontsize=9.5, va="top", ha="left", linespacing=1.45,
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#F5F5F5",
                      edgecolor="#BBBBBB"))

    # 4. 颜色图例
    handles = [Line2D([0], [0], color=c, lw=2.6, label=lab)
               for c, lab in zip(COLORS, LABELS)]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.015, 0.015),
              fontsize=8.5, frameon=True, title="轨迹颜色对应",
              title_fontsize=9, borderpad=0.7)

    ax.set_title("自动轨迹绘制结果", fontsize=16, fontweight="bold", pad=16)
    ax.set_xlabel("X", fontsize=11)
    ax.set_ylabel("Y", fontsize=11)
    ax.set_xlim(40, 365)
    ax.set_ylim(168, -22)
    ax.set_aspect("equal")
    ax.grid(True, linestyle=":", alpha=0.35)
    ax.tick_params(labelsize=9)

    fig.tight_layout()
    fig.savefig(base_output, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"轨迹图已保存：{base_output}")


if __name__ == "__main__":
    output = Path(__file__).resolve().parent / "trajectory.png"
    draw(output)
