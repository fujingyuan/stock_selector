"""沪深300 基准数据：腾讯源拉取 + 本地 CSV 缓存。

不写入 hikyuu h5（避免与 K 线导入进程的写锁冲突），独立缓存在
项目 data/ 目录下，按需增量更新。
"""
import datetime
from pathlib import Path

import pandas as pd

CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "benchmark_sh000300.csv"
CODE, MARKET = "000300", "SH"
BEG = "2010-01-01"


def _fetch_df(beg: str) -> pd.DataFrame:
    from hikyuudata.tencent_kline import fetch_klines

    rows = fetch_klines(CODE, MARKET, beg=beg)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(
        [(datetime.date(d // 10000, d // 100 % 100, d % 100).isoformat(), c)
         for d, _o, _h, _l, c, _v in rows],
        columns=["date", "close"],
    )


def get_benchmark(beg: str | None = None, end: str | None = None,
                  refresh: bool = False) -> pd.DataFrame:
    """返回沪深300 日收盘（date, close），区间 [beg, end]，本地缓存增量更新。"""
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame()
    if CACHE_PATH.exists() and not refresh:
        try:
            df = pd.read_csv(CACHE_PATH)
        except Exception:  # noqa: BLE001 缓存损坏则重拉
            df = pd.DataFrame()
    need_beg = BEG
    if not df.empty:
        need_beg = (datetime.date.fromisoformat(df["date"].max())
                    + datetime.timedelta(days=1)).isoformat()
    if df.empty or need_beg <= datetime.date.today().isoformat():
        try:
            fresh = _fetch_df(need_beg)
        except Exception:  # noqa: BLE001 网络失败时用已有缓存
            fresh = pd.DataFrame()
        if not fresh.empty:
            df = pd.concat([df, fresh], ignore_index=True)
            df = df.drop_duplicates("date").sort_values("date")
            df.to_csv(CACHE_PATH, index=False)
    if df.empty:
        return df
    out = df
    if beg:
        out = out[out["date"] >= beg]
    if end:
        out = out[out["date"] <= end]
    return out.reset_index(drop=True)
