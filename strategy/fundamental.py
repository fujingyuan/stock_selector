"""多因子筛选引擎：快照因子 × K线因子，支持 AND/OR 分组组合 + 技术面增强过滤。

因子分两类（kind）：
- snap : 腾讯行情快照（hikyuudata.em_finance 导入），全市场过滤零成本
- kline: K线衍生因子（strategy.kline_factors 现算），只对快照条件幸存股计算，
         避免全市场加载 K 线；组内无快照条件时退化为全市场 K 线扫描

分组语义：组内 AND、组间 OR（对标专业因子平台的分组筛选）。
例：(PE<30 且 ROE>15) 或 (PB<1 且 换手>2) → groups=[[cond,cond],[cond,cond]]

技术面增强（超越纯静态因子筛选）：分组筛完后，可再对结果集
逐股运行内置技术策略条件（金叉/突破/多头排列等），输出双筛结果。
"""
import json
from typing import Callable

from .kline_factors import KLINE_FACTOR_FUNCS, KlineFactorCalc, needed_window

# 因子注册表：key -> (中文名, 类别, 说明, kind)
FACTORS = {
    # ---- 快照：估值 ----
    "pe":          ("PE(TTM)", "估值", "越低越便宜", "snap"),
    "pe_static":   ("PE(静态)", "估值", "按上年报", "snap"),
    "pe_dyn":      ("PE(动态)", "估值", "按已披露季报年化", "snap"),
    "pb":          ("PB(市净率)", "估值", "越低越便宜", "snap"),
    "roe":         ("ROE(%)", "估值", "盈利质量（PB/PE 推导）", "snap"),
    # ---- 快照：规模 ----
    "market_cap":  ("总市值(亿)", "规模", "", "snap"),
    "liutong_cap": ("流通市值(亿)", "规模", "", "snap"),
    # ---- 快照：行情/活跃度 ----
    "change_pct":  ("当日涨跌幅(%)", "行情", "快照当日", "snap"),
    "turnover":    ("换手率(%)", "活跃度", "", "snap"),
    "amplitude":   ("当日振幅(%)", "活跃度", "", "snap"),
    "vol_ratio":   ("量比", "活跃度", ">1 即放量", "snap"),
    "amount_yi":   ("成交额(亿)", "活跃度", "", "snap"),
    "limit_up_hit": ("涨停", "行情", "1=收盘价涨停", "snap"),
    # ---- K线：动量 ----
    "ret_5d":      ("近5日涨跌幅(%)", "动量", "", "kline"),
    "ret_10d":     ("近10日涨跌幅(%)", "动量", "", "kline"),
    "ret_20d":     ("近20日涨跌幅(%)", "动量", "", "kline"),
    "ret_60d":     ("近60日涨跌幅(%)", "动量", "", "kline"),
    # ---- K线：趋势/均线 ----
    "ma_bull":     ("均线多头排列", "趋势", "1=MA5>MA10>MA20>MA60", "kline"),
    "ma20_bias":   ("MA20乖离(%)", "趋势", "收盘相对MA20偏离", "kline"),
    "ma60_bias":   ("MA60乖离(%)", "趋势", "收盘相对MA60偏离", "kline"),
    # ---- K线：MACD ----
    "macd_dif":    ("MACD DIF", "MACD", "", "kline"),
    "macd_dea":    ("MACD DEA", "MACD", "", "kline"),
    "macd_hist":   ("MACD柱", "MACD", "2×(DIF-DEA)", "kline"),
    "macd_gold":   ("MACD金叉", "MACD", "1=当日DIF上穿DEA", "kline"),
    "macd_above":  ("DIF零轴上方", "MACD", "1=DIF>0", "kline"),
    # ---- K线：KDJ ----
    "kdj_k":       ("KDJ K值", "KDJ", "", "kline"),
    "kdj_d":       ("KDJ D值", "KDJ", "", "kline"),
    "kdj_j":       ("KDJ J值", "KDJ", "3K-2D，<20超卖 >80超买", "kline"),
    "kdj_gold":    ("KDJ金叉", "KDJ", "1=当日K上穿D", "kline"),
    # ---- K线：RSI ----
    "rsi6":        ("RSI6", "RSI", "<20超卖 >80超买", "kline"),
    "rsi12":       ("RSI12", "RSI", "", "kline"),
    "rsi24":       ("RSI24", "RSI", "", "kline"),
    # ---- K线：乖离/BOLL ----
    "bias6":       ("BIAS6(%)", "乖离", "收盘相对MA6偏离", "kline"),
    "bias12":      ("BIAS12(%)", "乖离", "", "kline"),
    "bias24":      ("BIAS24(%)", "乖离", "", "kline"),
    "boll_pos":    ("BOLL位置(%)", "BOLL", "0=下轨 100=上轨", "kline"),
    "boll_break":  ("突破BOLL上轨", "BOLL", "1=收盘>上轨", "kline"),
    # ---- K线：形态 ----
    "up_days":     ("连续阳线天数", "形态", "收阳连续天数", "kline"),
    "vol_up_days": ("连续放量天数", "形态", "", "kline"),
    "vol_down_days": ("连续缩量天数", "形态", "", "kline"),
    "new_high_60": ("创60日新高", "形态", "1=收盘为近60日最高", "kline"),
    # ---- K线：分位 ----
    "price_pct_1y": ("价格分位1年(%)", "分位", "近250日价格从低到高分位", "kline"),
    "price_pct_3y": ("价格分位3年(%)", "分位", "近750日价格从低到高分位", "kline"),
}

FACTOR_KEYS = tuple(FACTORS)
SNAP_KEYS = tuple(k for k, v in FACTORS.items() if v[3] == "snap")
_GROUP_ORDER = ("估值", "规模", "行情", "活跃度", "动量", "趋势", "MACD", "KDJ",
                "RSI", "乖离", "BOLL", "形态", "分位")


def factor_groups_for_ui() -> list[tuple[str, list[str]]]:
    """按类别分组的因子键，供 UI 下拉展示。"""
    groups: dict[str, list[str]] = {}
    for k, v in FACTORS.items():
        groups.setdefault(v[1], []).append(k)
    return [(g, groups[g]) for g in _GROUP_ORDER if g in groups]


OPS = {
    "gte": "≥", "lte": "≤", "gt": ">", "lt": "<", "eq": "=",
    "between": "介于(含边界)",
}


def _get(snap: dict, key: str):
    return snap.get(key)


def _judge(value, op: str, threshold) -> bool:
    """单条件判定；因子缺数据时一律淘汰（宁缺毋滥）。"""
    if value is None:
        return False
    if op == "gte":
        return value >= threshold
    if op == "lte":
        return value <= threshold
    if op == "gt":
        return value > threshold
    if op == "lt":
        return value < threshold
    if op == "eq":
        return value == threshold
    if op == "between":
        lo, hi = threshold
        return lo <= value <= hi
    raise ValueError(f"未知运算符: {op}")


# 精选预设（模仿专业因子平台的一键筛选策略）
PRESETS = {
    "价值低估": [
        {"factor": "pe", "op": "between", "value": [0, 20]},
        {"factor": "pb", "op": "between", "value": [0, 2]},
    ],
    "高ROE白马": [
        {"factor": "roe", "op": "gte", "value": 15},
        {"factor": "pe", "op": "between", "value": [0, 40]},
    ],
    "大盘蓝筹": [
        {"factor": "market_cap", "op": "gte", "value": 500},
        {"factor": "turnover", "op": "gte", "value": 0.3},
    ],
    "小盘活跃": [
        {"factor": "market_cap", "op": "between", "value": [0, 100]},
        {"factor": "turnover", "op": "gte", "value": 3},
    ],
    "放量异动": [
        {"factor": "vol_ratio", "op": "gte", "value": 2},
        {"factor": "turnover", "op": "gte", "value": 3},
    ],
    "今日强势": [
        {"factor": "change_pct", "op": "gte", "value": 3},
        {"factor": "turnover", "op": "gte", "value": 2},
    ],
    "破净稳健": [
        {"factor": "pb", "op": "between", "value": [0, 0.8]},
        {"factor": "roe", "op": "gte", "value": 5},
    ],
    "低波红利": [
        {"factor": "pe", "op": "between", "value": [0, 15]},
        {"factor": "pb", "op": "between", "value": [0, 1.5]},
        {"factor": "amplitude", "op": "lte", "value": 3},
    ],
    # ---- K线因子预设（技术面因子化，直接参与组合） ----
    "涨停放量": [
        {"factor": "limit_up_hit", "op": "eq", "value": 1},
        {"factor": "vol_ratio", "op": "gte", "value": 2},
    ],
    "KDJ低位金叉": [
        {"factor": "kdj_gold", "op": "eq", "value": 1},
        {"factor": "kdj_j", "op": "lte", "value": 20},
    ],
    "均线多头回踩": [
        {"factor": "ma_bull", "op": "eq", "value": 1},
        {"factor": "ma20_bias", "op": "between", "value": [-2, 1]},
    ],
    "底部反转": [
        {"factor": "price_pct_1y", "op": "lte", "value": 20},
        {"factor": "macd_gold", "op": "eq", "value": 1},
    ],
    "突破60日新高": [
        {"factor": "new_high_60", "op": "eq", "value": 1},
        {"factor": "turnover", "op": "gte", "value": 2},
    ],
}


def describe_conditions(conditions: list[dict]) -> str:
    """条件列表 → 人话描述，如 'PE(TTM) 0~20 且 PB(市净率) 0~2'。"""
    parts = []
    for c in conditions:
        label = FACTORS[c["factor"]][0]
        v = c["value"]
        if c["op"] == "between":
            parts.append(f"{label} {v[0]:g}~{v[1]:g}")
        else:
            parts.append(f"{label} {OPS[c['op']]} {v:g}")
    return " 且 ".join(parts)


def describe_groups(groups: list[list[dict]]) -> str:
    """分组 → 人话描述：'(A 且 B) 或 (C 且 D)'。"""
    return " 或 ".join(f"（{describe_conditions(g)}）" for g in groups if g)


def scan_factors(
    conditions: list[dict] | None = None,
    *,
    groups: list[list[dict]] | None = None,
    boards=None,
    exclude_st: bool = True,
    tech_filter: dict | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> list[dict]:
    """多因子组合扫描全市场（组内 AND、组间 OR）。

    :param conditions: [{factor, op, value}]，单组 AND（旧用法，等价 groups=[conditions]）
    :param groups: [[cond, ...], ...]，多组 OR
    :param boards: 板块过滤（None=全部）
    :param exclude_st: 剔除 ST/退市
    :param tech_filter: 技术面增强 {"name": 内置策略名, "params": {...}}；
        对因子筛选结果再跑 K 线条件（取条件序列最新一根为真才保留）
    :return: [{market_code, stock_code, stock_name, close, change_pct, detail}]
        detail 含快照因子值 + 行业 + 板块 + 命中的 K线因子值
    """
    from hikyuudata import em_finance
    from selector.scanner import stock_board

    import store

    if groups is None:
        groups = [conditions or []]
    groups = [[c for c in g if c] for g in groups if g]
    if not groups:
        raise ValueError("请至少配置一个筛选条件")

    snapshots = em_finance.load_all()
    if not snapshots:
        raise RuntimeError(
            "因子快照为空，请先在「数据管理」页执行「导入财务快照」")

    boards = tuple(boards) if boards is not None else None
    total = len(snapshots)

    # 全部组用到的 K线因子（共享一个计算器，K线窗口取并集）
    all_kline_keys = {
        c["factor"] for g in groups for c in g
        if FACTORS[c["factor"]][3] == "kline" and c["factor"] in KLINE_FACTOR_FUNCS
    }
    calc = (KlineFactorCalc(sorted(all_kline_keys), needed_window(all_kline_keys))
            if all_kline_keys else None)

    hits: dict[str, dict] = {}  # market_code -> row（组间 OR 去重）
    for i, (market_code, snap) in enumerate(sorted(snapshots.items()), 1):
        if boards is not None and stock_board(snap["market"], snap["code"]) not in boards:
            continue
        if exclude_st and ("ST" in (snap["name"] or "") or "退" in (snap["name"] or "")):
            continue

        snap_detail = None  # 首次需要时构造
        kline_vals = None  # 首次需要时计算（同股多组复用）
        for g in groups:
            snap_conds = [c for c in g if FACTORS[c["factor"]][3] == "snap"]
            kline_conds = [c for c in g if FACTORS[c["factor"]][3] == "kline"]
            if not all(_judge(_get(snap, c["factor"]), c["op"], c["value"])
                       for c in snap_conds):
                continue  # 组内快照条件不满足 → 本组出局
            if kline_conds:
                if calc is None:
                    continue  # 未知 K线因子，安全起见不命中
                if kline_vals is None:
                    kline_vals = calc.values(market_code)
                if not all(_judge(kline_vals.get(c["factor"]), c["op"], c["value"])
                           for c in kline_conds):
                    continue
            # 本组命中（OR 语义：任一组命中即入选）
            if snap_detail is None:
                snap_detail = {k: snap.get(k) for k in SNAP_KEYS}
                snap_detail["行业"] = snap.get("industry", "未知")
                snap_detail["板块"] = stock_board(snap["market"], snap["code"])
            detail = dict(snap_detail)
            if kline_vals is not None:
                detail.update({k: round(v, 4) if isinstance(v, float) else v
                               for k, v in kline_vals.items() if v is not None})
            hits[market_code.upper()] = {
                "market_code": market_code.upper(),
                "stock_code": snap["code"],
                "stock_name": snap["name"],
                "close": snap["close"],
                "change_pct": snap.get("change_pct"),
                "detail": json.dumps(detail, ensure_ascii=False),
            }
            break  # 已命中，无需再判其它组

        if progress and (i % 200 == 0 or i == total):
            progress(i, total)

    rows = list(hits.values())

    # 技术面增强过滤（对结果集逐股跑内置策略 K 线条件）
    if tech_filter and rows:
        rows = _apply_tech_filter(rows, tech_filter, progress)

    if rows:
        store.save_scan_result("factor", rows)
    return rows


def _apply_tech_filter(rows: list[dict], tech_filter: dict, progress=None) -> list[dict]:
    """对因子筛选结果逐股运行内置策略条件，保留最新一根 K 线条件为真的股票。"""
    from strategy.builtin import build_condition

    cond = build_condition(tech_filter["name"], **(tech_filter.get("params") or {}))

    from hikyuu import Query

    from hikyuudata.initializer import get_sm

    sm = get_sm()
    out = []
    total = len(rows)
    for i, row in enumerate(rows, 1):
        try:
            stk = sm[row["market_code"].lower()]
            if not (stk and stk.valid):
                continue
            kd = stk.get_kdata(Query(-120, ktype=Query.DAY,
                                     recover_type=Query.EQUAL_FORWARD))
            if len(kd) < 30:
                continue
            vals = cond(kd)
            last = vals[len(vals) - 1]
            if last == last and last:  # NaN 防护
                out.append(row)
        except Exception:  # noqa: BLE001 数据缺失/停牌等，跳过
            continue
        if progress and (i % 200 == 0 or i == total):
            progress(i, total)
    return out


# ---------- 兼容旧接口 ----------
FILTERS = {
    "pe_max": ("市盈率上限", lambda s, v: s["pe"] is not None and s["pe"] <= v),
    "pe_min": ("市盈率下限", lambda s, v: s["pe"] is not None and s["pe"] >= v),
    "pb_max": ("市净率上限", lambda s, v: s["pb"] is not None and s["pb"] <= v),
    "market_cap_max": ("总市值上限(亿)", lambda s, v: s["market_cap"] and s["market_cap"] <= v),
    "market_cap_min": ("总市值下限(亿)", lambda s, v: s["market_cap"] and s["market_cap"] >= v),
    "liutong_cap_max": ("流通市值上限(亿)", lambda s, v: s["liutong_cap"] and s["liutong_cap"] <= v),
    "liutong_cap_min": ("流通市值下限(亿)", lambda s, v: s["liutong_cap"] and s["liutong_cap"] >= v),
    "roe_min": ("ROE下限(%)", lambda s, v: s["roe"] is not None and s["roe"] >= v),
}


def scan_fundamental(conditions: dict, **kwargs) -> list[dict]:
    """旧接口兼容：{条件名: 阈值} → 新多因子引擎。"""
    name2factor = {
        "pe_max": ("pe", "lte"), "pe_min": ("pe", "gte"),
        "pb_max": ("pb", "lte"),
        "market_cap_max": ("market_cap", "lte"), "market_cap_min": ("market_cap", "gte"),
        "liutong_cap_max": ("liutong_cap", "lte"), "liutong_cap_min": ("liutong_cap", "gte"),
        "roe_min": ("roe", "gte"),
    }
    conds = [
        {"factor": name2factor[k][0], "op": name2factor[k][1], "value": v}
        for k, v in conditions.items() if k in name2factor
    ]
    return scan_factors(conds, **kwargs)
