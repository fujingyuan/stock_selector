import sys
import time

sys.path.insert(0, "/home/fu/stock-slector")

from hikyuudata.tencent_kline import _fetch_page, fetch_klines

t0 = time.time()
bars = _fetch_page("600036", "SH", "2026-10-17")
print(f"单页: {time.time()-t0:.2f}s n={len(bars)}")

t0 = time.time()
bars = _fetch_page("000651", "SZ", "2026-10-17")
print(f"单页2: {time.time()-t0:.2f}s n={len(bars)}")

t0 = time.time()
rows = fetch_klines("601318", "SH")
print(f"全历史7页: {time.time()-t0:.2f}s n={len(rows)}")
