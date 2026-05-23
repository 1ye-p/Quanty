"""cquant.newsflow.sentiment — Keyword-based financial sentiment scorer.

Returns a score in [-1.0, 1.0] based on the presence of positive and negative
financial keywords in Chinese and English. Returns None when no keywords match.
"""
from __future__ import annotations

_POSITIVE_ZH = [
    "上涨", "涨停", "大涨", "好消息", "利好", "增长", "盈利",
    "突破", "创新高", "加仓", "业绩增长", "超预期", "强劲", "飙升",
]
_NEGATIVE_ZH = [
    "下跌", "跌停", "暴跌", "坏消息", "利空", "下滑", "亏损",
    "业绩下滑", "减仓", "不及预期", "崩盘", "大跌", "萎缩",
]

_POSITIVE_EN = [
    "gain", "rise", "rally", "beat", "strong", "growth", "profit",
    "outperform", "surge", "soar", "record", "high", "earn",
]
_NEGATIVE_EN = [
    "loss", "fall", "drop", "miss", "weak", "decline", "deficit",
    "underperform", "plunge", "crash", "low", "slump", "shrink",
]


def score_sentiment(text: str, language: str = "zh-CN") -> float | None:
    """Score financial sentiment from headline/body text.

    Parameters
    ----------
    text:
        The text to analyze (headline or body).
    language:
        ISO language code. ``"zh-CN"`` or ``"zh"`` for Chinese; anything else English.

    Returns
    -------
    Float in [-1.0, 1.0] or ``None`` if no keywords match.
    Positive = bullish, negative = bearish.
    """
    if not text or not text.strip():
        return None

    text_lower = text.lower()
    is_chinese = language.startswith("zh")

    if is_chinese:
        pos_kws = _POSITIVE_ZH + _POSITIVE_EN
        neg_kws = _NEGATIVE_ZH + _NEGATIVE_EN
    else:
        pos_kws = _POSITIVE_EN
        neg_kws = _NEGATIVE_EN

    pos_count = sum(1 for kw in pos_kws if kw in text or kw in text_lower)
    neg_count = sum(1 for kw in neg_kws if kw in text or kw in text_lower)

    total = pos_count + neg_count
    if total == 0:
        return None

    return (pos_count - neg_count) / total
