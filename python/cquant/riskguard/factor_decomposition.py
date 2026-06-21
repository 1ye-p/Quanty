"""cquant.riskguard.factor_decomposition — Barra-style factor risk decomposition.

Computes portfolio factor exposures (style + industry) and decomposes total
risk into factor-driven and idiosyncratic components.

Style factors:
    - market_cap: ln(market_cap) from silver_fundamentals
    - value: 1/PB from silver_fundamentals
    - momentum: past 20-day return from silver_prices_1d
    - volatility: past 60-day standard deviation from silver_prices_1d
    - turnover: average daily turnover from silver_fundamentals (amount-based)
    - quality: ROE from silver_fundamentals

Industry factors:
    - Shenwan Level-1 industry dummies from silver_assets.industry
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Any

import numpy as np
import polars as pl

if TYPE_CHECKING:
    from cquant.datahub.catalog import Catalog

logger = logging.getLogger(__name__)

# ── Factor names ─────────────────────────────────────────────────────────────

STYLE_FACTORS = ["market_cap", "value", "momentum", "volatility", "turnover", "quality"]


# ── Core computation ─────────────────────────────────────────────────────────


def compute_factor_exposures(
    catalog: "Catalog",
    asset_ids: list[str],
    as_of_date: str | None = None,
) -> tuple[pl.DataFrame, list[str]]:
    """Compute per-asset style and industry factor exposures.

    Returns
    -------
    exposures_df : pl.DataFrame
        Columns: asset_id, market_cap, value, momentum, volatility,
        turnover, quality, plus one column per industry (dummy 0/1).
    industries : list[str]
        Sorted list of industry names (matching the dummy columns).
    """
    if not asset_ids:
        return pl.DataFrame(), []

    # ── 1. Fetch fundamentals (latest per asset) ────────────────────────────
    placeholders = ",".join(["?"] * len(asset_ids))
    fund_sql = f"""
        SELECT asset_id, pb, market_cap, roe
        FROM silver_fundamentals
        WHERE asset_id IN ({placeholders})
          AND pb IS NOT NULL AND pb > 0
          AND market_cap IS NOT NULL AND market_cap > 0
        ORDER BY asset_id, report_date DESC
    """
    fund_df = catalog.query(fund_sql, asset_ids)

    if fund_df.is_empty():
        logger.warning("No fundamental data found for requested assets")
        return pl.DataFrame(), []

    # Keep latest record per asset
    fund_df = fund_df.unique(subset=["asset_id"], keep="first")

    # ── 2. Fetch price history for momentum & volatility ────────────────────
    price_sql = f"""
        SELECT asset_id, trade_date, close, volume
        FROM silver_prices_1d
        WHERE asset_id IN ({placeholders})
        ORDER BY asset_id, trade_date DESC
    """
    price_df = catalog.query(price_sql, asset_ids)

    momentum_map: dict[str, float] = {}
    volatility_map: dict[str, float] = {}
    turnover_map: dict[str, float] = {}

    if not price_df.is_empty():
        for aid in asset_ids:
            sub = price_df.filter(pl.col("asset_id") == aid).sort("trade_date", descending=True)
            if sub.height < 2:
                continue

            closes = sub["close"].to_numpy().astype(float)
            volumes = sub["volume"].to_numpy().astype(float)

            # Momentum: 20-day return
            if len(closes) >= 20:
                momentum_map[aid] = float((closes[0] / closes[19]) - 1.0)

            # Volatility: 60-day std of daily returns
            if len(closes) >= 61:
                daily_ret = np.diff(closes[:61]) / closes[:60]
                volatility_map[aid] = float(np.std(daily_ret))

            # Turnover: average daily volume (normalised later)
            n = min(len(volumes), 60)
            if n > 0:
                turnover_map[aid] = float(np.mean(volumes[:n]))

    # ── 3. Fetch industry mapping ───────────────────────────────────────────
    ind_sql = f"""
        SELECT asset_id, industry
        FROM silver_assets
        WHERE asset_id IN ({placeholders}) AND industry IS NOT NULL
    """
    ind_df = catalog.query(ind_sql, asset_ids)
    industry_map: dict[str, str] = {}
    if not ind_df.is_empty():
        industry_map = dict(zip(ind_df["asset_id"].to_list(), ind_df["industry"].to_list()))

    industries = sorted(set(industry_map.values()))

    # ── 4. Build exposure matrix ────────────────────────────────────────────
    rows: list[dict[str, Any]] = []
    for aid in asset_ids:
        fund_row = fund_df.filter(pl.col("asset_id") == aid)
        if fund_row.is_empty():
            continue

        pb = float(fund_row["pb"][0])
        mcap = float(fund_row["market_cap"][0])
        roe = float(fund_row["roe"][0]) if fund_row["roe"][0] is not None else 0.0

        row: dict[str, Any] = {"asset_id": aid}
        # Style factors (raw, will be cross-sectionally standardised)
        row["market_cap"] = math.log(mcap) if mcap > 0 else 0.0
        row["value"] = 1.0 / pb if pb > 0 else 0.0
        row["momentum"] = momentum_map.get(aid, 0.0)
        row["volatility"] = volatility_map.get(aid, 0.0)
        row["turnover"] = turnover_map.get(aid, 0.0)
        row["quality"] = roe

        # Industry dummies
        ind = industry_map.get(aid)
        for ind_name in industries:
            row[ind_name] = 1.0 if ind == ind_name else 0.0

        rows.append(row)

    if not rows:
        return pl.DataFrame(), industries

    df = pl.DataFrame(rows)

    # ── 5. Cross-sectional standardisation (z-score) for style factors ──────
    for col_name in STYLE_FACTORS:
        vals = df[col_name].to_numpy().astype(float)
        mu = np.nanmean(vals)
        sigma = np.nanstd(vals)
        if sigma > 1e-12:
            df = df.with_columns(
                ((pl.col(col_name) - mu) / sigma).alias(col_name)
            )
        else:
            df = df.with_columns(pl.lit(0.0).alias(col_name))

    return df, industries


def compute_portfolio_exposures(
    exposures_df: pl.DataFrame,
    weights: dict[str, float],
    industries: list[str],
) -> tuple[dict[str, float], dict[str, float]]:
    """Compute portfolio-level factor exposures as weighted sum.

    Returns
    -------
    style_exposures : dict[str, float]
    industry_exposures : dict[str, float]
    """
    if exposures_df.is_empty():
        return {}, {}

    style_exp: dict[str, float] = {f: 0.0 for f in STYLE_FACTORS}
    ind_exp: dict[str, float] = {i: 0.0 for i in industries}

    for _, row in enumerate(exposures_df.iter_rows(named=True)):
        aid = row["asset_id"]
        w = weights.get(aid, 0.0)
        if abs(w) < 1e-12:
            continue
        for f in STYLE_FACTORS:
            style_exp[f] += w * row.get(f, 0.0)
        for ind_name in industries:
            ind_exp[ind_name] += w * row.get(ind_name, 0.0)

    return style_exp, ind_exp


def compute_risk_decomposition(
    exposures_df: pl.DataFrame,
    weights: dict[str, float],
    industries: list[str],
    style_exposures: dict[str, float],
    industry_exposures: dict[str, float],
) -> dict[str, Any]:
    """Compute factor risk decomposition.

    Steps:
    1. Build factor matrix F (N_assets x K_factors)
    2. Estimate factor covariance: Sigma_F = (F'F) / (N-1)  (cross-sectional)
    3. Portfolio factor exposure: f_p = F' * w
    4. Factor risk: sigma2_factor = f_p' * Sigma_F * f_p
    5. Estimate total risk from asset return covariance
    6. Idiosyncratic risk: sigma2_total - sigma2_factor

    Returns dict with total_risk, factor_risk, idiosyncratic_risk,
    factor_risk_pct, and per-factor risk contributions.
    """
    factor_cols = STYLE_FACTORS + industries
    n_assets = exposures_df.height
    n_factors = len(factor_cols)

    if n_assets < 2 or n_factors == 0:
        return {
            "total_risk": 0.0,
            "factor_risk": 0.0,
            "idiosyncratic_risk": 0.0,
            "factor_risk_pct": 0.0,
            "style_risk_contributions": {f: 0.0 for f in STYLE_FACTORS},
            "industry_risk_contributions": {i: 0.0 for i in industries},
        }

    # Build factor matrix
    F = np.zeros((n_assets, n_factors))
    for j, col in enumerate(factor_cols):
        F[:, j] = exposures_df[col].to_numpy().astype(float)

    # Weight vector aligned with exposures_df
    w = np.array([
        weights.get(row["asset_id"], 0.0)
        for row in exposures_df.iter_rows(named=True)
    ])

    # Factor covariance (cross-sectional sample covariance)
    if n_assets > 1:
        F_centered = F - F.mean(axis=0, keepdims=True)
        Sigma_F = (F_centered.T @ F_centered) / (n_assets - 1)
    else:
        Sigma_F = np.eye(n_factors) * 0.01

    # Portfolio factor exposure vector
    f_p = F.T @ w  # shape (K,)

    # Factor risk: f_p' * Sigma_F * f_p
    factor_var = float(f_p @ Sigma_F @ f_p)
    factor_risk = math.sqrt(max(factor_var, 0.0))

    # Total risk estimate: w' * (F * Sigma_F * F' + D) * w
    # where D = diag(idiosyncratic variances)
    # Estimate idiosyncratic variance per asset as residual from factor model
    # For cross-sectional model, approximate total variance from factor model:
    asset_cov = F @ Sigma_F @ F.T  # (N x N) factor-implied covariance
    total_var = float(w @ asset_cov @ w)

    # Add idiosyncratic residual: estimate from cross-sectional R^2
    # sigma2_idio_i = var(residual_i) -- approximated as average residual variance
    # For a simpler model, use factor-implied total and subtract
    # Here: total_risk = sqrt(factor_var + idio_var)
    # idio_var estimated as: average residual variance * sum(w_i^2)
    residual_vars = np.zeros(n_assets)
    for i in range(n_assets):
        # Residual = asset_exposure - F_i * (F'F)^-1 * F' * asset_exposure
        # Simplified: use trace of residual covariance
        fitted = F @ np.linalg.lstsq(F, F[i, :], rcond=None)[0]
        residual_vars[i] = float(np.var(F[i, :] - fitted))

    idio_var = float(np.sum(w ** 2 * residual_vars))
    total_risk = math.sqrt(max(total_var + idio_var, 0.0))
    idio_risk = math.sqrt(max(idio_var, 0.0))

    factor_risk_pct = (factor_risk / total_risk * 100.0) if total_risk > 1e-12 else 0.0

    # Marginal risk contributions per factor
    # RC_k = f_p_k * (Sigma_F * f_p)_k / sigma_factor
    Sigma_f_p = Sigma_F @ f_p
    style_contribs: dict[str, float] = {}
    industry_contribs: dict[str, float] = {}

    if factor_risk > 1e-12:
        for j, col in enumerate(factor_cols):
            contrib = float(f_p[j] * Sigma_f_p[j]) / factor_risk
            if col in STYLE_FACTORS:
                style_contribs[col] = contrib
            else:
                industry_contribs[col] = contrib
    else:
        for f in STYLE_FACTORS:
            style_contribs[f] = 0.0
        for i in industries:
            industry_contribs[i] = 0.0

    return {
        "total_risk": total_risk,
        "factor_risk": factor_risk,
        "idiosyncratic_risk": idio_risk,
        "factor_risk_pct": factor_risk_pct,
        "style_risk_contributions": style_contribs,
        "industry_risk_contributions": industry_contribs,
    }


def run_factor_decomposition(
    catalog: "Catalog",
    weights: dict[str, float],
    as_of_date: str | None = None,
) -> dict[str, Any]:
    """End-to-end factor risk decomposition.

    Parameters
    ----------
    catalog : Catalog
        Open database connection.
    weights : dict[str, float]
        {asset_id: weight} mapping. Weights are normalised internally.
    as_of_date : str, optional
        ISO date for data cutoff (currently unused, uses latest data).

    Returns
    -------
    dict with style_exposures, industry_exposures, risk_decomposition.
    """
    if not weights:
        return {
            "style_exposures": {f: 0.0 for f in STYLE_FACTORS},
            "industry_exposures": {},
            "risk_decomposition": {
                "total_risk": 0.0,
                "factor_risk": 0.0,
                "idiosyncratic_risk": 0.0,
                "factor_risk_pct": 0.0,
                "style_risk_contributions": {f: 0.0 for f in STYLE_FACTORS},
                "industry_risk_contributions": {},
            },
        }

    # Normalise weights
    total_w = sum(weights.values())
    if abs(total_w) > 1e-12 and abs(total_w - 1.0) > 0.01:
        weights = {k: v / total_w for k, v in weights.items()}

    asset_ids = list(weights.keys())

    # Compute exposures
    exposures_df, industries = compute_factor_exposures(
        catalog, asset_ids, as_of_date
    )

    if exposures_df.is_empty():
        return {
            "style_exposures": {f: 0.0 for f in STYLE_FACTORS},
            "industry_exposures": {},
            "risk_decomposition": {
                "total_risk": 0.0,
                "factor_risk": 0.0,
                "idiosyncratic_risk": 0.0,
                "factor_risk_pct": 0.0,
                "style_risk_contributions": {f: 0.0 for f in STYLE_FACTORS},
                "industry_risk_contributions": {},
            },
        }

    # Portfolio-level exposures
    style_exp, ind_exp = compute_portfolio_exposures(
        exposures_df, weights, industries
    )

    # Risk decomposition
    risk_decomp = compute_risk_decomposition(
        exposures_df, weights, industries, style_exp, ind_exp
    )

    return {
        "style_exposures": style_exp,
        "industry_exposures": ind_exp,
        "risk_decomposition": risk_decomp,
    }
