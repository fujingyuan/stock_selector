"""K线衍生因子：多因子筛选时对候选股票按需现算。

设计要点：
- 公式用 pandas ewm/rolling 实现，与策略引擎（hikyuu EMA/SMA 重建版）数值一致
- 每股只加载一次 K 线（窗口取所需因子的最大暖机长度），全部因子算完缓存
- 数据不足/NaN 返回 None，由上层按「宁缺毋滥」淘汰
"""
import pandas as pd

# ---------- 因子计算函数（输入 df，返回最新一根的值或 None） ----------


def _last(s: pd.Series):
    if s is None or len(s) == 0:
        return None
    v = s.iloc[-1]
    return float(v) if v == v else None


def _ret(df: pd.DataFrame, n: int):
    c = df["close"]
    if len(c) < n + 1:
        return None
    base = c.iloc[-1 - n]
    return float((c.iloc[-1] / base - 1) * 100) if base else None


def _ma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def _macd(df: pd.DataFrame):
    c = df["close"]
    dif = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    dea = dif.ewm(span=9, adjust=False).mean()
    return dif, dea, 2 * (dif - dea)


def _kdj(df: pd.DataFrame):
    c, h, lo = df["close"], df["high"], df["low"]
    low9 = lo.rolling(9).min()
    high9 = h.rolling(9).max()
    rsv = (c - low9) / (high9 - low9) * 100
    k = rsv.ewm(alpha=1 / 3, adjust=False).mean()  # 等价 hikyuu SMA(x,3,1)
    d = k.ewm(alpha=1 / 3, adjust=False).mean()
    return k, d, 3 * k - 2 * d


def _rsi(df: pd.DataFrame, n: int):
    """hikyuu RSI 语义：SMA(MAX(ΔC,0),N,1)/SMA(|ΔC|,N,1)×100（alpha=1/N）。"""
    delta = df["close"].diff()
    up = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = delta.abs().ewm(alpha=1 / n, adjust=False).mean()
    if len(dn) == 0 or not dn.iloc[-1]:
        return None
    return float(up.iloc[-1] / dn.iloc[-1] * 100)


def _boll(df: pd.DataFrame):
    c = df["close"]
    mid = _ma(c, 20)
    std = c.rolling(20).std(ddof=0)  # hikyuu STDEV 为总体标准差
    return mid + 2 * std, mid, mid - 2 * std


def _streak(cond: pd.Series) -> float:
    """末根起连续满足条件的天数。"""
    n = 0
    for v in cond.iloc[::-1]:
        if not v:
            break
        n += 1
    return float(n)


def _price_pct(df: pd.DataFrame, days: int):
    """价格分位%：最近 days 根收盘价中不超过当前收盘的比例。"""
    c = df["close"]
    if len(c) < max(60, days // 2):  # 历史太短时分位无意义
        return None
    win = c.iloc[-days:] if len(c) >= days else c
    return float((win <= c.iloc[-1]).mean() * 100)


# 因子 -> (暖机所需 K 线根数, 计算函数)
KLINE_FACTOR_FUNCS = {
    "ret_5d": (10, lambda df: _ret(df, 5)),
    "ret_10d": (15, lambda df: _ret(df, 10)),
    "ret_20d": (25, lambda df: _ret(df, 20)),
    "ret_60d": (65, lambda df: _ret(df, 60)),
    "ma_bull": (65, lambda df: float(
        _ma(df["close"], 5).iloc[-1] > _ma(df["close"], 10).iloc[-1]
        > _ma(df["close"], 20).iloc[-1] > _ma(df["close"], 60).iloc[-1])
        if len(df) >= 60 else None),
    "ma20_bias": (25, lambda df: float(
        (df["close"].iloc[-1] / _ma(df["close"], 20).iloc[-1] - 1) * 100)
        if len(df) >= 20 else None),
    "ma60_bias": (65, lambda df: float(
        (df["close"].iloc[-1] / _ma(df["close"], 60).iloc[-1] - 1) * 100)
        if len(df) >= 60 else None),
    "macd_dif": (60, lambda df: _last(_macd(df)[0])),
    "macd_dea": (60, lambda df: _last(_macd(df)[1])),
    "macd_hist": (60, lambda df: _last(_macd(df)[2])),
    "macd_gold": (60, lambda df: float(
        _macd(df)[0].iloc[-2] <= _macd(df)[1].iloc[-2]
        and _macd(df)[0].iloc[-1] > _macd(df)[1].iloc[-1])
        if len(df) >= 2 else None),
    "macd_above": (60, lambda df: (lambda v: float(v > 0) if v is not None else None)
        (_last(_macd(df)[0]))),
    "kdj_k": (40, lambda df: _last(_kdj(df)[0])),
    "kdj_d": (40, lambda df: _last(_kdj(df)[1])),
    "kdj_j": (40, lambda df: _last(_kdj(df)[2])),
    "kdj_gold": (40, lambda df: float(
        _kdj(df)[0].iloc[-2] <= _kdj(df)[1].iloc[-2]
        and _kdj(df)[0].iloc[-1] > _kdj(df)[1].iloc[-1])
        if len(df) >= 2 else None),
    "rsi6": (30, lambda df: _rsi(df, 6)),
    "rsi12": (30, lambda df: _rsi(df, 12)),
    "rsi24": (40, lambda df: _rsi(df, 24)),
    "bias6": (10, lambda df: float(
        (df["close"].iloc[-1] / _ma(df["close"], 6).iloc[-1] - 1) * 100)
        if len(df) >= 6 else None),
    "bias12": (15, lambda df: float(
        (df["close"].iloc[-1] / _ma(df["close"], 12).iloc[-1] - 1) * 100)
        if len(df) >= 12 else None),
    "bias24": (30, lambda df: float(
        (df["close"].iloc[-1] / _ma(df["close"], 24).iloc[-1] - 1) * 100)
        if len(df) >= 24 else None),
    "boll_pos": (30, lambda df: (lambda u, lo: float(
        (df["close"].iloc[-1] - lo.iloc[-1]) / (u.iloc[-1] - lo.iloc[-1]) * 100)
        if u.iloc[-1] > lo.iloc[-1] else None)(*_boll(df)[::2])
        if len(df) >= 20 else None),
    "boll_break": (30, lambda df: float(
        df["close"].iloc[-1] > _boll(df)[0].iloc[-1]) if len(df) >= 20 else None),
    "up_days": (15, lambda df: _streak(df["close"] > df["open"])),
    "vol_up_days": (15, lambda df: _streak(df["volume"].diff() > 0)),
    "vol_down_days": (15, lambda df: _streak(df["volume"].diff() < 0)),
    "price_pct_1y": (250, lambda df: _price_pct(df, 250)),
    "price_pct_3y": (750, lambda df: _price_pct(df, 750)),
    "new_high_60": (65, lambda df: float(
        df["close"].iloc[-1] >= df["close"].iloc[-60:].max())
        if len(df) >= 60 else None),
}

KLINE_FACTOR_KEYS = tuple(KLINE_FACTOR_FUNCS)


def needed_window(factors) -> int:
    """所需因子的最大暖机长度 + 缓冲。"""
    ws = [KLINE_FACTOR_FUNCS[f][0] for f in factors if f in KLINE_FACTOR_FUNCS]
    return (max(ws) + 10) if ws else 0


class KlineFactorCalc:
    """按股票缓存 K 线与因子值，避免扫描中重复加载/计算。"""

    def __init__(self, factors, window: int):
        self.factors = tuple(f for f in factors if f in KLINE_FACTOR_FUNCS)
        self.window = window
        self._sm = None
        self._cache: dict[str, dict] = {}

    def values(self, market_code: str) -> dict:
        """返回 {factor: value|None}；加载失败返回全 None。"""
        key = market_code.lower()
        if key in self._cache:
            return self._cache[key]
        out = {f: None for f in self.factors}
        try:
            df = self._load_df(key)
            if df is not None and len(df) >= 30:
                for f in self.factors:
                    try:
                        v = KLINE_FACTOR_FUNCS[f][1](df)
                        out[f] = v if (v is None or v == v) else None
                    except (IndexError, ValueError, ZeroDivisionError):
                        out[f] = None
        except Exception:  # noqa: BLE001 停牌/缺数据等，保持全 None
            pass
        self._cache[key] = out
        return out

    def _load_df(self, market_code: str):
        if self._sm is None:
            from hikyuudata.initializer import get_sm

            self._sm = get_sm()
        from hikyuu import Query

        stk = self._sm[market_code]
        if not (stk and stk.valid):
            return None
        kd = stk.get_kdata(Query(-self.window, ktype=Query.DAY,
                                 recover_type=Query.EQUAL_FORWARD))
        if len(kd) == 0:
            return None
        rows = [(kd[i].open, kd[i].high, kd[i].low, kd[i].close, kd[i].volume)
                for i in range(len(kd))]
        df = pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"])
        return df if not df.empty else None


__all__ = ["KLINE_FACTOR_KEYS", "KlineFactorCalc", "needed_window"]
