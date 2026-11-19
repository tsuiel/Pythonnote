

import math
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
# 配置中文字体，避免图中文字显示为方块
matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE, "screenshots")
os.makedirs(OUT_DIR, exist_ok=True)


def koch_curve(p1, p2, order):
    """
    递归生成从 p1 到 p2 的科赫曲线点列。

    参数:
        p1, p2 : 线段起点、终点 (x, y)
        order  : 阶数，0 表示一条直线
    返回:
        点列表（含起点和终点）
    """
    if order == 0:
        return [p1, p2]

    p1 = np.asarray(p1, dtype=float)
    p2 = np.asarray(p2, dtype=float)
    delta = (p2 - p1) / 3.0

    # 三等分点 a、b
    a = p1 + delta
    b = p1 + 2 * delta

    # 将向量 (b-a) 顺时针旋转 60°，得到向外凸起的顶点 c
    angle = math.radians(-60)
    rot = np.array([[math.cos(angle), -math.sin(angle)],
                    [math.sin(angle),  math.cos(angle)]])
    c = a + rot.dot(b - a)

    # 四段递归：p1→a, a→c, c→b, b→p2（拼接时去掉重复端点）
    return (koch_curve(p1, a, order - 1)[:-1] +
            koch_curve(a, c, order - 1)[:-1] +
            koch_curve(c, b, order - 1)[:-1] +
            koch_curve(b, p2, order - 1))


def koch_snowflake(order, side=1.0):
    """
    生成 n 阶科赫雪花的闭合点列（以等边三角形为基础）。
    """
    h = side * math.sqrt(3) / 2
    # 等边三角形，逆时针排列，使凸起方向朝外
    A = (0.0, 0.0)
    B = (side, 0.0)
    C = (side / 2, h)

    pts = []
    for p, q in ((A, B), (B, C), (C, A)):
        pts += koch_curve(p, q, order)[:-1]
    pts.append(pts[0])  # 闭合
    return np.array(pts)


def draw_one(ax, order, color="#2b6cb0"):
    pts = koch_snowflake(order)
    ax.fill(pts[:, 0], pts[:, 1], color=color, alpha=0.10)
    ax.plot(pts[:, 0], pts[:, 1], color=color, linewidth=1.1)

    # 顶点数 = 3 * 4^order
    segments = 3 * (4 ** order)
    ax.set_title(f"{order} 阶科赫雪花\n线段数 = {segments}", fontsize=12)
    ax.set_aspect("equal")
    ax.axis("off")
    # 科赫曲线会向三角形外侧凸起，需留出足够边距，避免高阶图形被截断
    margin = 0.12
    ax.set_xlim(-margin, 1 + margin)
    ax.set_ylim(-0.45, math.sqrt(3) / 2 + margin)


def main():
    # 图 1：0~4 阶汇总对比
    fig, axes = plt.subplots(2, 3, figsize=(12, 7.6))
    axes = axes.ravel()
    for order in range(5):
        draw_one(axes[order], order)

    # 第 6 个子图放说明文字
    axes[5].axis("off")
    info = ("科赫雪花 (Koch Snowflake)\n\n"
            "生成规则：\n"
            "  1. 从等边三角形开始\n"
            "  2. 每条边三等分\n"
            "  3. 中间段替换为向外凸的等边三角形两边\n"
            "  4. 对新线段递归重复\n\n"
            "线段数：3 x 4^n\n"
            "分形维数：log4 / log3 ≈ 1.2619")
    axes[5].text(0.02, 0.98, info, va="top", ha="left", fontsize=11,
                 transform=axes[5].transAxes,
                 bbox=dict(boxstyle="round,pad=0.5",
                           facecolor="#f4f6f8", edgecolor="#cbd5e0"))

    fig.suptitle("科赫雪花 —— 0~4 阶生成结果", fontsize=19, fontweight="bold", y=0.98)
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    out = os.path.join(OUT_DIR, "koch_all_orders.png")
    fig.savefig(out, dpi=170, bbox_inches="tight", facecolor="white")
    print(f"已保存: {out}")

    # 图 2~6：每一阶单独大图
    palette = ["#2b6cb0", "#2f855a", "#b7791f", "#c53030", "#6b46c1"]
    for order in range(5):
        fig, ax = plt.subplots(figsize=(6.4, 6.0))
        draw_one(ax, order, color=palette[order])
        ax.set_title(f"{order} 阶科赫雪花\n线段数 = {3 * 4 ** order}",
                     fontsize=15, pad=12)
        fig.suptitle("Koch Snowflake", fontsize=12, color="#718096", y=0.94)
        plt.tight_layout()
        out = os.path.join(OUT_DIR, f"koch_order_{order}.png")
        fig.savefig(out, dpi=170, bbox_inches="tight", facecolor="white")
        print(f"已保存: {out}")
        plt.close(fig)


if __name__ == "__main__":
    main()
