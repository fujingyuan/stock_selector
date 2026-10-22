"""回测引擎：单票系统回测 + 组合回测，输出绩效与交易明细。

- 单票：SYS_Simple + SG_Bool 信号直接 run
- 组合：PF_WithoutAF + SE_Signal（所有单系统共享一个账户 tm）
- 复权：Query.EQUAL_BACKWARD（等比后复权，避免前复权的未来函数问题）
- v2：支持 SellRules 卖出规则（止损/止盈/移动止损/持有天数/独立卖出条件）
"""
from hikyuu import Datetime, Performance, Query

from hikyuudata.initializer import get_sm
from selector.dsl_selector import build_proto_system, build_selector


def _query(days: int, start: str | None = None) -> Query:
    if start:
        return Query(
            Datetime(start),
            Query.MAX,
            ktype=Query.DAY,
            recover_type=Query.EQUAL_BACKWARD,
        )
    return Query(-days, ktype=Query.DAY, recover_type=Query.EQUAL_BACKWARD)


def _perf_dict(tm) -> dict:
    perf = Performance()
    perf.statistics(tm)
    return dict(zip(perf.names(), perf.values()))


def backtest_portfolio(
    buy_cond,
    stocks: list,
    days: int = 500,
    start: str | None = None,
    init_cash: float = 300000,
    n: int = 100,
    cost: bool = True,
    rules=None,
) -> dict:
    """组合回测：对股票列表统一选股、统一账户买卖。

    :param buy_cond: 0/1 买入条件 Indicator（在每只股票的后复权日线上求值）
    :param stocks: 股票对象列表（如全市场 A 股或某次选股结果）
    :param days/start: 回测区间（最近 days 根日线，或自 start 起至最新）
    :param n: 每次买入固定股数
    :param rules: 卖出规则 SellRules（见 backtest.sell_rules）
    :return: {performance, trades, pf, tm, query, stock_count}
    """
    proto = build_proto_system(buy_cond, init_cash=init_cash, n=n, cost=cost, rules=rules)
    se = build_selector(stocks, proto)
    tm = _new_tm(init_cash)
    from hikyuu import PF_WithoutAF

    pf = PF_WithoutAF(tm=tm, se=se, adjust_mode="query")
    q = _query(days, start)
    pf.run(q)
    trades = tm.get_trade_list().to_df()
    return {
        "performance": _perf_dict(tm),
        "trades": trades,
        "pf": pf,
        "tm": tm,
        "query": q,
        "stock_count": len(stocks),
    }


def _new_tm(init_cash: float):
    from hikyuu import TC_FixedA, crtTM

    return crtTM(init_cash=init_cash, cost_func=TC_FixedA())


def backtest_single(
    buy_cond,
    stock,
    days: int = 500,
    start: str | None = None,
    init_cash: float = 300000,
    n: int = 100,
    cost: bool = True,
    rules=None,
) -> dict:
    """单票回测（调试策略用）。"""
    proto = build_proto_system(buy_cond, init_cash=init_cash, n=n, cost=cost, rules=rules)
    q = _query(days, start)
    proto.run(stock, q)
    tm = proto.tm
    return {
        "performance": _perf_dict(tm),
        "trades": tm.get_trade_list().to_df(),
        "sys": proto,
        "tm": tm,
        "query": q,
    }


def resolve_stocks(spec: dict) -> list:
    """把股票范围描述解析为股票列表。

    spec 形如 {"mode": "market"} 全市场，或 {"mode": "codes", "codes": ["sh600000", ...]}
    """
    sm = get_sm()
    from selector.scanner import get_universe

    if spec.get("mode") == "market":
        return get_universe(exclude_st=spec.get("exclude_st", True),
                            boards=spec.get("boards"))
    out = []
    for mc in spec.get("codes") or []:
        stk = sm[str(mc).strip().lower()]
        if stk and stk.valid:
            out.append(stk)
    return out


def performance_summary(result: dict) -> tuple[list[tuple], str]:
    """(关键指标[(名,值)], 完整文本报告)"""
    from hikyuu import Performance

    perf = Performance()
    perf.statistics(result["tm"])
    report = perf.report(result["tm"])
    key_names = [
        "帐户初始金额",
        "累计投入本金",
        "当前总资产",
        "已平仓帐户收益率%",
        "帐户年复合收益率%",
        "已平仓交易总数",
        "赢利交易比例%",
        "已平仓净利润总额",
    ]
    perf_map = result["performance"]
    rows = [(k, perf_map[k]) for k in key_names if k in perf_map]
    return rows, report
