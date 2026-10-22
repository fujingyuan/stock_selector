"""卖出规则：独立于买入条件的离场控制，映射到 hikyuu SYS_Simple 组件。

- 止损方式（单选）：无 / 固定百分比 ST_FixedPercent /
  移动止损（吊灯式，HHV(HIGH,n)*(1-p) 经 ST_Indicator）/ 安全线 ST_Saftyloss
- 止盈 + 最大持有天数（可同时生效）：
  * 只启用其一 → 内置 PG_FixedPercent / PG_FixedHoldDays（按交易日）
  * 同时启用   → 自定义 ProfitGoalBase 组合（buy_notify 跟踪持仓，
    持有天数按自然日近似）
- 独立卖出条件：并入 SG 卖出信号，与“买入条件失效”取或
"""
from dataclasses import dataclass

from hikyuu import BUSINESS, HIGH, HHV, ProfitGoalBase


@dataclass
class SellRules:
    """卖出规则配置（可序列化保存）。"""

    # 止损方式: none / fixed / trail / saftyloss
    stop_mode: str = "none"
    stop_pct: float = 0.08          # 固定止损：跌破买入价 stop_pct 止损
    trail_n: int = 20               # 移动止损：回溯周期
    trail_pct: float = 0.15         # 移动止损：自 N 日最高价回撤幅度
    saftyloss: tuple = (10, 3, 2.0)  # ST_Saftyloss(n1, n2, p)

    take_profit: float | None = None   # 止盈百分比（如 0.2 = +20%），None 不启用
    max_hold_days: int | None = None   # 最大持有天数，None 不启用

    sell_cond: object = None            # 独立卖出条件 Indicator（0/1 序列）
    sell_on_signal_exit: bool = True    # 买入条件失效时卖出

    def active(self) -> bool:
        """是否有除默认信号外的离场规则。"""
        return bool(
            self.stop_mode != "none"
            or self.take_profit
            or self.max_hold_days
            or self.sell_cond is not None
            or not self.sell_on_signal_exit
        )

    def describe(self) -> str:
        parts = []
        if self.stop_mode == "fixed":
            parts.append(f"固定止损 {self.stop_pct:.0%}")
        elif self.stop_mode == "trail":
            parts.append(f"移动止损 {self.trail_n}日高点回撤 {self.trail_pct:.0%}")
        elif self.stop_mode == "saftyloss":
            n1, n2, p = self.saftyloss
            parts.append(f"安全线止损({n1},{n2},{p})")
        if self.take_profit:
            parts.append(f"止盈 +{self.take_profit:.0%}")
        if self.max_hold_days:
            parts.append(f"最长持有 {self.max_hold_days} 日")
        if self.sell_cond is not None:
            parts.append("独立卖出条件")
        if not self.sell_on_signal_exit:
            parts.append("不随买入条件失效离场")
        return "；".join(parts) if parts else "默认（买入条件失效时卖出）"


def build_stoploss(rules: SellRules):
    """按配置构建 Stoploss 组件（hikyuu 系统仅支持一个，故止损方式单选）。"""
    if rules.stop_mode == "fixed":
        from hikyuu import ST_FixedPercent

        return ST_FixedPercent(float(rules.stop_pct))
    if rules.stop_mode == "trail":
        from hikyuu import ST_Indicator

        # 吊灯式移动止损：止损线随 N 日最高价上移，收盘跌破即离场
        return ST_Indicator(HHV(HIGH(), int(rules.trail_n)) * (1.0 - float(rules.trail_pct)))
    if rules.stop_mode == "saftyloss":
        from hikyuu import ST_Saftyloss

        n1, n2, p = rules.saftyloss
        return ST_Saftyloss(int(n1), int(n2), float(p))
    return None


class _GoalPG(ProfitGoalBase):
    """止盈 + 最大持有天数组合盈利目标。

    通过 buy_notify/sell_notify 跟踪本系统（单票）的持仓状态；
    持有天数按自然日近似（内置 PG_FixedHoldDays 按交易日，两者同时
    启用时才走本组合实现）。

    pybind11 注意：hikyuu C++ 侧不持有 Python 子类对象的引用，对象被
    GC 后虚函数覆盖即丢失（表现为 pure virtual 调用错误），故模块级
    保活，与官方 crtPG 的 globals().update 规避方式一致。
    """

    _KEEPALIVE: list = []

    def __init__(self, take_profit: float, max_hold_days: int):
        super().__init__("GoalPG")
        self._tp = float(take_profit)
        self._max_days = int(max_hold_days)
        self._buy_price = 0.0
        self._buy_date = None
        _GoalPG._KEEPALIVE.append(self)

    def _clone(self):
        return _GoalPG(self._tp, self._max_days)

    def _calculate(self):
        """纯虚接口占位：状态在 buy_notify/get_goal 中维护。"""

    def _reset(self):
        self._buy_price = 0.0
        self._buy_date = None

    def buy_notify(self, trade):
        if trade.business == BUSINESS.BUY:
            self._buy_price = float(trade.real_price)
            self._buy_date = trade.datetime

    # 旧版绑定名兜底
    buyNotify = buy_notify

    def sell_notify(self, trade):
        self._buy_price = 0.0
        self._buy_date = None

    sellNotify = sell_notify

    def get_goal(self, datetime, price):
        if self._buy_price <= 0:
            return 0.0
        if self._tp > 0 and price >= self._buy_price * (1.0 + self._tp):
            return price  # 触及止盈价，按当前价离场
        if self._max_days > 0 and self._buy_date is not None:
            if (datetime - self._buy_date).days >= self._max_days:
                return price
        return 0.0

    # 旧版绑定名兜底
    getGoal = get_goal


def build_profit_goal(rules: SellRules):
    """按配置构建盈利目标组件。"""
    tp, md = rules.take_profit, rules.max_hold_days
    if tp and md:
        return _GoalPG(tp, md)
    if tp:
        from hikyuu import PG_FixedPercent

        return PG_FixedPercent(float(tp))
    if md:
        from hikyuu import PG_FixedHoldDays

        return PG_FixedHoldDays(int(md))
    return None


def build_signal(buy_cond, rules: SellRules | None = None):
    """构建 SG_Bool 信号：买入信号 + 卖出信号（信号失效 / 独立卖出条件取或）。"""
    from hikyuu import SG_Bool

    if rules is None or not rules.active():
        return SG_Bool(buy_cond, buy_cond == 0)

    parts = []
    if rules.sell_on_signal_exit:
        parts.append(buy_cond == 0)
    if rules.sell_cond is not None:
        parts.append(rules.sell_cond > 0)
    if not parts:
        # 无任何信号卖出 → 永不主动卖出，仅靠止损/止盈/持有天数离场
        parts.append(buy_cond * 0)
    sell = parts[0]
    for p in parts[1:]:
        sell = sell | p
    return SG_Bool(buy_cond, sell)
