"""考题二：SQLite 记账存储层。

并发写入一致性（对应验收标准「并发写入不产生数据错误」）：
1. 每个请求使用独立 sqlite3 连接，不跨线程复用连接；
2. 写事务用 BEGIN IMMEDIATE 抢占写锁，并由进程内 threading.Lock 再串行化一层，
   彻底避免 SQLITE_BUSY / 丢失更新；
3. id 由 SQLite AUTOINCREMENT 原子分配，多线程并发插入不会撞主键；
4. 文件型数据库连接开启 WAL + busy_timeout，读写互不阻塞；
5. 汇总用单条 SQL 聚合，读到的始终是已提交数据，不会出现「读到半条流水」。

默认使用共享内存库（不落盘、方便一键运行）；设置 LEDGER_DB 环境变量即可切换为
持久化 SQLite 文件，例如：set LEDGER_DB=data\\ledger.db
"""
from __future__ import annotations

import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    amount      REAL    NOT NULL CHECK (amount > 0),
    type        TEXT    NOT NULL CHECK (type IN ('收入', '支出')),
    category    TEXT    NOT NULL,
    record_date TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_records_date ON records(record_date);
CREATE INDEX IF NOT EXISTS idx_records_type ON records(type);
"""


class Ledger:
    """线程安全的记账仓储。"""

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            raw = os.environ.get("LEDGER_DB")
            db_path = Path(raw) if raw else None
        self._shared_memory = db_path is None
        if self._shared_memory:
            # 每个实例一个独立的共享内存库，避免多实例互相污染
            self.db_path = f"file:ledger_{uuid.uuid4().hex}?mode=memory&cache=shared"
        else:
            self.db_path = str(db_path)
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.Lock()
        self._keeper = self._connect()  # 共享内存库需要至少一个常驻连接
        self._keeper.executescript(SCHEMA)
        self._keeper.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.db_path,
            uri=self._shared_memory,
            timeout=10,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 10000")
        if not self._shared_memory:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    @contextmanager
    def _write_tx(self) -> Iterator[sqlite3.Connection]:
        with self._write_lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    @staticmethod
    def _to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "金额": row["amount"],
            "类型": row["type"],
            "分类": row["category"],
            "日期": row["record_date"],
        }

    def add_record(self, amount: float, type_: str, category: str, date: str) -> dict[str, Any]:
        with self._write_tx() as conn:
            cur = conn.execute(
                "INSERT INTO records (amount, type, category, record_date) VALUES (?, ?, ?, ?)",
                (float(amount), type_, category, date),
            )
            new_id = cur.lastrowid
            row = conn.execute("SELECT * FROM records WHERE id = ?", (new_id,)).fetchone()
        return self._to_dict(row)

    def list_records(
        self,
        type_: str | None = None,
        category: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        clauses: list[str] = []
        params: list[Any] = []
        if type_ is not None:
            clauses.append("type = ?")
            params.append(type_)
        if category is not None:
            clauses.append("category = ?")
            params.append(category)
        if start_date is not None:
            clauses.append("record_date >= ?")
            params.append(start_date)
        if end_date is not None:
            clauses.append("record_date <= ?")
            params.append(end_date)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

        conn = self._connect()
        try:
            total = conn.execute(
                f"SELECT COUNT(*) FROM records{where}", params
            ).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM records{where} ORDER BY id DESC LIMIT ? OFFSET ?",
                params + [limit, offset],
            ).fetchall()
        finally:
            conn.close()
        return [self._to_dict(r) for r in rows], total

    def summary(self, start_date: str | None = None, end_date: str | None = None) -> dict[str, float]:
        clauses: list[str] = []
        params: list[Any] = []
        if start_date is not None:
            clauses.append("record_date >= ?")
            params.append(start_date)
        if end_date is not None:
            clauses.append("record_date <= ?")
            params.append(end_date)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT "
                "COALESCE(SUM(CASE WHEN type = '收入' THEN amount ELSE 0 END), 0) AS income, "
                "COALESCE(SUM(CASE WHEN type = '支出' THEN amount ELSE 0 END), 0) AS expense "
                f"FROM records{where}",
                params,
            ).fetchone()
        finally:
            conn.close()
        income = round(float(row["income"]), 2)
        expense = round(float(row["expense"]), 2)
        return {
            "收入合计": income,
            "支出合计": expense,
            "结余": round(income - expense, 2),
        }

    def close(self) -> None:
        self._keeper.close()
