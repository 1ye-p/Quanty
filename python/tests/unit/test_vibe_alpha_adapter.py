"""Unit tests for VibeFactor adapter — mocks Vibe functions, no real submodule needed."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pandas as pd
import polars as pl
import pytest


def _make_frame(n_days: int = 5) -> pl.DataFrame:
    dates = [date(2026, 1, i + 1) for i in range(n_days)]
    assets = ["SSE:000001", "SSE:600036"]
    rows = []
    for d in dates:
        for a in assets:
            rows.append(
                {
                    "asset_id": a,
                    "trade_date": d,
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.0,
                    "volume": 1_000_000.0,
                    "amount": 100_000_000.0,
                }
            )
    return pl.DataFrame(rows)


class TestVibeFactor:
    def _ctx(self):
        from cquant.factorlab.factor import FactorContext

        return FactorContext(as_of_date=date(2026, 1, 5))

    def _make_wide_result(self, frame: pl.DataFrame) -> pd.DataFrame:
        """Create a wide pd.DataFrame result like Vibe returns."""
        dates = sorted(frame["trade_date"].unique().to_list())
        assets = sorted(frame["asset_id"].unique().to_list())
        return pd.DataFrame(
            1.0,
            index=pd.DatetimeIndex(pd.to_datetime(dates)),
            columns=assets,
        )

    def test_factor_name_and_tags(self) -> None:
        from cquant.vibe_bridge.alpha_zoo import VibeFactor

        f = VibeFactor("qlib158_ma5", lambda p: None, tags_=["qlib158", "vibe"])
        assert f.name == "qlib158_ma5"
        assert "qlib158" in f.tags
        assert "vibe" in f.tags

    def test_lookback_days_default(self) -> None:
        from cquant.vibe_bridge.alpha_zoo import VibeFactor

        f = VibeFactor("test", lambda p: None)
        assert f.lookback_days == 60

    def test_compute_returns_series_same_length(self) -> None:
        from cquant.vibe_bridge.alpha_zoo import VibeFactor

        frame = _make_frame(5)  # 5 days × 2 assets = 10 rows
        wide_result = self._make_wide_result(frame)
        factor = VibeFactor("test_alpha", lambda panel: wide_result)
        result = factor.compute(frame, self._ctx())
        assert isinstance(result, pl.Series)
        assert len(result) == len(frame)

    def test_compute_handles_exception_gracefully(self) -> None:
        from cquant.vibe_bridge.alpha_zoo import VibeFactor

        def bad_fn(panel):
            raise ValueError("simulated error")

        factor = VibeFactor("broken", bad_fn)
        frame = _make_frame(3)
        result = factor.compute(frame, self._ctx())
        assert len(result) == len(frame)
        assert result.is_null().all()

    def test_compute_without_close_returns_nulls(self) -> None:
        from cquant.vibe_bridge.alpha_zoo import VibeFactor

        factor = VibeFactor("null_test", lambda p: None)
        frame = pl.DataFrame(
            {
                "asset_id": ["SSE:000001"],
                "trade_date": [date(2026, 1, 1)],
                "volume": [1000.0],
            }
        )
        result = factor.compute(frame, self._ctx())
        assert result.is_null().all()

    def test_build_panel_creates_wide_dfs(self) -> None:
        from cquant.vibe_bridge.alpha_zoo import _build_panel

        frame = _make_frame(3)
        panel = _build_panel(frame)
        assert "close" in panel
        assert hasattr(panel["close"], "index")  # pd.DataFrame
        assert len(panel["close"].columns) == 2  # 2 assets

    def test_build_panel_empty_without_close(self) -> None:
        from cquant.vibe_bridge.alpha_zoo import _build_panel

        frame = pl.DataFrame(
            {
                "asset_id": ["SSE:000001"],
                "trade_date": [date(2026, 1, 1)],
                "volume": [1000.0],
            }
        )
        panel = _build_panel(frame)
        assert panel == {}


class TestLoadZoo:
    def test_load_zoo_raises_when_vibe_unavailable(self) -> None:
        from cquant.vibe_bridge.alpha_zoo import load_zoo

        with patch(
            "cquant.vibe_bridge.alpha_zoo.require_vibe",
            side_effect=ImportError("no vibe"),
        ):
            with pytest.raises(ImportError):
                load_zoo("qlib158")

    def test_load_zoo_raises_for_unknown_zoo(self) -> None:
        from cquant.vibe_bridge.alpha_zoo import load_zoo

        with patch("cquant.vibe_bridge.alpha_zoo.require_vibe"):
            with pytest.raises(ValueError, match="Zoo"):
                load_zoo("nonexistent_zoo_name_xyz")

    def test_load_zoo_qlib158_returns_factors(self) -> None:
        """Real test against actual vibe-trading submodule (skips if unavailable)."""
        from cquant.vibe_bridge._compat import VIBE_AVAILABLE

        if not VIBE_AVAILABLE:
            pytest.skip("VIBE_AVAILABLE=False")
        from cquant.vibe_bridge.alpha_zoo import VibeFactor, load_zoo

        factors = load_zoo("qlib158")
        assert len(factors) > 0
        assert all(isinstance(f, VibeFactor) for f in factors)
        assert all("qlib158" in f.tags for f in factors)
