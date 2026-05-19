"""cquant.ml_lab.datasets — Feature loading and time-aware dataset splitting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import polars as pl

from cquant.datahub.catalog import Catalog
from cquant.factorlab.pipeline import FeatureSetVersion
from cquant.ml_lab.base import infer_feature_names


@dataclass
class MLDataset:
    """ML-ready feature matrix with metadata for reproducible training."""

    data: pl.DataFrame
    feature_names: list[str]
    target_name: str = "ret_5d"
    date_column: str = "trade_date"
    asset_id_column: str = "asset_id"
    feature_set_version: str = ""

    @classmethod
    def from_feature_set(
        cls,
        feature_set: FeatureSetVersion,
        target_name: str = "ret_5d",
        feature_names: Sequence[str] | None = None,
        labels: pl.DataFrame | None = None,
        date_column: str = "trade_date",
        asset_id_column: str = "asset_id",
        drop_null_target: bool = True,
    ) -> "MLDataset":
        """Build an MLDataset from an in-memory FeatureSetVersion."""
        frame = feature_set.data
        _require_columns(frame, [asset_id_column, date_column])

        if labels is not None:
            _require_columns(labels, [asset_id_column, date_column, target_name])
            if target_name in frame.columns:
                frame = frame.drop(target_name)
            frame = frame.join(
                labels.select([asset_id_column, date_column, target_name]),
                on=[asset_id_column, date_column],
                how="left",
            )

        if target_name not in frame.columns:
            raise ValueError(
                f"Target column '{target_name}' not found in feature_set.data "
                "and no labels DataFrame provided"
            )

        resolved = infer_feature_names(frame, target_name, configured=feature_names)
        selected = frame.select([asset_id_column, date_column, *resolved, target_name])
        if drop_null_target:
            selected = selected.filter(pl.col(target_name).is_not_null())

        return cls(
            data=selected.sort([date_column, asset_id_column]),
            feature_names=resolved,
            target_name=target_name,
            date_column=date_column,
            asset_id_column=asset_id_column,
            feature_set_version=feature_set.version_id,
        )

    @classmethod
    def from_catalog(
        cls,
        catalog: Catalog,
        feature_set_version: str,
        feature_names: Sequence[str],
        target_name: str = "ret_5d",
        date_column: str = "trade_date",
        asset_id_column: str = "asset_id",
        drop_null_target: bool = True,
    ) -> "MLDataset":
        """Load a persisted feature matrix from gold_factor_values in DuckDB."""
        if not feature_names:
            raise ValueError("feature_names must not be empty when loading from catalog")

        requested = list(dict.fromkeys([*feature_names, target_name]))
        placeholders = ", ".join("?" * len(requested))
        sql = f"""
            SELECT trade_date, asset_id, factor_name, value
            FROM gold_factor_values
            WHERE feature_set_version = ?
              AND factor_name IN ({placeholders})
            ORDER BY trade_date, asset_id, factor_name
        """
        raw = catalog.query(sql, [feature_set_version, *requested])
        if raw.is_empty():
            raise ValueError(
                f"No factor values found for feature_set_version='{feature_set_version}'"
            )

        frame = (
            raw.pivot(
                values="value",
                index=[asset_id_column, date_column],
                on="factor_name",
                aggregate_function="first",
            )
            .sort([date_column, asset_id_column])
        )

        if target_name not in frame.columns:
            raise ValueError(
                f"Target factor '{target_name}' not present in feature_set_version='{feature_set_version}'"
            )

        if drop_null_target:
            frame = frame.filter(pl.col(target_name).is_not_null())

        return cls(
            data=frame,
            feature_names=list(feature_names),
            target_name=target_name,
            date_column=date_column,
            asset_id_column=asset_id_column,
            feature_set_version=feature_set_version,
        )

    def train_valid_test_split(
        self,
        train_ratio: float = 0.7,
        valid_ratio: float = 0.15,
    ) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
        """Create time-ordered train / valid / test splits by unique trade_date."""
        if not (0 < train_ratio < 1) or not (0 < valid_ratio < 1):
            raise ValueError("train_ratio and valid_ratio must be in (0, 1)")
        if train_ratio + valid_ratio >= 1:
            raise ValueError("train_ratio + valid_ratio must be < 1")

        dates = sorted(self.data.get_column(self.date_column).unique().to_list())
        if len(dates) < 3:
            raise ValueError("At least 3 unique dates are required for train/valid/test splitting")

        train_cut = max(1, int(len(dates) * train_ratio))
        valid_cut = max(train_cut + 1, int(len(dates) * (train_ratio + valid_ratio)))
        valid_cut = min(valid_cut, len(dates) - 1)

        return (
            self._filter_dates(dates[:train_cut]),
            self._filter_dates(dates[train_cut:valid_cut]),
            self._filter_dates(dates[valid_cut:]),
        )

    def _filter_dates(self, dates: Sequence[object]) -> pl.DataFrame:
        return self.data.filter(pl.col(self.date_column).is_in(dates)).sort(
            [self.date_column, self.asset_id_column]
        )


def _require_columns(frame: pl.DataFrame, columns: Sequence[str]) -> None:
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise ValueError(f"Required columns not found in DataFrame: {missing}")
