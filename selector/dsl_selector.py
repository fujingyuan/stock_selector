"""把条件指标包装为组合回测可用的选股器。

实现说明：hikyuu 自带的 SE_Signal 会在组合运行时对每只股票执行原型系统、
读取其信号发生器（SG_Bool）的买入信号作为选股结果。因此无需手写
SelectorBase 子类，直接把条件编译为 SG_Bool 放入原型系统即可。
"""
from hikyuu import MM_FixedCount, SYS_Simple, crtTM


def build_proto_system(
    buy_cond,
    sell_cond=None,
    init_cash: float = 300000,
    n: int = 100,
    cost: bool = True,
    rules=None,
):
    """由 0/1 条件指标构建原型交易系统。

    :param buy_cond: 买入条件 Indicator（0/1 序列）
    :param sell_cond: 兼容旧参数：独立卖出条件 Indicator，等效 rules.sell_cond
    :param n: 每次买入固定股数
    :param cost: 是否计入交易成本（佣金千三 + 印花税，用 hikyuu 默认 TC_FixedA）
    :param rules: backtest.sell_rules.SellRules 卖出规则配置（优先于 sell_cond）
    """
    from backtest.sell_rules import SellRules, build_profit_goal, build_signal, build_stoploss

    if rules is None and sell_cond is not None:
        rules = SellRules(sell_cond=sell_cond)
    tm = crtTM(init_cash=init_cash)
    sg = build_signal(buy_cond, rules)
    st = build_stoploss(rules) if rules else None
    pg = build_profit_goal(rules) if rules else None
    sys = SYS_Simple(tm=tm, sg=sg, mm=MM_FixedCount(n), st=st, pg=pg)
    if not cost:
        from hikyuu import TC_Zero

        sys.tm.cost_func = TC_Zero()
    return sys


def build_selector(stocks, proto_sys):
    """构建信号选股器（对股票列表逐一运行原型系统并按信号选股）。"""
    from hikyuu import SE_Signal

    return SE_Signal(list(stocks), proto_sys)
