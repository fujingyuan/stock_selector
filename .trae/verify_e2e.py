"""端到端验证：选股扫描 + 回测（使用 /tmp/hky_verify 数据副本，避开导入进程的 h5 锁）。"""
import sys

sys.path.insert(0, "/home/fu/stock-slector")

import hikyuu

hikyuu.load_hikyuu(
    config_file="/tmp/hky_verify/hikyuu.ini",
    stock_list=["all"],
    ktype_list=["day"],
    load_history_finance=False,
    load_weight=True,
    start_spot=False,
)
sm = hikyuu.StockManager.instance()
from hikyuu import Query

stk = sm["sh600036"]
kd = stk.get_kdata(Query(-10))
print("sh600036 kdata:", len(kd), kd[-1] if len(kd) else "")

# 有数据的股票数
cnt = 0
codes = []
for s in sm.get_stock_list():
    if s.valid and s.get_kdata(Query(-1)).size() > 0:
        cnt += 1
        codes.append(s.market_code)
print("有K线数据的股票数:", cnt)

# ---- 扫描验证 ----
from strategy.builtin import build_condition

cond = build_condition("ma_golden_cross", short=5, long=20)
rows = []
for s in sm.get_stock_list():
    if not s.valid:
        continue
    k = s.get_kdata(Query(-120, ktype=Query.DAY, recover_type=Query.EQUAL_FORWARD))
    if k.empty():
        continue
    r = cond(k)
    if not r.empty() and r[-1] != 0:
        rows.append(s.market_code)
print("ma_golden_cross 选中:", rows[:20], f"(共{len(rows)})")

# ---- 单票回测验证 ----
from backtest.runner import backtest_single, performance_summary

stocks = [sm[c] for c in ["sh600036", "sz000001", "sh600519"] if sm[c].valid and sm[c].get_kdata(Query(-1)).size() > 0]
print("回测标的:", [s.market_code for s in stocks])
for s in stocks:
    c = build_condition("ma_golden_cross")
    r = backtest_single(c, s, days=500)
    key_rows, report = performance_summary(r)
    print(f"--- {s.market_code} {s.name} 交易 {len(r['trades'])} 笔")
    for k, v in key_rows[:5]:
        print(f"    {k}: {v}")
