"""数据管理页：数据状态、导入/更新操作。"""
import threading
import time

import streamlit as st

from ui_components import guide, page_header

page_header("数据管理", "行情 / 权息 / 财务快照的导入、增量更新与状态监控", icon="🗄")
guide("第一次使用：选「全量导入行情」，点「开始执行」，等待约 1 小时完成；"
      "之后每天开盘前用「增量更新行情(快)」补充最新 K 线即可。导入过程中请勿运行选股/回测。")

import hikyuu  # noqa: E402,F401  主线程先加载模块（静态 TLS 依赖）

from hikyuudata import importer  # noqa: E402

if "import_thread_done" not in st.session_state:
    st.session_state["import_thread_done"] = True
    st.session_state["import_log"] = []
    st.session_state["import_error"] = None

status = importer.data_status()
from hikyuudata import em_finance  # noqa: E402

fin_count = len(em_finance.load_all())
fin_date = em_finance.data_date()
c1, c2, c3, c4 = st.columns(4)
c1.metric("有效股票数", status["stock_count"] or "—")
c2.metric("K线 h5 文件", status["h5_files"] or "—")
c3.metric("权息记录", status["tables"].get("stockweight", "—"))
c4.metric("财务快照", f"{fin_count}" if fin_count else "—",
          help=f"更新时间: {fin_date}" if fin_date else None)
st.caption(f"数据目录: {importer.get_db_path()}")

if not status["db_exists"] or not status["stock_count"]:
    from ui_components import empty_state

    empty_state(
        "📥", "数据尚未导入",
        "本地数据库为空，选股与回测功能暂不可用。<br>"
        "在下方选择「全量导入行情(首次, 约1小时)」并点击「开始执行」，全程自动完成。",
    )

action = st.radio(
    "选择操作",
    ["增量更新行情(快)", "全量导入行情(首次, 约1小时)", "导入因子快照", "导入板块信息"],
    horizontal=True,
)

start = st.button("开始执行", type="primary", disabled=not st.session_state["import_thread_done"])

if start:
    st.session_state["import_log"] = []
    st.session_state["import_error"] = None
    st.session_state["import_thread_done"] = False

    def _worker():
        try:
            if action.startswith("增量"):
                importer.update_all(progress=_log)
            elif action.startswith("全量"):
                importer.import_all(progress=_log)
            elif action.startswith("导入财务"):
                importer.import_finance(progress=_log)
            else:
                importer.import_blocks(progress=_log)
        except Exception as e:  # noqa: BLE001
            st.session_state["import_error"] = str(e)
        finally:
            st.session_state["import_thread_done"] = True

    def _log(msg: str):
        st.session_state["import_log"].append(f"{time.strftime('%H:%M:%S')} {msg}")
        if len(st.session_state["import_log"]) > 400:
            del st.session_state["import_log"][:200]

    threading.Thread(target=_worker, daemon=True).start()

if not st.session_state["import_thread_done"]:
    with st.status("数据导入进行中 ...", state="running", expanded=True) as s:
        box = st.empty()
        while not st.session_state["import_thread_done"]:
            box.code("\n".join(st.session_state["import_log"][-15:]) or "准备中 ...")
            time.sleep(1.5)
        box.code("\n".join(st.session_state["import_log"][-15:]))
        if st.session_state.get("import_error"):
            s.update(state="error", label=f"导入失败: {st.session_state['import_error']}")
        else:
            s.update(state="complete", label="导入完成")
    st.rerun()

if st.session_state.get("import_error"):
    st.error(f"上次导入失败: {st.session_state['import_error']}")

st.divider()
st.markdown(
    """
    **说明**
    - 行情 K 线按库内最后日期自动增量续导，重复执行安全。
    - K 线源为公开行情接口（全历史约 1 小时，不含北交所）。
    - 日常增量更新通常只需几分钟，建议每天收盘后执行
      （UI 按钮或命令行 `python3 cli.py update`）。
    - 因子快照（估值/市值/换手率/量比等）与板块信息独立于行情，
      建议收盘后一并更新，多因子筛选使用最新数据。
    """
)
