"""内置技术指标选股策略。

每条策略统一暴露：
- title: 显示名
- description: 说明
- params: {参数名: (默认值, 中文说明)}
- build_condition(**params) -> hikyuu Indicator（0/1 序列）

扫描时取条件序列最后非零值；回测时包成 SG_Bool(cond, ~cond)。
"""
from hikyuu import (
    AVEDEV,
    CLOSE,
    CROSS,
    EMA,
    EVERY,
    HIGH,
    HHV,
    IF,
    LLV,
    LOW,
    MA,
    REF,
    RSI,
    SLOPE,
    SMA,
    STDEV,
    SUM,
    VOL,
)


def _macd_golden(fast=12, slow=26, signal=9):
    # 注意：不要用 MACD(...).get_result(0) —— 多结果指标的子序列
    # 在 cond(kd) 晚绑定时不会重算，求值全 NaN。改用 EMA 重建标准公式。
    c = CLOSE()
    dif = EMA(c, fast) - EMA(c, slow)
    dea = EMA(dif, signal)
    return CROSS(dif, dea)


def _macd_above_zero(fast=12, slow=26, signal=9):
    c = CLOSE()
    dif = EMA(c, fast) - EMA(c, slow)
    dea = EMA(dif, signal)
    return (dif > 0) & (dea > 0)


def _ma_bullish(short=5, mid=10, long=20):
    c = CLOSE()
    return (MA(c, short) >= MA(c, mid)) & (MA(c, mid) >= MA(c, long))


def _ma_golden_cross(short=5, long=20):
    c = CLOSE()
    return CROSS(MA(c, short), MA(c, long))


def _kdj_golden(n=9, m1=3, m2=3):
    # KDJ 同理用基础指标重建：RSV -> SMA 平滑，避免 get_result 晚绑定 NaN
    rsv = (CLOSE() - LLV(LOW(), n)) / (HHV(HIGH(), n) - LLV(LOW(), n)) * 100
    k = SMA(rsv, m1, 1)
    d = SMA(k, m2, 1)
    return CROSS(k, d)


def _vol_breakout(vol_n=20, vol_ratio=2.0):
    return (VOL() > MA(VOL(), vol_n) * vol_ratio) & (CLOSE() > REF(CLOSE(), 1))


def _breakout_n_high(n=60):
    from hikyuu import HHV

    return CLOSE() >= REF(HHV(CLOSE(), n), 1)


# ---------------- v2 新增因子（全部为单结果/基础指标重建，避免晚绑定 NaN） ----------------


def _rsi_oversold_bounce(n=14, level=30):
    # RSI 从超卖区（<level）回升上穿 level
    r = RSI(CLOSE(), int(n))
    return (REF(r, 1) < level) & (r >= level)


def _rsi_strong(n=14, level=55, ma_n=20):
    # RSI 强势区 + 价格站上均线：动量与趋势共振
    return (RSI(CLOSE(), int(n)) >= level) & (CLOSE() > MA(CLOSE(), int(ma_n)))


def _boll_break(n=20, k=2.0, vol_ratio=1.5):
    # 放量突破布林上轨
    up = MA(CLOSE(), int(n)) + STDEV(CLOSE(), int(n)) * float(k)
    return CROSS(CLOSE(), up) & (VOL() > MA(VOL(), 5) * float(vol_ratio))


def _boll_lower_support(n=20, k=2.0):
    # 触及布林下轨后企稳回升
    low = MA(CLOSE(), int(n)) - STDEV(CLOSE(), int(n)) * float(k)
    return (REF(CLOSE(), 1) <= REF(low, 1)) & (CLOSE() > REF(CLOSE(), 1)) & (CLOSE() >= low)


def _pullback_ma_bull(short=5, mid=10, long=20, vol_n=5, shrink=1.0):
    # 多头排列中缩量回踩长期均线并收回（趋势回调买点）
    c = CLOSE()
    bull = (MA(c, int(short)) >= MA(c, int(mid))) & (MA(c, int(mid)) >= MA(c, int(long)))
    return (
        bull
        & (LOW() <= MA(c, int(long)))
        & (c > MA(c, int(long)))
        & (VOL() <= MA(VOL(), int(vol_n)) * float(shrink))
    )


def _volume_price_rise(days=3):
    # 连续 N 日价涨量增
    up = (CLOSE() > REF(CLOSE(), 1)) & (VOL() > REF(VOL(), 1))
    return EVERY(up, int(days))


def _platform_breakout(n=20, width=0.15, vol_ratio=2.0):
    # 前 N 日窄幅平台（振幅 ≤ width）后放量突破平台上沿
    hh = REF(HHV(HIGH(), int(n)), 1)
    ll = REF(LLV(LOW(), int(n)), 1)
    return (
        ((hh / ll - 1) <= float(width))
        & (CLOSE() >= hh)
        & (VOL() > MA(VOL(), 5) * float(vol_ratio))
    )


def _kdj_oversold_golden(n=9, m1=3, m2=3, level=25):
    # KDJ 在超卖区（K < level）金叉，反弹成功率高
    rsv = (CLOSE() - LLV(LOW(), int(n))) / (HHV(HIGH(), int(n)) - LLV(LOW(), int(n))) * 100
    k = SMA(rsv, int(m1), 1)
    d = SMA(k, int(m2), 1)
    return CROSS(k, d) & (REF(k, 1) < level)


def _cci_start(n=14, level=100):
    # CCI 上穿 +level：强势趋势启动（CCI 用 AVEDEV 重建标准公式）
    tp = (HIGH() + LOW() + CLOSE()) / 3
    cci = (tp - MA(tp, int(n))) / (AVEDEV(tp, int(n)) * 0.015)
    return (REF(cci, 1) < level) & (cci >= level)


def _wr_escape(n=14, level=80):
    # WR 脱离超卖区（WR ≥ level 后回落之下）：超跌反弹
    hh = HHV(HIGH(), int(n))
    wr = (hh - CLOSE()) / (hh - LLV(LOW(), int(n))) * 100
    return (REF(wr, 1) >= level) & (wr < level)


def _obv():
    # OBV 用基础指标重建：涨跌日成交量正/负累加
    x = IF(
        CLOSE() > REF(CLOSE(), 1),
        VOL(),
        IF(CLOSE() < REF(CLOSE(), 1), 0 - VOL(), 0.0),
    )
    return SUM(x, 100000)


def _obv_up(ma_n=30, price_ma=20):
    # OBV 站上其均线（资金持续流入）且价格在均线上方
    obv = _obv()
    return (obv > MA(obv, int(ma_n))) & (CLOSE() > MA(CLOSE(), int(price_ma)))


def _trend_slope_up(short=5, mid=10, long=20, slope_n=5, vol_ratio=1.2):
    # 多头排列 + 长期均线斜率向上 + 放量：趋势加速
    c = CLOSE()
    bull = (MA(c, int(short)) >= MA(c, int(mid))) & (MA(c, int(mid)) >= MA(c, int(long)))
    return (
        bull
        & (SLOPE(MA(c, int(long)), int(slope_n)) > 0)
        & (VOL() > MA(VOL(), 20) * float(vol_ratio))
    )


# ---------------- MACD × KDJ 组合（趋势过滤 + 摆动扳机） ----------------


def _dif_dea(fast=12, slow=26, signal=9):
    dif = EMA(CLOSE(), int(fast)) - EMA(CLOSE(), int(slow))
    dea = EMA(dif, int(signal))
    return dif, dea


def _kdj_kd(n=9, m1=3, m2=3):
    rsv = (CLOSE() - LLV(LOW(), int(n))) / (HHV(HIGH(), int(n)) - LLV(LOW(), int(n))) * 100
    k = SMA(rsv, int(m1), 1)
    d = SMA(k, int(m2), 1)
    return k, d


def _macd_above_zero_kdj_golden(fast=12, slow=26, signal=9, k_max=50):
    # 老手打法1「零上金叉」：DIF/DEA 在零轴上方（多头）时，KDJ 低位金叉=回调买点
    dif, dea = _dif_dea(fast, slow, signal)
    k, d = _kdj_kd()
    return (dif > 0) & (dea > 0) & CROSS(k, d) & (REF(k, 1) < k_max)


def _macd_kdj_double_golden(window=3):
    # 老手打法2「双金叉共振」：KDJ 金叉 且 MACD 金叉发生在近 window 日内（含当日）
    from hikyuu import COUNT

    dif, dea = _dif_dea()
    k, d = _kdj_kd()
    return CROSS(k, d) & (COUNT(CROSS(dif, dea), int(window)) >= 1)


def _kdj_oversold_macd_turn(level=20):
    # 老手打法3「低位共振」：KDJ 超卖区金叉 + DIF 拐头向上（抢反弹起点）
    dif, _ = _dif_dea()
    k, d = _kdj_kd()
    return CROSS(k, d) & (REF(k, 1) < level) & (dif > REF(dif, 1))


BUILTIN_STRATEGIES = {
    "macd_golden": {
        "title": "MACD 金叉",
        "description": "DIF 上穿 DEA（MACD 金叉）",
        "params": {"fast": (12, "快线周期"), "slow": (26, "慢线周期"), "signal": (9, "信号线周期")},
        "build_condition": _macd_golden,
    },
    "macd_above_zero": {
        "title": "MACD 零上强势",
        "description": "DIF 与 DEA 均在零轴上方",
        "params": {"fast": (12, "快线周期"), "slow": (26, "慢线周期"), "signal": (9, "信号线周期")},
        "build_condition": _macd_above_zero,
    },
    "ma_bullish": {
        "title": "均线多头排列",
        "description": "短期均线 ≥ 中期均线 ≥ 长期均线",
        "params": {"short": (5, "短期"), "mid": (10, "中期"), "long": (20, "长期")},
        "build_condition": _ma_bullish,
    },
    "ma_golden_cross": {
        "title": "均线金叉",
        "description": "短期均线上穿长期均线",
        "params": {"short": (5, "短期"), "long": (20, "长期")},
        "build_condition": _ma_golden_cross,
    },
    "kdj_golden": {
        "title": "KDJ 金叉",
        "description": "K 线上穿 D 线",
        "params": {"n": (9, "RSV 周期"), "m1": (3, "K 平滑"), "m2": (3, "D 平滑")},
        "build_condition": _kdj_golden,
    },
    "vol_breakout": {
        "title": "放量突破",
        "description": "成交量放大且收盘价上涨",
        "params": {"vol_n": (20, "均量周期"), "vol_ratio": (2.0, "放量倍数")},
        "build_condition": _vol_breakout,
    },
    "breakout_n_high": {
        "title": "N 日新高突破",
        "description": "收盘价创 N 日新高",
        "params": {"n": (60, "周期")},
        "build_condition": _breakout_n_high,
    },
    "rsi_oversold_bounce": {
        "title": "RSI 超卖反弹",
        "description": "RSI 从超卖区回升上穿分界线",
        "params": {"n": (14, "RSI 周期"), "level": (30, "超卖分界线")},
        "build_condition": _rsi_oversold_bounce,
    },
    "rsi_strong": {
        "title": "RSI 强势共振",
        "description": "RSI ≥ 强势线 且收盘价站上均线",
        "params": {"n": (14, "RSI 周期"), "level": (55, "强势分界线"), "ma_n": (20, "均线周期")},
        "build_condition": _rsi_strong,
    },
    "boll_break": {
        "title": "BOLL 放量突破上轨",
        "description": "放量上穿布林上轨（n 日 k 倍标准差）",
        "params": {"n": (20, "周期"), "k": (2.0, "标准差倍数"), "vol_ratio": (1.5, "放量倍数")},
        "build_condition": _boll_break,
    },
    "boll_lower_support": {
        "title": "BOLL 下轨企稳",
        "description": "触及布林下轨后回升收回",
        "params": {"n": (20, "周期"), "k": (2.0, "标准差倍数")},
        "build_condition": _boll_lower_support,
    },
    "pullback_ma_bull": {
        "title": "多头缩量回踩",
        "description": "均线多头排列中缩量回踩长期均线并收回上方",
        "params": {
            "short": (5, "短期均线"), "mid": (10, "中期均线"), "long": (20, "长期均线"),
            "vol_n": (5, "均量周期"), "shrink": (1.0, "缩量系数(≤1)"),
        },
        "build_condition": _pullback_ma_bull,
    },
    "volume_price_rise": {
        "title": "量价齐升",
        "description": "连续 N 日价涨量增",
        "params": {"days": (3, "连续天数")},
        "build_condition": _volume_price_rise,
    },
    "platform_breakout": {
        "title": "平台放量突破",
        "description": "前 N 日窄幅平台（振幅 ≤ 阈值）后放量突破平台上沿",
        "params": {"n": (20, "平台周期"), "width": (0.15, "平台振幅上限"), "vol_ratio": (2.0, "放量倍数")},
        "build_condition": _platform_breakout,
    },
    "kdj_oversold_golden": {
        "title": "KDJ 超卖金叉",
        "description": "K 值低于阈值区域时 K 上穿 D",
        "params": {"n": (9, "RSV 周期"), "m1": (3, "K 平滑"), "m2": (3, "D 平滑"), "level": (25, "超卖阈值")},
        "build_condition": _kdj_oversold_golden,
    },
    "cci_start": {
        "title": "CCI 强势启动",
        "description": "CCI 上穿分界线（默认 +100）",
        "params": {"n": (14, "CCI 周期"), "level": (100, "分界线")},
        "build_condition": _cci_start,
    },
    "wr_escape": {
        "title": "WR 脱离超卖",
        "description": "威廉指标自超卖区（≥阈值）回落脱离",
        "params": {"n": (14, "WR 周期"), "level": (80, "超卖阈值")},
        "build_condition": _wr_escape,
    },
    "obv_up": {
        "title": "OBV 资金走强",
        "description": "OBV 站上其均线且收盘价在均线上方（量价配合）",
        "params": {"ma_n": (30, "OBV 均线周期"), "price_ma": (20, "价格均线周期")},
        "build_condition": _obv_up,
    },
    "trend_slope_up": {
        "title": "趋势加速",
        "description": "多头排列 + 长期均线斜率向上 + 放量",
        "params": {
            "short": (5, "短期均线"), "mid": (10, "中期均线"), "long": (20, "长期均线"),
            "slope_n": (5, "斜率周期"), "vol_ratio": (1.2, "放量倍数"),
        },
        "build_condition": _trend_slope_up,
    },
    "macd_above_zero_kdj_golden": {
        "title": "MACD零上·KDJ金叉",
        "description": "DIF/DEA 均在零轴上方（多头）时，K 值低于阈值的 KDJ 金叉（回调买点）",
        "params": {
            "fast": (12, "MACD 快线"), "slow": (26, "MACD 慢线"), "signal": (9, "信号线"),
            "k_max": (50, "K 值上限(低位金叉)"),
        },
        "build_condition": _macd_above_zero_kdj_golden,
    },
    "macd_kdj_double_golden": {
        "title": "双金叉共振",
        "description": "KDJ 金叉 且 MACD 金叉出现在近 N 日内（趋势启动确认）",
        "params": {"window": (3, "共振时间窗(日)")},
        "build_condition": _macd_kdj_double_golden,
    },
    "kdj_oversold_macd_turn": {
        "title": "超卖金叉·DIF拐头",
        "description": "KDJ 超卖区金叉 + MACD DIF 拐头向上（抢反弹起点）",
        "params": {"level": (20, "K 值超卖阈值")},
        "build_condition": _kdj_oversold_macd_turn,
    },
}


def build_condition(name: str, **params):
    """按策略名构建条件指标（0/1 序列）。"""
    if name not in BUILTIN_STRATEGIES:
        raise ValueError(f"未知内置策略: {name}")
    info = BUILTIN_STRATEGIES[name]
    defaults = {k: v[0] for k, v in info["params"].items()}
    defaults.update(params)
    return info["build_condition"](**defaults)
