"""cquant.vibe_bridge.alpha_zoo — Vibe-Trading Alpha 因子适配器。

将 Vibe-Trading 的 Alpha 函数包装为 cQuant Factor ABC。

Vibe-Trading Alpha 接口：
    每个因子是一个独立 .py 文件，包含 compute() 函数：
    def compute(panel: dict[str, pd.DataFrame]) -> pd.DataFrame

    panel 键：open, high, low, close, volume, amount 等（宽表，dates × assets）
    返回值：pd.DataFrame（宽表，同 panel["close"] 的 shape）
"""
from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

import polars as pl

from cquant.factorlab.factor import Factor, FactorContext
from cquant.vibe_bridge._compat import require_vibe

logger = logging.getLogger(__name__)

# 从 cQuant 长表列名映射到 Vibe panel keys
_PRICE_COLS: list[str] = ["open", "high", "low", "close", "volume", "amount", "adj_close"]

# Vibe-Trading zoo 目录（需要 VIBE_AVAILABLE=True）
_VIBE_AGENT_ROOT = Path(__file__).resolve().parents[3] / "lib" / "vibe-trading" / "agent"
_VIBE_ZOO_ROOT = _VIBE_AGENT_ROOT / "src" / "factors" / "zoo"


class VibeFactor(Factor):
    """将 Vibe-Trading 的 compute() 函数包装为 cQuant Factor ABC。

    Parameters
    ----------
    name_
        因子名称（如 "qlib158_ma5"）。
    vibe_fn
        Vibe-Trading 的 compute(panel: dict) -> pd.DataFrame 函数。
    tags_
        因子标签列表（如 ["qlib158", "vibe"]）。
    lookback_days_
        所需历史天数，默认 60。
    """

    def __init__(
        self,
        name_: str,
        vibe_fn: Any,
        tags_: list[str] | None = None,
        lookback_days_: int = 60,
    ) -> None:
        self._name = name_
        self._vibe_fn = vibe_fn
        self._tags = tags_ or ["vibe"]
        self._lookback = lookback_days_

    @property
    def name(self) -> str:
        return self._name

    @property
    def tags(self) -> list[str]:
        return self._tags

    @property
    def lookback_days(self) -> int:
        return self._lookback

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        """Compute the Vibe alpha factor.

        1. pl.DataFrame (long) → panel dict (wide pandas DataFrames)
        2. Call compute(panel)
        3. pd.DataFrame (wide) → pl.Series (long, aligned to frame rows)
        """
        try:
            import pandas as pd  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError("pandas is required for VibeFactor") from exc

        panel = _build_panel(frame)
        if not panel:
            return pl.Series(self._name, [None] * len(frame), dtype=pl.Float64)

        try:
            result = self._vibe_fn(panel)
        except Exception as exc:
            logger.warning("VibeFactor %s: computation failed: %s", self._name, exc)
            return pl.Series(self._name, [None] * len(frame), dtype=pl.Float64)

        if result is None:
            return pl.Series(self._name, [None] * len(frame), dtype=pl.Float64)

        return _wide_to_series(result, frame, self._name)


def _build_panel(frame: pl.DataFrame) -> dict[str, Any]:
    """Convert long-format Polars DataFrame to Vibe panel dict.

    Keys: price field names (close, open, etc.)
    Values: pd.DataFrame with date index and asset_id columns
    """
    import pandas as pd  # noqa: PLC0415

    present_cols = [c for c in _PRICE_COLS if c in frame.columns]
    if "close" not in present_cols:
        return {}

    panel: dict[str, Any] = {}
    for col in present_cols:
        wide = (
            frame.select(["asset_id", "trade_date", col])
            .pivot(index="trade_date", on="asset_id", values=col)
            .sort("trade_date")
        )
        pdf = wide.to_pandas()
        pdf["trade_date"] = pd.to_datetime(pdf["trade_date"])
        pdf = pdf.set_index("trade_date")
        panel[col] = pdf

    return panel


def _wide_to_series(
    result: Any,
    original_frame: pl.DataFrame,
    factor_name: str,
) -> pl.Series:
    """Convert Vibe wide result (pd.DataFrame) back to pl.Series aligned to original_frame."""
    import pandas as pd  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    if isinstance(result, pd.DataFrame):
        result_reset = result.reset_index()
        date_col = result_reset.columns[0]
        result_long = result_reset.melt(
            id_vars=date_col, var_name="asset_id", value_name=factor_name
        )
        result_long = result_long.rename(columns={date_col: "trade_date"})
        result_long["trade_date"] = pd.to_datetime(result_long["trade_date"]).dt.date

        result_pl = pl.from_pandas(result_long)
        merged = original_frame.select(["asset_id", "trade_date"]).join(
            result_pl, on=["asset_id", "trade_date"], how="left"
        )
        return merged[factor_name]

    if isinstance(result, pd.Series):
        vals = result.values.tolist()
        return pl.Series(factor_name, vals[: len(original_frame)])

    if isinstance(result, np.ndarray):
        flat = result.flatten()[: len(original_frame)]
        return pl.Series(factor_name, flat.tolist())

    logger.warning("VibeFactor %s: unexpected result type %s", factor_name, type(result))
    return pl.Series(factor_name, [None] * len(original_frame), dtype=pl.Float64)


def load_zoo(zoo_name: str) -> list[VibeFactor]:
    """批量加载 Vibe-Trading Alpha Zoo 中的所有因子。

    Parameters
    ----------
    zoo_name
        Zoo 名称：'qlib158', 'alpha101', 'gtja191' 等。
        每个 Zoo 是 src/factors/zoo/<zoo_name>/ 目录下的一组 .py 文件，
        每个文件包含一个 compute(panel) 函数。

    Returns
    -------
    list[VibeFactor]
        该 Zoo 中所有因子包装为 VibeFactor 的列表，按文件名排序。
    """
    require_vibe()

    zoo_dir = _VIBE_ZOO_ROOT / zoo_name
    if not zoo_dir.is_dir():
        raise ValueError(
            f"Zoo '{zoo_name}' 目录未找到：{zoo_dir}. "
            f"可用 zoo: {[d.name for d in _VIBE_ZOO_ROOT.iterdir() if d.is_dir()]}"
        )

    factors: list[VibeFactor] = []
    for py_file in sorted(zoo_dir.glob("*.py")):
        if py_file.stem.startswith("_"):
            continue  # skip __init__.py etc.

        module_path = f"src.factors.zoo.{zoo_name}.{py_file.stem}"
        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:
            logger.warning("load_zoo: failed to import %s: %s", module_path, exc)
            continue

        compute_fn = getattr(module, "compute", None)
        if compute_fn is None or not callable(compute_fn):
            logger.warning("load_zoo: %s has no callable 'compute', skipping", py_file.name)
            continue

        # Build factor name from Zoo name + stem (e.g., "qlib158_ma5", "alpha101_001")
        stem = py_file.stem
        if zoo_name == "alpha101" and stem.startswith("alpha_"):
            factor_name = f"alpha101_{stem[6:]}"  # alpha_001 → alpha101_001
        else:
            factor_name = f"{zoo_name}_{stem}"  # ma5 → qlib158_ma5

        factors.append(
            VibeFactor(
                name_=factor_name,
                vibe_fn=compute_fn,
                tags_=[zoo_name, "vibe"],
                lookback_days_=60,
            )
        )

    logger.info("load_zoo('%s'): loaded %d factors", zoo_name, len(factors))
    return factors
