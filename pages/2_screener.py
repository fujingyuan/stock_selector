"""选股页：内置策略 / 自定义条件 / 多因子筛选，全市场扫描。"""
import json

import pandas as pd
import streamlit as st

import hikyuu  # noqa: E402,F401

from hikyuudata.initializer import get_sm  # noqa: E402,F401  提前完成全局初始化
from ui_components import (  # noqa: E402
    board_selector,
    build_condition_from_spec,
    guide,
    page_header,
    strategy_editor,
)

page_header("选股扫描", "内置多因子策略 / 自定义条件组合 / 多因子筛选 · 点击结果行查看个股图表", icon="🎯")
guide("三个入口：<b>内置技术策略</b>（新手推荐「MACD零上·KDJ金叉」）｜<b>自定义条件组合</b>（指标自由搭配）｜"
      "<b>多因子筛选</b>（估值/市值/换手率等一键预设或自由组合，还能叠加技术形态二次过滤）。"
      "扫描后<b>点击结果行</b>查看个股 K线/MACD/KDJ 图，选完到「回测」页验证。")

tab_builtin, tab_dsl, tab_fund = st.tabs(["内置技术策略", "自定义条件组合", "多因子筛选"])

rows: list[dict] = []
strategy_label = ""

with tab_builtin:
    spec = strategy_editor("scan")
    boards = board_selector("scan_boards")
    c1, c2, c3 = st.columns(3)
    days = c1.slider("参与计算的交易日数", 60, 800, 250, 50, key="scan_days",
                     help="需覆盖指标暖机期（如 MA20/HHV60 需 ≥ 100）")
    exclude_st = c2.checkbox("剔除 ST/退市", value=True, key="scan_st")
    run = c3.button("运行选股", type="primary", key="scan_run", use_container_width=True)
    if run:
        cond = build_condition_from_spec(spec)
        from selector.scanner import scan_condition

        strategy_label = spec["title"]
        with st.status("全市场扫描中 ...", expanded=True) as s:
            box = st.empty()
            rows = scan_condition(
                cond, days=days, exclude_st=exclude_st, boards=boards,
                progress=lambda cur, total: box.progress(
                    cur / total, text=f"{cur}/{total}"),
                strategy_name=strategy_label,
            )
            st.session_state["scan_rows"] = rows
            s.update(state="complete", label=f"扫描完成，选中 {len(rows)} 只")

with tab_dsl:
    spec_d = strategy_editor("scand")
    boards_d = board_selector("scan_boards_d")
    c1, c2, c3 = st.columns(3)
    days_d = c2.slider("交易日数", 60, 800, 250, 50, key="scan_days_d")
    exclude_st_d = c1.checkbox("剔除 ST/退市", value=True, key="scan_st_d")
    run_d = c3.button("运行选股", type="primary", key="scan_run_d", use_container_width=True)
    if run_d:
        cond = build_condition_from_spec(spec_d)
        from selector.scanner import scan_condition

        strategy_label = spec_d["title"]
        with st.status("全市场扫描中 ...", expanded=True) as s:
            box = st.empty()
            rows = scan_condition(
                cond, days=days_d, exclude_st=exclude_st_d, boards=boards_d,
                progress=lambda cur, total: box.progress(
                    cur / total, text=f"{cur}/{total}"),
                strategy_name=strategy_label,
            )
            st.session_state["scan_rows"] = rows
            s.update(state="complete", label=f"扫描完成，选中 {len(rows)} 只")

with tab_fund:
    from strategy.fundamental import (FACTORS, OPS, PRESETS, describe_conditions,
                                      describe_groups, scan_factors)

    from hikyuudata import em_finance

    st.caption(f"📅 快照数据更新于：{em_finance.data_date() or '未知'}"
               "（估值/行情类按快照日；均线/MACD/KDJ/分位等 K 线因子按最新本地 K 线现算）")

    st.markdown("##### 🎁 精选策略（点击一键填充条件）")
    preset_keys = list(PRESETS)
    _preset_icons = {
        "价值低估": "💎", "高ROE白马": "🐎", "大盘蓝筹": "🏢", "小盘活跃": "🌱",
        "放量异动": "🚀", "今日强势": "💪", "破净稳健": "🛡", "低波红利": "🕊",
        "涨停放量": "🔥", "KDJ低位金叉": "✨", "均线多头回踩": "📈",
        "底部反转": "🔄", "突破60日新高": "🏔",
    }
    pcols = st.columns(5)
    for idx, pk in enumerate(preset_keys):
        if pcols[idx % 5].button(
                f"{_preset_icons.get(pk, '▸')} {pk}", key=f"preset_{pk}",
                use_container_width=True,
                help=describe_conditions(PRESETS[pk])):
            st.session_state["factor_groups"] = [
                [dict(c) for c in PRESETS[pk]]]
            st.rerun()

    st.markdown("##### 自定义条件（组内 AND · 组间 OR）")
    if "factor_groups" not in st.session_state:
        st.session_state["factor_groups"] = [
            [{"factor": "pe", "op": "lte", "value": 30.0}]]
    groups = st.session_state["factor_groups"]
    factor_keys = list(FACTORS)

    def _cond_row(cnd: dict, gi: int, ci: int, show_del: bool) -> bool:
        """渲染一行条件；返回是否点击了行内删除。"""
        fc1, fc2, fc3, fc4 = st.columns([2.4, 0.9, 1.5, 0.35])
        f_idx = fc1.selectbox(
            f"因子{gi}_{ci}", factor_keys,
            index=factor_keys.index(cnd.get("factor", "pe")),
            format_func=lambda k: f"[{FACTORS[k][1]}] {FACTORS[k][0]}",
            key=f"f_factor_{gi}_{ci}", label_visibility="collapsed",
            help=FACTORS[cnd.get("factor", "pe")][2] or None)
        o_idx = fc2.selectbox(
            f"算子{gi}_{ci}", list(OPS),
            index=list(OPS).index(cnd.get("op", "lte")),
            format_func=lambda o: OPS[o],
            key=f"f_op_{gi}_{ci}", label_visibility="collapsed")
        if o_idx == "between":
            v = cnd.get("value") if isinstance(cnd.get("value"), list) else [0.0, 100.0]
            b1, b2 = fc3.columns(2)
            lo = b1.number_input("下界", value=float(v[0]), key=f"f_lo_{gi}_{ci}",
                                 label_visibility="collapsed")
            hi = b2.number_input("上界", value=float(v[1]), key=f"f_hi_{gi}_{ci}",
                                 label_visibility="collapsed")
            cnd["value"] = [float(lo), float(hi)]
        else:
            cnd["value"] = float(fc3.number_input(
                "数值",
                value=float(cnd.get("value", 0)
                            if not isinstance(cnd.get("value"), list) else 0),
                key=f"f_val_{gi}_{ci}", label_visibility="collapsed"))
        cnd["factor"], cnd["op"] = f_idx, o_idx
        return show_del and fc4.button("✕", key=f"c_del_{gi}_{ci}",
                                       help="删除此条件")

    for gi, g in enumerate(groups):
        with st.container(border=True):
            hc1, hc2 = st.columns([4, 1])
            hc1.markdown(f"**组 {gi + 1}**（组内 AND）")
            if hc2.button("🗑 删除组", key=f"g_del_{gi}", disabled=len(groups) <= 1):
                groups.pop(gi)
                st.rerun()
            for ci, cnd in enumerate(g):
                if _cond_row(cnd, gi, ci, len(g) > 1):
                    g.pop(ci)
                    st.rerun()
            if st.button("＋ 本组加条件", key=f"g_add_{gi}"):
                g.append({"factor": "pe", "op": "lte", "value": 30.0})
                st.rerun()
        if gi < len(groups) - 1:
            st.markdown(
                "<div style='text-align:center;color:#d4a017;font-weight:600;"
                "margin:-4px 0'>—— 或（OR）——</div>",
                unsafe_allow_html=True)
    if st.button("＋ 添加组（组间 OR）", key="g_add_group"):
        groups.append([{"factor": "pe", "op": "lte", "value": 30.0}])
        st.rerun()
    st.caption(f"当前条件：{describe_groups(groups)}")

    with st.expander("⚡ 技术面增强过滤（可选，进阶）"):
        st.caption("先按上面因子筛出候选池，再对每只股票验证技术形态（最新一根 K 线条件成立才保留）。"
                   "这是「基本面选好公司 + 技术面选好时机」的组合打法。")
        use_tech = st.checkbox("启用技术面二次过滤", key="f_use_tech")
        tech_name = "macd_golden"
        if use_tech:
            from strategy.builtin import BUILTIN_STRATEGIES

            title2key = {v["title"]: k for k, v in BUILTIN_STRATEGIES.items()}
            tech_title = st.selectbox("技术形态", list(title2key), key="f_tech_name")
            tech_name = title2key[tech_title]

    boards_f = board_selector("scan_boards_f")
    fa1, fa2, fa3 = st.columns([1, 1, 3])
    exclude_st_f = fa1.checkbox("剔除 ST/退市", value=True, key="scan_st_f")
    run_f = fa2.button("运行筛选", type="primary", key="scan_run_f")
    if run_f:
        tech = {"name": tech_name} if use_tech else None
        strategy_label = "多因子: " + describe_groups(groups) + (
            f" + {tech_title}" if use_tech else "")
        with st.status("多因子筛选中 ...", expanded=True) as s:
            box = st.empty()
            rows = scan_factors(
                groups=groups, exclude_st=exclude_st_f, boards=boards_f,
                tech_filter=tech,
                progress=lambda cur, total: box.progress(
                    cur / total, text=f"{cur}/{total}"),
            )
            st.session_state["scan_rows"] = rows
            s.update(state="complete", label=f"筛选完成，命中 {len(rows)} 只")

rows = st.session_state.get("scan_rows", [])
if rows:
    st.success(f"选中 {len(rows)} 只（结果已保存，可在「结果导出」页查看历史）")
    nav1, _ = st.columns([1, 3])
    nav1.page_link("pages/3_backtest.py", label="🧪 拿这批股票去回测 →")
    df = pd.DataFrame(rows)
    factor_mode = "change_pct" in df.columns  # 多因子结果：detail 展开为因子列
    if factor_mode and "detail" in df.columns:
        detail_df = pd.DataFrame(
            [json.loads(x) if x and x.startswith("{") else {} for x in df["detail"]])
        detail_df = detail_df.drop(
            columns=[c for c in detail_df.columns if c in df.columns])  # 去重列
        df = pd.concat([df.drop(columns=["detail"]), detail_df], axis=1)
    elif "detail" in df.columns:
        df["detail"] = df["detail"].apply(
            lambda x: ", ".join(f"{k}={v}" for k, v in json.loads(x).items())
            if x and x.startswith("{") else x)
    # 专业排序：多因子按当日涨跌幅降序；技术按信号日期降序
    sort_col = ("change_pct" if factor_mode else
                ("signal_date" if "signal_date" in df.columns else None))
    if sort_col:
        df = df.sort_values(sort_col, ascending=False, na_position="last")
    from streamlit.column_config import NumberColumn, TextColumn

    col_cfg = {}
    if "market_code" in df.columns:
        col_cfg["market_code"] = TextColumn("代码", width="small")
    if "stock_name" in df.columns:
        col_cfg["stock_name"] = TextColumn("名称", width="small")
    if "板块" in df.columns:
        col_cfg["板块"] = TextColumn("板块", width="small")
    if "close" in df.columns:
        col_cfg["close"] = NumberColumn("收盘价", format="%.2f")
    if "change_pct" in df.columns:
        col_cfg["change_pct"] = NumberColumn("涨跌幅%", format="%+.2f%%")
    if "pe" in df.columns:
        col_cfg["pe"] = NumberColumn("PE(TTM)", format="%.1f")
    if "pb" in df.columns:
        col_cfg["pb"] = NumberColumn("PB", format="%.2f")
    if "roe" in df.columns:
        col_cfg["roe"] = NumberColumn("ROE%", format="%.1f")
    if "market_cap" in df.columns:
        col_cfg["market_cap"] = NumberColumn("总市值(亿)", format="%.0f")
    if "liutong_cap" in df.columns:
        col_cfg["liutong_cap"] = NumberColumn("流通市值(亿)", format="%.0f")
    if "turnover" in df.columns:
        col_cfg["turnover"] = NumberColumn("换手率%", format="%.2f")
    if "amplitude" in df.columns:
        col_cfg["amplitude"] = NumberColumn("振幅%", format="%.2f")
    if "vol_ratio" in df.columns:
        col_cfg["vol_ratio"] = NumberColumn("量比", format="%.2f")
    if "行业" in df.columns:
        col_cfg["行业"] = TextColumn("行业", width="small")
    # 扩展因子列：按注册表自动生成列配置
    from strategy.fundamental import FACTORS as _F

    _BOOL_F = {"limit_up_hit", "ma_bull", "macd_gold", "macd_above", "kdj_gold",
               "boll_break", "new_high_60", "up_days", "vol_up_days", "vol_down_days"}
    for k in _F:
        if k in df.columns and k not in col_cfg:
            col_cfg[k] = NumberColumn(
                _F[k][0], format="%.0f" if k in _BOOL_F else "%.2f")
    if "signal_date" in df.columns:
        col_cfg["signal_date"] = TextColumn("信号日期", width="small")
    if "signal_value" in df.columns:
        col_cfg["signal_value"] = NumberColumn("条件值", format="%.4f")
    if "detail" in df.columns:
        col_cfg["detail"] = TextColumn("指标详情", width="large")
    sel_df = df
    if factor_mode and "change_pct" in df.columns:
        # 专业信号：涨跌幅红涨绿跌（A股习惯），NaN 不着色
        def _pct_color(v):
            if v != v:
                return ""
            if v > 0:
                return "color:#e05252;font-weight:600"
            if v < 0:
                return "color:#26a69a;font-weight:600"
            return ""
        sel_df = df.style.map(_pct_color, subset=["change_pct"])
    sel = st.dataframe(
        sel_df, use_container_width=True, height=480, row_height=30,
        on_select="rerun", selection_mode="single-row", key="scan_result_table",
        column_config=col_cfg or None, hide_index=True,
    )
    st.caption("点击表格中的股票行，下方显示该股 K线 / 成交量 / MACD / KDJ 图")
    picked = (sel.selection.rows or []) if sel else []
    if picked:
        from ui_components import stock_chart_panel

        stock_chart_panel(df.iloc[picked[0]]["market_code"])
else:
    from ui_components import empty_state

    empty_state(
        "🎯", "还没有选股结果",
        "在上方选择一个策略（推荐从「内置技术策略」开始），点击「运行选股」即可全市场扫描。<br>"
        "扫描完成后：点击结果行可查看个股 K 线图，也可一键转去回测页验证策略。",
        page="pages/3_backtest.py", label="查看回测功能 →",
    )
