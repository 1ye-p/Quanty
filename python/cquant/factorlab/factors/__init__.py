"""Built-in factors: momentum, volatility, turnover, technical, value, quality, growth, size."""

from cquant.factorlab.factors.momentum import (
    Return1d,
    Return5d,
    Return20d,
    Return60d,
    Return120d,
    Return240d,
    Momentum12_1,
)
from cquant.factorlab.factors.volatility import (
    Vol20d,
    Vol60d,
    Vol120d,
    DownsideVol20d,
    MaxDrawdown20d,
)
from cquant.factorlab.factors.turnover import (
    TurnoverRate20d,
    VolumeRatio5d,
    AmountRatio5d,
)
from cquant.factorlab.factors.technical import (
    ZscoreClose60d,
    MA20dRatio,
    RSI14d,
    BollingerBandWidth20d,
    PriceHigh20dRatio,
)
from cquant.factorlab.factors.value import (
    PETTM,
    PB,
    DividendYield,
)
from cquant.factorlab.factors.quality import (
    ROE,
    ROA,
    GrossMargin,
)
from cquant.factorlab.factors.growth import (
    RevenueGrowth,
    EarningsGrowth,
)
from cquant.factorlab.factors.size import (
    MarketCap,
    LogMarketCap,
)

BUILTIN_FACTORS = [
    # Momentum
    Return1d(), Return5d(), Return20d(), Return60d(), Return120d(), Return240d(),
    Momentum12_1(),
    # Volatility
    Vol20d(), Vol60d(), Vol120d(),
    DownsideVol20d(), MaxDrawdown20d(),
    # Turnover
    TurnoverRate20d(), VolumeRatio5d(), AmountRatio5d(),
    # Technical
    ZscoreClose60d(), MA20dRatio(), RSI14d(),
    BollingerBandWidth20d(), PriceHigh20dRatio(),
    # Value
    PETTM(), PB(), DividendYield(),
    # Quality
    ROE(), ROA(), GrossMargin(),
    # Growth
    RevenueGrowth(), EarningsGrowth(),
    # Size
    MarketCap(), LogMarketCap(),
]

__all__ = [
    "Return1d", "Return5d", "Return20d", "Return60d", "Return120d", "Return240d",
    "Momentum12_1",
    "Vol20d", "Vol60d", "Vol120d", "DownsideVol20d", "MaxDrawdown20d",
    "TurnoverRate20d", "VolumeRatio5d", "AmountRatio5d",
    "ZscoreClose60d", "MA20dRatio", "RSI14d", "BollingerBandWidth20d", "PriceHigh20dRatio",
    "PETTM", "PB", "DividendYield",
    "ROE", "ROA", "GrossMargin",
    "RevenueGrowth", "EarningsGrowth",
    "MarketCap", "LogMarketCap",
    "BUILTIN_FACTORS",
]
