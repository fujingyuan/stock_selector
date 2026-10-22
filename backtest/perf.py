"""绩效扩展：资金曲线提取、风险调整指标（夏普/卡玛/索提诺）、分年度收益。

hikyuu Performance 不含夏普/卡玛等比率指标，这里基于账户每日总资产
（tm.get_funds_curve）自行计算；风险自由利率取 0。
"""
import math

import pandas as pd
from hikyuu import DatetimeList

TRADING_DAYS = 252


def _curve_dates(result: dict, stocks: list) -> list:
    """取回测区间内交易日历：用 kdata 最长的股票的日线日期近似。"""
    q = result.get("query")
    if q is None:
        return []
    best: list = []
    for stk in stocks[:20]:
        try:
            k = stk.get_kdata(q)
        except Exception:  # noqa: BLE001
            continue
        if len(k) > len(best):
            best = [k[i].datetime for i in range(len(k))]
    return best


def funds_curve(result: dict, stocks: list) -> pd.DataFrame:
    """账户每日总资产曲线 -> DataFrame(date, assets)。"""
    tm = result["tm"]
    dates = _curve_dates(result, stocks)
    if not dates:
        return pd.DataFrame(columns=["date", "assets"])
    vals = list(tm.get_funds_curve(DatetimeList(dates), "DAY"))
    return pd.DataFrame({
        "date": [str(d)[:10] for d in dates],
        "assets": [float(v) for v in vals],
    })


def risk_metrics(curve: pd.DataFrame) -> dict:
    """基于资金曲线计算风险调整指标（年化按 252 交易日）。"""
    out = {}
    if curve.empty or len(curve) < 3:
        return out
    assets = curve["assets"].astype(float)
    total_ret = assets.iloc[-1] / assets.iloc[0] - 1.0
    n_days = max(len(assets) - 1, 1)
    annual = (1.0 + total_ret) ** (TRADING_DAYS / n_days) - 1.0

    ret = assets.pct_change().dropna()
    vol = float(ret.std(ddof=1)) * math.sqrt(TRADING_DAYS)
    sharpe = sortino = float("nan")
    downside = ret[ret < 0]
    if vol > 1e-12 and float(ret.std(ddof=1)) > 1e-12:
        sharpe = float(ret.mean() / ret.std(ddof=1) * math.sqrt(TRADING_DAYS))
    if len(downside) >= 2 and float(downside.std(ddof=1)) > 1e-12:
        sortino = float(ret.mean() / downside.std(ddof=1) * math.sqrt(TRADING_DAYS))

    roll_max = assets.cummax()
    dd = assets / roll_max - 1.0
    max_dd = float(dd.min())
    dd_end = int(dd.idxmin()) if not dd.empty else 0
    dd_start = int(assets[: dd_end + 1].idxmax()) if dd_end > 0 else 0

    out.update({
        "区间收益率": total_ret,
        "年化收益率": annual,
        "年化波动率": vol,
        "夏普比率": sharpe,
        "索提诺比率": sortino,
        "最大回撤": max_dd,
        "卡玛比率": (annual / abs(max_dd)) if max_dd < -1e-12 else float("nan"),
        "回撤开始": curve.loc[dd_start, "date"] if len(curve) > dd_start else "",
        "回撤结束": curve.loc[dd_end, "date"] if len(curve) > dd_end else "",
    })
    return out


def yearly_returns(curve: pd.DataFrame) -> pd.DataFrame:
    """分年度收益表（按年末资产环比；首年以区间起始资产为基数）。"""
    if curve.empty:
        return pd.DataFrame()
    df = curve.copy()
    df["year"] = df["date"].str[:4]
    year_end = df.groupby("year")["assets"].last()
    rows = []
    base = float(df["assets"].iloc[0])
    for year in year_end.index:
        end_v = float(year_end[year])
        ret = end_v / base - 1.0
        rows.append({"年份": year, "年末资产": round(end_v, 2), "年度收益率": ret})
        base = end_v
    return pd.DataFrame(rows)


def normalized_compare(curve: pd.DataFrame, bench: pd.DataFrame) -> pd.DataFrame:
    """策略资金曲线与基准收盘价归一化对齐（期初=1.0）。

    :param bench: DataFrame(date, close)（基准数据，允许日期缺失）
    :return: DataFrame(index=date, columns=[策略, 沪深300])
    """
    if curve.empty or bench.empty:
        return pd.DataFrame()
    df = curve.merge(bench, on="date", how="left")
    df["close"] = df["close"].ffill()
    g = df.dropna(subset=["close"]).set_index("date")
    if g.empty:
        return pd.DataFrame()
    return pd.DataFrame({
        "策略": g["assets"].astype(float) / float(g["assets"].iloc[0]),
        "沪深300": g["close"].astype(float) / float(g["close"].iloc[0]),
    })
