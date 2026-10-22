import sys

sys.path.insert(0, "/home/fu/stock-slector")

import hikyuu

hikyuu.load_hikyuu(
    config_file="/tmp/hky_verify/hikyuu.ini",
    stock_list=["all"], ktype_list=["day"], load_history_finance=False,
    load_weight=True, start_spot=False,
)
from strategy.fundamental import scan_fundamental

rows = scan_fundamental(
    {"pe_max": 30, "market_cap_min": 100},
    progress=lambda cur, total: None,
)
print(f"基本面筛选命中 {len(rows)} 只:")
for r in rows[:10]:
    print(f"  {r['market_code']} {r['stock_name']} close={r['close']} {r['detail']}")
