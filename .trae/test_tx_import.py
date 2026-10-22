import sqlite3
import sys
import time

sys.path.insert(0, "/home/fu/stock-slector")

from hikyuu.data.common_h5 import open_h5file

from hikyuudata.initializer import DATA_DIR, get_db_path
from hikyuudata.tencent_kline import import_one_stock

conn = sqlite3.connect(get_db_path())
codes = [("SH", "600000"), ("SH", "600036"), ("SH", "600519"),
         ("SZ", "000001"), ("SZ", "300750")]
t_all = time.time()
for market, code in codes:
    marketid = 1 if market == "SH" else 2
    sid, = conn.execute(
        "select stockid from stock where marketid=? and code=?",
        (marketid, code)).fetchone()
    h5 = open_h5file(str(DATA_DIR), market, "DAY")
    t0 = time.time()
    n = import_one_stock(h5, conn, market, code, sid)
    h5.close()
    print(f"{market}{code}: 新增 {n} ({time.time()-t0:.2f}s)", flush=True)
print(f"合计 {time.time()-t_all:.2f}s")

# 增量路径耗时
h5 = open_h5file(str(DATA_DIR), "SH", "DAY")
t0 = time.time()
n = import_one_stock(h5, conn, "SH", "600000", 2)
h5.close()
print(f"增量重复导入: 新增 {n} ({time.time()-t0:.2f}s)")

# 数据抽查
import tables
f = tables.open_file(str(DATA_DIR / "sh_day.h5"))
t = f.get_node("/data", "SH600036")
print("SH600036 行数:", t.nrows, "首:", t[0]["datetime"], "末:", t[t.nrows - 1]["datetime"])
r = t[t.nrows - 1]
print("末行 o/h/l/c/a/v:", r["openPrice"], r["highPrice"], r["lowPrice"],
      r["closePrice"], r["transAmount"], r["transCount"])
f.close()
conn.close()
