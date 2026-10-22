"""选股/回测结果存储（sqlite）。"""
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "results.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scan_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                strategy TEXT NOT NULL,
                market_code TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                stock_name TEXT,
                close REAL,
                detail TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_scan_strategy_time "
            "ON scan_results(strategy, created_at)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS backtest_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                strategy TEXT NOT NULL,
                scope TEXT NOT NULL,
                query_start TEXT,
                query_end TEXT,
                summary TEXT,
                performance TEXT
            )
            """
        )


def save_scan_result(strategy: str, rows: list[dict]) -> None:
    """rows: [{market_code, stock_code, stock_name, close, detail}]"""
    init_db()
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        conn.executemany(
            "INSERT INTO scan_results(created_at, strategy, market_code, stock_code,"
            " stock_name, close, detail) VALUES (?,?,?,?,?,?,?)",
            [
                (
                    now,
                    strategy,
                    r["market_code"],
                    r["stock_code"],
                    r.get("stock_name", ""),
                    r.get("close"),
                    r.get("detail", ""),
                )
                for r in rows
            ],
        )


def latest_scan(strategy: str | None = None, limit: int = 200) -> list[dict]:
    init_db()
    sql = (
        "SELECT * FROM scan_results WHERE created_at = "
        "(SELECT MAX(created_at) FROM scan_results WHERE strategy = ? OR ? = '')"
    )
    params: tuple = (strategy or "", strategy or "")
    if strategy:
        sql = (
            "SELECT * FROM scan_results WHERE created_at = "
            "(SELECT MAX(created_at) FROM scan_results WHERE strategy = ?)"
        )
        params = (strategy,)
    sql += " ORDER BY stock_code LIMIT ?"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, (*params, limit))]


def distinct_scan_strategies() -> list[dict]:
    """有选股结果的策略名列表。"""
    init_db()
    with get_conn() as conn:
        return [
            {"strategy": r["strategy"], "count": r["c"]}
            for r in conn.execute(
                "SELECT strategy, COUNT(*) AS c FROM scan_results "
                "GROUP BY strategy ORDER BY MAX(created_at) DESC"
            )
        ]


def save_backtest_result(
    strategy: str, scope: str, q_start: str, q_end: str, summary: str, performance: str
) -> None:
    init_db()
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO backtest_results(created_at, strategy, scope, query_start,"
            " query_end, summary, performance) VALUES (?,?,?,?,?,?,?)",
            (now, strategy, scope, q_start, q_end, summary, performance),
        )


def list_backtest(limit: int = 50) -> list[dict]:
    init_db()
    with get_conn() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM backtest_results ORDER BY id DESC LIMIT ?", (limit,)
            )
        ]
