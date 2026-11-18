"""考题二：FastAPI 简易记账 HTTP 服务。

启动：
    python -m uvicorn src.task2_api.app:app --reload --port 8000
或（在本目录内）：
    python src/task2_api/app.py
接口文档：http://127.0.0.1:8000/docs

所有错误（含参数校验失败）统一返回 4xx + 结构化 JSON：
    {"error": {"code": "...", "message": "...", "details": [...]}}
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

try:  # 支持「包内导入」和「直接运行脚本」两种方式
    from .storage import Ledger
except ImportError:  # pragma: no cover
    from storage import Ledger

app = FastAPI(title="简易记账服务", version="1.0.0")
ledger = Ledger()

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def reset_state() -> None:
    """清空数据（供测试隔离使用）。"""
    global ledger
    ledger.close()
    ledger = Ledger()


def _check_date(value: str, label: str) -> str:
    if not DATE_PATTERN.fullmatch(value):
        raise ValueError(f"{label}必须为 YYYY-MM-DD 格式，例如 2026-10-03")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{label}不是有效日期：{value}") from exc
    return value


def _query_date(value: Optional[str], label: str) -> Optional[str]:
    if value is None:
        return None
    try:
        return _check_date(value, label)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _error_payload(code: str, message: str,
                   details: Optional[list[dict[str, Any]]] = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {"字段": ".".join(str(x) for x in err["loc"]), "原因": err["msg"]}
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=_error_payload("VALIDATION_ERROR", "请求参数不合法", details),
    )


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload("HTTP_ERROR", str(exc.detail)),
    )


class RecordIn(BaseModel):
    金额: float = Field(gt=0, description="金额必须大于 0")
    类型: Literal["收入", "支出"]
    分类: str = Field(min_length=1, max_length=50)
    日期: str

    @field_validator("分类")
    @classmethod
    def _category_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("分类不能为空白字符串")
        return value

    @field_validator("日期")
    @classmethod
    def _date_valid(cls, value: str) -> str:
        return _check_date(value, "日期")


class RecordOut(BaseModel):
    id: int
    金额: float
    类型: str
    分类: str
    日期: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/records", status_code=201, response_model=RecordOut)
def create_record(payload: RecordIn) -> dict[str, Any]:
    return ledger.add_record(payload.金额, payload.类型, payload.分类, payload.日期)


@app.get("/records")
def list_records(
    类型: Optional[Literal["收入", "支出"]] = Query(default=None, description="按类型筛选"),
    分类: Optional[str] = Query(default=None, max_length=50, description="按分类精确筛选"),
    开始日期: Optional[str] = Query(default=None, description="YYYY-MM-DD，含当天"),
    结束日期: Optional[str] = Query(default=None, description="YYYY-MM-DD，含当天"),
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数，1~100"),
) -> dict[str, Any]:
    start = _query_date(开始日期, "开始日期")
    end = _query_date(结束日期, "结束日期")
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="开始日期不能晚于结束日期")
    items, total = ledger.list_records(
        type_=类型, category=分类, start_date=start, end_date=end,
        limit=page_size, offset=(page - 1) * page_size,
    )
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@app.get("/summary")
def get_summary(
    开始日期: Optional[str] = Query(default=None, description="YYYY-MM-DD，含当天"),
    结束日期: Optional[str] = Query(default=None, description="YYYY-MM-DD，含当天"),
) -> dict[str, Any]:
    start = _query_date(开始日期, "开始日期")
    end = _query_date(结束日期, "结束日期")
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="开始日期不能晚于结束日期")
    result = ledger.summary(start, end)
    return {"开始日期": start, "结束日期": end, **result}


if __name__ == "__main__":  # pragma: no cover
    uvicorn.run(app, host="127.0.0.1", port=8000)
