
import os
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
os.makedirs(OUT_DIR, exist_ok=True)

FONT_PATH = "C:/Windows/Fonts/consola.ttf"
FONT_BOLD = "C:/Windows/Fonts/consolab.ttf"
MONO = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 17)
MONO_BOLD = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 17)
TITLE_FONT = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 18)

BG = "#0d1117"
BAR = "#161b22"
FG = "#c9d1d9"
GREEN = "#3fb950"
BLUE = "#58a6ff"
YELLOW = "#d29922"
GREY = "#8b949e"
RED = "#f85149"

WIN_W = 980
BAR_H = 40
PAD_X = 20
LINE_H = 26
TOP_PAD = 18
BOT_PAD = 18


def colorize(line: str):
    """返回 [(片段, 颜色), ...] 简易语法高亮。"""
    s = line
    if s.startswith("[SUCCESS]"):
        return [(s, GREEN)]
    if s.startswith("[INFO]"):
        return [(s, BLUE)]
    if s.startswith("[WARN]"):
        return [(s, YELLOW)]
    if s.startswith("[ERROR]") or s.startswith("Traceback"):
        return [(s, RED)]
    if s.startswith("[VERIFY]"):
        return [(s, "#bc8cff")]
    if s.startswith("[方案A]"):
        return [(s, BLUE)]
    if s.startswith("[方案B]"):
        return [(s, GREEN)]
    if s.startswith("[exit=") or s.startswith("[") and "exit=" in s:
        return [(s, GREY)]
    if s.startswith("  ·") or s.startswith("=") or s.startswith("-"):
        return [(s, GREY)]
    if s.lstrip().startswith(("标题：", "时间：", "链接：")):
        return [(s, FG)]
    return [(s, FG)]


def make_screenshot(filename: str, title: str, lines: list[str]) -> str:
    n = len(lines)
    win_h = BAR_H + TOP_PAD + n * LINE_H + BOT_PAD
    img = Image.new("RGB", (WIN_W, win_h), BG)
    d = ImageDraw.Draw(img)

    # 标题栏
    d.rectangle([0, 0, WIN_W, BAR_H], fill=BAR)
    for cx, c in [(22, RED), (44, YELLOW), (66, GREEN)]:
        d.ellipse([cx - 6, 14, cx + 6, 26], fill=c)
    d.text((90, 10), title, font=TITLE_FONT, fill=FG)

    y = BAR_H + TOP_PAD
    for line in lines:
        x = PAD_X
        for seg, col in colorize(line):
            d.text((x, y), seg, font=MONO, fill=col)
            x += d.textlength(seg, font=MONO)
        y += LINE_H

    path = os.path.join(OUT_DIR, filename)
    img.save(path)
    return path


def run_script(name: str) -> list[str]:
    """真实运行指定脚本并捕获其标准输出（含 stderr）。"""
    import subprocess
    root = os.path.dirname(os.path.abspath(__file__))
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.run(
        ["python", name + ".py"], cwd=root, env=env,
        capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    text = (proc.stdout + proc.stderr).strip()
    print(f"运行 {name}.py, exit={proc.returncode}, 输出 {len(text.splitlines())} 行")
    return text.splitlines()


def csv_lines() -> list[str]:
    root = os.path.dirname(os.path.abspath(__file__))
    run_script("step3_persist")
    with open(os.path.join(root, "result.csv"), "r", encoding="utf-8-sig") as f:
        return f.read().splitlines()


if __name__ == "__main__":
    outputs = [
        ("01_step1_fetch_html.png", "爬虫实验 - 步骤1：发送请求获取 HTML",
         run_script("step1_fetch_html")),
        ("02_step2_parse_fields.png", "爬虫实验 - 步骤2：解析 HTML 提取字段",
         run_script("step2_parse_fields")),
        ("03_step3_persist.png", "爬虫实验 - 步骤3：CSV 持久化与异常处理",
         run_script("step3_persist")),
        ("04_step4_refactor.png", "爬虫实验 - 步骤4：NewsCrawler 重构版运行",
         run_script("step4_news_crawler")),
        ("05_advanced_compare.png", "爬虫实验 - 进阶挑战：静态 vs 动态渲染对比",
         run_script("advanced_dynamic")),
        ("06_result_csv.png", "爬虫实验 - result.csv 数据文件", csv_lines()),
    ]
    for fn, title, lines in outputs:
        p = make_screenshot(fn, title, lines)
        print("ok:", p)
