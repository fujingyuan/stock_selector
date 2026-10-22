"""腾讯行情快照因子数据（估值/规模/动量/活跃度）导入与查询。

背景：pytdx get_finance_info 在当前可用服务器上返回乱值（字段错乱），
东方财富 clist 快照接口限流严格。腾讯 qt.gtimg.cn 行情串稳定可用：
- 一次请求可带 ~60 只代码，全市场约 90 个请求
- 字段：[3]现价 [32]涨跌幅% [37]成交额(万) [38]换手率% [39]PE(TTM)
        [43]振幅% [44]流通市值(亿) [45]总市值(亿) [46]PB [47]涨停价
        [48]跌停价 [49]量比 [52]PE(动态) [53]PE(静态)
- ROE 由 PB/PE×100 推导（ROE = PB/PE，等价于 E/B）
- 行业来自 hikyuu 板块文件 block/hybk.ini（本地解析，无网络请求）

存储：独立 sqlite（DATA_DIR/finance_em.db 表 finance），不污染 hikyuu 库。
"""
import re
import sqlite3
import time
from functools import lru_cache

import requests

from hikyuu.data.common import MARKETID, STOCKTYPE

from .initializer import DATA_DIR

URL = "https://qt.gtimg.cn/q="
CHUNK = 60  # 每次请求代码数
FIELD_PCT = 32  # 涨跌幅%
FIELD_AMOUNT = 37  # 成交额（万）
FIELD_TURNOVER = 38  # 换手率%
FIELD_PE = 39
FIELD_AMPLITUDE = 43  # 振幅%
FIELD_LIUTONG_CAP = 44  # 流通市值（亿）
FIELD_CAP = 45  # 总市值（亿）
FIELD_PB = 46
FIELD_LIMIT_UP = 47  # 涨停价
FIELD_LIMIT_DOWN = 48  # 跌停价
FIELD_VOLRATIO = 49  # 量比
FIELD_PE_DYN = 52  # PE(动态)
FIELD_PE_STATIC = 53  # PE(静态)

_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Referer": "https://gu.qq.com/",
})

_line_re = re.compile(r'v_(?:sh|sz|bj)(\d{6})="([^"]*)"')


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DATA_DIR / "finance_em.db", timeout=60)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS finance (
                market_code TEXT PRIMARY KEY,
                code TEXT NOT NULL,
                market TEXT NOT NULL,
                name TEXT,
                close REAL,
                pe REAL,
                pb REAL,
                roe REAL,
                market_cap REAL,
                liutong_cap REAL,
                change_pct REAL,
                turnover REAL,
                amplitude REAL,
                vol_ratio REAL,
                amount_yi REAL,
                pe_static REAL,
                pe_dyn REAL,
                limit_up REAL,
                limit_down REAL,
                updated_at TEXT NOT NULL
            )
            """
        )
        # 旧库迁移：补新增因子列
        cols = {r[1] for r in conn.execute("PRAGMA table_info(finance)").fetchall()}
        for col in ("change_pct", "turnover", "amplitude", "vol_ratio",
                    "amount_yi", "pe_static", "pe_dyn", "limit_up", "limit_down"):
            if col not in cols:
                conn.execute(f"ALTER TABLE finance ADD COLUMN {col} REAL")


def _a_stock_codes(conn: sqlite3.Connection) -> list[tuple[str, str, str]]:
    """[(market_code, market, code)]，仅 A 股（排除指数/基金/债券）。"""
    types = ",".join(
        str(t) for t in (STOCKTYPE.A, STOCKTYPE.GEM, STOCKTYPE.START, STOCKTYPE.A_BJ)
    )
    out = []
    for mid, market in ((MARKETID.SH, "SH"), (MARKETID.SZ, "SZ")):
        rows = conn.execute(
            f"select code from stock where marketid={mid} and type in ({types})"
        ).fetchall()
        out.extend((f"{market.lower()}{code}", market, code) for (code,) in rows)
    return out


def _parse_chunk(text: str) -> dict[str, dict]:
    """解析 qt.gtimg.cn 响应 → {sh600036: {...}}。"""
    out = {}
    for m in _line_re.finditer(text):
        code, body = m.group(1), m.group(2)
        parts = body.split("~")
        if len(parts) <= FIELD_PB:
            continue
        try:
            close = float(parts[3])
            pe = float(parts[FIELD_PE]) if parts[FIELD_PE] not in ("", "0.00") else None

            def _f(idx: int):
                try:
                    v = float(parts[idx])
                    return v if v == v else None
                except (ValueError, IndexError):
                    return None

            pb = _f(FIELD_PB)
            pct = _f(FIELD_PCT)
            turnover = _f(FIELD_TURNOVER)
            amp = _f(FIELD_AMPLITUDE)
            vr = _f(FIELD_VOLRATIO)
            cap = _f(FIELD_CAP)
            lcap = _f(FIELD_LIUTONG_CAP)
            amount_wan = _f(FIELD_AMOUNT)
            limit_up = _f(FIELD_LIMIT_UP)
            limit_down = _f(FIELD_LIMIT_DOWN)
            pe_dyn = _f(FIELD_PE_DYN)
            pe_static = _f(FIELD_PE_STATIC)
        except ValueError:
            continue
        if close <= 0:
            continue
        roe = (pb / pe * 100) if (pb and pe) else None
        out[code] = {
            "name": parts[1],
            "close": close,
            "pe": pe,
            "pb": pb,
            "roe": roe,
            "market_cap": cap,  # 亿元
            "liutong_cap": lcap,  # 亿元
            "change_pct": pct,  # 当日涨跌幅%
            "turnover": turnover,  # 换手率%
            "amplitude": amp,  # 当日振幅%
            "vol_ratio": vr,  # 量比
            "amount_yi": (amount_wan / 10000) if amount_wan else None,  # 成交额(亿)
            "pe_static": pe_static,
            "pe_dyn": pe_dyn,
            "limit_up": limit_up,
            "limit_down": limit_down,
        }
    return out


def import_finance_tencent(progress=None) -> int:
    """导入/更新全市场财务快照（腾讯行情源）。返回更新股票数。"""
    from .initializer import get_db_path

    stock_conn = sqlite3.connect(get_db_path(), timeout=60)
    codes = _a_stock_codes(stock_conn)
    stock_conn.close()

    init_db()
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    total = len(codes)
    updated = 0
    for i in range(0, total, CHUNK):
        chunk = codes[i:i + CHUNK]
        joined = ",".join(c[0] for c in chunk)
        last_err = None
        parsed = {}
        for attempt in range(3):
            try:
                r = _session.get(URL + joined, timeout=10)
                r.encoding = "gbk"
                parsed = _parse_chunk(r.text)
                break
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(1.0 * (attempt + 1))
        if not parsed:
            if progress:
                progress(f"块 {i//CHUNK + 1} 失败: {last_err}")
            continue
        conn = get_conn()
        try:
            for market_code, market, code in chunk:
                info = parsed.get(code)
                if not info:
                    continue
                conn.execute(
                    "INSERT INTO finance(market_code, code, market, name, close,"
                    " pe, pb, roe, market_cap, liutong_cap,"
                    " change_pct, turnover, amplitude, vol_ratio,"
                    " amount_yi, pe_static, pe_dyn, limit_up, limit_down, updated_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
                    " ON CONFLICT(market_code) DO UPDATE SET name=?, close=?,"
                    " pe=?, pb=?, roe=?, market_cap=?, liutong_cap=?,"
                    " change_pct=?, turnover=?, amplitude=?, vol_ratio=?,"
                    " amount_yi=?, pe_static=?, pe_dyn=?, limit_up=?, limit_down=?,"
                    " updated_at=?",
                    (market_code, code, market, info["name"], info["close"],
                     info["pe"], info["pb"], info["roe"], info["market_cap"],
                     info["liutong_cap"], info["change_pct"], info["turnover"],
                     info["amplitude"], info["vol_ratio"], info["amount_yi"],
                     info["pe_static"], info["pe_dyn"], info["limit_up"],
                     info["limit_down"], now,
                     info["name"], info["close"], info["pe"], info["pb"],
                     info["roe"], info["market_cap"], info["liutong_cap"],
                     info["change_pct"], info["turnover"], info["amplitude"],
                     info["vol_ratio"], info["amount_yi"], info["pe_static"],
                     info["pe_dyn"], info["limit_up"], info["limit_down"], now),
                )
                updated += 1
            conn.commit()
        finally:
            conn.close()
        if progress:
            progress(min(i + CHUNK, total), total)
        time.sleep(0.3)
    return updated


@lru_cache(maxsize=1)
def _industry_map() -> dict[str, str]:
    """解析 hikyuu 板块文件 block/hybk.ini → {market_code(小写): 行业名}。

    文件格式：[行业名] 段，每行 "市场id,代码"（0=SH 1=SZ/BJ）。
    市场按代码前缀判定更稳：6 开头=sh，0/3=sz，4/8/920=bj。
    """
    path = DATA_DIR / "block" / "hybk.ini"
    out: dict[str, str] = {}
    if not path.exists():
        return out
    cur = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("[") and line.endswith("]"):
                cur = line[1:-1]
                continue
            if cur is None or "," not in line:
                continue
            _, code = line.split(",", 1)
            code = code.strip()
            if code.startswith("6"):
                mc = "sh" + code
            elif code.startswith(("0", "3")):
                mc = "sz" + code
            elif code.startswith(("4", "8", "920")):
                mc = "bj" + code
            else:
                continue
            out.setdefault(mc, cur)  # 一股多行业时取第一个
    return out


def load_all() -> dict[str, dict]:
    """全部财务快照 {sh600036: {...}}，附带行业与涨停标记派生字段。"""
    init_db()
    conn = get_conn()
    try:
        rows = {
            r["market_code"]: dict(r)
            for r in conn.execute("SELECT * FROM finance")
        }
    finally:
        conn.close()
    ind = _industry_map()
    for mc, d in rows.items():
        d["industry"] = ind.get(mc.lower(), "未知")
        limit_up = d.get("limit_up")
        close = d.get("close")
        d["limit_up_hit"] = (
            1.0 if (limit_up and close and close >= limit_up - 1e-6) else 0.0
        )
    return rows


def data_date() -> str | None:
    init_db()
    conn = get_conn()
    try:
        row = conn.execute("SELECT MAX(updated_at) FROM finance").fetchone()
        return row[0]
    finally:
        conn.close()
