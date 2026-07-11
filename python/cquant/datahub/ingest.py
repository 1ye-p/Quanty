"""cquant.datahub.ingest — Market data ingestion orchestrator.

Coordinates the full pipeline: connector → normalize → DuckDB silver layer.
Single-process, synchronous, designed for daily-bar ingestion.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

import polars as pl

from cquant.core.enums import Frequency, Market
from cquant.core.errors import IngestError
from cquant.datahub.catalog import Catalog
from cquant.datahub.bronze_writer import BronzeWriter
from cquant.datahub.connectors.base import DataConnector, DataSpec, RawBatch
from cquant.datahub.pipelines.silver import SilverNormalizer
from cquant.datahub.quality_scorer import DataQualityScorer

logger = logging.getLogger(__name__)

_SILVER_PRICE_COLS = [
    "asset_id", "trade_date", "open", "high", "low", "close",
    "volume", "amount", "adj_factor", "adj_close", "is_suspended", "source",
]


@dataclass
class IngestionSpec:
    """Specification for a market data ingestion run."""

    market: Market
    symbols: list[str]
    start_date: date
    end_date: date
    frequency: Frequency = Frequency.D1
    dataset_name: str = "daily_bar"


class MarketIngestionOrchestrator:
    """Orchestrate market data fetch → normalize → DuckDB silver write.

    Usage::

        from cquant.core.enums import Market
        from datetime import date

        orchestrator = MarketIngestionOrchestrator(catalog, [TushareConnector()])
        version_id = orchestrator.ingest(IngestionSpec(
            market=Market.CN,
            symbols=["SSE:600036", "SZSE:000001"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        ))
    """

    def __init__(
        self,
        catalog: Catalog,
        connectors: list[DataConnector],
        normalizer: SilverNormalizer | None = None,
    ) -> None:
        self._catalog = catalog
        self._connectors = {c.source_name: c for c in connectors}
        self._market_connectors: dict[Market, DataConnector] = {}
        for c in connectors:
            for m in c.supported_markets:
                self._market_connectors.setdefault(m, c)
        self._normalizer = normalizer or SilverNormalizer()
        self._bronze_writer = BronzeWriter(catalog)
        self._quality_threshold = 0.7

    def ingest(self, spec: IngestionSpec) -> str:
        """Run the full ingestion pipeline and return a dataset_version_id."""
        self._catalog.initialize()

        connector = self._select_connector(spec)
        batches, symbols = self._fetch_batches(connector, spec)
        if not batches:
            raise IngestError(
                f"No data returned for {symbols} ({spec.market.value}). "
                f"Ensure silver_assets is populated (run bootstrap) or provide explicit symbols."
            )

        # Dedup: filter out rows with dates that already exist
        existing_dates = self._get_existing_date_boundaries(symbols)
        if existing_dates:
            original_total = sum(len(b.data) for b in batches)

            for batch in batches:
                if batch.data.is_empty():
                    continue

                # Build filter: keep rows where trade_date > existing max for that asset
                # Use Polars expression for efficiency
                conditions = []
                for asset_id, max_date in existing_dates.items():
                    conditions.append(
                        ~((pl.col("asset_id") == asset_id) & (pl.col("trade_date") <= max_date))
                    )

                if conditions:
                    # Combine with AND: keep row if it passes ALL conditions
                    combined = conditions[0]
                    for c in conditions[1:]:
                        combined = combined & c
                    batch.data = batch.data.filter(combined)

            # Remove empty batches
            batches = [b for b in batches if not b.data.is_empty()]

            new_total = sum(len(b.data) for b in batches)
            skipped = original_total - new_total
            if skipped > 0:
                logger.info("Dedup: skipped %d rows already in silver_prices_1d", skipped)

            if not batches:
                logger.info("All data already exists — nothing to ingest")
                # Return a sentinel indicating no new data was ingested
                return f"dedup:{spec.dataset_name}:{spec.start_date}"

        # Write raw batches to Bronze layer (data provenance)
        for batch in batches:
            self._bronze_writer.write(
                source=connector.source_name,
                dataset=spec.dataset_name,
                data=batch.data,
                fetch_start=spec.start_date,
                fetch_end=spec.end_date,
            )

        frame = self._normalize_batches(batches)
        self._validate_schema(frame)

        row_count = len(frame)
        asset_count = frame["asset_id"].n_unique()
        ingestion_id = self._write_prices(frame)

        # Quality gate
        try:
            scorer = DataQualityScorer(self._catalog)
            report = scorer.score(
                "silver_prices_1d",
                spec.start_date.isoformat(),
                spec.end_date.isoformat(),
            )
            if report.overall_score < self._quality_threshold:
                logger.warning(
                    "Data quality gate: score=%.3f below threshold %.1f — "
                    "completeness=%.3f consistency=%.3f freshness=%.3f",
                    report.overall_score, self._quality_threshold,
                    report.completeness.score, report.consistency.score, report.freshness.score,
                )
        except Exception as exc:
            logger.warning("Data quality scoring failed (non-blocking): %s", exc)

        version_id = self._register_dataset_version(frame, spec, connector.source_name)

        logger.info(
            "Ingested %d rows, %d assets → version %s",
            row_count, asset_count, version_id,
        )
        return version_id

    def _get_existing_date_boundaries(self, asset_ids: list[str]) -> dict[str, str]:
        """Get the latest trade_date for each asset in silver_prices_1d.

        Returns:
            Dict mapping asset_id to its latest trade_date (YYYY-MM-DD string).
        """
        if not asset_ids:
            return {}

        # Build parameterized query
        placeholders = ", ".join(["?" for _ in asset_ids])
        df = self._catalog.query(
            f"SELECT asset_id, MAX(trade_date) as max_date "
            f"FROM silver_prices_1d "
            f"WHERE asset_id IN ({placeholders}) "
            f"GROUP BY asset_id",
            asset_ids,
        )
        if df.is_empty():
            return {}
        return {row["asset_id"]: str(row["max_date"]) for row in df.to_dicts()}

    def _select_connector(self, spec: IngestionSpec) -> DataConnector:
        connector = self._market_connectors.get(spec.market)
        if connector is None:
            available = [c.source_name for c in self._connectors.values()]
            raise IngestError(
                f"No connector for market {spec.market.value}. Available: {available}"
            )
        return connector

    def _resolve_symbols(self, spec: IngestionSpec) -> list[str]:
        """Resolve an empty symbols list to all known assets from the catalog."""
        if spec.symbols:
            return spec.symbols

        try:
            market = spec.market.value if hasattr(spec.market, 'value') else str(spec.market)
            df = self._catalog.query(
                "SELECT asset_id FROM silver_assets WHERE status = 'active' AND market = ? ORDER BY asset_id",
                [market],
            )
        except Exception as exc:
            logger.warning("Failed to resolve symbols from silver_assets: %s", exc)
            return []

        if df.is_empty():
            logger.warning("No active assets found in silver_assets; cannot ingest")
            return []

        symbols = df["asset_id"].to_list()
        logger.info("Resolved %d symbols from silver_assets for ingestion", len(symbols))
        return symbols

    def _fetch_batches(
        self, connector: DataConnector, spec: IngestionSpec
    ) -> tuple[list[RawBatch], list[str]]:
        """Fetch data batches. Returns (batches, resolved_symbols)."""
        symbols = self._resolve_symbols(spec)
        if not symbols:
            return [], []

        data_spec = DataSpec(
            symbols=symbols,
            start_date=spec.start_date,
            end_date=spec.end_date,
            frequency=spec.frequency,
            market=spec.market,
        )
        batches = list(connector.fetch(data_spec))
        logger.info("Fetched %d batch(es) from %s", len(batches), connector.source_name)
        return batches, symbols

    def _normalize_batches(self, batches: list[RawBatch]) -> pl.DataFrame:
        frames = [self._normalizer.normalize(b) for b in batches]
        combined = pl.concat(frames, how="vertical_relaxed")
        # Deduplicate by (asset_id, trade_date), keep last
        if "asset_id" in combined.columns and "trade_date" in combined.columns:
            combined = combined.unique(subset=["asset_id", "trade_date"], keep="last")
        return combined.sort(["asset_id", "trade_date"])

    def _validate_schema(self, frame: pl.DataFrame) -> None:
        required = {"asset_id", "trade_date", "open", "high", "low", "close", "volume"}
        missing = required - set(frame.columns)
        if missing:
            raise IngestError(f"Normalized data missing required columns: {missing}")
        if frame.is_empty():
            raise IngestError("Normalized data is empty after validation")

    def _write_prices(self, frame: pl.DataFrame) -> str:
        """Write normalized data to silver_prices_1d via DuckDB stage table."""
        import uuid

        ingestion_id = str(uuid.uuid4())
        cols_to_write = [c for c in _SILVER_PRICE_COLS if c in frame.columns]
        write_frame = frame.select(cols_to_write).with_columns(
            pl.lit(ingestion_id).alias("ingestion_id")
        )

        all_cols = cols_to_write + ["ingestion_id"]
        rows = write_frame.rows()
        n_cols = len(all_cols)
        assert not rows or len(rows[0]) == n_cols, (
            f"Column mismatch: {len(rows[0])} values vs {n_cols} placeholders"
        )
        try:
            self._catalog.upsert(
                "silver_prices_1d",
                all_cols,
                rows,
                ["asset_id", "trade_date"],
            )
        except Exception as exc:
            raise IngestError(f"Failed to write silver_prices_1d: {exc}") from exc

        return ingestion_id

    def ingest_bulk_tdx(
        self,
        db_path: str,
        start_date: date,
        end_date: date,
        chunk_days: int = 365,
    ) -> str:
        """Bulk ingest ALL symbols from a TDX DuckDB file, chunked by date.

        This is the recommended path for initial TDX data loading (21M+ rows).
        Processes one year at a time to avoid memory exhaustion.
        """
        from cquant.datahub.connectors.tdx_connector import TdxDuckDBConnector

        self._catalog.initialize()
        connector = TdxDuckDBConnector(db_path)

        total_rows = 0
        total_assets: set[str] = set()
        last_version_id = ""

        for batch in connector.fetch_all(start_date, end_date, chunk_days):
            # Write raw batch to Bronze layer (data provenance)
            self._bronze_writer.write(
                source="tdx",
                dataset="daily_bar",
                data=batch.data,
                fetch_start=start_date,
                fetch_end=end_date,
            )

            frame = self._normalizer.normalize(batch)
            if frame.is_empty():
                continue
            self._validate_schema(frame)
            total_rows += len(frame)
            total_assets.update(frame["asset_id"].unique().to_list())
            self._write_prices(frame)
            logger.info("Chunk ingested: %d rows, running total: %d", len(frame), total_rows)

        if total_rows == 0:
            raise IngestError("No data ingested from TDX")

        # Quality gate (bulk)
        try:
            scorer = DataQualityScorer(self._catalog)
            report = scorer.score(
                "silver_prices_1d",
                start_date.isoformat(),
                end_date.isoformat(),
            )
            if report.overall_score < self._quality_threshold:
                logger.warning(
                    "Data quality gate (bulk TDX): score=%.3f below threshold %.1f — "
                    "completeness=%.3f consistency=%.3f freshness=%.3f",
                    report.overall_score, self._quality_threshold,
                    report.completeness.score, report.consistency.score, report.freshness.score,
                )
        except Exception as exc:
            logger.warning("Data quality scoring failed (non-blocking): %s", exc)

        last_version_id = self._catalog.register_dataset(
            dataset_name="daily_bar",
            frequency="1d",
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            asset_count=len(total_assets),
            row_count=total_rows,
            storage_uri="duckdb:silver_prices_1d",
            source="tdx",
        )
        logger.info(
            "Bulk TDX ingestion complete: %d rows, %d assets → version %s",
            total_rows, len(total_assets), last_version_id,
        )
        return last_version_id

    def _register_dataset_version(
        self, frame: pl.DataFrame, spec: IngestionSpec, source: str
    ) -> str:
        return self._catalog.register_dataset(
            dataset_name=spec.dataset_name,
            frequency=spec.frequency.value,
            start_date=spec.start_date.isoformat(),
            end_date=spec.end_date.isoformat(),
            asset_count=frame["asset_id"].n_unique(),
            row_count=len(frame),
            storage_uri=f"duckdb:silver_prices_1d",
            source=source,
        )
