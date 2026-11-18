# Python Vibe Coding 实操 · 交付工程

两个考题的完整可运行工程 + 测试 + 验收证据 + 过程记录。**本文件夹是唯一交付根目录**，直接整体拷贝即可。

## 1. 目录结构

```
Python_Vibe_Coding_lab1/
├── README.md                    ← 本文件：运行说明
├── 00_需求澄清清单.md            ← 交付物 1
├── 01_AI协作过程记录.md          ← 交付物 4（关键对话摘要 + diff）
├── 02_复盘.md                   ← 交付物 5
├── requirements.txt
├── pytest.ini
├── run_all.py                   ← 一键运行全部流程
├── run_all.bat                  ← Windows 双击运行
├── src/
│   ├── task1_excel/
│   │   ├── make_sample_data.py  ← 生成含脏数据的 sales_raw.xlsx
│   │   └── sales_report.py      ← 考题一主脚本：清洗 → 统计 → report.xlsx
│   └── task2_api/
│       ├── storage.py           ← SQLite 存储层（并发安全）
│       └── app.py               ← 考题二 FastAPI 应用
├── tests/
│   ├── test_task1_excel.py      ← 8 个用例
│   ├── test_task2_api.py        ← 18 个用例（参数化展开）
│   └── conftest.py
├── data/
│   ├── sales_raw.xlsx           ← 样例原始数据（16 行，8 行脏数据）
│   └── report.xlsx              ← 运行产物（4 个工作表）
├── evidence/                    ← 交付物 3：运行结果
│   ├── pytest_output.txt        真实 pytest -v 日志
│   ├── task1_output.txt         报表生成 + 四表内容核对日志
│   ├── api_smoke_output.txt     uvicorn 真实 HTTP 调用日志
│   ├── 01_测试运行结果.png      截图（由上述日志渲染）
│   ├── 02_报表生成结果.png
│   ├── 03_接口运行结果.png
│   └── code_diff.txt            v1 → v2 真实 git diff
└── tools/
    ├── api_smoke.py             启动真实 uvicorn 做 HTTP 冒烟
    ├── inspect_report.py        打印 report.xlsx 四表内容供人工核对
    └── make_evidence.py         把日志渲染成终端风格 PNG
```

> `evidence/*.png` 是**由同目录下真实命令输出日志渲染的终端风格截图**，不是屏幕录制；原始 `.txt` 日志一并保留，可逐行核对，内容未改写。
> 目录内保留 `.git/`，`git log` 与 `evidence/code_diff.txt` 构成代码修改轨迹。

## 2. 环境准备

- Python **3.10+**（本机实测 3.13.14）
- 安装依赖：

```bash
python -m pip install -r requirements.txt
```

依赖：pandas、openpyxl、fastapi、pydantic、uvicorn、pytest、httpx、pillow（pillow 仅用于生成证据截图）。

## 3. 一键运行（推荐）

```bash
python run_all.py
```

或 Windows 下双击 `run_all.bat`。它按顺序完成：

1. 生成样例数据 `data/sales_raw.xlsx`
2. 清洗统计并生成 `data/report.xlsx`
3. 运行 `pytest -v`（26 个用例）
4. 真实启动 uvicorn（127.0.0.1:8765）做 HTTP 冒烟测试并自动关闭

实测结果：`26 passed`，HTTP 冒烟全部返回预期状态码。

## 4. 分开运行

```bash
# 考题一
python src/task1_excel/make_sample_data.py
python src/task1_excel/sales_report.py
python src/task1_excel/sales_report.py -i 你的表.xlsx -o 输出.xlsx   # 自定义路径
python tools/inspect_report.py                                       # 打印四表核对数值

# 考题二：启动服务
python -m uvicorn src.task2_api.app:app --host 127.0.0.1 --port 8000
# 浏览器打开 http://127.0.0.1:8000/docs 查看接口文档并在线调试
python tools/api_smoke.py                                            # 独立冒烟测试

# 测试
python -m pytest -v
```

持久化存储（默认内存库、进程退出即清空）：

```bash
set LEDGER_DB=data\ledger.db     # Windows
export LEDGER_DB=data/ledger.db  # Linux / macOS
```

## 5. 考题一：数据口径与核对基准

清洗顺序：关键字段缺失 → 数量 ≤ 0 → 单价 ≤ 0 → 全字段去重 → 日期不可解析。
销售额 = 数量 × 单价，四个工作表全部从**同一份清洗结果**派生，保证口径一致。

| 核对项 | 值 |
|---|---|
| 原始 / 有效行数 | 16 / 8 |
| 按销售员 | 张三 14400、李四 5400、王五 3000、赵六 900 |
| 按地区 | 华东 15300、华北 5400、华南 3000 |
| 月度总额 | 2026-10 = 19600，2026-11 = 4100 |
| 总计 | **23700**（三处合计必须相等） |

异常输入（缺字段 / 空文件 / 无有效数据 / 文件不存在）统一抛 `ReportInputError`，命令行打印 `[错误] ...` 并以退出码 2 结束，不产生半成品报表；测试用例中用 sha256 断言原始文件未被修改。

## 6. 考题二：接口与并发说明

| 接口 | 说明 |
|---|---|
| `POST /records` | 新增流水；金额 > 0、类型 ∈ {收入, 支出}、分类非空、日期严格 `YYYY-MM-DD` |
| `GET /records` | 类型 / 分类 / 日期区间筛选 + 分页，返回 `total, page, page_size, items` |
| `GET /summary` | 指定日期区间内的收入合计、支出合计、结余 |
| `GET /health` | 健康检查 |
| 错误 | 统一 `{"error": {"code": "...", "message": "...", "details": [...]}}`，4xx |

**并发写入不产生数据错误的保证**（`src/task2_api/storage.py`）：

1. 每个请求独立 `sqlite3` 连接，不跨线程复用；
2. 写事务使用 `BEGIN IMMEDIATE` 抢写锁，并由进程内 `threading.Lock` 再串行化一层，避免 `SQLITE_BUSY` 与丢失更新；
3. 主键 `AUTOINCREMENT` 由 SQLite 原子分配，并发插入不会撞 id；
4. 文件型连接开启 WAL + `busy_timeout`，读写互不阻塞；
5. 汇总用单条 SQL 聚合，只读已提交数据。

`test_concurrent_writes_are_consistent` 用 16 线程发起 40 个真实 HTTP POST，断言 40 个 id 全不重复、总数 = 40、收入合计 = 40.0。

## 7. 已知限制（人工审查后如实记录）

- 金额使用 `REAL`/`float`，超大额或含多位小数时可能有浮点误差；生产实现应改用「整数分」存储。当前用例金额均为可精确表示的值，并在汇总处 `round(2)`。
- 默认内存库不持久化，重启服务数据清空；需要持久化请设 `LEDGER_DB`。
- 本地环境若配置了全局 HTTP 代理，回环地址请求必须绕开；`tools/api_smoke.py` 已设 `NO_PROXY` 与 `trust_env=False`。
- 截图为日志渲染图而非录屏；如需真实录屏，按第 3 节运行 `run_all.py` 自行录制即可。
