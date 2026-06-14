"""Alpha158 / Alpha360 因子结构化描述数据。

每条记录包含 7 个字段：
    factor_name       — 因子唯一标识（与代码中的 .name 对应）
    category          — 分类标签
    display_name      — 中文显示名
    description       — 简要说明
    formula           — 数学公式
    economic_meaning  — 经济含义
    use_case          — 典型使用场景
"""
from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# KBAR 因子（9 个）
# ─────────────────────────────────────────────────────────────────────────────
KBAR_DESCRIPTIONS: list[dict] = [
    {
        "factor_name": "KMID",
        "category": "kbar",
        "display_name": "K线中间位置",
        "description": "收盘价相对开盘价的涨跌幅",
        "formula": "(close - open) / open",
        "economic_meaning": "衡量单日多空力量对比，正值表示多方占优，负值表示空方占优",
        "use_case": "日内动量信号、K线形态识别",
    },
    {
        "factor_name": "KLEN",
        "category": "kbar",
        "display_name": "K线长度",
        "description": "日内振幅（最高价与最低价之差相对开盘价）",
        "formula": "(high - low) / open",
        "economic_meaning": "反映日内价格波动剧烈程度，值越大说明市场分歧越大",
        "use_case": "波动率过滤、异常波动检测",
    },
    {
        "factor_name": "KMID2",
        "category": "kbar",
        "display_name": "K线中间位置(归一化)",
        "description": "收盘价相对开盘价的位置，归一化到振幅",
        "formula": "(close - open) / (high - low + eps)",
        "economic_meaning": "在当日振幅范围内，收盘价所处的相对位置，[-1, 1] 区间",
        "use_case": "标准化的日内方向信号，可跨股票比较",
    },
    {
        "factor_name": "KUP",
        "category": "kbar",
        "display_name": "上影线长度",
        "description": "上影线相对开盘价的长度",
        "formula": "(high - max(open, close)) / open",
        "economic_meaning": "上方抛压强度，上影线越长说明高位卖压越重",
        "use_case": "阻力位分析、顶部形态识别",
    },
    {
        "factor_name": "KUP2",
        "category": "kbar",
        "display_name": "上影线长度(归一化)",
        "description": "上影线长度归一化到振幅",
        "formula": "(high - max(open, close)) / (high - low + eps)",
        "economic_meaning": "上影线占当日振幅的比例，标准化后可跨股票比较",
        "use_case": "标准化的抛压信号",
    },
    {
        "factor_name": "KLOW",
        "category": "kbar",
        "display_name": "下影线长度",
        "description": "下影线相对开盘价的长度",
        "formula": "(min(open, close) - low) / open",
        "economic_meaning": "下方支撑强度，下影线越长说明低位买盘越强",
        "use_case": "支撑位分析、底部形态识别",
    },
    {
        "factor_name": "KLOW2",
        "category": "kbar",
        "display_name": "下影线长度(归一化)",
        "description": "下影线长度归一化到振幅",
        "formula": "(min(open, close) - low) / (high - low + eps)",
        "economic_meaning": "下影线占当日振幅的比例，标准化后可跨股票比较",
        "use_case": "标准化的支撑信号",
    },
    {
        "factor_name": "KSFT",
        "category": "kbar",
        "display_name": "K线偏移量",
        "description": "收盘价相对日内中点的偏移",
        "formula": "(2 * close - high - low) / open",
        "economic_meaning": "正值表示收盘偏高（强势），负值表示收盘偏低（弱势）",
        "use_case": "日内强弱判断",
    },
    {
        "factor_name": "KSFT2",
        "category": "kbar",
        "display_name": "K线偏移量(归一化)",
        "description": "K线偏移量归一化到振幅",
        "formula": "(2 * close - high - low) / (high - low + eps)",
        "economic_meaning": "标准化的收盘偏移信号",
        "use_case": "标准化的日内强弱信号，可跨股票比较",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# Rolling 因子模板 — ROC / MA / STD / MAX / MIN（窗口 5/10/20/30）
# ─────────────────────────────────────────────────────────────────────────────
_ROC_TEMPLATE = {
    "category": "rolling_roc",
    "display_name_tpl": "{n}日变动率",
    "description_tpl": "{n}日前收盘价相对当前价的比值",
    "formula_tpl": "close.shift({n}) / close",
    "economic_meaning": "衡量{n}日价格变动，值>1表示{n}天前价格更高（下跌趋势），<1表示上涨",
    "use_case": "动量反转信号、趋势判断",
}

_MA_TEMPLATE = {
    "category": "rolling_ma",
    "display_name_tpl": "{n}日均线比值",
    "description_tpl": "{n}日收盘价均值相对当前价",
    "formula_tpl": "rolling_mean(close, {n}) / close",
    "economic_meaning": "均值回归信号，>1表示当前价低于均线（可能被低估），<1表示高于均线",
    "use_case": "均值回归策略、趋势过滤",
}

_STD_TEMPLATE = {
    "category": "rolling_std",
    "display_name_tpl": "{n}日波动率",
    "description_tpl": "{n}日收盘价标准差相对当前价",
    "formula_tpl": "rolling_std(close, {n}) / close",
    "economic_meaning": "衡量{n}日价格波动率，值越大波动越剧烈",
    "use_case": "波动率择时、风险控制",
}

_MAX_TEMPLATE = {
    "category": "rolling_max",
    "display_name_tpl": "{n}日最高价比",
    "description_tpl": "{n}日内最高价相对当前价",
    "formula_tpl": "rolling_max(high, {n}) / close",
    "economic_meaning": "衡量当前价格距离{n}日高点的位置，值越大说明离高点越远",
    "use_case": "突破信号、阻力位判断",
}

_MIN_TEMPLATE = {
    "category": "rolling_min",
    "display_name_tpl": "{n}日最低价比",
    "description_tpl": "{n}日内最低价相对当前价",
    "formula_tpl": "rolling_min(low, {n}) / close",
    "economic_meaning": "衡量当前价格距离{n}日低点的位置，值越小说明离低点越近",
    "use_case": "支撑位判断、抄底信号",
}


def _expand_rolling(template: dict, windows: list[int]) -> list[dict]:
    """根据模板和窗口列表展开为具体因子描述。"""
    prefix = template["category"].split("_")[-1].upper()  # ROC, MA, STD, MAX, MIN
    result = []
    for n in windows:
        result.append({
            "factor_name": f"{prefix}{n}",
            "category": template["category"],
            "display_name": template["display_name_tpl"].format(n=n),
            "description": template["description_tpl"].format(n=n),
            "formula": template["formula_tpl"].format(n=n),
            "economic_meaning": template["economic_meaning"].format(n=n),
            "use_case": template["use_case"],
        })
    return result


_ROLLING_WINDOWS = [5, 10, 20, 30, 60]

ROLLING_DESCRIPTIONS: list[dict] = (
    _expand_rolling(_ROC_TEMPLATE, _ROLLING_WINDOWS)
    + _expand_rolling(_MA_TEMPLATE, _ROLLING_WINDOWS)
    + _expand_rolling(_STD_TEMPLATE, _ROLLING_WINDOWS)
    + _expand_rolling(_MAX_TEMPLATE, _ROLLING_WINDOWS)
    + _expand_rolling(_MIN_TEMPLATE, _ROLLING_WINDOWS)
)

# ─────────────────────────────────────────────────────────────────────────────
# BETA / RSQR / RESI — 滚动线性回归因子
# ─────────────────────────────────────────────────────────────────────────────
_REG_TEMPLATE: dict[str, dict] = {
    "BETA": {
        "category": "regression",
        "display_name_tpl": "{n}日回归斜率",
        "description_tpl": "{n}日滚动线性回归斜率（close 对时间的 OLS）",
        "formula_tpl": "OLS_slope(close, time_index, window={n})",
        "economic_meaning": "价格趋势强度，正值表示上升趋势，负值表示下降趋势，绝对值越大趋势越强",
        "use_case": "趋势跟踪、动量策略",
    },
    "RSQR": {
        "category": "regression",
        "display_name_tpl": "{n}日回归R²",
        "description_tpl": "{n}日滚动线性回归决定系数",
        "formula_tpl": "OLS_R²(close, time_index, window={n})",
        "economic_meaning": "趋势的可信度，越接近1说明价格走势越接近线性趋势",
        "use_case": "趋势质量过滤、剔除震荡行情",
    },
    "RESI": {
        "category": "regression",
        "display_name_tpl": "{n}日回归残差",
        "description_tpl": "{n}日滚动线性回归末期残差",
        "formula_tpl": "close[-1] - OLS_predicted[-1], window={n}",
        "economic_meaning": "价格偏离趋势线的程度，正残差表示高于趋势线（短期超买），负残差表示低于趋势线（短期超卖）",
        "use_case": "均值回归信号、趋势偏离交易",
    },
}

_REG_WINDOWS = [5, 10, 20, 30, 60]

REGRESSION_DESCRIPTIONS: list[dict] = []
for prefix, tpl in _REG_TEMPLATE.items():
    for n in _REG_WINDOWS:
        REGRESSION_DESCRIPTIONS.append({
            "factor_name": f"{prefix}{n}",
            "category": tpl["category"],
            "display_name": tpl["display_name_tpl"].format(n=n),
            "description": tpl["description_tpl"].format(n=n),
            "formula": tpl["formula_tpl"].format(n=n),
            "economic_meaning": tpl["economic_meaning"],
            "use_case": tpl["use_case"],
        })

# ─────────────────────────────────────────────────────────────────────────────
# QTLU / QTLD / RANK — 分位数与排名因子
# ─────────────────────────────────────────────────────────────────────────────
_QTL_TEMPLATE: dict[str, dict] = {
    "QTLU": {
        "category": "quantile",
        "display_name_tpl": "{n}日80分位比",
        "description_tpl": "{n}日滚动80%分位数相对当前价",
        "formula_tpl": "rolling_quantile(close, 0.8, {n}) / close",
        "economic_meaning": "当前价格在{n}日高位区间的相对位置，>1表示当前价低于80分位",
        "use_case": "高位阻力参考、突破确认",
    },
    "QTLD": {
        "category": "quantile",
        "display_name_tpl": "{n}日20分位比",
        "description_tpl": "{n}日滚动20%分位数相对当前价",
        "formula_tpl": "rolling_quantile(close, 0.2, {n}) / close",
        "economic_meaning": "当前价格在{n}日低位区间的相对位置，<1表示当前价低于20分位",
        "use_case": "低位支撑参考、抄底信号",
    },
}

_QTL_WINDOWS = [5, 10, 20, 30, 60]

QUANTILE_DESCRIPTIONS: list[dict] = []
for prefix, tpl in _QTL_TEMPLATE.items():
    for n in _QTL_WINDOWS:
        QUANTILE_DESCRIPTIONS.append({
            "factor_name": f"{prefix}{n}",
            "category": tpl["category"],
            "display_name": tpl["display_name_tpl"].format(n=n),
            "description": tpl["description_tpl"].format(n=n),
            "formula": tpl["formula_tpl"].format(n=n),
            "economic_meaning": tpl["economic_meaning"],
            "use_case": tpl["use_case"],
        })

_RANK_DESCRIPTIONS: list[dict] = []
for n in _QTL_WINDOWS:
    _RANK_DESCRIPTIONS.append({
        "factor_name": f"RANK{n}",
        "category": "quantile",
        "display_name": f"{n}日排名百分位",
        "description": f"当前收盘价在{n}日滚动窗口中的排名百分位",
        "formula": f"count(close_j < close_i in window={n}) / {n}",
        "economic_meaning": f"值在[0,1]之间，1表示当前价是{n}日最高，0表示{n}日最低",
        "use_case": "突破信号、相对强弱判断",
    })

QUANTILE_DESCRIPTIONS.extend(_RANK_DESCRIPTIONS)

# ─────────────────────────────────────────────────────────────────────────────
# IMAX / IMIN / IMXD — 极值位置因子
# ─────────────────────────────────────────────────────────────────────────────
_EXTREMA_TEMPLATE: dict[str, dict] = {
    "IMAX": {
        "category": "extrema",
        "display_name_tpl": "{n}日距最高价天数",
        "description_tpl": "距{n}日内最高价的天数（0=今天就是最高价）",
        "formula_tpl": "argmax(high[-{n}:]) from end, window={n}",
        "economic_meaning": "值越小说明近期刚创新高（动量强），值越大说明高点已远（可能回落）",
        "use_case": "新高信号、动量持续性判断",
    },
    "IMIN": {
        "category": "extrema",
        "display_name_tpl": "{n}日距最低价天数",
        "description_tpl": "距{n}日内最低价的天数（0=今天就是最低价）",
        "formula_tpl": "argmin(low[-{n}:]) from end, window={n}",
        "economic_meaning": "值越小说明近期刚创新低（可能超卖），值越大说明低点已远（可能反弹）",
        "use_case": "新低信号、超卖判断",
    },
    "IMXD": {
        "category": "extrema",
        "display_name_tpl": "{n}日极值位置差",
        "description_tpl": "距最高价天数 - 距最低价天数（{n}日窗口）",
        "formula_tpl": "IMAX{n} - IMIN{n}",
        "economic_meaning": "正值表示高点比低点更近（近期偏强），负值表示低点更近（近期偏弱）",
        "use_case": "强弱转换信号",
    },
}

_EXTREMA_WINDOWS = [5, 10, 20, 30, 60]

EXTREMA_DESCRIPTIONS: list[dict] = []
for prefix, tpl in _EXTREMA_TEMPLATE.items():
    for n in _EXTREMA_WINDOWS:
        EXTREMA_DESCRIPTIONS.append({
            "factor_name": f"{prefix}{n}",
            "category": tpl["category"],
            "display_name": tpl["display_name_tpl"].format(n=n),
            "description": tpl["description_tpl"].format(n=n),
            "formula": tpl["formula_tpl"].format(n=n),
            "economic_meaning": tpl["economic_meaning"],
            "use_case": tpl["use_case"],
        })

# ─────────────────────────────────────────────────────────────────────────────
# CORR / CORD — 相关性因子
# ─────────────────────────────────────────────────────────────────────────────
_CORR_TEMPLATE: dict[str, dict] = {
    "CORR": {
        "category": "correlation",
        "display_name_tpl": "{n}日量价相关系数",
        "description_tpl": "{n}日滚动 close-volume Pearson 相关系数",
        "formula_tpl": "rolling_corr(close, volume, window={n})",
        "economic_meaning": "量价配合度，正值表示价涨量增（健康上涨），负值表示量价背离（趋势可能反转）",
        "use_case": "量价分析、趋势确认",
    },
    "CORD": {
        "category": "correlation",
        "display_name_tpl": "{n}日相关系数变化率",
        "description_tpl": "{n}日 CORR 的变化率",
        "formula_tpl": "CORR{n}(t) / CORR{n}(t-1) - 1",
        "economic_meaning": "量价关系的变化速度，急剧变化可能预示趋势转折",
        "use_case": "趋势转折预警",
    },
}

_CORR_WINDOWS = [5, 10, 20, 30, 60]

CORRELATION_DESCRIPTIONS: list[dict] = []
for prefix, tpl in _CORR_TEMPLATE.items():
    for n in _CORR_WINDOWS:
        CORRELATION_DESCRIPTIONS.append({
            "factor_name": f"{prefix}{n}",
            "category": tpl["category"],
            "display_name": tpl["display_name_tpl"].format(n=n),
            "description": tpl["description_tpl"].format(n=n),
            "formula": tpl["formula_tpl"].format(n=n),
            "economic_meaning": tpl["economic_meaning"],
            "use_case": tpl["use_case"],
        })

# ─────────────────────────────────────────────────────────────────────────────
# CNTP / CNTN / CNTD — 涨跌天数统计因子
# ─────────────────────────────────────────────────────────────────────────────
_CNT_TEMPLATE: dict[str, dict] = {
    "CNTP": {
        "category": "counting",
        "display_name_tpl": "{n}日上涨天数比例",
        "description_tpl": "{n}日内上涨天数占比",
        "formula_tpl": "count(close > prev_close, window={n}) / {n}",
        "economic_meaning": "上涨频率，值越高说明近期涨多跌少（趋势向好）",
        "use_case": "趋势持续性判断、动量过滤",
    },
    "CNTN": {
        "category": "counting",
        "display_name_tpl": "{n}日下跌天数比例",
        "description_tpl": "{n}日内下跌天数占比",
        "formula_tpl": "count(close < prev_close, window={n}) / {n}",
        "economic_meaning": "下跌频率，值越高说明近期跌多涨少（趋势向淡）",
        "use_case": "弱势识别、止损信号",
    },
    "CNTD": {
        "category": "counting",
        "display_name_tpl": "{n}日涨跌天数差",
        "description_tpl": "{n}日内上涨天数占比 - 下跌天数占比",
        "formula_tpl": "CNTP{n} - CNTN{n}",
        "economic_meaning": "综合涨跌频率，正值表示涨多跌少，负值表示跌多涨少",
        "use_case": "趋势强度综合指标",
    },
}

_CNT_WINDOWS = [5, 10, 20, 30, 60]

COUNTING_DESCRIPTIONS: list[dict] = []
for prefix, tpl in _CNT_TEMPLATE.items():
    for n in _CNT_WINDOWS:
        COUNTING_DESCRIPTIONS.append({
            "factor_name": f"{prefix}{n}",
            "category": tpl["category"],
            "display_name": tpl["display_name_tpl"].format(n=n),
            "description": tpl["description_tpl"].format(n=n),
            "formula": tpl["formula_tpl"].format(n=n),
            "economic_meaning": tpl["economic_meaning"],
            "use_case": tpl["use_case"],
        })

# ─────────────────────────────────────────────────────────────────────────────
# SUMP / SUMN / SUMD — RSI-like 正负变动占比因子
# ─────────────────────────────────────────────────────────────────────────────
_SUM_TEMPLATE: dict[str, dict] = {
    "SUMP": {
        "category": "rsi_like",
        "display_name_tpl": "{n}日正向变动占比",
        "description_tpl": "{n}日内正向变动总和占总绝对变动的比例（类RSI）",
        "formula_tpl": "sum(max(Δclose, 0), {n}) / sum(|Δclose|, {n})",
        "economic_meaning": "类似RSI的强度指标，值越高说明近期上涨力度越大",
        "use_case": "超买超卖判断、RSI替代指标",
    },
    "SUMN": {
        "category": "rsi_like",
        "display_name_tpl": "{n}日负向变动占比",
        "description_tpl": "{n}日内负向变动总和占总绝对变动的比例",
        "formula_tpl": "sum(max(-Δclose, 0), {n}) / sum(|Δclose|, {n})",
        "economic_meaning": "下跌力度占比，值越高说明近期下跌力度越大",
        "use_case": "下跌力度监控",
    },
    "SUMD": {
        "category": "rsi_like",
        "display_name_tpl": "{n}日正负变动差",
        "description_tpl": "{n}日内正向变动占比 - 负向变动占比",
        "formula_tpl": "SUMP{n} - SUMN{n}",
        "economic_meaning": "综合多空力度，正值表示多方主导，负值表示空方主导",
        "use_case": "多空力量对比、趋势方向判断",
    },
}

_SUM_WINDOWS = [5, 10, 20, 30, 60]

RSI_LIKE_DESCRIPTIONS: list[dict] = []
for prefix, tpl in _SUM_TEMPLATE.items():
    for n in _SUM_WINDOWS:
        RSI_LIKE_DESCRIPTIONS.append({
            "factor_name": f"{prefix}{n}",
            "category": tpl["category"],
            "display_name": tpl["display_name_tpl"].format(n=n),
            "description": tpl["description_tpl"].format(n=n),
            "formula": tpl["formula_tpl"].format(n=n),
            "economic_meaning": tpl["economic_meaning"],
            "use_case": tpl["use_case"],
        })

# ─────────────────────────────────────────────────────────────────────────────
# 成交量因子 — VMA / VSTD / WVMA / VSUMP / VSUMN / VSUMD
# ─────────────────────────────────────────────────────────────────────────────
_VOL_TEMPLATE: dict[str, dict] = {
    "VMA": {
        "category": "volume",
        "display_name_tpl": "{n}日成交量均线比",
        "description_tpl": "{n}日成交量均值相对当前成交量",
        "formula_tpl": "rolling_mean(volume, {n}) / volume",
        "economic_meaning": "量能相对强弱，>1表示当前成交量低于均值（缩量），<1表示放量",
        "use_case": "量能分析、缩量/放量信号",
    },
    "VSTD": {
        "category": "volume",
        "display_name_tpl": "{n}日成交量波动率",
        "description_tpl": "{n}日成交量标准差相对当前成交量",
        "formula_tpl": "rolling_std(volume, {n}) / volume",
        "economic_meaning": "成交量的稳定程度，值越大说明成交量波动越剧烈",
        "use_case": "异常放量检测、成交量择时",
    },
}

_VOL_WINDOWS = [5, 10, 20, 30, 60]

VOLUME_DESCRIPTIONS: list[dict] = []
for prefix, tpl in _VOL_TEMPLATE.items():
    for n in _VOL_WINDOWS:
        VOLUME_DESCRIPTIONS.append({
            "factor_name": f"{prefix}{n}",
            "category": tpl["category"],
            "display_name": tpl["display_name_tpl"].format(n=n),
            "description": tpl["description_tpl"].format(n=n),
            "formula": tpl["formula_tpl"].format(n=n),
            "economic_meaning": tpl["economic_meaning"],
            "use_case": tpl["use_case"],
        })

# WVMA — 加权成交量波动率
for n in _VOL_WINDOWS:
    VOLUME_DESCRIPTIONS.append({
        "factor_name": f"WVMA{n}",
        "category": "volume",
        "display_name": f"{n}日加权成交量波动率",
        "description": f"{n}日 |收益率| * 成交量 的滚动标准差 / close",
        "formula": f"rolling_std(abs(returns) * volume, {n}) / close",
        "economic_meaning": "价格变动加权的成交量波动，同时反映量和价的波动",
        "use_case": "综合波动率指标、风险度量",
    })

# VSUMP / VSUMN / VSUMD — 成交量 RSI
_VSUM_TEMPLATE: dict[str, dict] = {
    "VSUMP": {
        "category": "volume_rsi",
        "display_name_tpl": "{n}日上涨成交量占比",
        "description_tpl": "{n}日内上涨日成交量占总成交量的比例",
        "formula_tpl": "sum(volume where Δclose>0, {n}) / sum(volume, {n})",
        "economic_meaning": "上涨时的量能占比，值越高说明上涨伴随更多成交量（量价配合好）",
        "use_case": "量价配合分析、上涨质量判断",
    },
    "VSUMN": {
        "category": "volume_rsi",
        "display_name_tpl": "{n}日下跌成交量占比",
        "description_tpl": "{n}日内下跌日成交量占总成交量的比例",
        "formula_tpl": "sum(volume where Δclose<0, {n}) / sum(volume, {n})",
        "economic_meaning": "下跌时的量能占比，值越高说明下跌伴随更多成交量（恐慌抛售）",
        "use_case": "恐慌检测、放量下跌预警",
    },
    "VSUMD": {
        "category": "volume_rsi",
        "display_name_tpl": "{n}日成交量方向差",
        "description_tpl": "{n}日内上涨成交量占比 - 下跌成交量占比",
        "formula_tpl": "VSUMP{n} - VSUMN{n}",
        "economic_meaning": "成交量的方向偏好，正值表示上涨放量（健康），负值表示下跌放量（危险）",
        "use_case": "量能方向综合指标",
    },
}

_VSUM_WINDOWS = [5, 10, 20, 30, 60]

for prefix, tpl in _VSUM_TEMPLATE.items():
    for n in _VSUM_WINDOWS:
        VOLUME_DESCRIPTIONS.append({
            "factor_name": f"{prefix}{n}",
            "category": tpl["category"],
            "display_name": tpl["display_name_tpl"].format(n=n),
            "description": tpl["description_tpl"].format(n=n),
            "formula": tpl["formula_tpl"].format(n=n),
            "economic_meaning": tpl["economic_meaning"],
            "use_case": tpl["use_case"],
        })

# ─────────────────────────────────────────────────────────────────────────────
# Alpha360 因子 — 60天 x 6字段 = 360 个
# Alpha360 是 Qlib 的另一种特征配置，将最近 60 天的 6 个字段
# (open, high, low, close, volume, vwap) 直接展开为 360 个特征列。
# ─────────────────────────────────────────────────────────────────────────────
_ALPHA360_FIELDS = ["open", "high", "low", "close", "volume", "vwap"]
_ALPHA360_FIELD_DISPLAY = {
    "open": "开盘价",
    "high": "最高价",
    "low": "最低价",
    "close": "收盘价",
    "volume": "成交量",
    "vwap": "成交均价",
}

ALPHA360_DESCRIPTIONS: list[dict] = []
for day_offset in range(60):
    for field in _ALPHA360_FIELDS:
        d = day_offset + 1  # 1-based: Ref_x_1 = 昨天
        ALPHA360_DESCRIPTIONS.append({
            "factor_name": f"{field}_{d}",
            "category": "alpha360",
            "display_name": f"{d}日前{_ALPHA360_FIELD_DISPLAY[field]}",
            "description": f"{d}个交易日之前的{field}值（原始值，非衍生）",
            "formula": f"Ref(${field}, {d})",
            "economic_meaning": f"历史第{d}天的{_ALPHA360_FIELD_DISPLAY[field]}原始值，用于深度学习模型直接输入",
            "use_case": "LSTM/Transformer 等序列模型的原始特征输入",
        })

# ─────────────────────────────────────────────────────────────────────────────
# 汇总：Alpha158 全部描述
# ─────────────────────────────────────────────────────────────────────────────
ALPHA158_DESCRIPTIONS: list[dict] = (
    KBAR_DESCRIPTIONS
    + ROLLING_DESCRIPTIONS
    + REGRESSION_DESCRIPTIONS
    + QUANTILE_DESCRIPTIONS
    + EXTREMA_DESCRIPTIONS
    + CORRELATION_DESCRIPTIONS
    + COUNTING_DESCRIPTIONS
    + RSI_LIKE_DESCRIPTIONS
    + VOLUME_DESCRIPTIONS
)
