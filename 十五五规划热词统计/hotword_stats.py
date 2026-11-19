
from __future__ import annotations

import argparse
import csv
import logging
import random
import re
import sys
import unicodedata
import warnings
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# 优先使用项目内置的 jieba（无需联网安装）；若用户已自行安装也可用
sys.path.insert(0, str(ROOT / "vendor"))
warnings.filterwarnings("ignore", category=SyntaxWarning)
logging.getLogger("jieba").setLevel(logging.ERROR)

try:
    import jieba
    # jieba 默认会把 DEBUG 日志打到 stderr，这里调高到 ERROR 保持输出干净
    getattr(jieba, "setLogLevel", lambda *_: None)(logging.ERROR)
except ImportError:  # 极端情况：内置库缺失时给出明确提示
    sys.exit("缺少分词库：请把 vendor/jieba 目录放回项目文件夹，或执行 pip install jieba")

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None  # 图画功能降级，统计与 CSV 仍可用

DEFAULT_INPUT = ROOT / "data" / "十五五规划纲要.txt"
DEFAULT_OUTDIR = ROOT / "output"
DEFAULT_STOPWORDS = ROOT / "stopwords.txt"
DEFAULT_DICT = ROOT / "custom_dict.txt"
DEFAULT_KEYWORDS = ROOT / "keywords.txt"

# 中文片段 / 英文(含 5G、AI+ 等)片段
CHUNK_RE = re.compile(r"[\u4e00-\u9fff]+|[A-Za-z0-9]*[A-Za-z][A-Za-z0-9+]*")
# 章节编号、专栏编号不属于正文热词
NOISE_RE = re.compile(r"第[一二三四五六七八九十百零〇\d]+[章节篇]|专栏\s*\d+")

FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",      # 微软雅黑
    "C:/Windows/Fonts/simhei.ttf",    # 黑体
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
]
BAR_COLORS = ["#b91c1c", "#c81e1e", "#dc2626", "#e11d48", "#ef4444", "#f97316"]
CLOUD_COLORS = ["#991b1b", "#b91c1c", "#dc2626", "#ea580c", "#f59e0b", "#334155", "#475569"]


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------
def display_width(text: str) -> int:
    """按东亚字符宽度计算显示宽度（中文算 2，英文算 1）。"""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def pad(text: str, width: int, align: str = "left") -> str:
    """按显示宽度对齐字符串，解决中英文混排的表格错位。"""
    gap = max(0, width - display_width(text))
    if align == "right":
        return " " * gap + text
    if align == "center":
        left = gap // 2
        return " " * left + text + " " * (gap - left)
    return text + " " * gap


def read_wordlist(path: Path) -> list[str]:
    """读取词表文件，忽略空行与 # 注释行。"""
    if not path.exists():
        return []
    words = []
    for line in path.read_text(encoding="utf-8").splitlines():
        word = line.strip()
        if word and not word.startswith("#"):
            words.append(word)
    return words


def load_stopwords(path: Path, keep_verbs: bool) -> tuple[set[str], int]:
    """
    停用词文件用 '# ---------- 段落名 ----------' 分段。
    其中"公文通用动词"段可通过 --keep-verbs 保留。
    """
    stops: set[str] = set()
    verbs: set[str] = set()
    in_verb_section = False
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            if "公文通用动词" in s:
                in_verb_section = True
            elif "----------" in s:
                in_verb_section = False
            continue
        stops.add(s)
        if in_verb_section:
            verbs.add(s)
    if keep_verbs:
        stops -= verbs
    return stops, len(verbs)


def font(size: int, bold: bool = False):
    """加载中文字体，按字号缓存。"""
    path = next((p for p in FONT_CANDIDATES if Path(p).exists()), None)
    if bold and Path("C:/Windows/Fonts/msyhbd.ttc").exists():
        path = "C:/Windows/Fonts/msyhbd.ttc"
    if path is None:
        return ImageFont.load_default(size=size)
    return ImageFont.truetype(path, size)


# ---------------------------------------------------------------------------
# 统计核心
# ---------------------------------------------------------------------------
def preprocess(text: str) -> str:
    return NOISE_RE.sub(" ", text)


def tokenize(text: str, min_len: int, stops: set[str]) -> tuple[list[str], int, int]:
    """
    分词并过滤：
      - 中文片段交给 jieba（已加载政策用户词典）
      - 英文/数字混合词（5G、AI、GDP）整体保留
      - 过滤停用词、单字、纯数字
    返回 (有效词列表, 切分总词数, 中文字符数)
    """
    tokens: list[str] = []
    total = 0
    for match in CHUNK_RE.finditer(text):
        chunk = match.group()
        if "\u4e00" <= chunk[0] <= "\u9fff":
            pieces = list(jieba.cut(chunk, cut_all=False))
        else:
            pieces = [chunk]
        for word in pieces:
            total += 1
            word = word.strip()
            if not word or word in stops:
                continue
            if len(word) < min_len:
                continue
            if word.isdigit():
                continue
            tokens.append(word)
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    return tokens, total, chinese_chars


def theme_word_counts(text: str, keywords: list[str]) -> list[tuple[str, int]]:
    """重点政策主题词：在原文上做精确字符串计数，不受分词影响。"""
    return sorted(((kw, text.count(kw)) for kw in keywords if text.count(kw) > 0),
                  key=lambda x: (-x[1], x[0]))


# ---------------------------------------------------------------------------
# 输出：CSV / 图表
# ---------------------------------------------------------------------------
def export_csv(counter: Counter, outdir: Path) -> Path:
    path = outdir / "词频统计结果.csv"
    total = sum(counter.values())
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["排名", "词语", "词频", "占比(%)", "词长"])
        for rank, (word, count) in enumerate(counter.most_common(), 1):
            writer.writerow([rank, word, count, f"{count / total * 100:.4f}", len(word)])
    return path


def draw_bar_chart(items: list[tuple[str, int]], path: Path, title: str = "热词词频") -> bool:
    """横向柱状图：红色系（符合中文语境），Pillow 手绘，无第三方绘图依赖。"""
    if Image is None or not items:
        return False
    row_h, top, bottom, left, right = 38, 100, 60, 250, 150
    width, height = 1280, top + row_h * len(items) + bottom
    img = Image.new("RGB", (width, height), "#f8fafc")
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, width, 6], fill="#b91c1c")
    d.text((40, 30), f"“十五五”规划纲要 · {title} Top {len(items)}",
           font=font(30, bold=True), fill="#0f172a")
    d.text((40, 68), "语料：《中华人民共和国国民经济和社会发展第十五个五年规划纲要》 | 已过滤停用词",
           font=font(14), fill="#64748b")

    max_count = max(c for _, c in items)
    for i, (word, count) in enumerate(items):
        y = top + i * row_h
        if i % 2 == 0:
            d.rectangle([30, y - 4, width - 30, y + row_h - 6], fill="#f1f5f9")
        d.text((44, y + 4), f"{i + 1:02d}", font=font(16), fill="#94a3b8")
        d.text((90, y + 3), word, font=font(19, bold=True), fill="#1e293b")
        bar_len = int((width - left - right) * count / max_count)
        color = BAR_COLORS[i % len(BAR_COLORS)]
        d.rounded_rectangle([left, y + 6, left + max(bar_len, 6), y + 27], radius=5, fill=color)
        d.text((left + bar_len + 12, y + 4), str(count), font=font(17, bold=True), fill="#b91c1c")

    d.line([30, height - 42, width - 30, height - 42], fill="#cbd5e1", width=1)
    d.text((44, height - 32), "分词：jieba + 政策自定义词典   |   绘图：Pillow   |   统计口径：词频 = 该词在全文出现的次数",
           font=font(13), fill="#94a3b8")
    img.save(path)
    return True


def draw_wordcloud(counter: Counter, path: Path, limit: int = 70) -> bool:
    """简易词云：按频次映射字号，随机布局 + 矩形碰撞检测（固定随机种子，可复现）。"""
    if Image is None:
        return False
    width, height = 1280, 720
    img = Image.new("RGB", (width, height), "#ffffff")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, width, 6], fill="#b91c1c")
    d.text((40, 26), "“十五五”规划纲要 · 热词词云", font=font(28, bold=True), fill="#0f172a")

    items = counter.most_common(limit)
    if not items:
        return False
    hi, lo = items[0][1], items[-1][1]
    rnd = random.Random(2026)
    placed: list[tuple[int, int, int, int]] = []
    for i, (word, count) in enumerate(items):
        ratio = (count - lo) / max(hi - lo, 1)
        size = int(16 + ratio ** 0.75 * 52)
        f = font(size, bold=ratio > 0.35)
        box = d.textbbox((0, 0), word, font=f)
        w, h = box[2] - box[0] + 14, box[3] - box[1] + 14
        if w >= width - 40 or h >= height - 90:
            continue
        for _ in range(400):
            x = rnd.randint(30, max(31, width - w - 30))
            y = rnd.randint(90, max(91, height - h - 30))
            rect = (x - 6, y - 4, x + w + 6, y + h + 4)
            if any(not (rect[2] < r[0] or rect[0] > r[2] or rect[3] < r[1] or rect[1] > r[3])
                   for r in placed):
                continue
            d.text((x, y), word, font=f, fill=CLOUD_COLORS[i % len(CLOUD_COLORS)])
            placed.append(rect)
            break
    d.text((40, height - 34), "字号与颜色深浅映射词频高低 | 随机种子 2026（结果可复现）",
           font=font(13), fill="#94a3b8")
    img.save(path)
    return True


# ---------------------------------------------------------------------------
# 控制台报表
# ---------------------------------------------------------------------------
def line(char: str = "-", n: int = 78) -> str:
    return char * n


def print_report(meta: dict, counter: Counter, themes: list[tuple[str, int]],
                 compound: list[tuple[str, int]], top: int,
                 outdir: Path, files: list[Path]) -> None:
    print()
    print(line("="))
    print("  “十五五”发展规划报告 · 热词频率统计")
    print(line("="))
    print(f"  语料文件   : {meta['input']}")
    print(f"  报告总字数 : {meta['chars']:,}    中文字数: {meta['chinese']:,}")
    print(f"  切分词总数 : {meta['total_tokens']:,}   过滤后有效词: {meta['valid_tokens']:,}")
    print(f"  不同词数   : {meta['unique']:,}    停用词: {meta['stops']} 条    用户词典: {meta['dict']} 词")
    print(f"  分词引擎   : jieba {meta['jieba']}  (最小词长 {meta['min_len']}, 保留公文动词: {meta['keep_verbs']})")
    print(line())

    total = sum(counter.values())
    print(f"  【通用热词 Top {top}】按词频降序（已过滤虚词、公文套话、单字、编号）")
    print("  " + pad("排名", 6) + pad("热词", 22) + pad("词频", 9, "right")
          + pad("占比", 11, "right") + pad("词长", 8, "right"))
    print("  " + line("-", 56))
    for rank, (word, count) in enumerate(counter.most_common(top), 1):
        print("  " + pad(str(rank), 6) + pad(word, 22) + pad(str(count), 9, "right")
              + pad(f"{count / total * 100:.2f}%", 11, "right") + pad(str(len(word)), 8, "right"))
    print(line())

    print(f"  【重点政策主题热词】全文精确匹配计数（共命中 {len(themes)} 个）")
    for i in range(0, min(len(themes), 18), 3):
        group = themes[i:i + 3]
        print("  " + "".join(pad(f"{kw}({cnt})", 26) for kw, cnt in group))
    print(line())

    print(f"  【复合主题热词 Top {len(compound)}】词长≥4 的政策短语，最能体现规划主题")
    print("  " + pad("排名", 6) + pad("复合热词", 30) + pad("词频", 9, "right")
          + pad("占比", 11, "right"))
    print("  " + line("-", 56))
    for rank, (word, count) in enumerate(compound, 1):
        print("  " + pad(str(rank), 6) + pad(word, 30) + pad(str(count), 9, "right")
              + pad(f"{count / total * 100:.2f}%", 11, "right"))
    print(line())
    print("  输出文件：")
    for p in files:
        print(f"    - {p.relative_to(ROOT)}")
    print(line("="))
    print()


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="“十五五”发展规划报告热词频率统计")
    ap.add_argument("-i", "--input", type=Path, default=DEFAULT_INPUT, help="报告纯文本路径")
    ap.add_argument("-n", "--top", type=int, default=20, help="显示/绘图的热词数量（默认 20）")
    ap.add_argument("-o", "--outdir", type=Path, default=DEFAULT_OUTDIR, help="输出目录")
    ap.add_argument("--stopwords", type=Path, default=DEFAULT_STOPWORDS, help="停用词表")
    ap.add_argument("--dict", type=Path, default=DEFAULT_DICT, help="jieba 用户词典")
    ap.add_argument("--keywords", type=Path, default=DEFAULT_KEYWORDS, help="重点主题热词清单")
    ap.add_argument("--min-len", type=int, default=2, help="最小词长（默认 2）")
    ap.add_argument("--keep-verbs", action="store_true", help="保留“加强/推进/推动”等公文通用动词")
    ap.add_argument("--no-chart", action="store_true", help="不生成柱状图与词云")
    args = ap.parse_args()

    if not args.input.exists():
        print(f"错误：找不到语料文件 {args.input}")
        print("请先运行 python fetch_corpus.py 抓取全文，或用 -i 指定自己的报告文本。")
        return 1
    args.outdir.mkdir(parents=True, exist_ok=True)

    raw_text = args.input.read_text(encoding="utf-8", errors="ignore")
    text = preprocess(raw_text)

    dict_words = read_wordlist(args.dict)
    for word in dict_words:
        jieba.add_word(word, freq=1000)
    stops, verb_count = load_stopwords(args.stopwords, args.keep_verbs)

    tokens, total_tokens, chinese_chars = tokenize(text, args.min_len, stops)
    counter = Counter(tokens)
    themes = theme_word_counts(raw_text, read_wordlist(args.keywords))
    # 复合主题词：长度 ≥4 且不是纯英文缩写，用于突出规划报告中的专有政策表述
    compound = [(w, c) for w, c in counter.most_common()
                if len(w) >= 4 and not re.fullmatch(r"[A-Za-z0-9+]+", w)][:15]

    meta = {
        "input": args.input.name,
        "chars": len(raw_text),
        "chinese": chinese_chars,
        "total_tokens": total_tokens,
        "valid_tokens": len(tokens),
        "unique": len(counter),
        "stops": len(stops),
        "dict": len(dict_words),
        "min_len": args.min_len,
        "keep_verbs": "是" if args.keep_verbs else "否",
        "jieba": getattr(jieba, "__version__", "0.42"),
    }

    files = [export_csv(counter, args.outdir)]
    if not args.no_chart and Image is not None:
        bar = args.outdir / f"热词Top{args.top}柱状图.png"
        bar2 = args.outdir / f"复合主题词Top{len(compound)}柱状图.png"
        cloud = args.outdir / "热词词云.png"
        if draw_bar_chart(counter.most_common(args.top), bar, "通用热词词频"):
            files.append(bar)
        if draw_bar_chart(compound, bar2, "复合主题热词词频"):
            files.append(bar2)
        if draw_wordcloud(counter, cloud):
            files.append(cloud)

    print_report(meta, counter, themes, compound, args.top, args.outdir, files)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
