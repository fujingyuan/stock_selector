"""hikyuu A 股选股软件 - Streamlit 入口（导航定义，侧边栏显示中文标签）。"""
# hikyuu 在 import 时会用 RotatingFileHandler 打开 ~/.hikyuu/hikyuu_py.log；
# 与其他实例并发轮转的瞬间可能出现 PermissionError 导致整个应用崩溃。
# 这里先给 RotatingFileHandler 加"失败回退到 /tmp"的保护，仅影响日志、不影响数据。
import logging.handlers as _lh
import os as _os
import tempfile as _tf

_OrigRFH = _lh.RotatingFileHandler


class _SafeRotatingFileHandler(_OrigRFH):
    def __init__(self, filename, *args, **kwargs):
        try:
            super().__init__(filename, *args, **kwargs)
        except OSError:
            fallback = _os.path.join(_tf.gettempdir(), _os.path.basename(str(filename)))
            super().__init__(fallback, *args, **kwargs)


_lh.RotatingFileHandler = _SafeRotatingFileHandler

# hikyuu 必须在 streamlit（会先 import pandas）之前加载，否则 libstdc++ TLS block
# 会导致 hikyuu C++ 扩展加载失败（No module named 'hikyuu.cpp.core'）。
import hikyuu  # noqa: E402,F401

import streamlit as st

st.set_page_config(
    page_title="A 股量化选股工作台",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

pg = st.navigation([
    st.Page("pages/0_home.py", title="首页", icon=":material/home:", url_path="home", default=True),
    st.Page("pages/1_data.py", title="数据管理", icon=":material/database:", url_path="data"),
    st.Page("pages/2_screener.py", title="选股", icon=":material/filter_alt:", url_path="screener"),
    st.Page("pages/3_backtest.py", title="回测", icon=":material/history:", url_path="backtest"),
    st.Page("pages/4_export.py", title="结果导出", icon=":material/download:", url_path="export"),
    st.Page("pages/9_about.py", title="关于", icon=":material/info:", url_path="about"),
])
from ui_components import inject_theme, top_status_bar  # noqa: E402

inject_theme()
top_status_bar()
pg.run()
