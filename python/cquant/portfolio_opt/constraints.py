"""cquant.portfolio_opt.constraints — Portfolio optimization constraint configuration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SectorLimit:
    """Weight limit for a sector or group."""

    min_weight: float = 0.0
    max_weight: float = 1.0

    def __post_init__(self) -> None:
        if self.min_weight < 0:
            raise ValueError(f"min_weight must be >= 0, got {self.min_weight}")
        if self.max_weight > 1:
            raise ValueError(f"max_weight must be <= 1, got {self.max_weight}")
        if self.min_weight > self.max_weight:
            raise ValueError(
                f"min_weight ({self.min_weight}) cannot exceed max_weight ({self.max_weight})"
            )


@dataclass
class FactorExposureLimit:
    """Exposure limit for a risk factor."""

    min_exposure: float = -1.0
    max_exposure: float = 1.0

    def __post_init__(self) -> None:
        if self.min_exposure > self.max_exposure:
            raise ValueError(
                f"min_exposure ({self.min_exposure}) cannot exceed "
                f"max_exposure ({self.max_exposure})"
            )


@dataclass
class ConstraintConfig:
    """Complete constraint configuration for portfolio optimization.

    Covers:
    - Weight bounds (long-only flag, global and per-asset min/max)
    - Turnover control (max turnover, penalty, current weights)
    - Target return
    - Sector / group exposure limits
    - Factor exposure limits
    - Tracking error budget vs. benchmark
    - Asset exclusion (by ID, ST flag, suspended flag)
    """

    # ── Weight bounds ─────────────────────────────────────────────────────────
    long_only: bool = True
    max_weight: float = 1.0
    min_weight: float = 0.0
    min_weights: dict[str, float] = field(default_factory=dict)  # per-asset lower
    max_weights: dict[str, float] = field(default_factory=dict)  # per-asset upper

    # ── Turnover ──────────────────────────────────────────────────────────────
    max_turnover: float | None = None
    turnover_penalty: float = 0.0
    current_weights: dict[str, float] = field(default_factory=dict)

    # ── Target return ─────────────────────────────────────────────────────────
    target_return: float | None = None

    # ── Sector / group limits ─────────────────────────────────────────────────
    # asset_id -> sector label; sector_label -> SectorLimit
    sector_map: dict[str, str] = field(default_factory=dict)
    sector_limits: dict[str, SectorLimit] = field(default_factory=dict)

    # ── Factor exposure limits ────────────────────────────────────────────────
    # asset_id -> {factor_name: loading}
    factor_loadings: dict[str, dict[str, float]] = field(default_factory=dict)
    factor_limits: dict[str, FactorExposureLimit] = field(default_factory=dict)

    # ── Tracking error budget ─────────────────────────────────────────────────
    max_tracking_error: float | None = None  # annualised TE limit
    benchmark_weights: dict[str, float] = field(default_factory=dict)

    # ── Asset exclusion ───────────────────────────────────────────────────────
    exclude_assets: set[str] = field(default_factory=set)
    exclude_st: bool = False  # exclude ST / *ST stocks
    st_assets: set[str] = field(default_factory=set)  # asset_ids flagged ST
    exclude_suspended: bool = False  # exclude suspended stocks
    suspended_assets: set[str] = field(default_factory=set)

    # ── Validation ────────────────────────────────────────────────────────────

    def validate(self) -> list[str]:
        """Validate the constraint configuration.

        Returns a list of error strings.  An empty list means the config is valid.
        """
        errors: list[str] = []

        # Weight bounds
        if self.max_weight <= 0 or self.max_weight > 1:
            errors.append(f"max_weight must be in (0, 1], got {self.max_weight}")
        if self.min_weight < 0 or self.min_weight > 1:
            errors.append(f"min_weight must be in [0, 1], got {self.min_weight}")
        if self.min_weight > self.max_weight:
            errors.append(
                f"min_weight ({self.min_weight}) cannot exceed max_weight ({self.max_weight})"
            )

        for asset, lo in self.min_weights.items():
            if lo < 0 or lo > 1:
                errors.append(f"min_weights[{asset!r}] must be in [0, 1], got {lo}")
        for asset, hi in self.max_weights.items():
            if hi < 0 or hi > 1:
                errors.append(f"max_weights[{asset!r}] must be in [0, 1], got {hi}")
        # Per-asset pair check
        for asset in set(self.min_weights) & set(self.max_weights):
            if self.min_weights[asset] > self.max_weights[asset]:
                errors.append(
                    f"min_weights[{asset!r}] ({self.min_weights[asset]}) > "
                    f"max_weights[{asset!r}] ({self.max_weights[asset]})"
                )

        # Turnover
        if self.max_turnover is not None and self.max_turnover < 0:
            errors.append(f"max_turnover must be >= 0, got {self.max_turnover}")
        if self.turnover_penalty < 0:
            errors.append(f"turnover_penalty must be >= 0, got {self.turnover_penalty}")

        # Sector limits
        for label, lim in self.sector_limits.items():
            try:
                # SectorLimit validates itself in __post_init__
                SectorLimit(min_weight=lim.min_weight, max_weight=lim.max_weight)
            except ValueError as exc:
                errors.append(f"sector_limits[{label!r}]: {exc}")

        # Factor limits
        for fname, lim in self.factor_limits.items():
            try:
                FactorExposureLimit(
                    min_exposure=lim.min_exposure, max_exposure=lim.max_exposure
                )
            except ValueError as exc:
                errors.append(f"factor_limits[{fname!r}]: {exc}")

        # Tracking error
        if self.max_tracking_error is not None and self.max_tracking_error < 0:
            errors.append(
                f"max_tracking_error must be >= 0, got {self.max_tracking_error}"
            )

        return errors

    def get_excluded_assets(self) -> set[str]:
        """Return the full set of asset IDs that should be excluded."""
        excluded = set(self.exclude_assets)
        if self.exclude_st:
            excluded |= self.st_assets
        if self.exclude_suspended:
            excluded |= self.suspended_assets
        return excluded
