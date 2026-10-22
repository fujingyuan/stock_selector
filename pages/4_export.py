"""结果导出页：选股历史与回测历史查询、CSV 下载。"""
import pandas as pd
import streamlit as st

from ui_components import guide, page_header

page_header("结果导出", "选股与回测历史留档查询 · 一键导出 CSV", icon="📤")
guide("所有选股和回测结果都会自动保存在本地，随时回来查看、对比或导出 CSV（Excel 可直接打开）。"
      "还没有记录？先到「选股」页跑一次扫描。")

import store  # noqa: E402

tab_scan, tab_bt = st.tabs(["选股历史", "回测历史"])

with tab_scan:
    strats = store.distinct_scan_strategies()
    if not strats:
        from ui_components import empty_state

        empty_state(
            "📭", "暂无选股记录",
            "每运行一次选股都会自动留档。<br>到「选股」页选择策略并点击「运行选股」，记录会出现在这里。",
            page="pages/2_screener.py", label="去选股 →",
        )
    else:
        chosen = st.selectbox(
            "策略",
            strats,
            format_func=lambda s: f"{s['strategy']}（{s['count']} 条）",
            key="exp_strategy",
        )
        rows = store.latest_scan(chosen["strategy"], limit=100000)
        st.caption(f"最近一次扫描时间: {rows[0]['created_at'] if rows else '—'}")
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, height=460)
        st.download_button(
            "下载选股结果 CSV",
            df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"scan_{chosen['strategy']}.csv", mime="text/csv")

with tab_bt:
    records = store.list_backtest(limit=100)
    if not records:
        from ui_components import empty_state

        empty_state(
            "📭", "暂无回测记录",
            "每次点击「开始回测」都会自动保存绩效报告。<br>到「回测」页完成第一次回测，报告会出现在这里。",
            page="pages/3_backtest.py", label="去回测 →",
        )
    else:
        for rec in records:
            with st.expander(
                f"[{rec['created_at']}] {rec['strategy']} @ {rec['scope']} ({rec['query_start']} ~ {rec['query_end']})"
            ):
                st.text(rec["performance"])
        if records:
            df = pd.DataFrame(
                [{"created_at": r["created_at"], "strategy": r["strategy"],
                  "scope": r["scope"], "query_start": r["query_start"],
                  "query_end": r["query_end"]} for r in records]
            )
            st.download_button(
                "下载回测记录 CSV",
                df.to_csv(index=False).encode("utf-8-sig"),
                file_name="backtest_history.csv", mime="text/csv")
