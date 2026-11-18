# -*- coding: utf-8 -*-
"""
将真实运行日志渲染为终端风格的实验截图（PNG）。
用途：实验报告中展示程序运行的真实输出。
"""
import os
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "C:/Windows/Fonts/msyh.ttc"
FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"

BG = (30, 30, 30)           # 终端深色背景
TITLE_BG = (45, 45, 45)
FG = (212, 212, 212)        # 默认前景色
GREEN = (106, 153, 85)      # 成功
YELLOW = (206, 145, 120)    # 信息/警告
CYAN = (86, 156, 214)       # 分段标题
WHITE = (240, 240, 240)
LINE_H = 26
PAD_X = 28
TOP_H = 56
WIDTH = 1080


def pick_color(line):
    if line.startswith("="):
        return CYAN
    if "[成功]" in line or "分析完成" in line:
        return GREEN
    if line.startswith("[信息]") or line.startswith("[分词]"):
        return YELLOW if line.startswith("[警告]") else FG
    if "[警告]" in line or "[错误]" in line:
        return (220, 120, 120)
    if "[蒙特卡洛]" in line or "进阶方向" in line:
        return CYAN
    if line.startswith("【"):
        return WHITE
    return FG


def render_terminal(log_text, title, out_path, highlight_keywords=None):
    lines = log_text.rstrip("\n").split("\n")
    height = TOP_H + LINE_H * len(lines) + 30
    img = Image.new("RGB", (WIDTH, height), BG)
    draw = ImageDraw.Draw(img)

    font = ImageFont.truetype(FONT_PATH, 17)
    font_title = ImageFont.truetype(FONT_BOLD, 18)
    font_dot = ImageFont.truetype(FONT_PATH, 22)

    # 标题栏
    draw.rectangle([0, 0, WIDTH, TOP_H], fill=TITLE_BG)
    colors = [(237, 106, 94), (245, 191, 79), (99, 199, 84)]
    for i, c in enumerate(colors):
        x = 18 + i * 28
        draw.ellipse([x, 20, x + 14, 34], fill=c)
    draw.text((WIDTH // 2, TOP_H // 2), title, font=font_title, fill=(200, 200, 200), anchor="mm")

    # 正文
    y = TOP_H + 14
    for line in lines:
        draw.text((PAD_X, y), line, font=font, fill=pick_color(line))
        y += LINE_H

    img.save(out_path, "PNG")
    print(f"[截图] 已生成：{out_path}  ({img.size[0]}x{img.size[1]})")


def main():
    base = "D:/workbuddy work/本地文档智能审查与摘要实验"
    ss_dir = os.path.join(base, "screenshots")
    os.makedirs(ss_dir, exist_ok=True)

    # 1. 主程序运行输出
    with open(os.path.join(base, "output/run_log.txt"), encoding="utf-8") as f:
        main_log = f.read()
    # 去掉 jieba 首次构建缓存与 matplotlib 警告，保留核心业务输出，使截图更聚焦
    main_log_clean = "\n".join(
        l for l in main_log.split("\n")
        if not l.startswith("Building prefix dict")
        and not l.startswith("Dumping model")
        and not l.startswith("Loading model")
        and not l.startswith("Prefix dict")
        and "UserWarning" not in l
        and not l.strip().startswith("plt.show()")
    )
    render_terminal(main_log_clean, "analyze_documents.py  ——  主程序运行结果",
                    os.path.join(ss_dir, "01_主程序运行输出.png"))

    # 2. 进阶 Agent 运行输出
    with open(os.path.join(base, "output/agent_run_log.txt"), encoding="utf-8") as f:
        agent_log = f.read()
    agent_log_clean = "\n".join(
        l for l in agent_log.split("\n")
        if not l.startswith("Building prefix dict")
        and not l.startswith("Dumping model")
        and not l.startswith("Loading model")
        and not l.startswith("Prefix dict")
    )
    render_terminal(agent_log_clean, "agent_advanced.py  ——  Agent 化进阶运行结果",
                    os.path.join(ss_dir, "02_进阶Agent运行输出.png"))

    # 3. 汇总报告内容（终端风格展示）
    with open(os.path.join(base, "output/summary_report.txt"), encoding="utf-8") as f:
        report = f.read()
    render_terminal(report, "summary_report.txt  ——  关键词汇总报告",
                    os.path.join(ss_dir, "03_汇总报告内容.png"))

    # 4. 词云图片复制到 screenshots
    from shutil import copyfile
    copyfile(os.path.join(base, "output/document_wordcloud.png"),
             os.path.join(ss_dir, "04_词云生成结果.png"))
    print("[截图] 已生成：04_词云生成结果.png")

    # 5. 项目目录结构（文本形式）
    tree = """本地文档智能审查与摘要实验/
├── src/
│   ├── analyze_documents.py      # 核心分析模块（基础功能）
│   └── agent_advanced.py         # 进阶 Agent 化模块
├── docs/                         # 待分析文档目录
│   ├── 人工智能技术发展趋势.txt
│   ├── 智慧教育应用实践总结.txt
│   └── 智能医疗研究进展.md
├── config/
│   ├── stopwords.txt             # 自定义停用词表（114 词）
│   └── user_dict.txt             # 自定义专业词典（31 词）
├── output/                       # 程序输出
│   ├── document_wordcloud.png    # 词云图片
│   ├── summary_report.csv        # 汇总报告（CSV）
│   ├── summary_report.txt        # 汇总报告（TXT）
│   └── monte_carlo_result.json   # 蒙特卡洛结果
└── screenshots/                  # 实验截图"""
    render_terminal(tree, "项目目录结构", os.path.join(ss_dir, "05_项目目录结构.png"))


if __name__ == "__main__":
    main()
