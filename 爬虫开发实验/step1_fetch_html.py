
import time
import requests

BASE_URL = "http://127.0.0.1:8000/index.html"   # 可替换为任意公开新闻列表页 URL

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def fetch_html(url: str, retries: int = 3, timeout: int = 5) -> str | None:
    """带重试的 GET 请求，成功返回 HTML 文本，失败返回 None。"""
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()          # 非 200 会抛异常，进入重试
            resp.encoding = resp.apparent_encoding or "utf-8"
            print(f"[INFO] 第 {attempt} 次请求成功，状态码：{resp.status_code}")
            return resp.text
        except requests.RequestException as e:
            print(f"[WARN] 第 {attempt}/{retries} 次请求失败：{e}")
            if attempt < retries:
                time.sleep(2)                # 请求间隔不低于 2 秒
    return None


if __name__ == "__main__":
    html = fetch_html(BASE_URL)
    if html:
        print(f"[INFO] HTML 长度：{len(html)} 字符")
        print("-" * 50)
        print(html[:500])                    # 打印前 500 字符做最小化验证
        print("-" * 50)
        print("[SUCCESS] 步骤1验证通过：成功获取 HTML。")
    else:
        print("[ERROR] 步骤1失败：3 次重试后仍未获取到 HTML。")
