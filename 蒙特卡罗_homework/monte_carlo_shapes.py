#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
蒙特卡罗方法手搓图形（Homework）

题目：用蒙特卡罗（Monte Carlo）随机投点的方法"手搓"图形——
      不调用任何画圆 API，只靠均匀随机数散点把圆 / 四分之一圆画出来，
      并顺便用面积比估算圆周率 π。

原理：
    在边长 2 的正方形 [-1,1] x [-1,1] 内均匀随机撒点，
    点到原点距离 <= 1 者落入单位圆。
        圆面积 / 正方形面积 ≈ 落入圆内点数 / 总点数
        π * 1^2 / 4 ≈ n_in / n
        => π ≈ 4 * n_in / n
    四分之一圆同理：在 [0,1] x [0,1] 内撒点，π ≈ 4 * n_in / n。

用法：
    python monte_carlo_shapes.py --n 20000 --seed 42 --outdir .

输出（即实验截图）：
    实验截图1_投点画圆.png
    实验截图2_四分之一圆.png
    实验截图3_圆周率收敛曲线.png
    实验截图4_综合结果.png
"""

import argparse
import os

import numpy as np
import matplotlib

matplotlib.use("Agg")  # 无界面环境也能出图
import matplotlib.pyplot as plt

# Windows 中文字体，避免中文标题显示成方块
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def make_circle_points(n: int, rng: np.random.Generator):
    """在 [-1,1]^2 内均匀撒 n 个点，返回坐标与是否落入单位圆的布尔掩码。"""
    xy = rng.uniform(-1.0, 1.0, size=(n, 2))
    inside = (xy[:, 0] ** 2 + xy[:, 1] ** 2) <= 1.0
    return xy, inside


def make_quarter_points(n: int, rng: np.random.Generator):
    """在 [0,1]^2 内均匀撒 n 个点。"""
    xy = rng.uniform(0.0, 1.0, size=(n, 2))
    inside = (xy[:, 0] ** 2 + xy[:, 1] ** 2) <= 1.0
    return xy, inside


def pi_estimate(n_in: int, n: int) -> float:
    """由落入圆内的点数估算 π。"""
    return 4.0 * n_in / n


def fig_darts(xy, inside, pi_hat: float, n: int, path: str):
    """实验截图 1：随机投点'手搓'出整个圆。"""
    fig, ax = plt.subplots(figsize=(7.2, 7.2), dpi=150)
    ax.scatter(xy[~inside, 0], xy[~inside, 1], s=4, c="#F0A202", alpha=0.45,
               label="圆外（舍去）", linewidths=0)
    ax.scatter(xy[inside, 0], xy[inside, 1], s=5, c="#2E86DE", alpha=0.75,
               label="圆内（保留）", linewidths=0)
    # 只画一条极细的参考圆弧用于对照，图形本身完全由散点"搓"出来
    t = np.linspace(0, 2 * np.pi, 400)
    ax.plot(np.cos(t), np.sin(t), "--", c="#C0392B", lw=1.0, alpha=0.7,
            label="理论边界（对照）")
    ax.set_title(f"实验1  蒙特卡罗投点手搓圆形\n投点 N={n:,}，圆内 {inside.sum():,}，π≈{pi_hat:.5f}",
                 fontsize=13)
    ax.set_xlabel("x"); ax.set_ylabel("y")
    ax.set_xlim(-1.08, 1.08); ax.set_ylim(-1.08, 1.08)
    ax.set_aspect("equal")
    ax.grid(alpha=0.2)
    ax.legend(loc="upper right", fontsize=9, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_quarter(xy, inside, pi_hat: float, n: int, path: str):
    """实验截图 2：四分之一圆扇形。"""
    fig, ax = plt.subplots(figsize=(7.2, 6.2), dpi=150)
    ax.scatter(xy[~inside, 0], xy[~inside, 1], s=5, c="#F0A202", alpha=0.5,
               label="扇形外", linewidths=0)
    ax.scatter(xy[inside, 0], xy[inside, 1], s=6, c="#2E86DE", alpha=0.8,
               label="扇形内", linewidths=0)
    t = np.linspace(0, np.pi / 2, 200)
    ax.plot(np.cos(t), np.sin(t), "--", c="#C0392B", lw=1.0, alpha=0.7,
            label="理论圆弧（对照）")
    ax.set_title(f"实验2  四分之一圆（面积法）\n投点 N={n:,}，π≈{pi_hat:.5f}，误差={abs(pi_hat - np.pi):.5f}",
                 fontsize=13)
    ax.set_xlabel("x"); ax.set_ylabel("y")
    ax.set_xlim(-0.05, 1.05); ax.set_ylim(-0.05, 1.05)
    ax.set_aspect("equal")
    ax.grid(alpha=0.2)
    ax.legend(loc="upper right", fontsize=9, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_convergence(xy, inside, path: str):
    """实验截图 3：估计值随样本数增加的收敛过程。"""
    cumulative = np.cumsum(inside)
    k = np.arange(1, len(inside) + 1)
    estimates = 4.0 * cumulative / k
    # 抽样若干点画曲线，避免图像过密
    idx = np.unique(np.geomspace(1, len(k), num=1200).astype(int)) - 1
    fig, ax = plt.subplots(figsize=(8.2, 5.2), dpi=150)
    ax.semilogx(k[idx], estimates[idx], color="#2E86DE", lw=1.3,
                label="蒙特卡罗估计值")
    ax.axhline(np.pi, color="#C0392B", ls="--", lw=1.2, label="真实 π")
    ax.set_title("实验3  圆周率估计的收敛曲线", fontsize=13)
    ax.set_xlabel("投点数量 N（对数坐标）"); ax.set_ylabel("π 的估计值")
    ax.grid(alpha=0.25, which="both")
    ax.legend(fontsize=10)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_summary(parts, pi_circle: float, pi_quarter: float, seed: int, path: str):
    """实验截图 4：把三次实验汇总到一张图，便于交作业。"""
    xy, inside, xy_q, inside_q, pi_series, k_series = parts
    fig, axes = plt.subplots(2, 2, figsize=(11, 9), dpi=150)
    fig.suptitle("蒙特卡罗方法手搓图形 —— 实验结果汇总", fontsize=16, fontweight="bold")

    ax = axes[0, 0]
    ax.scatter(xy[~inside, 0], xy[~inside, 1], s=2, c="#F0A202", alpha=0.35, linewidths=0)
    ax.scatter(xy[inside, 0], xy[inside, 1], s=3, c="#2E86DE", alpha=0.7, linewidths=0)
    ax.set_title(f"(a) 手搓圆：π ≈ {pi_circle:.5f}")
    ax.set_aspect("equal"); ax.set_xlim(-1.05, 1.05); ax.set_ylim(-1.05, 1.05)

    ax = axes[0, 1]
    ax.scatter(xy_q[~inside_q, 0], xy_q[~inside_q, 1], s=2, c="#F0A202", alpha=0.35, linewidths=0)
    ax.scatter(xy_q[inside_q, 0], xy_q[inside_q, 1], s=3, c="#2E86DE", alpha=0.7, linewidths=0)
    ax.set_title(f"(b) 四分之一圆：π ≈ {pi_quarter:.5f}")
    ax.set_aspect("equal"); ax.set_xlim(-0.05, 1.05); ax.set_ylim(-0.05, 1.05)

    ax = axes[1, 0]
    idx = np.unique(np.geomspace(1, len(k_series), num=1000).astype(int)) - 1
    ax.semilogx(k_series[idx], pi_series[idx], c="#2E86DE", lw=1.2, label="估计值")
    ax.axhline(np.pi, c="#C0392B", ls="--", lw=1.1, label="真实 π")
    ax.set_title("(c) π 估计收敛曲线")
    ax.set_xlabel("投点数 N"); ax.set_ylabel("π"); ax.legend(fontsize=9)

    ax = axes[1, 1]
    ax.axis("off")
    report = (
        "实验参数与结果\n"
        "────────────────────\n"
        f"随机数种子 seed : {seed}\n"
        f"投点总数 N      : {len(xy):,}\n"
        f"圆内点数 n_in   : {inside.sum():,}\n"
        f"四分之一圆内    : {inside_q.sum():,}\n\n"
        f"整圆法  π ≈ {pi_circle:.6f}\n"
        f"1/4圆法 π ≈ {pi_quarter:.6f}\n"
        f"参考值  π = {np.pi:.6f}\n\n"
        "结论：散点越密，圆/扇形轮廓越清晰；\n"
        "投点数增大时 π 的估计逐渐收敛。"
    )
    ax.text(0.02, 0.95, report, va="top", ha="left", fontsize=11, family="Microsoft YaHei")

    for a in axes.flat[:3]:
        a.grid(alpha=0.2)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(path)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="蒙特卡罗方法手搓图形")
    parser.add_argument("--n", type=int, default=20000, help="每次实验的投点数量")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--outdir", default=".", help="实验截图输出目录")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    xy, inside = make_circle_points(args.n, rng)
    xy_q, inside_q = make_quarter_points(args.n, rng)
    pi_circle = pi_estimate(int(inside.sum()), args.n)
    pi_quarter = pi_estimate(int(inside_q.sum()), args.n)

    k = np.arange(1, args.n + 1)
    pi_series = 4.0 * np.cumsum(inside) / k

    out = lambda name: os.path.join(args.outdir, name)
    fig_darts(xy, inside, pi_circle, args.n, out("实验截图1_投点画圆.png"))
    fig_quarter(xy_q, inside_q, pi_quarter, args.n, out("实验截图2_四分之一圆.png"))
    fig_convergence(xy, inside, out("实验截图3_圆周率收敛曲线.png"))
    fig_summary((xy, inside, xy_q, inside_q, pi_series, k),
                pi_circle, pi_quarter, args.seed, out("实验截图4_综合结果.png"))

    print(f"投点总数 N = {args.n:,}, seed = {args.seed}")
    print(f"整圆法   : 圆内 {inside.sum():,} 点, π ≈ {pi_circle:.6f}, 误差 {abs(pi_circle-np.pi):.6f}")
    print(f"1/4圆法  : 圆内 {inside_q.sum():,} 点, π ≈ {pi_quarter:.6f}, 误差 {abs(pi_quarter-np.pi):.6f}")
    print("实验截图已保存到:", os.path.abspath(args.outdir))


if __name__ == "__main__":
    main()
