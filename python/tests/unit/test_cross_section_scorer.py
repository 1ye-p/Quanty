"""Tests for CrossSectionScorer neutralization."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import polars as pl
import pytest

from cquant.factorlab.cross_section_scorer import (
    CrossSectionScorer,
    FactorWeight,
    ScoringConfig,
)


@pytest.fixture
def mock_catalog():
    """Create a mock catalog with test data."""
    catalog = MagicMock()
    return catalog


@pytest.fixture
def sample_factor_data():
    """Sample factor data for testing."""
    dates = ["2024-01-01", "2024-01-01", "2024-01-01", "2024-01-02", "2024-01-02", "2024-01-02"]
    assets = ["A", "B", "C", "A", "B", "C"]
    factor1 = [1.0, 2.0, 3.0, 1.5, 2.5, 3.5]
    factor2 = [0.1, 0.2, 0.3, 0.15, 0.25, 0.35]

    return pl.DataFrame(
        {
            "trade_date": dates,
            "asset_id": assets,
            "factor1": factor1,
            "factor2": factor2,
        }
    ).with_columns(pl.col("trade_date").cast(pl.Date))


@pytest.fixture
def sample_mktcap_data():
    """Sample market cap data."""
    dates = ["2024-01-01", "2024-01-01", "2024-01-01", "2024-01-02", "2024-01-02", "2024-01-02"]
    assets = ["A", "B", "C", "A", "B", "C"]
    market_cap = [1e9, 2e9, 3e9, 1.1e9, 2.1e9, 3.1e9]

    return pl.DataFrame(
        {
            "asset_id": assets,
            "trade_date": dates,
            "market_cap": market_cap,
        }
    ).with_columns(
        pl.col("trade_date").cast(pl.Date),
        pl.col("market_cap").log().alias("ln_mktcap"),
    ).drop("market_cap")


@pytest.fixture
def sample_industry_data():
    """Sample industry data."""
    assets = ["A", "B", "C"]
    industry = ["Tech", "Finance", "Tech"]

    return pl.DataFrame(
        {
            "asset_id": assets,
            "industry": industry,
        }
    )


class TestNeutralizeFactors:
    """Test _neutralize_factors method."""

    def test_empty_neutralize_list(self, mock_catalog, sample_factor_data):
        """When neutralize list is empty, return original data."""
        scorer = CrossSectionScorer(mock_catalog)
        config = ScoringConfig(
            name="test",
            factors=[FactorWeight(factor_name="factor1")],
            neutralize=[],
        )

        result = scorer._neutralize_factors(sample_factor_data, config, "2024-01-01", "2024-01-02")
        assert result.equals(sample_factor_data)

    def test_no_factor_columns(self, mock_catalog, sample_factor_data):
        """When factor columns not in DataFrame, return original data."""
        scorer = CrossSectionScorer(mock_catalog)
        config = ScoringConfig(
            name="test",
            factors=[FactorWeight(factor_name="missing_factor")],
            neutralize=["market_cap"],
        )

        result = scorer._neutralize_factors(sample_factor_data, config, "2024-01-01", "2024-01-02")
        assert result.equals(sample_factor_data)

    def test_neutralize_market_cap(self, mock_catalog, sample_factor_data, sample_mktcap_data):
        """Test market cap neutralization produces residuals."""
        scorer = CrossSectionScorer(mock_catalog)

        # Mock the _load_neutralization_data method
        with patch.object(scorer, "_load_neutralization_data", return_value=sample_mktcap_data):
            config = ScoringConfig(
                name="test",
                factors=[FactorWeight(factor_name="factor1"), FactorWeight(factor_name="factor2")],
                neutralize=["market_cap"],
            )

            result = scorer._neutralize_factors(sample_factor_data, config, "2024-01-01", "2024-01-02")

            # Check that result has same columns as input
            assert set(result.columns) == set(sample_factor_data.columns)

            # Check that factor values have been modified (neutralized)
            original = sample_factor_data.sort(["trade_date", "asset_id"])
            neutralized = result.sort(["trade_date", "asset_id"])

            # The values should be different after neutralization
            assert not original["factor1"].equals(neutralized["factor1"])
            assert not original["factor2"].equals(neutralized["factor2"])

    def test_neutralize_industry(self, mock_catalog):
        """Test industry neutralization produces residuals."""
        scorer = CrossSectionScorer(mock_catalog)

        # Use more assets to avoid perfect fit
        factor_data = pl.DataFrame(
            {
                "trade_date": ["2024-01-01"] * 6,
                "asset_id": ["A", "B", "C", "D", "E", "F"],
                "factor1": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
                "factor2": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
            }
        ).with_columns(pl.col("trade_date").cast(pl.Date))

        # Create industry neutralization data with one-hot encoding (3 industries, 6 assets)
        industry_data = pl.DataFrame(
            {
                "asset_id": ["A", "B", "C", "D", "E", "F"],
                "trade_date": ["2024-01-01"] * 6,
                "industry_Finance": [0.0, 1.0, 0.0, 0.0, 1.0, 0.0],
                "industry_Healthcare": [0.0, 0.0, 1.0, 0.0, 0.0, 1.0],
                "industry_Tech": [1.0, 0.0, 0.0, 1.0, 0.0, 0.0],
            }
        ).with_columns(pl.col("trade_date").cast(pl.Date))

        with patch.object(scorer, "_load_neutralization_data", return_value=industry_data):
            config = ScoringConfig(
                name="test",
                factors=[FactorWeight(factor_name="factor1"), FactorWeight(factor_name="factor2")],
                neutralize=["industry"],
            )

            result = scorer._neutralize_factors(factor_data, config, "2024-01-01", "2024-01-01")

            # Check that result has same columns as input (industry dummies should be dropped)
            assert set(result.columns) == set(factor_data.columns)

            # Check that factor values have been modified
            original = factor_data.sort(["trade_date", "asset_id"])
            neutralized = result.sort(["trade_date", "asset_id"])

            assert not original["factor1"].equals(neutralized["factor1"])

    def test_neutralize_both(self, mock_catalog, sample_factor_data, sample_mktcap_data):
        """Test neutralization with both market_cap and industry."""
        scorer = CrossSectionScorer(mock_catalog)

        # Combine market cap and industry data
        combined_data = sample_mktcap_data.with_columns(
            pl.Series("industry_Finance", [0.0, 1.0, 0.0, 0.0, 1.0, 0.0]),
            pl.Series("industry_Tech", [1.0, 0.0, 1.0, 1.0, 0.0, 1.0]),
        )

        with patch.object(scorer, "_load_neutralization_data", return_value=combined_data):
            config = ScoringConfig(
                name="test",
                factors=[FactorWeight(factor_name="factor1")],
                neutralize=["market_cap", "industry"],
            )

            result = scorer._neutralize_factors(sample_factor_data, config, "2024-01-01", "2024-01-02")

            # Check that result has same columns as input
            assert set(result.columns) == set(sample_factor_data.columns)

            # Check that helper columns are dropped
            assert "ln_mktcap" not in result.columns
            assert not any(c.startswith("industry_") for c in result.columns)

    def test_insufficient_observations(self, mock_catalog):
        """When too few observations for regression, keep original values."""
        scorer = CrossSectionScorer(mock_catalog)

        # Only 1 observation per date - not enough for regression
        small_data = pl.DataFrame(
            {
                "trade_date": ["2024-01-01"],
                "asset_id": ["A"],
                "factor1": [1.0],
            }
        ).with_columns(pl.col("trade_date").cast(pl.Date))

        small_mktcap = pl.DataFrame(
            {
                "asset_id": ["A"],
                "trade_date": ["2024-01-01"],
                "ln_mktcap": [20.0],
            }
        ).with_columns(pl.col("trade_date").cast(pl.Date))

        with patch.object(scorer, "_load_neutralization_data", return_value=small_mktcap):
            config = ScoringConfig(
                name="test",
                factors=[FactorWeight(factor_name="factor1")],
                neutralize=["market_cap"],
            )

            result = scorer._neutralize_factors(small_data, config, "2024-01-01", "2024-01-01")

            # Should keep original values since we can't regress with 1 observation
            assert result["factor1"][0] == 1.0

    def test_empty_neutralization_data(self, mock_catalog, sample_factor_data):
        """When neutralization data is empty, return original data."""
        scorer = CrossSectionScorer(mock_catalog)

        with patch.object(scorer, "_load_neutralization_data", return_value=pl.DataFrame()):
            config = ScoringConfig(
                name="test",
                factors=[FactorWeight(factor_name="factor1")],
                neutralize=["market_cap"],
            )

            result = scorer._neutralize_factors(sample_factor_data, config, "2024-01-01", "2024-01-02")
            assert result.equals(sample_factor_data)


class TestLoadNeutralizationData:
    """Test _load_neutralization_data method."""

    def test_load_market_cap(self, mock_catalog):
        """Test loading market cap data from silver_fundamentals."""
        scorer = CrossSectionScorer(mock_catalog)

        mock_catalog.query.return_value = pl.DataFrame(
            {
                "asset_id": ["A", "B"],
                "trade_date": ["2024-01-01", "2024-01-01"],
                "market_cap": [1e9, 2e9],
            }
        ).with_columns(pl.col("trade_date").cast(pl.Date))

        result = scorer._load_neutralization_data(["market_cap"], "2024-01-01", "2024-01-01")

        assert "ln_mktcap" in result.columns
        assert "asset_id" in result.columns
        assert "trade_date" in result.columns

    def test_load_industry(self, mock_catalog):
        """Test loading industry data from silver_assets."""
        scorer = CrossSectionScorer(mock_catalog)

        # Mock two queries: one for industry, one for dates
        mock_catalog.query.side_effect = [
            # First call: industry data
            pl.DataFrame(
                {
                    "asset_id": ["A", "B", "C"],
                    "industry": ["Tech", "Finance", "Tech"],
                }
            ),
            # Second call: distinct dates
            pl.DataFrame(
                {
                    "trade_date": ["2024-01-01", "2024-01-02"],
                }
            ).with_columns(pl.col("trade_date").cast(pl.Date)),
        ]

        result = scorer._load_neutralization_data(["industry"], "2024-01-01", "2024-01-02")

        assert "industry_Tech" in result.columns
        assert "industry_Finance" in result.columns
        assert "asset_id" in result.columns
        assert "trade_date" in result.columns

    def test_load_both(self, mock_catalog):
        """Test loading both market cap and industry data."""
        scorer = CrossSectionScorer(mock_catalog)

        mock_catalog.query.side_effect = [
            # First call: market cap
            pl.DataFrame(
                {
                    "asset_id": ["A", "B"],
                    "trade_date": ["2024-01-01", "2024-01-01"],
                    "market_cap": [1e9, 2e9],
                }
            ).with_columns(pl.col("trade_date").cast(pl.Date)),
            # Second call: industry
            pl.DataFrame(
                {
                    "asset_id": ["A", "B"],
                    "industry": ["Tech", "Finance"],
                }
            ),
            # Third call: distinct dates
            pl.DataFrame(
                {
                    "trade_date": ["2024-01-01"],
                }
            ).with_columns(pl.col("trade_date").cast(pl.Date)),
        ]

        result = scorer._load_neutralization_data(
            ["market_cap", "industry"], "2024-01-01", "2024-01-01"
        )

        assert "ln_mktcap" in result.columns
        assert "industry_Tech" in result.columns
        assert "industry_Finance" in result.columns


class TestScoreIntegration:
    """Test that score() correctly integrates neutralization."""

    def test_score_with_neutralization(self, mock_catalog):
        """Test full scoring pipeline with neutralization."""
        scorer = CrossSectionScorer(mock_catalog)

        # Mock _load_factors
        factor_data = pl.DataFrame(
            {
                "trade_date": ["2024-01-01", "2024-01-01", "2024-01-01"],
                "asset_id": ["A", "B", "C"],
                "factor1": [1.0, 2.0, 3.0],
            }
        ).with_columns(pl.col("trade_date").cast(pl.Date))

        mktcap_data = pl.DataFrame(
            {
                "asset_id": ["A", "B", "C"],
                "trade_date": ["2024-01-01", "2024-01-01", "2024-01-01"],
                "ln_mktcap": [20.0, 21.0, 22.0],
            }
        ).with_columns(pl.col("trade_date").cast(pl.Date))

        with patch.object(scorer, "_load_factors", return_value=factor_data):
            with patch.object(scorer, "_load_neutralization_data", return_value=mktcap_data):
                config = ScoringConfig(
                    name="test",
                    factors=[FactorWeight(factor_name="factor1")],
                    neutralize=["market_cap"],
                )

                result = scorer.score(config, "v1", "2024-01-01", "2024-01-01")

                assert "trade_date" in result.columns
                assert "asset_id" in result.columns
                assert "score" in result.columns
                assert "rank" in result.columns
                assert len(result) == 3

    def test_score_without_neutralization(self, mock_catalog):
        """Test scoring pipeline without neutralization."""
        scorer = CrossSectionScorer(mock_catalog)

        factor_data = pl.DataFrame(
            {
                "trade_date": ["2024-01-01", "2024-01-01", "2024-01-01"],
                "asset_id": ["A", "B", "C"],
                "factor1": [1.0, 2.0, 3.0],
            }
        ).with_columns(pl.col("trade_date").cast(pl.Date))

        with patch.object(scorer, "_load_factors", return_value=factor_data):
            config = ScoringConfig(
                name="test",
                factors=[FactorWeight(factor_name="factor1")],
                neutralize=[],
            )

            result = scorer.score(config, "v1", "2024-01-01", "2024-01-01")

            assert len(result) == 3
            # Without neutralization, scores should be z-scored factor values
