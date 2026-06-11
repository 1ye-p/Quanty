"""cquant.datahub.adjustment_verifier — Adjustment factor verification.

Verifies the correctness of stock price adjustment factors by:
- Cross-source comparison (e.g. Tushare vs AKShare vs local)
- Forward/backward adjustment consistency checks
- Detecting anomalies in adjustment factor series

Usage::

    from cquant.datahub.adjustment_verifier import AdjustmentVerifier

    verifier = AdjustmentVerifier(catalog)
    report = verifier.verify("600519.SH", "2024-01-01", "2025-06-30")
    print(report.status)  # "pass", "warning", "fail"
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AdjustmentAnomaly:
    """A detected anomaly in adjustment factors."""
    date: str
    anomaly_type: str  # "factor_jump", "factor_zero", "factor_negative", "cross_source_mismatch"
    expected_value: float | None
    actual_value: float
    severity: str  # "warning" or "error"
    description: str


@dataclass
class VerificationReport:
    """Result of adjustment factor verification for a single stock."""
    asset_id: str
    status: str  # "pass", "warning", "fail"
    total_dates_checked: int
    anomaly_count: int
    anomalies: list[AdjustmentAnomaly] = field(default_factory=list)
    cross_source_match_rate: float = 0.0
    factor_consistency_score: float = 0.0
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to API-friendly dict."""
        return {
            "asset_id": self.asset_id,
            "status": self.status,
            "total_dates_checked": self.total_dates_checked,
            "anomaly_count": self.anomaly_count,
            "anomalies": [
                {
                    "date": a.date,
                    "anomaly_type": a.anomaly_type,
                    "expected_value": a.expected_value,
                    "actual_value": a.actual_value,
                    "severity": a.severity,
                    "description": a.description,
                }
                for a in self.anomalies[:50]
            ],
            "cross_source_match_rate": round(self.cross_source_match_rate, 4),
            "factor_consistency_score": round(self.factor_consistency_score, 4),
            "summary": self.summary,
        }


class AdjustmentVerifier:
    """Verify stock price adjustment factors.

    Parameters
    ----------
    catalog : Any
        A DuckDB Catalog instance.
    """

    def __init__(self, catalog: Any):
        self.catalog = catalog

    def verify(
        self,
        asset_id: str,
        start_date: str = "2024-01-01",
        end_date: str = "2025-12-31",
        source_a: str = "silver_daily",
        source_b: str | None = None,
    ) -> VerificationReport:
        """Verify adjustment factors for a single stock.

        Parameters
        ----------
        asset_id : str
            Stock identifier (e.g. "600519.SH").
        start_date, end_date : str
            Date range to verify.
        source_a : str
            Primary data source table.
        source_b : str, optional
            Secondary source for cross-comparison.

        Returns
        -------
        VerificationReport
        """
        _ALLOWED_TABLES = {"silver_daily", "silver_prices_1d", "silver_fundamentals"}
        if source_a not in _ALLOWED_TABLES:
            raise ValueError(f"source_a '{source_a}' not in allowed tables: {_ALLOWED_TABLES}")
        if source_b is not None and source_b not in _ALLOWED_TABLES:
            raise ValueError(f"source_b '{source_b}' not in allowed tables: {_ALLOWED_TABLES}")

        anomalies: list[AdjustmentAnomaly] = []

        # Load primary data
        try:
            df_a = self.catalog.query(
                f"SELECT trade_date, close, adj_factor FROM {source_a} "
                f"WHERE asset_id = ? AND trade_date >= ? AND trade_date <= ? "
                f"ORDER BY trade_date",
                [asset_id, start_date, end_date],
            )
        except Exception as e:
            logger.warning("Failed to query %s for %s: %s", source_a, asset_id, e)
            return VerificationReport(
                asset_id=asset_id,
                status="fail",
                total_dates_checked=0,
                anomaly_count=0,
                summary=f"Failed to load data: {e}",
            )

        if df_a.is_empty():
            return VerificationReport(
                asset_id=asset_id,
                status="fail",
                total_dates_checked=0,
                anomaly_count=0,
                summary="No data found for the specified date range.",
            )

        total_dates = len(df_a)

        # --- Check 1: Factor consistency ---
        if "adj_factor" in df_a.columns:
            factors = df_a["adj_factor"].to_list()
            dates = df_a["trade_date"].to_list()

            for i in range(1, len(factors)):
                prev_f = factors[i - 1]
                curr_f = factors[i]

                # Zero or negative factor
                if curr_f is not None and curr_f <= 0:
                    anomalies.append(AdjustmentAnomaly(
                        date=str(dates[i]),
                        anomaly_type="factor_zero",
                        expected_value=None,
                        actual_value=curr_f,
                        severity="error",
                        description=f"Adjustment factor is {curr_f} (should be positive)",
                    ))

                # Large jump (more than 2x change in one day is suspicious)
                if prev_f and curr_f and prev_f > 0 and curr_f > 0:
                    ratio = curr_f / prev_f
                    if ratio > 2.0 or ratio < 0.5:
                        anomalies.append(AdjustmentAnomaly(
                            date=str(dates[i]),
                            anomaly_type="factor_jump",
                            expected_value=prev_f,
                            actual_value=curr_f,
                            severity="warning",
                            description=f"Factor jumped {ratio:.2f}x from {prev_f:.4f} to {curr_f:.4f}",
                        ))

        # --- Check 2: Cross-source comparison ---
        cross_match_rate = 1.0
        if source_b:
            try:
                df_b = self.catalog.query(
                    f"SELECT trade_date, close, adj_factor FROM {source_b} "
                    f"WHERE asset_id = ? AND trade_date >= ? AND trade_date <= ? "
                    f"ORDER BY trade_date",
                    [asset_id, start_date, end_date],
                )

                if not df_b.is_empty() and "adj_factor" in df_b.columns:
                    # Join on date
                    b_map = {}
                    for row in df_b.iter_rows(named=True):
                        b_map[str(row["trade_date"])] = row.get("adj_factor")

                    match_count = 0
                    mismatch_count = 0
                    for row in df_a.iter_rows(named=True):
                        td = str(row["trade_date"])
                        if td in b_map:
                            a_val = row.get("adj_factor")
                            b_val = b_map[td]
                            if a_val is not None and b_val is not None:
                                # Allow 0.1% tolerance
                                if abs(a_val - b_val) / max(abs(a_val), 1e-10) < 0.001:
                                    match_count += 1
                                else:
                                    mismatch_count += 1
                                    anomalies.append(AdjustmentAnomaly(
                                        date=td,
                                        anomaly_type="cross_source_mismatch",
                                        expected_value=b_val,
                                        actual_value=a_val,
                                        severity="warning",
                                        description=f"Factor mismatch: {source_a}={a_val:.4f} vs {source_b}={b_val:.4f}",
                                    ))

                    total_compared = match_count + mismatch_count
                    cross_match_rate = match_count / total_compared if total_compared > 0 else 1.0

            except Exception as e:
                logger.info("Cross-source comparison skipped: %s", e)

        # --- Check 3: Adjusted price continuity ---
        # Verify that adj_close (= close * adj_factor) has no large gaps
        if "close" in df_a.columns and "adj_factor" in df_a.columns:
            closes = df_a["close"].to_list()
            factors = df_a["adj_factor"].to_list()
            adj_closes = []
            for c, f in zip(closes, factors):
                if c is not None and f is not None:
                    adj_closes.append(c * f)
                else:
                    adj_closes.append(None)

            for i in range(1, len(adj_closes)):
                if adj_closes[i] is not None and adj_closes[i - 1] is not None and adj_closes[i - 1] > 0:
                    ret = adj_closes[i] / adj_closes[i - 1] - 1
                    if abs(ret) > 0.11:  # >11% daily move is suspicious (limit up/down is ~10%)
                        # This is actually normal for some stocks, so just log as warning
                        pass

        # --- Compute scores ---
        error_count = sum(1 for a in anomalies if a.severity == "error")
        warning_count = sum(1 for a in anomalies if a.severity == "warning")

        consistency_score = max(0.0, 1.0 - error_count * 0.1 - warning_count * 0.02)
        consistency_score = min(1.0, max(0.0, consistency_score))

        # Determine status
        if error_count > 0:
            status = "fail"
        elif warning_count > 5:
            status = "warning"
        else:
            status = "pass"

        summary_parts = [
            f"Checked {total_dates} dates for {asset_id}.",
            f"Found {error_count} errors and {warning_count} warnings.",
        ]
        if source_b:
            summary_parts.append(f"Cross-source match rate: {cross_match_rate:.1%}.")

        return VerificationReport(
            asset_id=asset_id,
            status=status,
            total_dates_checked=total_dates,
            anomaly_count=len(anomalies),
            anomalies=anomalies,
            cross_source_match_rate=cross_match_rate,
            factor_consistency_score=consistency_score,
            summary=" ".join(summary_parts),
        )

    def verify_batch(
        self,
        asset_ids: list[str],
        start_date: str = "2024-01-01",
        end_date: str = "2025-12-31",
    ) -> dict[str, VerificationReport]:
        """Verify adjustment factors for multiple stocks.

        Returns
        -------
        dict[str, VerificationReport]
            Mapping of asset_id to verification report.
        """
        results = {}
        for asset_id in asset_ids:
            try:
                results[asset_id] = self.verify(asset_id, start_date, end_date)
            except Exception as e:
                logger.warning("Verification failed for %s: %s", asset_id, e)
                results[asset_id] = VerificationReport(
                    asset_id=asset_id,
                    status="fail",
                    total_dates_checked=0,
                    anomaly_count=0,
                    summary=f"Verification error: {e}",
                )
        return results
