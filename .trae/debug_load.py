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
s = sm["sh600036"]
print("valid:", s.valid)
print("type:", s.type)
print("last_datetime:", s.last_datetime)
print("get_count DAY:", s.get_count("DAY"))
print("[attr]", [m for m in dir(s) if "count" in m.lower() or "load" in m.lower()])

# 直接检查副本 h5
import tables

f = tables.open_file("/tmp/hky_verify/sh_day.h5")
print("h5 tables:", len(f.root.data._v_children) if hasattr(f.root, "data") else "no /data")
print("SH600036 in h5:", "/data/SH600036" in f)
if "/data/SH600036" in f:
    t = f.get_node("/data", "SH600036")
    print("rows:", t.nrows, "first:", t[0]["datetime"], "last:", t[t.nrows - 1]["datetime"])
f.close()

# ini 内容
print(open("/tmp/hky_verify/hikyuu.ini").read())
