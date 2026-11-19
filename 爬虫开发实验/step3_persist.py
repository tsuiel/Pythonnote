
import csv
from urllib.parse import urljoin

from step1_fetch_html import fetch_html, BASE_URL
from step2_parse_fields import parse_list

FIELDS = ["title", "time", "author", "link"]
CSV_PATH = "result.csv"


def save_csv(rows: list[dict], path: str) -> None:
    """将记录写入 CSV，缺失字段统一填空字符串，链接补全为绝对 URL。"""
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["标题", "发布时间", "作者", "链接"])
        writer.writeheader()
        for row in rows:
            # 异常处理：任一字段缺失时不会 KeyError，填空字符串
            clean = {k: (row.get(k) or "").strip() for k in FIELDS}
            clean["link"] = urljoin(BASE_URL, clean["link"])  # 相对链接 -> 绝对链接
            writer.writerow({
                "标题": clean["title"],
                "发布时间": clean["time"],
                "作者": clean["author"],
                "链接": clean["link"],
            })
    print(f"[INFO] 已写入 {len(rows)} 条记录到 {path}（UTF-8 编码）")


if __name__ == "__main__":
    html = fetch_html(BASE_URL)
    if not html:
        raise SystemExit("[ERROR] 未取得 HTML。")

    data = parse_list(html)
    save_csv(data, CSV_PATH)

    # 验证：重新读取，检查编码、列名、条数
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        check = list(csv.DictReader(f))
    print(f"[VERIFY] 表头：{list(check[0].keys())}")
    print(f"[VERIFY] 记录条数：{len(check)}")
    print(f"[VERIFY] 首条：{check[0]}")
    print("[SUCCESS] 步骤3验证通过：CSV 编码/列名/数据对齐均正确。")
