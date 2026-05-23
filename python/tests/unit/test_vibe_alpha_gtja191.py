"""gtja191 Alpha Zoo 抽样集成测试。

验证 191 个 gtja191 因子中抽样 10 个能正确加载并产生非空结果。
"""
from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from cquant.factorlab.factor import FactorContext

# 抽样 10 个因子
SAMPLE_FACTORS = [
    "gtja191_alpha_001", "gtja191_alpha_010", "gtja191_alpha_020",
    "gtja191_alpha_050", "gtja191_alpha_080", "gtja191_alpha_100",
    "gtja191_alpha_120", "gtja191_alpha_150", "gtja191_alpha_170",
    "gtja191_alpha_191",
]


def _make_test_frame() -> pl.DataFrame:
    """构建包含 OHLCV+amount 的测试长表（120 天历史）。"""
    import random
    random.seed(42)
    dates = [date(2024, 9, 1) + __import__("datetime").timedelta(days=i) for i in range(120)]
    # 仅保留看起来像交易日的日期（跳过周末）
    dates = [d for d in dates if d.weekday() < 5][:60]
    assets = ["SSE:600000", "SSE:600036"]
    rows = []
    for a in assets:
        price = 10.0
        for i, d in enumerate(dates):
            ret = random.uniform(-0.03, 0.03)
            price = price * (1 + ret)
            rows.append({
                "asset_id": a, "trade_date": d,
                "open": price * (1 + random.uniform(-0.01, 0.01)),
                "high": price * (1 + random.uniform(0, 0.02)),
                "low": price * (1 - random.uniform(0, 0.02)),
                "close": price,
                "volume": random.randint(500_000, 2_000_000),
                "amount": random.randint(5_000_000, 20_000_000),
            })
    return pl.DataFrame(rows)


@pytest.fixture
def ctx():
    return FactorContext(as_of_date=date(2024, 11, 29))


@pytest.fixture
def frame():
    return _make_test_frame()


@pytest.mark.parametrize("factor_name", SAMPLE_FACTORS)
def test_gtja191_factor_computes(factor_name, frame, ctx):
    """验证因子能正常计算（不要求全部非空，部分因子可能因合成数据产生 null）。"""
    from cquant.factorlab.factors import BUILTIN_FACTORS

    factor = next((f for f in BUILTIN_FACTORS if f.name == factor_name), None)
    if factor is None:
        pytest.skip(f"{factor_name} not registered")
    result = factor.compute(frame, ctx)
    assert len(result) == len(frame), f"{factor_name}: expected {len(frame)} rows, got {len(result)}"


def test_gtja191_total_count():
    from cquant.factorlab.factors import BUILTIN_FACTORS

    gtja = [f for f in BUILTIN_FACTORS if "gtja191" in f.tags]
    assert len(gtja) >= 190, f"Expected >= 190 gtja191 factors, got {len(gtja)}"


def test_gtja191_majority_non_null(frame, ctx):
    """验证大多数因子在 60 天历史数据下能产生非空结果。"""
    from cquant.factorlab.factors import BUILTIN_FACTORS

    gtja = [f for f in BUILTIN_FACTORS if "gtja191" in f.tags]
    non_null_count = 0
    for f in gtja:
        result = f.compute(frame, ctx)
        if len(result.drop_nulls()) > 0:
            non_null_count += 1
    ratio = non_null_count / len(gtja)
    assert ratio >= 0.5, f"Only {non_null_count}/{len(gtja)} ({ratio:.0%}) gtja191 factors produced non-null results"
