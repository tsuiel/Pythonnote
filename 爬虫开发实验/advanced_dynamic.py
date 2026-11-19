
import time
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from step4_news_crawler import NewsCrawler, DEFAULT_HEADERS, FIELDS_CN

URL = "http://127.0.0.1:8000/index.html"


def plan_a_requests(url: str) -> int:
    """方案 A：纯静态请求，速度快、依赖少。"""
    t0 = time.time()
    crawler = NewsCrawler(base_url=url, delay=2.0)
    html = crawler.fetch(url)
    rows = crawler.parse(html) if html else []
    cost = time.time() - t0
    print(f"[方案A] requests+BS4：{len(rows)} 条，耗时 {cost:.2f}s，依赖 2 个库")
    return len(rows)


def plan_b_playwright(url: str) -> int:
    """方案 B：真实浏览器渲染，可处理 JS 动态加载内容。"""
    t0 = time.time()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[方案B] 未安装 playwright，跳过。安装：pip install playwright")
        return -1
    try:
        with sync_playwright() as p:
            # 优先用已安装的 Edge/Chrome（channel），无需额外下载 Chromium；
            # 若都没有则回退到 playwright 自带的 chromium。
            launched = None
            for channel in ("msedge", "chrome", None):
                try:
                    launched = (p.chromium.launch(headless=True, channel=channel)
                                if channel else p.chromium.launch(headless=True))
                    break
                except Exception:
                    continue
            if launched is None:
                print("[方案B] 未找到可用浏览器，跳过。")
                return -1
            browser = launched
            page = browser.new_page(user_agent=DEFAULT_HEADERS["User-Agent"])
            page.goto(url, wait_until="networkidle", timeout=15000)
            page.wait_for_selector("div.news-item", timeout=10000)
            html = page.content()
            browser.close()
    except Exception as exc:
        print(f"[方案B] 浏览器渲染失败：{exc}")
        return -1
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for block in soup.select("div.news-item"):
        a = block.select_one("h2 a")
        t = block.select_one(".meta .time")
        au = block.select_one(".meta .author")
        rows.append({
            "标题": a.get_text(strip=True) if a else "",
            "发布时间": t.get_text(strip=True) if t else "",
            "作者": au.get_text(strip=True) if au else "",
            "链接": urljoin(url, a.get("href", "")) if a else "",
        })
    cost = time.time() - t0
    print(f"[方案B] Playwright：{len(rows)} 条，耗时 {cost:.2f}s，需下载 Chromium 浏览器")
    return len(rows)


def compare() -> None:
    print("=" * 60)
    print("进阶挑战：静态爬取 vs 动态渲染爬取 方案对比")
    print("=" * 60)
    a = plan_a_requests(URL)
    b = plan_b_playwright(URL)
    print("-" * 60)
    print("对比结论：")
    print("  · 代码复杂度：方案A 约10行；方案B 需管理浏览器生命周期，更复杂")
    print("  · 运行效率：方案A 毫秒级；方案B 需启动浏览器，耗时高一个数量级")
    print("  · 适用场景：静态HTML用方案A；Vue/React等JS渲染页面必须用方案B")
    print(f"  · 本次结果：方案A={a} 条，方案B={b} 条（静态站点两者数据一致）")


if __name__ == "__main__":
    compare()
