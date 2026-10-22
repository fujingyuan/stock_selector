"""全市场扫描：对所有 A 股评估条件指标末值，输出选中股票清单。"""
from typing import Callable

from hikyuu import Query

from hikyuudata.initializer import get_sm

# A 股代码前缀（过滤指数、基金、债券、B股等）
_A_PREFIX = {
    "SH": ("600", "601", "603", "605", "688"),
    "SZ": ("000", "001", "002", "003", "300", "301"),
    "BJ": ("4", "8", "920"),
}

# 板块 -> (市场, 代码前缀)，覆盖全部 A 股
BOARD_PREFIX = {
    "沪主板": ("SH", ("600", "601", "603", "605")),
    "深主板": ("SZ", ("000", "001", "002", "003")),
    "创业板": ("SZ", ("300", "301")),
    "科创板": ("SH", ("688",)),
    "北交所": ("BJ", ("4", "8", "920")),
}
ALL_BOARDS = tuple(BOARD_PREFIX)


def stock_board(market: str, code: str) -> str | None:
    """返回股票所属板块名（不在 A 股板块内返回 None）。"""
    for name, (m, prefixes) in BOARD_PREFIX.items():
        if market == m and code.startswith(prefixes):
            return name
    return None


def is_a_share(market: str, code: str) -> bool:
    return code.startswith(_A_PREFIX.get(market, ()))


def get_universe(
    markets: tuple[str, ...] = ("SH", "SZ", "BJ"),
    exclude_st: bool = False,
    boards: tuple[str, ...] | list[str] | None = None,
) -> list:
    """获取 A 股股票列表（可选剔除 ST/退市、按板块过滤）。

    :param boards: 板块名列表（见 BOARD_PREFIX），None 表示全部板块；
                   如只要主板传 ["沪主板", "深主板"]
    """
    sm = get_sm()
    boards = tuple(boards) if boards is not None else None
    result = []
    for stk in sm.get_stock_list():
        if stk.market not in markets:
            continue
        if not stk.valid or not is_a_share(stk.market, stk.code):
            continue
        if boards is not None and stock_board(stk.market, stk.code) not in boards:
            continue
        if exclude_st and ("ST" in stk.name or "退" in stk.name):
            continue
        result.append(stk)
    return result


def scan_condition(
    cond,
    days: int = 250,
    markets: tuple[str, ...] = ("SH", "SZ", "BJ"),
    exclude_st: bool = True,
    boards=None,
    progress: Callable[[int, int], None] | None = None,
    save: bool = True,
    strategy_name: str = "custom",
) -> list[dict]:
    """用 0/1 条件指标扫描全市场，返回当日条件为真的股票。

    :param cond: hikyuu Indicator（0/1 序列），将在每只股票的 K 线上求值
    :param days: 参与计算的最近交易日数（需覆盖指标暖机期）
    :param boards: 板块过滤（如 ["沪主板", "深主板"] 只选主板），None 为全部
    :param progress: 进度回调 progress(cur, total)
    :param save: 结果是否落库 store.results
    :return: [{market_code, stock_code, stock_name, close, detail}]
    """
    import store

    stocks = get_universe(markets, exclude_st, boards=boards)
    total = len(stocks)
    rows: list[dict] = []
    for i, stk in enumerate(stocks, 1):
        try:
            kdata = stk.get_kdata(
                Query(-days, ktype=Query.DAY, recover_type=Query.EQUAL_FORWARD)
            )
            if kdata.empty():
                continue
            result = cond(kdata)
            if result.empty() or len(result) == 0:
                continue
            last = result[-1]
            if last == last and last != 0:  # NaN == NaN 为 False，排除 NaN 污染
                rec = kdata[-1]
                rows.append(
                    {
                        "market_code": stk.market_code,
                        "stock_code": stk.code,
                        "stock_name": stk.name,
                        "close": round(rec.close, 3),
                        "detail": str(rec.datetime),
                    }
                )
        except Exception:  # noqa: BLE001 单票失败不影响整体扫描
            continue
        finally:
            if progress and (i % 50 == 0 or i == total):
                progress(i, total)

    if save and rows:
        store.save_scan_result(strategy_name, rows)
    return rows


def scan_builtin(
    name: str,
    params: dict | None = None,
    days: int = 250,
    markets: tuple[str, ...] = ("SH", "SZ", "BJ"),
    exclude_st: bool = True,
    boards=None,
    progress: Callable[[int, int], None] | None = None,
) -> list[dict]:
    """用内置策略扫描全市场。"""
    from strategy.builtin import build_condition

    cond = build_condition(name, **(params or {}))
    return scan_condition(
        cond,
        days=days,
        markets=markets,
        exclude_st=exclude_st,
        boards=boards,
        progress=progress,
        strategy_name=name,
    )
