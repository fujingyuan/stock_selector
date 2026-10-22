import sys

sys.path.insert(0, "/home/fu/stock-slector")

import hikyuu

hikyuu.load_hikyuu(
    config_file="/tmp/hky_verify/hikyuu.ini",
    stock_list=["all"], ktype_list=["day"], load_history_finance=False,
    load_weight=True, start_spot=False,
)
sm = hikyuu.StockManager.instance()
from hikyuu import Query

stocks = [sm[c] for c in ["sh600036", "sz000001", "sh600519"]]
print("标的:", [(s.market_code, len(s.get_kdata(Query(-1)))) for s in stocks])

from strategy.builtin import build_condition
from backtest.runner import backtest_portfolio, performance_summary

cond = build_condition("ma_golden_cross")
r = backtest_portfolio(cond, stocks, days=500, init_cash=300000, n=100)
key_rows, report = performance_summary(r)
print("组合交易笔数:", len(r["trades"]))
for k, v in key_rows:
    print(f"  {k}: {v}")
print(r["trades"].tail(5).to_string())
