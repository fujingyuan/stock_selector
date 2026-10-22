"""hikyuu 初始化封装（hikyuu 2.5.x）。

hikyuu 全局初始化只能执行一次，所有页面/模块共用本模块的 get_sm()。
Streamlit 页面应配合 st.cache_resource 缓存本函数返回值。
数据目录为 ~/.hikyuu（hikyuu 首次加载时自动生成默认 hikyuu.ini）。
"""
from pathlib import Path

HIKYUU_HOME = Path.home() / ".hikyuu"
# hikyuu 默认配置的数据目录（Linux: ~/stock）
DATA_DIR = Path.home() / "stock"

_initialized = False


def ensure_config() -> None:
    """确保数据目录存在（hikyuu.ini 由 load_hikyuu 自动生成）。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_sm():
    """初始化 hikyuu 并返回 StockManager 单例。进程内幂等。"""
    global _initialized
    ensure_config()
    import hikyuu

    if not _initialized:
        hikyuu.load_hikyuu(
            stock_list=["all"],
            ktype_list=["day"],
            load_history_finance=False,
            load_weight=True,
            start_spot=False,
        )
        _initialized = True
    return hikyuu.StockManager.instance()


def get_db_path() -> Path:
    return DATA_DIR / "stock.db"
