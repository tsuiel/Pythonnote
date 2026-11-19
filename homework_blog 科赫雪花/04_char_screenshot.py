

import os
import subprocess
import sys
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
CHAR_SCRIPT = os.path.join(BASE, "01_tianzige_char.py")
OUT = os.path.join(BASE, "screenshots", "tianzige_char.png")


def load_font(paths, size):
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def main():
    # 捕获字符田字格程序的输出
    result = subprocess.run([sys.executable, CHAR_SCRIPT],
                            capture_output=True, text=True,
                            encoding="utf-8", cwd=BASE)
    text = result.stdout

    mono = load_font([r"C:\Windows\Fonts\consola.ttf",
                      r"C:\Windows\Fonts\consolab.ttf"], 22)
    cjk_font = load_font([r"C:\Windows\Fonts\msyh.ttc",
                          r"C:\Windows\Fonts\simhei.ttf"], 20)
    title_font = cjk_font

    def has_cjk(s):
        return any("\u4e00" <= ch <= "\u9fff" for ch in s)

    # 估算文本尺寸
    lines = text.splitlines()
    char_w = mono.getlength("M")
    line_h = 30
    width = int(max((cjk_font if has_cjk(line) else mono).getlength(line)
                    for line in lines)) + 80
    height = line_h * len(lines) + 90

    img = Image.new("RGB", (width, height), "#1e1e1e")
    draw = ImageDraw.Draw(img)

    # 终端标题栏
    draw.rectangle([0, 0, width, 40], fill="#2d2d2d")
    draw.text((16, 9), "终端  —  python 01_tianzige_char.py",
              font=title_font, fill="#d4d4d4")

    # 三个窗口控制圆点
    for i, c in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        draw.ellipse([width - 74 + i * 22, 13, width - 60 + i * 22, 27], fill=c)

    # 正文：含中文的行用中文字体，纯字符行用等宽字体
    y = 56
    for line in lines:
        font = cjk_font if has_cjk(line) else mono
        draw.text((24, y), line, font=font, fill="#dcdcaa")
        y += line_h

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT)
    print(f"已保存: {OUT}")


if __name__ == "__main__":
    main()
