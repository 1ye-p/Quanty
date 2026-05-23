"""cquant.riskguard.policies.sector_limit — Sector exposure limit policy."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from cquant.core.enums import RiskDecisionType
from cquant.core.types import OrderIntent, RiskDecision, RiskSnapshot
from cquant.riskguard.models import RiskContext
from cquant.riskguard.policies.base import RiskPolicy

if TYPE_CHECKING:
    from cquant.datahub.catalog import Catalog


class SectorLimitPolicy(RiskPolicy):
    """Enforces a maximum sector concentration constraint.

    Parameters:
        max_sector_pct: Maximum weight for any single sector (default 0.30 = 30%).
        sector_map: Mapping of asset_id to sector name. If None, all assets
            pass through (no sector info available).
    """

    def __init__(
        self,
        max_sector_pct: float = 0.30,
        sector_map: dict[str, str] | None = None,
    ) -> None:
        self._max_pct = max_sector_pct
        self._sector_map = sector_map or {}

    @classmethod
    def from_catalog(
        cls,
        catalog: "Catalog",
        max_sector_pct: float = 0.30,
    ) -> "SectorLimitPolicy":
        """Build a SectorLimitPolicy by loading industry mappings from silver_assets.

        Parameters
        ----------
        catalog:
            Open Catalog connection.
        max_sector_pct:
            Maximum weight per sector (default 30%).
        """
        try:
            df = catalog.query(
                "SELECT asset_id, industry FROM silver_assets WHERE industry IS NOT NULL"
            )
        except Exception:
            df = __import__("polars").DataFrame()

        if df.is_empty():
            sector_map: dict[str, str] = {}
        else:
            sector_map = dict(
                zip(df["asset_id"].to_list(), df["industry"].to_list())
            )

        return cls(max_sector_pct=max_sector_pct, sector_map=sector_map)

    @property
    def name(self) -> str:
        return "sector_limit"

    def evaluate(
        self,
        candidate: OrderIntent,
        snapshot: RiskSnapshot,
        ctx: RiskContext,
        price: float = 0.0,
    ) -> RiskDecision:
        original_qty = candidate.requested_qty

        # Look up sector for the candidate asset
        sector = self._sector_map.get(candidate.asset_id)
        if sector is None:
            # No sector info — approve (cannot evaluate)
            return RiskDecision(
                decision=RiskDecisionType.APPROVED,
                original_qty=original_qty,
                approved_qty=original_qty,
                reasons=[],
                policy_names=[self.name],
            )

        # Current exposure for this sector
        current_exposure = ctx.sector_exposure.get(sector, 0.0)

        # Already at limit — reject
        if current_exposure >= self._max_pct:
            return RiskDecision(
                decision=RiskDecisionType.REJECTED,
                original_qty=original_qty,
                approved_qty=Decimal("0"),
                reasons=[
                    f"Sector '{sector}' exposure {current_exposure:.4f} "
                    f">= limit {self._max_pct:.4f}"
                ],
                policy_names=[self.name],
            )

        # No price available — cannot compute notional; approve as-is
        if price <= 0:
            return RiskDecision(
                decision=RiskDecisionType.APPROVED,
                original_qty=original_qty,
                approved_qty=original_qty,
                reasons=[],
                policy_names=[self.name],
            )

        nav = ctx.portfolio_nav
        if nav <= 0:
            return RiskDecision(
                decision=RiskDecisionType.APPROVED,
                original_qty=original_qty,
                approved_qty=original_qty,
                reasons=[],
                policy_names=[self.name],
            )

        order_notional = original_qty * Decimal(str(price))
        order_pct = float(order_notional / nav)
        projected_exposure = current_exposure + order_pct

        if projected_exposure <= self._max_pct:
            return RiskDecision(
                decision=RiskDecisionType.APPROVED,
                original_qty=original_qty,
                approved_qty=original_qty,
                reasons=[],
                policy_names=[self.name],
            )

        # Clip to stay within the sector limit
        allowed_additional_pct = Decimal(str(self._max_pct)) - Decimal(str(current_exposure))
        allowed_notional = allowed_additional_pct * nav
        max_qty = int(allowed_notional / Decimal(str(price)))

        if max_qty <= 0:
            return RiskDecision(
                decision=RiskDecisionType.REJECTED,
                original_qty=original_qty,
                approved_qty=Decimal("0"),
                reasons=[
                    f"Sector '{sector}' projected exposure {projected_exposure:.4f} "
                    f"exceeds limit {self._max_pct:.4f}"
                ],
                policy_names=[self.name],
            )

        approved_qty = Decimal(str(max_qty))
        return RiskDecision(
            decision=RiskDecisionType.CLIPPED,
            original_qty=original_qty,
            approved_qty=approved_qty,
            reasons=[
                f"Clipped from {original_qty} to {approved_qty} "
                f"(sector '{sector}' limit {self._max_pct:.4f})"
            ],
            policy_names=[self.name],
        )
