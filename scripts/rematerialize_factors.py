#!/usr/bin/env python3
"""rematerialize_factors.py — Re-materialize close-dependent factors.

After Phase 2 made ``close`` a fully-adjusted price (see ``_load_prices``),
every previously-materialized factor that reads ``close`` is now stale because
it was computed from raw (un-adjusted) closes.  This script recomputes them
with the adjusted prices.

Which factors are close-dependent (and therefore re-materialized here):

  * Momentum  — ret_1d / ret_5d / ret_20d / ret_60d / ret_120d / ret_240d,
                momentum_12_1
  * Volatility — vol_20d / vol_60d / vol_120d, downside_vol_20d, max_drawdown_20d
  * Technical  — zscore_close_60d, ma_20d_ratio, rsi_14d,
                 bollinger_width_20d, price_high_20d_ratio
  * Alpha158 rolling (close-based) — ROC{5,10,20,30}, MA{5,10,20,30},
                 STD{5,10,20,30}, MAX{5,20}, MIN{5,20}
  * Alpha158 KBAR (OHLC-based, includes close) — KMID, KLEN, KMID2, KUP, KUP2,
                 KLOW, KLOW2, KSFT, KSFT2

Fundamental / valuation factors (PE / PB / DividendYield / ROE / ROA /
margins / growth / MarketCap) read from ``silver_fundamentals`` and
``silver_valuation_daily`` and do NOT depend on ``close`` — they are explicitly
EXCLUDED.  Turnover factors read volume/amount, also excluded.

The script reuses the production materialization path
(``FactorMaterializer``) so that the adjusted-ohlc SQL helper
(``adjusted_ohlc_sql``) and PIT-correct fundamental/valuation loading are
applied identically to the backtest path.

Usage::

    python scripts/rematerialize_factors.py \
        --dataset-version tdx_bulk_v1 \
        --start 2024-01-01 --end 2025-12-31

    # Restrict to a subset of factor groups
    python scripts/rematerialize_factors.py \
        --dataset-version tdx_bulk_v1 \
        --start 2024-01-01 --end 2025-12-31 \
        --groups momentum volatility technical
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

# Ensure project root is on sys.path so ``cquant`` is importable when run as a
# plain script (matching the convention used by other scripts/ entries).
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ─── Close-dependent factor groups (registered names) ──────────────────────
# NOTE: kept as explicit lists rather than introspecting tags so the script is
# self-documenting and survives factor renames with a clear failure.
CLOSE_DEPENDENT_GROUPS: dict[str, list[str]] = {
    "momentum": [
        "ret_1d", "ret_5d", "ret_20d", "ret_60d", "ret_120d", "ret_240d",
        "momentum_12_1",
    ],
    "volatility": [
        "vol_20d", "vol_60d", "vol_120d", "downside_vol_20d", "max_drawdown_20d",
    ],
    "technical": [
        "zscore_close_60d", "ma_20d_ratio", "rsi_14d",
        "bollinger_width_20d", "price_high_20d_ratio",
    ],
    "alpha158_rolling": [
        "ROC5", "ROC10", "ROC20", "ROC30",
        "MA5", "MA10", "MA20", "MA30",
        "STD5", "STD10", "STD20", "STD30",
        "MAX5", "MAX20", "MIN5", "MIN20",
    ],
    "kbar": [
        "KMID", "KLEN", "KMID2", "KUP", "KUP2",
        "KLOW", "KLOW2", "KSFT", "KSFT2",
    ],
}

# Explicit exclusions — these factors have NO close dependency:
#   * value/size (PE/PB/DividendYield/MarketCap) → silver_valuation_daily
#   * quality/growth (ROE/ROA/margins/growth)    → silver_fundamentals
#   * turnover (volume/amount ratios)            → volume/amount columns
EXCLUDED_GROUPS = {"value", "size", "quality", "growth", "turnover"}


def select_factor_names(groups: list[str] | None) -> list[str]:
    """Return the ordered, de-duplicated list of close-dependent factor names.

    Parameters
    ----------
    groups:
        Subset of :data:`CLOSE_DEPENDENT_GROUPS` keys to restrict to.
        ``None`` (default) selects every group.
    """
    if groups is None:
        groups = list(CLOSE_DEPENDENT_GROUPS.keys())

    invalid = [g for g in groups if g not in CLOSE_DEPENDENT_GROUPS]
    if invalid:
        raise SystemExit(
            f"Unknown group(s) {invalid}. "
            f"Valid groups: {sorted(CLOSE_DEPENDENT_GROUPS)}"
        )

    names: list[str] = []
    seen: set[str] = set()
    for g in groups:
        for n in CLOSE_DEPENDENT_GROUPS[g]:
            if n not in seen:
                names.append(n)
                seen.add(n)
    return names


def rematerialize(
    dataset_version: str,
    start: date,
    end: date,
    factor_names: list[str],
    db_path: str = "data/catalog.duckdb",
) -> str:
    """Build a registry limited to *factor_names* and (re-)materialize them.

    Returns the ``feature_set_version`` written to ``gold_factor_values``.
    """
    from cquant.datahub.catalog import Catalog  # noqa: PLC0415
    from cquant.factorlab.factor import FactorRegistry  # noqa: PLC0415
    from cquant.factorlab.factors import BUILTIN_FACTORS  # noqa: PLC0415
    from cquant.factorlab.materialize import (  # noqa: PLC0415
        FactorMaterializationSpec,
        FactorMaterializer,
    )

    # Build a registry restricted to the requested factors so the materializer
    # only computes what we need (and so a typo surfaces as "unknown factor").
    available = {f.name for f in BUILTIN_FACTORS}
    wanted = set(factor_names)
    missing = sorted(wanted - available)
    if missing:
        logger.warning(
            "These close-dependent factors are not registered in BUILTIN_FACTORS "
            "(skipping): %s", missing,
        )
    registry = FactorRegistry()
    for factor in BUILTIN_FACTORS:
        if factor.name in wanted and factor.name in available:
            registry.register(factor)

    if not registry.all_names():
        raise SystemExit(
            "No registered factors matched the requested set — nothing to do."
        )

    logger.info(
        "Re-materializing %d close-dependent factors: %s",
        len(registry.all_names()), ", ".join(registry.all_names()),
    )
    logger.info(
        "Excluded (no close dependency): %s", ", ".join(sorted(EXCLUDED_GROUPS)),
    )

    catalog = Catalog(db_path)
    materializer = FactorMaterializer(catalog, registry)
    spec = FactorMaterializationSpec(
        dataset_version=dataset_version,
        factor_names=registry.all_names(),
        start_date=start,
        end_date=end,
    )
    version_id = materializer.run(spec)
    logger.info(
        "Re-materialization complete → feature_set_version=%s (%d factors, %s → %s)",
        version_id, len(registry.all_names()), start.isoformat(), end.isoformat(),
    )
    return version_id


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Re-materialize close-dependent factors (momentum/volatility/"
            "technical/alpha158-rolling/kbar) with adjusted prices."
        ),
    )
    parser.add_argument(
        "--dataset-version", required=True,
        help="Dataset version tag (e.g. tdx_bulk_v1).",
    )
    parser.add_argument(
        "--start", required=True,
        help="Start date YYYY-MM-DD (materialization window start).",
    )
    parser.add_argument(
        "--end", required=True,
        help="End date YYYY-MM-DD (materialization window end).",
    )
    parser.add_argument(
        "--groups", nargs="+", default=None,
        choices=sorted(CLOSE_DEPENDENT_GROUPS.keys()),
        help=(
            "Subset of close-dependent groups to re-materialize "
            "(default: all). Fundamental/value/turnover groups are always "
            "excluded."
        ),
    )
    parser.add_argument(
        "--db-path", default="data/catalog.duckdb",
        help="DuckDB catalog path (default: data/catalog.duckdb).",
    )
    args = parser.parse_args()

    factor_names = select_factor_names(args.groups)
    start_date = date.fromisoformat(args.start)
    end_date = date.fromisoformat(args.end)

    if start_date > end_date:
        raise SystemExit(f"start ({args.start}) must be <= end ({args.end})")

    rematerialize(
        dataset_version=args.dataset_version,
        start=start_date,
        end=end_date,
        factor_names=factor_names,
        db_path=args.db_path,
    )


if __name__ == "__main__":
    main()
