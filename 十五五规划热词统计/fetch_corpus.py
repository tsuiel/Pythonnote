

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import requests

SOURCE_URL = "http://www.npc.gov.cn/npc/c2/c30834/202603/t20260316_453274.html"
OUT_FILE = Path(__file__).resolve().parent / "data" / "十五五规划纲要.txt"


class ZoomExtractor(HTMLParser):
    """只抽取页面 <div id="Zoom"> ... </div> 正文容器内的文字。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.active = False
        self.depth = 0
        self.in_script = False
        self.lines: list[str] = []
        self._buf: list[str] = []

    def _flush(self) -> None:
        text = "".join(self._buf).strip()
        if text:
            self.lines.append(text)
        self._buf.clear()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "div":
            if not self.active and attr.get("id") == "Zoom":
                self.active, self.depth = True, 1
                return
            if self.active:
                self.depth += 1
        if not self.active:
            return
        if tag == "script":
            self.in_script = True
        if tag in ("br", "p", "div", "li", "tr"):
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if not self.active:
            return
        if tag == "script":
            self.in_script = False
        if tag == "div":
            self._flush()
            self.depth -= 1
            if self.depth <= 0:
                self.active = False
        if tag in ("p", "li", "tr"):
            self._flush()

    def handle_data(self, data: str) -> None:
        if self.active and not self.in_script:
            self._buf.append(data)


def clean_lines(raw: list[str]) -> list[str]:
    result: list[str] = []
    for line in raw:
        line = line.replace("\u3000", " ").replace("\xa0", " ")
        line = re.sub(r"\s+", " ", line).strip()
        if not line or line in {"大", "中", "小"}:
            continue
        result.append(line)
    return result


def drop_toc(lines: list[str]) -> list[str]:
    """目录会重复统计章节标题，尝试去掉目录部分，只保留正文。"""
    toc_idx = next((i for i, s in enumerate(lines) if s.strip() == "目录"), None)
    if toc_idx is None:
        return lines
    # 目录中出现一次"第一篇"，正文中再次出现"第一篇"即为正文起点
    hits = [i for i in range(toc_idx + 1, len(lines)) if lines[i].startswith("第一篇")]
    if len(hits) >= 2:
        return lines[hits[1]:]
    return lines


def main() -> None:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    resp = requests.get(SOURCE_URL, headers=headers, timeout=30)
    resp.encoding = "utf-8"
    resp.raise_for_status()

    parser = ZoomExtractor()
    parser.feed(resp.text)
    lines = drop_toc(clean_lines(parser.lines))

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    text = "".join(lines)
    print(f"抓取成功: {SOURCE_URL}")
    print(f"输出文件: {OUT_FILE}")
    print(f"段落数  : {len(lines)}")
    print(f"总字数  : {len(text)}")
    print("前 5 行预览:")
    for line in lines[:5]:
        print("  " + line)


if __name__ == "__main__":
    main()
