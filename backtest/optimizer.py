"""策略参数网格寻优：对内置策略的参数做网格扫描，按绩效排名。"""
import itertools

import pandas as pd

from backtest.runner import backtest_portfolio
from strategy.builtin import build_condition


def grid_search(
    strategy_name: str,
    grid: dict[str, list],
    stocks: list,
    days: int = 500,
    start: str | None = None,
    init_cash: float = 300000,
    n: int = 100,
    cost: bool = True,
    rules=None,
    progress=None,
) -> pd.DataFrame:
    """遍历参数组合做组合回测，返回按年化收益率降序的 DataFrame。

    :param grid: {参数名: [取值...]}
    :param progress: 可选回调 fn(已完成数, 总数)，用于 UI 进度
    """
    names = list(grid)
    combos = list(itertools.product(*(grid[k] for k in names)))
    rows = []
    for i, combo in enumerate(combos, 1):
        params = dict(zip(names, combo))
        try:
            cond = build_condition(strategy_name, **params)
            res = backtest_portfolio(
                cond, stocks, days=days, start=start, init_cash=init_cash,
                n=n, cost=cost, rules=rules)
            perf = res["performance"]
            rows.append({
                **{k: v for k, v in params.items()},
                "累计收益率%": perf.get("已平仓帐户收益率%"),
                "年化收益率%": perf.get("帐户年复合收益率%"),
                "交易次数": perf.get("已平仓交易总数"),
                "赢利交易比例%": perf.get("赢利交易比例%"),
                "净赢利": perf.get("已平仓净利润总额"),
            })
        except Exception as e:  # noqa: BLE001 单组合失败不中止
            rows.append({**params, "错误": str(e)[:80]})
        if progress:
            progress(i, len(combos))
    df = pd.DataFrame(rows)
    if "年化收益率%" in df.columns:
        df = df.sort_values("年化收益率%", ascending=False, na_position="last")
    return df.reset_index(drop=True)
