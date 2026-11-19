
import argparse
import csv
import logging
import time
from typing import List, Dict
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("NewsCrawler")

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
FIELDS_CN = ["标题", "发布时间", "作者", "链接"]


class NewsCrawler:
    """静态新闻列表页爬虫：抓取 -> 解析 -> 持久化。"""

    def __init__(
        self,
        base_url: str,
        delay: float = 2.0,
        retries: int = 3,
        timeout: int = 5,
        headers: dict = None,
    ) -> None:
        self.base_url = base_url
        self.delay = delay
        self.retries = retries
        self.timeout = timeout
        self.headers = headers or DEFAULT_HEADERS
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    # ---------- 1. 请求层 ----------
    def fetch(self, url: str) -> str | None:
        """带重试的 GET；成功返回 HTML 文本，失败返回 None。"""
        for attempt in range(1, self.retries + 1):
            try:
                resp = self.session.get(url, timeout=self.timeout)
                resp.raise_for_status()
                resp.encoding = resp.apparent_encoding or "utf-8"
                logger.info("请求成功（第 %d 次），状态码 %d", attempt, resp.status_code)
                return resp.text
            except requests.RequestException as exc:
                logger.warning("第 %d/%d 次请求失败：%s", attempt, self.retries, exc)
                if attempt < self.retries:
                    time.sleep(self.delay)
        return None

    # ---------- 2. 解析层 ----------
    def parse(self, html: str) -> List[Dict[str, str]]:
        """BeautifulSoup 解析列表页；字段缺失时填空字符串。"""
        soup = BeautifulSoup(html, "html.parser")
        results: List[Dict[str, str]] = []
        for block in soup.select("div.news-item"):
            a = block.select_one("h2 a")
            t = block.select_one(".meta .time")
            au = block.select_one(".meta .author")
            results.append({
                "标题": a.get_text(strip=True) if a else "",
                "发布时间": t.get_text(strip=True) if t else "",
                "作者": au.get_text(strip=True) if au else "",
                "链接": urljoin(self.base_url, a.get("href", "")) if a else "",
            })
        logger.info("解析完成，共 %d 条记录", len(results))
        return results

    # ---------- 3. 持久化层 ----------
    def save(self, rows: List[Dict[str, str]], path: str) -> None:
        """写出 UTF-8（含 BOM）CSV。"""
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS_CN)
            writer.writeheader()
            writer.writerows(rows)
        logger.info("已保存 %d 条数据 -> %s", len(rows), path)

    # ---------- 4. 编排 ----------
    def crawl(self, output: str = "result.csv") -> int:
        """执行完整流程，返回成功抓取条数。"""
        html = self.fetch(self.base_url)
        if not html:
            logger.error("抓取失败：%d 次重试后仍无响应", self.retries)
            return 0
        rows = self.parse(html)
        if rows:
            self.save(rows, output)
        return len(rows)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="静态新闻列表页爬虫（重构版）")
    parser.add_argument("-u", "--url", default="http://127.0.0.1:8000/index.html")
    parser.add_argument("-o", "--output", default="result.csv")
    parser.add_argument("--delay", type=float, default=2.0, help="请求间隔（秒）")
    args = parser.parse_args()

    with NewsCrawler(base_url=args.url, delay=args.delay) as crawler:
        count = crawler.crawl(args.output)

    if count:
        print(f"[SUCCESS] 重构版 NewsCrawler 运行成功，共抓取 {count} 条数据。")
    else:
        print("[ERROR] 未抓取到数据，请检查目标 URL 与网络。")


if __name__ == "__main__":
    main()
