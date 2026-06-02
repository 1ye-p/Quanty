"""ST/delist status tracking with data source + runtime derivation."""

from __future__ import annotations

import logging
from datetime import date

from cquant.core.enums import AssetStatus

logger = logging.getLogger(__name__)


class StatusTracker:
    """Tracks asset status (ST, delisted, etc.) with three-tier data strategy."""

    def __init__(self, fetcher=None, cache_table: str = "market_status_cache"):
        self._cache: dict[tuple, str] = {}
        self._fetcher = fetcher
        self._cache_table = cache_table

    def get_status(self, asset_id: str, trade_date: date) -> str | None:
        """Get cached status. Returns None if not cached."""
        key = (asset_id, trade_date, "st")
        return self._cache.get(key)

    def set_status(self, asset_id: str, trade_date: date, status: str, source: str = "derived") -> None:
        """Cache a status value."""
        key = (asset_id, trade_date, "st")
        self._cache[key] = status

    def get_delist_date(self, asset_id: str) -> date | None:
        """Get delist date from cache or data source."""
        key = (asset_id, "delist_date")
        cached = self._cache.get(key)
        if cached:
            return date.fromisoformat(cached) if cached != "none" else None
        if self._fetcher:
            try:
                result = self._fetcher.get_delist_date(asset_id)
                self._cache[key] = result.isoformat() if result else "none"
                return result
            except Exception as e:
                logger.warning("Failed to fetch delist date for %s: %s", asset_id, e)
        self._cache[key] = "none"
        return None

    def fetch_and_cache_status(self, asset_ids: list[str], trade_date: date) -> dict[str, str]:
        """Batch fetch status for multiple assets. Returns {asset_id: status}."""
        results: dict[str, str] = {}
        uncached: list[str] = []
        for aid in asset_ids:
            cached = self.get_status(aid, trade_date)
            if cached:
                results[aid] = cached
            else:
                uncached.append(aid)

        if uncached and self._fetcher:
            try:
                fetched = self._fetcher.fetch_st_status(uncached, trade_date)
                for aid, status in fetched.items():
                    self.set_status(aid, trade_date, status, "tushare")
                    results[aid] = status
            except Exception as e:
                logger.warning("Data fetch failed, falling back to derivation: %s", e)
                for aid in uncached:
                    derived = self._derive_status(aid)
                    self.set_status(aid, trade_date, derived, "derived")
                    results[aid] = derived

        return results

    def _derive_status(self, asset_id: str) -> str:
        """Runtime derivation fallback."""
        return AssetStatus.ACTIVE.value

    @staticmethod
    def derive_st_from_name(name: str) -> AssetStatus:
        """Derive ST status from stock name."""
        if "*" in name and "ST" in name:
            return AssetStatus.STAR_ST
        if "ST" in name:
            return AssetStatus.ST
        return AssetStatus.ACTIVE
