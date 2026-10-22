"""自定义条件组合 DSL：界面配置的条件列表 → hikyuu Indicator 表达式。

条件格式（dict）：
{
    "left":  {"kind": "indicator", "name": "MA", "params": [5], "result": 0, "ref": 0}
            | {"kind": "const", "value": 20},
    "op":    ">=" | ">" | "<=" | "<" | "==" | "cross_above" | "cross_below",
    "right": 同 left,
}
多条件以 logic = "AND" / "OR" 组合，编译为 0/1 Indicator 序列。
"""
from hikyuu import (
    AVEDEV,
    CLOSE,
    CROSS,
    EMA,
    HHV,
    HHVBARS,
    HIGH,
    IF,
    LLV,
    LLVBARS,
    LOW,
    MA,
    OPEN,
    REF,
    ROC,
    RSI,
    SLOPE,
    SMA,
    STDEV,
    SUM,
    VOL,
)


def _bias(n=20):
    """乖离率% = (C - MA(C,n)) / MA(C,n) × 100。"""
    m = MA(CLOSE(), int(n))
    return (CLOSE() - m) / m * 100


def _wr(n=14):
    """威廉指标 = (HHV(H,n) - C) / (HHV(H,n) - LLV(L,n)) × 100（≥80 超卖）。"""
    hh = HHV(HIGH(), int(n))
    return (hh - CLOSE()) / (hh - LLV(LOW(), int(n))) * 100


def _cci(n=14):
    """CCI = (TP - MA(TP,n)) / (0.015 × AVEDEV(TP,n))，TP = (H+L+C)/3。"""
    tp = (HIGH() + LOW() + CLOSE()) / 3
    return (tp - MA(tp, int(n))) / (AVEDEV(tp, int(n)) * 0.015)


def _boll_up(n=20, k=2.0):
    return MA(CLOSE(), int(n)) + STDEV(CLOSE(), int(n)) * float(k)


def _boll_down(n=20, k=2.0):
    return MA(CLOSE(), int(n)) - STDEV(CLOSE(), int(n)) * float(k)


def _obv():
    """OBV：涨跌日成交量正/负累加（基础指标重建）。"""
    x = IF(
        CLOSE() > REF(CLOSE(), 1),
        VOL(),
        IF(CLOSE() < REF(CLOSE(), 1), 0 - VOL(), 0.0),
    )
    return SUM(x, 100000)


def _atr(n=14):
    """ATR：hikyuu 原生 ATR(n) 无 data 形式晚绑定求值全 NaN，用 TR 重建。

    TR = MAX(H-L, |H-REF(C,1)|, |L-REF(C,1)|)，ATR = MA(TR, n)
    """
    from hikyuu import ABS, MAX

    tr = MAX(
        HIGH() - LOW(),
        MAX(ABS(HIGH() - REF(CLOSE(), 1)), ABS(LOW() - REF(CLOSE(), 1))),
    )
    return MA(tr, int(n))


# 可在界面选择的操作数（指标名 -> 构建函数）
INDICATORS = {
    "CLOSE": (lambda: CLOSE(), "收盘价"),
    "OPEN": (lambda: OPEN(), "开盘价"),
    "HIGH": (lambda: HIGH(), "最高价"),
    "LOW": (lambda: LOW(), "最低价"),
    "VOL": (lambda: VOL(), "成交量"),
    "MA": (lambda n=5: MA(CLOSE(), int(n)), "均线(收盘价, n)"),
    "MA_VOL": (lambda n=5: MA(VOL(), int(n)), "均量线(n)"),
    "EMA": (lambda n=5: EMA(CLOSE(), int(n)), "指数均线(n)"),
    "HHV": (lambda n=20: HHV(CLOSE(), int(n)), "N日最高收盘价"),
    "LLV": (lambda n=20: LLV(CLOSE(), int(n)), "N日最低收盘价"),
    "RSI": (lambda n=14: RSI(CLOSE(), int(n)), "相对强弱指数 RSI(n)"),
    "ATR": (lambda n=14: _atr(n), "平均真实波幅 ATR(n)"),
    "ROC": (lambda n=10: ROC(CLOSE(), int(n)), "变动速率 ROC%(n)"),
    "STDEV": (lambda n=20: STDEV(CLOSE(), int(n)), "收盘价标准差(n)"),
    "SLOPE": (lambda n=5: SLOPE(CLOSE(), int(n)), "收盘价回归斜率(n)"),
    "BIAS": (lambda n=20: _bias(n), "乖离率%(n)"),
    "WR": (lambda n=14: _wr(n), "威廉指标 WR(n)"),
    "CCI": (lambda n=14: _cci(n), "顺势指标 CCI(n)"),
    "BOLL_MID": (lambda n=20: MA(CLOSE(), int(n)), "BOLL 中轨(n)"),
    "BOLL_UP": (lambda n=20, k=2.0: _boll_up(n, k), "BOLL 上轨(n,k)"),
    "BOLL_DOWN": (lambda n=20, k=2.0: _boll_down(n, k), "BOLL 下轨(n,k)"),
    "OBV": (lambda: _obv(), "能量潮 OBV"),
    "OBV_MA": (lambda n=30: MA(_obv(), int(n)), "OBV 均线(n)"),
    "HHVBARS": (lambda n=60: HHVBARS(CLOSE(), int(n)), "距N日高点周期数"),
    "LLVBARS": (lambda n=60: LLVBARS(CLOSE(), int(n)), "距N日低点周期数"),
    "MACD_DIF": (
        # 多结果指标 get_result 子序列晚绑定会全 NaN，用 EMA 重建标准公式
        lambda fast=12, slow=26, signal=9: EMA(CLOSE(), int(fast)) - EMA(CLOSE(), int(slow)),
        "MACD DIF",
    ),
    "MACD_DEA": (
        lambda fast=12, slow=26, signal=9: EMA(
            EMA(CLOSE(), int(fast)) - EMA(CLOSE(), int(slow)), int(signal)
        ),
        "MACD DEA",
    ),
    "KDJ_K": (
        lambda n=9, m1=3, m2=3: SMA(
            (CLOSE() - LLV(LOW(), int(n))) / (HHV(HIGH(), int(n)) - LLV(LOW(), int(n))) * 100,
            int(m1), 1,
        ),
        "KDJ K 值",
    ),
    "KDJ_D": (
        lambda n=9, m1=3, m2=3: SMA(
            SMA(
                (CLOSE() - LLV(LOW(), int(n))) / (HHV(HIGH(), int(n)) - LLV(LOW(), int(n))) * 100,
                int(m1), 1,
            ),
            int(m2), 1,
        ),
        "KDJ D 值",
    ),
    "KDJ_J": (
        # J = 3K - 2D；同样用基础指标 SMA 重建（不能用多结果指标的 get_result，
        # 晚绑定求值会全 NaN），与 KDJ_K/D 同源一致
        lambda n=9, m1=3, m2=3: (
            3 * SMA(
                (CLOSE() - LLV(LOW(), int(n))) / (HHV(HIGH(), int(n)) - LLV(LOW(), int(n))) * 100,
                int(m1), 1,
            )
            - 2 * SMA(
                SMA(
                    (CLOSE() - LLV(LOW(), int(n))) / (HHV(HIGH(), int(n)) - LLV(LOW(), int(n))) * 100,
                    int(m1), 1,
                ),
                int(m2), 1,
            )
        ),
        "KDJ J 值",
    ),
}

OPERATORS = {
    ">": ("大于", lambda a, b: a > b),
    ">=": ("大于等于", lambda a, b: a >= b),
    "<": ("小于", lambda a, b: a < b),
    "<=": ("小于等于", lambda a, b: a <= b),
    "==": ("等于", lambda a, b: a == b),
    "between": ("介于(含边界)", lambda a, b: (a >= b[0]) & (a <= b[1])),
    "cross_above": ("上穿", lambda a, b: CROSS(a, b)),
    "cross_below": ("下穿", lambda a, b: CROSS(b, a)),
}


def build_operand(spec: dict):
    """构建单个操作数（Indicator 或常量）。"""
    if spec["kind"] == "const":
        v = spec["value"]
        if isinstance(v, (list, tuple)):  # between 运算符的上下界
            return tuple(float(x) for x in v)
        return float(v)
    name = spec["name"]
    if name not in INDICATORS:
        raise ValueError(f"不支持的指标: {name}")
    fn, _ = INDICATORS[name]
    ind = fn(*spec.get("params", []))
    result_idx = int(spec.get("result", 0))
    if result_idx:
        ind = ind.get_result(result_idx)
    ref = int(spec.get("ref", 0))
    if ref:
        ind = REF(ind, ref)
    return ind


def compile_conditions(conditions: list[dict], logic: str = "AND"):
    """把条件列表编译为 0/1 Indicator 序列。"""
    if not conditions:
        raise ValueError("至少需要一个条件")
    expr = None
    for c in conditions:
        left = build_operand(c["left"])
        right = build_operand(c["right"])
        op = c["op"]
        if op not in OPERATORS:
            raise ValueError(f"不支持的算子: {op}")
        item = OPERATORS[op][1](left, right)
        if expr is None:
            expr = item
        elif logic == "OR":
            expr = expr | item
        else:
            expr = expr & item
    return expr


def describe(spec: dict) -> str:
    """生成条件的可读描述（用于界面显示）。"""
    def _op_desc(o):
        if o["kind"] == "const":
            v = o["value"]
            if isinstance(v, (list, tuple)):
                return f"{v[0]} ~ {v[1]}"
            return str(v)
        base = o["name"]
        params = o.get("params") or []
        if params:
            base += "(" + ",".join(str(p) for p in params) + ")"
        if o.get("ref"):
            base += f"[前{o['ref']}日]"
        return base

    op_text = OPERATORS.get(spec["op"], (spec["op"],))[0]
    return f"{_op_desc(spec['left'])} {op_text} {_op_desc(spec['right'])}"
