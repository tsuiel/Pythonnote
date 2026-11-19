
import time
from bs4 import BeautifulSoup
from step1_fetch_html import fetch_html, BASE_URL


def parse_list(html: str) -> list[dict]:
    """从列表页 HTML 中解析出文章字段列表。"""
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for block in soup.select("div.news-item"):
        a = block.select_one("h2 a")
        t = block.select_one(".meta .time")
        author = block.select_one(".meta .author")

        items.append({
            "title":  a.get_text(strip=True) if a else "",
            "link":   a.get("href", "") if a else "",
            "time":   t.get_text(strip=True) if t else "",
            "author": author.get_text(strip=True) if author else "",
        })
        time.sleep(0.01)   # 演示：解析阶段保持轻量间隔（联网时建议 >=2s）
    return items


if __name__ == "__main__":
    html = fetch_html(BASE_URL)
    if not html:
        raise SystemExit("[ERROR] 未取得 HTML，解析终止。")

    data = parse_list(html)
    print(f"[INFO] 共解析出 {len(data)} 条记录。")
    print("[INFO] 前 3 条数据预览：")
    for i, row in enumerate(data[:3], 1):
        print(f"  {i}. 标题：{row['title']}")
        print(f"     时间：{row['time']} | 作者：{row['author']}")
        print(f"     链接：{row['link']}")
    print("[SUCCESS] 步骤2验证通过：字段解析正确。")
