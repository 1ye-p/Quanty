"""Walk-forward backtest runner tests."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from cquant.backtest_vector.run import BacktestRunSpec


def _make_spec(walk_forward=True) -> BacktestRunSpec:
    """Create a minimal BacktestRunSpec for testing."""
    from cquant.api_server.schemas.common import WalkForwardConfig

    wf = WalkForwardConfig(n_splits=2, gap_days=5, window_type="expanding") if walk_forward else None
    return BacktestRunSpec(
        dataset_version="test_v1",
        strategy_id="test_strat",
        start_date=date(2020, 1, 1),
        end_date=date(2023, 12, 31),
        strategy_type="MLModelStrategy",
        model_version="test_model",
        walk_forward=wf,
    )


def test_backtest_run_spec_has_walk_forward():
    spec = _make_spec()
    assert spec.walk_forward is not None
    assert spec.walk_forward.n_splits == 2
    assert spec.walk_forward.gap_days == 5


def test_backtest_run_spec_without_walk_forward():
    spec = _make_spec(walk_forward=False)
    assert spec.walk_forward is None


def test_generate_walk_forward_splits_expanding():
    """Test that expanding splits are generated correctly."""
    from cquant.backtest_vector.run import BacktestRunner
    from cquant.api_server.schemas.common import WalkForwardConfig

    dates = [date(2020, 1, 1), date(2021, 1, 1), date(2022, 1, 1), date(2023, 1, 1)]
    wf = WalkForwardConfig(n_splits=2, gap_days=0, window_type="expanding")
    splits = BacktestRunner._generate_splits_static(dates, wf, min_train_size=1)
    assert len(splits) == 2
    # Each split has (train_start, train_end, test_start, test_end)
    assert splits[0][0] == date(2020, 1, 1)  # train_start always first date for expanding
    assert splits[0][2] > splits[0][1]  # test_start > train_end


def test_generate_walk_forward_splits_sliding():
    """Test that sliding splits are generated correctly."""
    from cquant.backtest_vector.run import BacktestRunner
    from cquant.api_server.schemas.common import WalkForwardConfig

    dates = [date(2020, 1, 1), date(2021, 1, 1), date(2022, 1, 1), date(2023, 1, 1)]
    wf = WalkForwardConfig(n_splits=2, gap_days=0, window_type="sliding")
    splits = BacktestRunner._generate_splits_static(dates, wf, min_train_size=1)
    assert len(splits) == 2
    # Sliding: train_start moves forward
    assert splits[1][0] > splits[0][0]


def test_generate_splits_with_gap():
    """Test that gap_days is applied between train and test."""
    from cquant.backtest_vector.run import BacktestRunner
    from cquant.api_server.schemas.common import WalkForwardConfig

    dates = [date(2020, 1, 1), date(2020, 6, 1), date(2021, 1, 1), date(2021, 6, 1),
             date(2022, 1, 1), date(2022, 6, 1)]
    wf = WalkForwardConfig(n_splits=2, gap_days=30, window_type="expanding")
    splits = BacktestRunner._generate_splits_static(dates, wf, min_train_size=1)
    assert len(splits) >= 1
    # Verify gap: test_start should be at least gap_days after train_end
    for train_start, train_end, test_start, test_end in splits:
        assert (test_start.toordinal() - train_end.toordinal()) >= 30


def test_generate_splits_insufficient_dates():
    """Test with too few dates for the requested splits."""
    from cquant.backtest_vector.run import BacktestRunner
    from cquant.api_server.schemas.common import WalkForwardConfig

    dates = [date(2020, 1, 1), date(2021, 1, 1)]
    wf = WalkForwardConfig(n_splits=5, gap_days=0, window_type="expanding")
    splits = BacktestRunner._generate_splits_static(dates, wf, min_train_size=1)
    # Should return fewer splits than requested when not enough data
    assert len(splits) <= 5


def test_run_method_branches_to_walk_forward():
    """Test that run() delegates to _run_walk_forward when walk_forward is set."""
    from cquant.backtest_vector.run import BacktestRunner

    catalog = MagicMock()
    runner = BacktestRunner(catalog)

    spec = _make_spec(walk_forward=True)

    with patch.object(runner, '_run_walk_forward', return_value='wf-run-id') as mock_wf:
        result = runner.run(spec)
        mock_wf.assert_called_once_with(spec)
        assert result == 'wf-run-id'


def test_run_method_branches_to_single():
    """Test that run() delegates to _run_single when walk_forward is None."""
    from cquant.backtest_vector.run import BacktestRunner

    catalog = MagicMock()
    runner = BacktestRunner(catalog)

    spec = _make_spec(walk_forward=False)

    with patch.object(runner, '_run_single', return_value='single-run-id') as mock_single:
        result = runner.run(spec)
        mock_single.assert_called_once_with(spec)
        assert result == 'single-run-id'
