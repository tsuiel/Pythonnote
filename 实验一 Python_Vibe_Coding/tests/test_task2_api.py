"""考题二测试：接口主流程 + 校验用例 + 边界/异常 + 并发写入。"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from src.task2_api import app as app_module


@pytest.fixture
def client():
    app_module.reset_state()
    with TestClient(app_module.app) as c:
        yield c


def post_record(client: TestClient, amount=100.0, type_="收入",
               category="工资", date="2026-10-01"):
    return client.post(
        "/records",
        json={"金额": amount, "类型": type_, "分类": category, "日期": date},
    )


def assert_structured_4xx(response, expected_status=422) -> None:
    """所有非法参数必须返回 4xx + 统一结构化错误体。"""
    assert 400 <= response.status_code < 500
    assert response.status_code == expected_status
    body = response.json()
    assert "error" in body
    assert set(["code", "message", "details"]).issubset(body["error"].keys())


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_normal_flow_filter_paging_summary(client: TestClient) -> None:
    """正常用例：新增 -> 筛选 -> 分页 -> 汇总，数值人工核对。"""
    seed = [
        (1000, "收入", "工资", "2026-10-01"),
        (30.5, "支出", "餐饮", "2026-10-05"),
        (20, "支出", "餐饮", "2026-10-10"),
        (500, "收入", "奖金", "2026-11-01"),
    ]
    for amount, type_, category, date in seed:
        resp = post_record(client, amount, type_, category, date)
        assert resp.status_code == 201
        assert resp.json()["金额"] == amount

    all_records = client.get("/records", params={"page_size": 50}).json()
    assert all_records["total"] == 4
    # 默认按 id 倒序
    assert [r["分类"] for r in all_records["items"]] == ["奖金", "餐饮", "餐饮", "工资"]

    expense = client.get("/records", params={"类型": "支出"}).json()
    assert expense["total"] == 2
    assert all(r["类型"] == "支出" for r in expense["items"])

    category_hit = client.get("/records", params={"分类": "餐饮"}).json()
    assert category_hit["total"] == 2

    ranged = client.get(
        "/records", params={"开始日期": "2026-10-01", "结束日期": "2026-10-31"}
    ).json()
    assert ranged["total"] == 3

    page1 = client.get("/records", params={"page": 1, "page_size": 2}).json()
    assert page1["total"] == 4 and len(page1["items"]) == 2
    page2 = client.get("/records", params={"page": 2, "page_size": 2}).json()
    assert len(page2["items"]) == 2
    assert {r["id"] for r in page1["items"]}.isdisjoint({r["id"] for r in page2["items"]})

    summary = client.get("/summary").json()
    assert summary["收入合计"] == pytest.approx(1500)
    assert summary["支出合计"] == pytest.approx(50.5)
    assert summary["结余"] == pytest.approx(1449.5)

    oct_summary = client.get(
        "/summary", params={"开始日期": "2026-10-01", "结束日期": "2026-10-31"}
    ).json()
    assert oct_summary["收入合计"] == pytest.approx(1000)
    assert oct_summary["结余"] == pytest.approx(949.5)


@pytest.mark.parametrize("payload", [
    {"金额": 0, "类型": "收入", "分类": "工资", "日期": "2026-10-01"},       # 金额 = 0
    {"金额": -1, "类型": "收入", "分类": "工资", "日期": "2026-10-01"},      # 金额 < 0
    {"金额": 10, "类型": "转账", "分类": "工资", "日期": "2026-10-01"},      # 类型非法
    {"金额": 10, "类型": "收入", "分类": "工资", "日期": "2026/10/01"},      # 日期格式
    {"金额": 10, "类型": "收入", "分类": "工资", "日期": "2026-02-30"},      # 不存在的日期
    {"金额": 10, "类型": "收入", "分类": "   ", "日期": "2026-10-01"},       # 分类空白
    {"金额": "abc", "类型": "收入", "分类": "工资", "日期": "2026-10-01"},   # 金额类型
    {"类型": "收入", "分类": "工资", "日期": "2026-10-01"},                  # 缺少金额
])
def test_post_validation_errors(client: TestClient, payload: dict) -> None:
    """边界 1：POST 非法字段一律 4xx + 结构化错误，且不落库。"""
    resp = client.post("/records", json=payload)
    assert_structured_4xx(resp)
    assert client.get("/records").json()["total"] == 0


@pytest.mark.parametrize("params, expected, applies_to", [
    ({"page": 0}, 422, "records"),            # 页码越界（/records 专有参数）
    ({"page_size": 101}, 422, "records"),     # 每页条数越界
    ({"类型": "转账"}, 422, "records"),        # 非法枚举
    ({"开始日期": "2026-13-01"}, 422, "both"),  # 非法日期
    ({"结束日期": "10/01/2026"}, 422, "both"),  # 非法日期格式
    ({"开始日期": "2026-11-01", "结束日期": "2026-10-01"}, 422, "both"),  # 区间倒置
])
def test_get_validation_errors(client: TestClient, params: dict,
                               expected: int, applies_to: str) -> None:
    """边界 2：GET 非法查询参数一律 4xx + 结构化错误。"""
    if applies_to in ("records", "both"):
        assert_structured_4xx(client.get("/records", params=params), expected)
    if applies_to in ("summary", "both"):
        assert_structured_4xx(client.get("/summary", params=params), expected)


def test_unknown_route_structured_404(client: TestClient) -> None:
    """边界 3：未知路由也返回统一结构化 404。"""
    assert_structured_4xx(client.get("/not-exist"), 404)


def test_concurrent_writes_are_consistent() -> None:
    """并发写入：40 个并发 POST，id 不重复、条数与金额完全正确。"""
    app_module.reset_state()

    def one(i: int):
        with TestClient(app_module.app) as c:
            return c.post(
                "/records",
                json={"金额": 1, "类型": "收入", "分类": "并发", "日期": "2026-10-01"},
            )

    with ThreadPoolExecutor(max_workers=16) as pool:
        responses = list(pool.map(one, range(40)))

    assert all(r.status_code == 201 for r in responses)
    ids = [r.json()["id"] for r in responses]
    assert len(set(ids)) == 40, "并发插入出现重复主键"

    with TestClient(app_module.app) as c:
        listed = c.get("/records", params={"分类": "并发", "page_size": 100}).json()
        assert listed["total"] == 40
        summary = c.get(
            "/summary", params={"开始日期": "2026-10-01", "结束日期": "2026-10-01"}
        ).json()
        assert summary["收入合计"] == pytest.approx(40.0)
