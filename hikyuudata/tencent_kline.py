"""腾讯行情日K线导入（写入 hikyuu h5 格式）。

数据源选型（2026-10 实测，本机网络环境）：
- pytdx 服务器：K线/报价类请求返回空存根（权息 get_xdxr_info、财务
  get_finance_info 正常，见 importer.py）
- 东方财富 HTTP：按 IP 限频严格（持续请求即断连）
- baostock：服务端延迟波动大（2~35s/查询）且并发会挂起
- 腾讯 web.ifzq.gtimg.cn：最快最稳 → 采用（持续高频请求会限流，已做
  节奏控制：页间 0.2s、股票间 0.15s、快速重试、连续失败熔断）

注意事项：
- 接口不返回成交额，transAmount 用 vol×close 近似（约 0.2% 误差，技术
  指标计算不受影响）；transCount(手) 为精确值
- fq 段留空 = 不复权原始价，复权由 hikyuu 依据权息数据计算
- 代码前缀 sh/sz；北交所不支持（stock 表中 BJ 记录保持 valid=0）
- 两种导入模式：
  * 增量（默认）：只取库内最后日期之后的数据（追加，快）
  * 回补 backfill=True：全历史重取，若拉到比库内更早的数据则合并排序
    整表重写（PyTables 不支持前插）；已完整的股票自动跳过不重写

h5 结构与 hikyuu 官方导入完全一致（common_h5.H5Record）：
- 文件 {DATA_DIR}/{market}_day.h5，/data 组，表名如 SH600000
- 记录: datetime=yyyymmdd (UInt64)，价格×1000 (UInt32)，
        transAmount=千元 (UInt64)，transCount=手 (UInt64)
"""
import datetime
import sqlite3
import time

import requests
from hikyuu.data.common_h5 import get_h5table, open_h5file

from .initializer import DATA_DIR, get_db_path

URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
PAGE = 640  # 单页最大条数
PAGE_PAUSE = 0.5  # 翻页间隔（秒），避免触发限流
STOCK_PAUSE = 0.8  # 股票间隔（秒）
FAIL_THRESHOLD = 20  # 连续失败 N 只 → 触发冷却
COOLDOWN_WAIT = 180  # 冷却时长（秒）
MAX_COOLDOWNS = 60  # 每市场最多冷却次数（超过则放弃本轮）
BENCHMARK = {"SH": "000001", "SZ": "399001"}

_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Referer": "https://gu.qq.com/",
})


def _fetch_page(code: str, market: str, end_date: str, retries: int = 2) -> list:
    """取截至 end_date 的最近一页日K线（不复权）。"""
    symbol = f"{market.lower()}{code}"
    param = f"{symbol},day,,{end_date},{PAGE},"
    last_err = None
    for attempt in range(retries):
        try:
            r = _session.get(URL, params={"param": param}, timeout=10)
            j = r.json()
            if j.get("code") != 0:
                raise RuntimeError(f"腾讯接口返回错误: {j.get('msg')}")
            node = (j.get("data") or {}).get(symbol)
            if isinstance(node, dict):
                for key, val in node.items():
                    if "day" in key and isinstance(val, list):
                        return val
            return []
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(0.6 * (attempt + 1))
    raise RuntimeError(f"腾讯取K线失败 {symbol} end={end_date}: {last_err}")


def fetch_klines(code: str, market: str, beg: str = "2010-01-01") -> list[tuple]:
    """自 beg 起取全部日K线（向后翻页），返回
    [(datetime yyyymmdd, open, high, low, close, vol手)]，按日期升序。"""
    begd = datetime.date.fromisoformat(beg)
    end = datetime.date.today().isoformat()
    out: dict[str, tuple] = {}
    while True:
        bars = _fetch_page(code, market, end)
        for b in bars:
            if len(b) < 6 or b[0] in out:
                continue
            try:
                o, c, h, l, v = (float(b[1]), float(b[2]), float(b[3]),
                                 float(b[4]), float(b[5]))
            except ValueError:
                continue
            if o <= 0 or h <= 0 or l <= 0 or c <= 0 or h < l:
                continue
            out[b[0]] = (int(b[0].replace("-", "")), o, h, l, c, v)
        if not bars:
            break
        first = datetime.date.fromisoformat(bars[0][0])
        if first <= begd:
            break
        end = (first - datetime.timedelta(days=1)).isoformat()
        time.sleep(PAGE_PAUSE)
    return sorted(out.values())


def _update_stock_meta(conn: sqlite3.Connection, stockid: int,
                       market: str, code: str, table) -> None:
    """更新 sqlite 中该股票的 valid/startdate/enddate，及基准指数的 lastDate。"""
    cur = conn.cursor()
    cur.execute(
        "update stock set valid=1, startdate=%i, enddate=99999999 where stockid=%i"
        % (int(table[0]["datetime"]) // 10000, stockid)
    )
    if code == BENCHMARK.get(market):
        from hikyuu.data.common import MARKETID

        # hikyuu 官方 update_last_date 对整型 marketid 不生效（SQL 按字符串比较），直写
        cur.execute(
            "update Market set lastDate=%i where marketid=%i"
            % (int(table[table.nrows - 1]["datetime"]),
               getattr(MARKETID, market))
        )
    conn.commit()
    cur.close()


def _append_rows(table, rows: list[tuple]) -> int:
    """把 (dt,o,h,l,c,v) 升序序列写入 h5 表（dt 必须大于表内最后日期）。"""
    last = int(table[table.nrows - 1]["datetime"]) if table.nrows > 0 else 0
    added = 0
    for dt, o, h, l, c, v in rows:
        if dt <= last:
            continue
        row = table.row
        row["datetime"] = dt
        row["openPrice"] = round(o * 1000)
        row["highPrice"] = round(h * 1000)
        row["lowPrice"] = round(l * 1000)
        row["closePrice"] = round(c * 1000)
        row["transAmount"] = round(v * c / 10)
        row["transCount"] = round(v)
        row.append()
        added += 1
    table.flush()
    return added


def import_one_stock(h5file, conn: sqlite3.Connection, market: str, code: str,
                     stockid: int, beg: str = "2010-01-01",
                     backfill: bool = False) -> int:
    """导入单只股票日K线，返回新增记录数。

    backfill=False: 增量（只取库内最后日期之后，追加写）。
    backfill=True: 全历史重取；若拉到比库内更早的数据则合并排序整表重写。
    """
    table = get_h5table(h5file, market, code)
    last = int(table[table.nrows - 1]["datetime"]) if table.nrows > 0 else 0

    if not backfill and last > 0:
        d = datetime.date(last // 10000, last // 100 % 100, last % 100)
        beg = max(beg, (d + datetime.timedelta(days=1)).isoformat())
        if beg > datetime.date.today().isoformat():
            return 0

    klines = fetch_klines(code, market, beg=beg)
    if not klines:
        return 0

    old = {}
    if table.nrows > 0:
        old = {int(r["datetime"]): r for r in table.read()}

    # 回补场景：拉到的数据比库内更早 → 需要整表重写（前插）
    need_rewrite = bool(old) and klines[0][0] < min(old)
    if need_rewrite:
        new = {dt: (o, h, l, c, v) for dt, o, h, l, c, v in klines}
        merged = []
        for dt in sorted(set(old) | set(new)):
            if dt in new:
                merged.append((dt, *new[dt]))
            else:
                r = old[dt]
                merged.append((
                    dt, r["openPrice"] / 1000.0, r["highPrice"] / 1000.0,
                    r["lowPrice"] / 1000.0, r["closePrice"] / 1000.0,
                    int(r["transCount"]),
                ))
        added = len(new) - len(set(new) & set(old))
        table.remove()
        table = get_h5table(h5file, market, code)
        _append_rows(table, merged)
        _update_stock_meta(conn, stockid, market, code, table)
        return added

    # 追加路径（增量 + 无需重写的回补）
    added = _append_rows(table, klines)
    if table.nrows > 0:
        _update_stock_meta(conn, stockid, market, code, table)
    elif table.nrows == 0:
        table.remove()
    return added


def _a_share_sql(market: str) -> str:
    """查询市场内证券（A股 + 指数，与 hikyuu get_a_stktype_list 一致）。"""
    from hikyuu.data.common import MARKETID, get_a_stktype_list

    types = ",".join(str(t) for t in get_a_stktype_list())
    return (
        "select stockid, code from stock "
        f"where marketid={getattr(MARKETID, market)} and type in ({types})"
    )


def import_kdata_tencent(start_date: str = "2010-01-01", markets=("SH", "SZ"),
                         progress=None, backfill: bool = False) -> tuple[int, int]:
    """全量/增量导入日K线（腾讯源，逐股票按库内最后日期续导）。

    限流自愈：连续失败 FAIL_THRESHOLD 只 → 冷却 COOLDOWN_WAIT 秒后从
    失败股票重试；每市场冷却超 MAX_COOLDOWNS 次则放弃本轮（已导入的
    部分有效，重复执行可续）。

    :return: (新增记录数, 跳过的股票数)
    """
    conn = sqlite3.connect(get_db_path(), timeout=1800)
    total_added = 0
    total_skipped = 0
    try:
        for market in markets:
            stocks = conn.execute(_a_share_sql(market)).fetchall()
            total = len(stocks)
            h5file = open_h5file(str(DATA_DIR), market, "DAY")
            consecutive_fail = 0
            cooldowns = 0
            try:
                i = 0
                retried_code = None  # 冷却后重试中的股票，若再失败则跳过
                while i < len(stocks):
                    stockid, code = stocks[i]
                    try:
                        total_added += import_one_stock(
                            h5file, conn, market, code, stockid, start_date,
                            backfill=backfill)
                        consecutive_fail = 0
                    except Exception:  # noqa: BLE001 单票失败不中止
                        if retried_code == code:
                            # 冷却后该股仍失败：确属问题股，跳过
                            retried_code = None
                            consecutive_fail = 0
                            total_skipped += 1
                            i += 1
                            continue
                        consecutive_fail += 1
                        if consecutive_fail >= FAIL_THRESHOLD:
                            cooldowns += 1
                            if cooldowns > MAX_COOLDOWNS:
                                raise RuntimeError(
                                    f"{market} 冷却 {MAX_COOLDOWNS} 次后仍持续失败，"
                                    "疑似当日限流，放弃本轮（已导入部分有效）"
                                )
                            time.sleep(COOLDOWN_WAIT)
                            consecutive_fail = 0
                            retried_code = code
                            continue  # 原地重试当前股票
                        total_skipped += 1
                    retried_code = None
                    i += 1
                    if progress and (i % 10 == 0 or i == total):
                        progress(i, total)
                    time.sleep(STOCK_PAUSE)
            finally:
                h5file.close()
    finally:
        conn.close()
    return total_added, total_skipped
