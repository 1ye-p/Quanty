"""cquant.core.enums — Stable domain enumerations shared across all modules."""

from enum import Enum, auto


class Market(str, Enum):
    CN = "CN"
    US = "US"
    HK = "HK"
    CRYPTO = "CRYPTO"


class Exchange(str, Enum):
    # China A-share
    SSE = "SSE"    # Shanghai Stock Exchange (上交所)
    SZSE = "SZSE"  # Shenzhen Stock Exchange (深交所)
    # Hong Kong
    HKEX = "HKEX"
    # US
    NYSE = "NYSE"
    NASDAQ = "NASDAQ"
    AMEX = "AMEX"
    # Crypto
    BINANCE = "BINANCE"
    OKX = "OKX"


class AssetClass(str, Enum):
    EQUITY = "equity"
    FUTURES = "futures"
    OPTIONS = "options"
    CRYPTO = "crypto"
    FUND = "fund"
    INDEX = "index"


class AssetStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"        # Trading halt / 停牌
    DELISTED = "delisted"
    ST = "st"                      # Special Treatment (ST)
    STAR_ST = "star_st"            # *ST


class Currency(str, Enum):
    CNY = "CNY"
    USD = "USD"
    HKD = "HKD"
    BTC = "BTC"
    USDT = "USDT"


class Frequency(str, Enum):
    TICK = "tick"
    S1 = "1s"
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"
    MO1 = "1mo"
    Q1 = "1q"
    Y1 = "1y"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class SignalDirection(str, Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class AdjMethod(str, Enum):
    """Price adjustment method for corporate actions."""
    FORWARD = "forward"      # 前复权 — prices adjusted toward latest
    BACKWARD = "backward"    # 后复权 — prices adjusted toward IPO
    NONE = "none"            # Raw unadjusted prices


class RiskDecisionType(str, Enum):
    APPROVED = "approved"
    CLIPPED = "clipped"      # Quantity reduced but order allowed
    REJECTED = "rejected"


class EngineType(str, Enum):
    VECTOR = "vector"
    EVENT = "event"
