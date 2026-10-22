"""行情/财务数据导入（hikyuu 2.5.x API）。

导入顺序（与 hikyuu 官方 GUI 导入任务一致）：
1. create_database        建库
2. import_new_holidays    休假日历
3. import_index_name      指数代码表
4. import_stock_name      股票代码表（基础信息，网络源）
5. import_kdata           日K线（tencent_kline 模块，逐股票自动增量；不含北交所）
6. pytdx_import_weight_to_sqlite    权息数据（pytdx 协议正常）
7. import_finance         财务快照（腾讯行情源，见 em_finance 模块）
8. em_import_block_to_sqlite        板块（东方财富）

数据源说明（2026-10 实测）：
- pytdx 服务器对 K线/报价/财务快照类请求返回空存根或乱值，
  仅 get_xdxr_info（权息）正常
- 东方财富 HTTP 接口按 IP 限频严格（板块低频请求可用）
- 腾讯 web.ifzq.gtimg.cn（日K线）与 qt.gtimg.cn（行情快照）快且稳 → 采用

注意：必须在本模块顶部先导入 hikyuu（其 C++ 扩展需静态 TLS），再导入 pytdx，
否则 glibc 报 "cannot allocate memory in static TLS block"。
"""
import sqlite3

from hikyuu.data.common_sqlite3 import create_database, import_new_holidays
from hikyuu.data.em_block_to_sqlite import em_import_block_to_sqlite
from hikyuu.data.pytdx_to_h5 import import_index_name, import_stock_name
from hikyuu.data.pytdx_weight_to_sqlite import pytdx_import_weight_to_sqlite
from pytdx.hq import TdxHq_API

from . import tencent_kline
from .initializer import DATA_DIR, ensure_config, get_db_path

# pytdx 服务器列表（权息/财务协议用，2026-10 实测可连通的）
SERVERS = [
    ("115.238.56.198", 7709),
    ("180.153.18.170", 7709),
    ("124.71.187.122", 7709),
    ("60.191.117.167", 7709),
    ("110.41.147.114", 7709),
    ("119.97.185.59", 7709),
    ("218.75.126.9", 7709),
    ("115.238.90.165", 7709),
    ("60.12.136.250", 7709),
]

MARKETS = ["SH", "SZ", "BJ"]
QUOTATIONS = ["stock"]


def connect_api(timeout: int = 10) -> TdxHq_API:
    """连接可用的 pytdx 行情服务器（先用 best_ip 优选，失败则轮换备选）。

    除连通性外还探测权息接口（部分劣质服务器对 xdxr 返回 None，
    会导致官方权息导入崩溃）。
    """
    candidates = list(SERVERS)
    try:
        from pytdx.util.best_ip import select_best_ip

        best = select_best_ip("hq")
        ip, port = best["ip"], int(best["port"])
        if (ip, port) not in candidates:
            candidates.insert(0, (ip, port))
    except Exception:
        pass

    last_err = None
    for ip, port in candidates:
        api = TdxHq_API(heartbeat=True, auto_retry=True)
        try:
            if not api.connect(ip, port, time_out=timeout):
                continue
            # 权息探针：招商银行必有权息记录
            probe = api.get_xdxr_info(1, "600036")
            if probe:
                return api
            last_err = RuntimeError(f"{ip}:{port} 权息探针返回空")
        except Exception as e:  # noqa: BLE001
            last_err = e
        finally:
            api.disconnect()
    raise RuntimeError(f"无法连接任何可用的行情服务器: {last_err}")


def _get_conn() -> sqlite3.Connection:
    ensure_config()
    return sqlite3.connect(get_db_path(), timeout=1800)


def import_base_info(progress=print) -> None:
    """建库 + 休假日历 + 指数/股票代码表。"""
    conn = _get_conn()
    create_database(conn)
    progress("导入交易所休假日历 ...")
    import_new_holidays(conn)
    count = import_index_name(conn)
    progress(f"指数代码表: {count}")

    api = connect_api()
    try:
        for market in MARKETS:
            count = import_stock_name(conn, api, market, QUOTATIONS)
            progress(f"{market} 新增股票数: {count}")
    finally:
        api.disconnect()
    conn.close()
    progress("基础信息导入完成")


def import_kdata(progress=print, start_date: str = "2024-01-01",
                 backfill: bool = False) -> None:
    """导入/更新日K线（腾讯源，逐股票按库内最后日期自动增量）。

    :param start_date: 首次导入起始日期（仅对无数据的股票生效）
    :param backfill: 历史回补模式（全历史重取，把短历史扩充为自 start_date
                     起的完整历史；已完整的股票自动跳过，重复执行安全）
    不含北交所（腾讯 K 线接口不支持，stock 表中 BJ 记录保持无效）。
    """
    def _p(cur, total):
        progress(f"日K线 {cur}/{total}")

    count, skipped = tencent_kline.import_kdata_tencent(
        start_date=start_date, progress=_p, backfill=backfill)
    progress(f"K线数据导入完成，新增记录 {count}，跳过 {skipped} 只（重复执行可续）")


def import_weight(progress=print) -> None:
    """导入权息数据（分红送配，pytdx 协议正常）。"""
    api = connect_api()
    try:
        # 部分股票/服务器对 xdxr 返回 None（官方代码不兼容），统一兜底为空列表
        orig_get_xdxr = TdxHq_API.get_xdxr_info

        def _get_xdxr(self, market, code):
            return orig_get_xdxr(self, market, code) or []

        TdxHq_API.get_xdxr_info = _get_xdxr
        try:
            conn = _get_conn()
            for market in MARKETS:
                progress(f"导入 {market} 权息数据 ...")
                pytdx_import_weight_to_sqlite(api, conn, market)
            conn.close()
        finally:
            TdxHq_API.get_xdxr_info = orig_get_xdxr
    finally:
        api.disconnect()
    progress("权息数据导入完成")


def import_finance(progress=print) -> None:
    """导入财务快照（PE/PB/市值/ROE，腾讯行情源）。"""
    from . import em_finance

    def _p(cur, total):
        progress(f"财务快照 {cur}/{total}")

    count = em_finance.import_finance_tencent(progress=_p)
    progress(f"财务快照导入完成，更新 {count} 只")


def import_blocks(progress=print) -> None:
    """导入板块分类信息（东方财富源）。"""
    from hikyuu.data.common import MARKETID

    conn = _get_conn()
    id_to_market = {v: k for k, v in vars(MARKETID).items() if not k.startswith("_")}
    rows = conn.execute(
        "SELECT marketid, code FROM stock WHERE valid = 1"
    ).fetchall()
    code_market_dict = {
        code: id_to_market.get(mid, "SH") for mid, code in rows
    }
    progress(f"导入板块信息（东方财富），股票数 {len(code_market_dict)} ...")
    em_import_block_to_sqlite(conn, code_market_dict)
    conn.close()
    progress("板块信息导入完成")


def import_all(progress=print) -> None:
    """首次全量导入：基础信息 + K线 + 权息。"""
    import_base_info(progress)
    import_kdata(progress)
    import_weight(progress)
    progress("全量导入全部完成")


def update_all(progress=print) -> None:
    """日常增量更新：基础信息 + K线 + 权息（import_data 内部按最后日期续导）。"""
    import_all(progress)


def data_status() -> dict:
    """当前数据状态：股票数、h5 文件数、各表概况。"""
    db = get_db_path()
    status = {"db_exists": db.exists(), "stock_count": 0, "h5_files": 0, "tables": {}}
    if not db.exists():
        return status
    conn = sqlite3.connect(db, timeout=60)
    try:
        status["stock_count"] = conn.execute(
            "SELECT COUNT(*) FROM stock WHERE valid = 1"
        ).fetchone()[0]
        for table in ("stock", "stockweight", "finance"):
            try:
                status["tables"][table] = conn.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0]
            except sqlite3.Error:
                status["tables"][table] = None
    finally:
        conn.close()
    status["h5_files"] = len(list(DATA_DIR.glob("*.h5")))
    return status
