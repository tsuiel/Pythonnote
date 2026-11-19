# -*- coding: utf-8 -*-
"""


运行方式：python tianzige_char.py
"""

# 字符常量：角点、横线、竖线、竖向虚线、横向虚线
CORNER = "+"
H_LINE = "-"
V_LINE = "|"
V_DASH = ":"   # 竖向中线（虚线效果）
H_DASH = "·"   # 横向中线（虚线效果）


def draw_tianzige(half_width=8, half_height=4):
    """
    绘制字符田字格。

    参数:
        half_width : 每个小格的宽度（字符数）
        half_height: 每个小格的高度（行数）
    """
    w, h = half_width, half_height
    border = H_LINE * w

    # 1. 上边框
    print(CORNER + border + CORNER + border + CORNER)

    # 2. 上半部分：左右两格，中间用竖向虚线分隔
    for _ in range(h):
        print(V_LINE + " " * w + V_DASH + " " * w + V_LINE)

    # 3. 横向中线（虚线），中间为十字交点
    print(H_DASH * w + CORNER + H_DASH * w)

    # 4. 下半部分
    for _ in range(h):
        print(V_LINE + " " * w + V_DASH + " " * w + V_LINE)

    # 5. 下边框
    print(CORNER + border + CORNER + border + CORNER)


if __name__ == "__main__":
    print("=" * 40)
    print("      P196 5.1  字符田字格（8x4 半格）")
    print("=" * 40)
    draw_tianzige(8, 4)

    print("\n" + "=" * 40)
    print("      字符田字格（5x2 半格，缩小版）")
    print("=" * 40)
    draw_tianzige(5, 2)
