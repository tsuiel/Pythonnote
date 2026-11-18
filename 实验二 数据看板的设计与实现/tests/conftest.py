"""pytest 公共夹具：保证从任意目录运行 `pytest -v` 都能找到 src 模块。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from config import CLEAN_CSV, RAW_CSV            # noqa: E402
from preprocess import load_clean                 # noqa: E402


@pytest.fixture(scope="session")
def clean_df():
    """若尚未生成数据集，则先跑一遍生成 + 清洗，保证测试可独立执行。"""
    if not CLEAN_CSV.is_file() or not RAW_CSV.is_file():
        import generate_data
        import preprocess
        generate_data.generate()
        preprocess.run()
    return load_clean()


@pytest.fixture(scope="session")
def raw_df():
    from preprocess import read_raw
    return read_raw()
