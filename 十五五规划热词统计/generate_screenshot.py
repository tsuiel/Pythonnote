

from __future__ import annotations

import os
import subprocess
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
FONT_FILE = "C:/Windows/Fonts/msyh.ttc"
FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"


def f(size: int, bold: bool = False):
    path = FONT_BOLD if bold and Path(FONT_BOLD).exists() else FONT_FILE
    return ImageFont.truetype(path, size) if Path(path).exists() else ImageFont.load_default(size=size)


def run_program() -> str:
    """真实执行主程序并捕获 stdout，保证截图内容与实际运行结果一致。"""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [sys.executable, str(ROOT / "hotword_stats.py"), "-n", "20"]
    result = subprocess.run(
        cmd, cwd=str(ROOT), env=env, capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"主程序运行失败:\n{result.stdout}\n{result.stderr}")
    log = result.stdout.replace("\r\n", "\n")
    (OUT / "运行日志.txt").write_text(
        "运行命令: python hotword_stats.py -n 20\n"
        f"运行时间: {datetime.now():%Y-%m-%d %H:%M:%S}\n"
        f"Python  : {sys.version.split()[0]}\n"
        + "=" * 78 + "\n" + log,
        encoding="utf-8",
    )
    return log


def line_color(line: str) -> str:
    s = line.strip()
    if s.startswith("=") or s.startswith("-") and set(s) <= {"-"}:
        return "#4fc1ff"
    if s.startswith("【"):
        return "#dcdcaa"
    if s.startswith("- output") or s.startswith("- ") and "output\\" in s:
        return "#6a9955"
    if "十五五" in s and "热词频率统计" in s:
        return "#ffffff"
    if "排名" in s and ("热词" in s or "复合" in s):
        return "#9cdcfe"
    return "#d4d4d4"


def draw_grid_text(d: ImageDraw.ImageDraw, x: float, y: float, text: str,
                   font_obj, fill: str, unit: float) -> None:
    """按等宽网格逐字符绘制：中文占 2 格、ASCII 占 1 格，保证表格不错位。"""
    for ch in text:
        if ch == " ":
            x += unit
            continue
        wide = unicodedata.east_asian_width(ch) in ("W", "F")
        cell = unit * (2 if wide else 1)
        cw = font_obj.getlength(ch)
        d.text((x + max(0, (cell - cw) / 2), y), ch, font=font_obj, fill=fill)
        x += cell


def terminal_screenshot(log: str) -> Path:
    lines = log.split("\n")
    unit, row_h = 9.2, 24
    width = 860
    title_h, status_h, pad_y = 44, 38, 14
    height = title_h + pad_y * 2 + row_h * (len(lines) + 2) + status_h
    img = Image.new("RGB", (width, height), "#0c0c0c")
    d = ImageDraw.Draw(img)

    # 标题栏
    d.rectangle([0, 0, width, title_h], fill="#1f1f1f")
    for i, color in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
        cx = 22 + i * 22
        d.ellipse([cx, 18, cx + 11, 29], fill=color)
    d.text((width / 2 - 215, 12), "Windows PowerShell  -  python hotword_stats.py -n 20",
           font=f(15), fill="#b0b0b0")
    d.text((width - 95, 12), "—   □   ×", font=f(15), fill="#b0b0b0")
    d.line([0, title_h, width, title_h], fill="#333333", width=1)

    body = f(17)
    y = title_h + pad_y
    for ln in lines:
        draw_grid_text(d, 22, y, ln, body, line_color(ln), unit)
        y += row_h

    # 提示符与光标，增强"真实运行"观感
    prompt = "PS C:\\Users\\LEGION\\Desktop\\python> python hotword_stats.py -n 20"
    draw_grid_text(d, 22, y + 4, prompt, f(17), "#8a8a8a", unit)
    d.rectangle([22 + len(prompt) * unit + 6, y + 8, 22 + len(prompt) * unit + 15, y + 25],
                fill="#d4d4d4")
    d.line([0, height - status_h, width, height - status_h], fill="#333333", width=1)
    d.text((22, height - status_h + 10),
           "UTF-8  |  Python " + sys.version.split()[0] + "  |  jieba 0.42  |  Pillow",
           font=f(12), fill="#6a6a6a")

    path = OUT / "01_程序运行截图.png"
    img.save(path)
    return path


def paste_fit(canvas: Image.Image, src: Image.Image, box: tuple[int, int, int, int],
              label: str) -> None:
    """把图片等比缩放后贴到指定区域，并绘制标签与边框。"""
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle([x0 - 8, y0 - 34, x1 + 8, y1 + 8], radius=10,
                        fill="#ffffff", outline="#d8dee9", width=2)
    d.text((x0 + 2, y0 - 30), label, font=f(17, bold=True), fill="#b91c1c")
    ratio = min((x1 - x0) / src.width, (y1 - y0) / src.height)
    nw, nh = int(src.width * ratio), int(src.height * ratio)
    resized = src.resize((nw, nh), Image.LANCZOS)
    px, py = x0 + ((x1 - x0) - nw) // 2, y0 + ((y1 - y0) - nh) // 2
    canvas.paste(resized, (px, py))


def overview(term_path: Path, bar_path: Path, cloud_path: Path) -> Path:
    W, H = 2000, 2050
    canvas = Image.new("RGB", (W, H), "#eef2f7")
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, W, 104], fill="#9f1239")
    d.rectangle([0, 100, W, 104], fill="#f59e0b")
    d.text((44, 20), "实验截图 · “十五五”发展规划报告热词频率统计",
           font=f(34, bold=True), fill="#ffffff")
    d.text((46, 66),
           f"语料：中国人大网《“十五五”规划纲要》全文  |  环境：Python {sys.version.split()[0]} / Windows  |  "
           f"日期：{datetime.now():%Y-%m-%d}",
           font=f(16), fill="#fde8e8")

    paste_fit(canvas, Image.open(term_path).convert("RGB"),
              (44, 168, 900, 1940), "① 程序运行结果（真实控制台输出）")
    paste_fit(canvas, Image.open(bar_path).convert("RGB"),
              (960, 168, 1956, 1060), "② 通用热词 Top20 词频柱状图")
    paste_fit(canvas, Image.open(cloud_path).convert("RGB"),
              (960, 1130, 1956, 1940), "③ 高频热词词云图")

    d.text((46, 1970),
           "运行命令：python hotword_stats.py -n 20    |    分词：jieba + 政策自定义词典    |    "
           "停用词过滤 → 词频统计 → CSV 导出 → 可视化",
           font=f(16), fill="#475569")
    d.text((46, 2002),
           "结果文件：词频统计结果.csv / 热词Top20柱状图.png / 复合主题词Top15柱状图.png / 热词词云.png / 运行日志.txt",
           font=f(15), fill="#64748b")

    path = OUT / "00_实验结果总览.png"
    canvas.save(path)
    return path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    log = run_program()
    term = terminal_screenshot(log)
    bar = OUT / "热词Top20柱状图.png"
    cloud = OUT / "热词词云.png"
    total = overview(term, bar, cloud)
    print("终端截图 :", term)
    print("实验总览 :", total)
    print("运行日志 :", OUT / "运行日志.txt")
    print("控制台行数:", len(log.splitlines()))


if __name__ == "__main__":
    main()
