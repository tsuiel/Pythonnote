# -*- coding: utf-8 -*-


import os
import matplotlib
matplotlib.use("Agg")  # 无界面后端，直接保存图片
# 配置中文字体，避免图中文字显示为方块
matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE, "screenshots")
os.makedirs(OUT_DIR, exist_ok=True)


def draw_tianzige(ax, size=10, with_diagonal=False, title="田字格"):
    """
    在坐标轴 ax 上绘制田字格。

    参数:
        size         : 正方形边长
        with_diagonal: 是否绘制对角线（米字格）
        title        : 子图标题
    """
    half = size / 2

    # 外框：实线矩形
    ax.add_patch(Rectangle((0, 0), size, size, fill=False,
                           edgecolor="#222222", linewidth=2.6))

    # 横、竖中线：红色虚线
    ax.plot([0, size], [half, half], color="#d64541",
            linewidth=1.8, linestyle=(0, (6, 4)))
    ax.plot([half, half], [0, size], color="#d64541",
            linewidth=1.8, linestyle=(0, (6, 4)))

    # 可选：对角线（米字格），浅灰虚线
    if with_diagonal:
        ax.plot([0, size], [0, size], color="#9aa0a6",
                linewidth=1.3, linestyle=(0, (4, 4)))
        ax.plot([0, size], [size, 0], color="#9aa0a6",
                linewidth=1.3, linestyle=(0, (4, 4)))

    # 中心十字交点
    ax.plot(half, half, marker="+", markersize=16,
            markeredgewidth=1.8, color="#d64541")

    # 四个小格中的轻淡提示字：横、竖、撇、捺方位
    ax.text(half / 2, half * 1.5, "上", ha="center", va="center",
            fontsize=13, color="#c9c9c9")
    ax.text(half * 1.5, half * 1.5, "右上", ha="center", va="center",
            fontsize=11, color="#c9c9c9")
    ax.text(half / 2, half / 2, "左下", ha="center", va="center",
            fontsize=11, color="#c9c9c9")
    ax.text(half * 1.5, half / 2, "右下", ha="center", va="center",
            fontsize=11, color="#c9c9c9")

    ax.set_xlim(-1.2, size + 1.2)
    ax.set_ylim(-1.2, size + 1.2)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, fontsize=14, pad=10)


def main():
    fig, axes = plt.subplots(1, 2, figsize=(10, 5.2))
    draw_tianzige(axes[0], title="标准田字格（实线框 + 虚线中线）")
    draw_tianzige(axes[1], with_diagonal=True, title="米字格（附加对角线）")

    fig.suptitle("P196 5.1  田字格绘制", fontsize=17, fontweight="bold", y=0.98)
    plt.tight_layout(rect=[0, 0, 1, 0.94])

    out = os.path.join(OUT_DIR, "tianzige_draw.png")
    fig.savefig(out, dpi=160, bbox_inches="tight", facecolor="white")
    print(f"已保存: {out}")


if __name__ == "__main__":
    main()
