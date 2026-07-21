"""Factor templates — preset portfolio factor configurations.

Provides 4 commonly-used factor template presets for quick strategy creation:
- value:  价值型 (low PE/PB + high ROE)
- growth: 成长型 (high growth + momentum)
- momentum: 动量型 (strong momentum + low volatility)
- low_vol:  低波动型 (low volatility + positive returns)
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass(frozen=True)
class FactorTemplate:
    """A reusable factor-weight configuration for multi-factor strategies."""

    template_id: str
    name: str
    description: str
    factor_weights: dict[str, float]
    top_n: int = 10
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Preset templates ──────────────────────────────────────────────────────────

PRESET_TEMPLATES: list[FactorTemplate] = [
    FactorTemplate(
        template_id="value",
        name="价值型",
        description="低估值 + 高盈利能力，适合长期持有。核心因子：PE、PB 越低越好，ROE 越高越好。",
        factor_weights={
            "pe_ttm": -0.30,
            "pb": -0.30,
            "roe_ttm": 0.25,
            "div_yield": 0.15,
        },
        top_n=10,
        tags=["价值", "基本面", "长期"],
    ),
    FactorTemplate(
        template_id="growth",
        name="成长型",
        description="高增长 + 动量驱动，适合趋势行情。核心因子：营收增速、利润增速、短期动量。",
        factor_weights={
            "revenue_yoy": 0.30,
            "profit_yoy": 0.25,
            "ret_20d": 0.25,
            "turnover_20d": 0.20,
        },
        top_n=10,
        tags=["成长", "动量", "趋势"],
    ),
    FactorTemplate(
        template_id="momentum",
        name="动量型",
        description="强动量 + 低波动，适合中期波段。核心因子：中期收益率、波动率取反。",
        factor_weights={
            "ret_60d": 0.40,
            "ret_20d": 0.25,
            "vol_20d": -0.20,
            "turnover_20d": 0.15,
        },
        top_n=10,
        tags=["动量", "波段", "中频"],
    ),
    FactorTemplate(
        template_id="low_vol",
        name="低波动型",
        description="低波动 + 正收益，适合稳健配置。核心因子：波动率越低越好，兼顾正收益。",
        factor_weights={
            "vol_20d": -0.40,
            "vol_60d": -0.20,
            "ret_20d": 0.25,
            "amount_20d": 0.15,
        },
        top_n=10,
        tags=["低波", "稳健", "防守"],
    ),
]

_PRESET_MAP: dict[str, FactorTemplate] = {t.template_id: t for t in PRESET_TEMPLATES}


def list_templates() -> list[dict]:
    """Return all preset templates as dicts."""
    return [t.to_dict() for t in PRESET_TEMPLATES]


def get_template(template_id: str) -> dict | None:
    """Return a single preset template by id, or None."""
    tpl = _PRESET_MAP.get(template_id)
    return tpl.to_dict() if tpl else None
