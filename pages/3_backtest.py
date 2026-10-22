"""回测页：对策略做单票/组合回测，输出绩效与交易明细。

v2：卖出规则独立配置（止损/止盈/移动止损/持有天数/独立卖出条件）、
资金曲线 + 沪深300 基准对比、夏普/卡玛等风险指标、分年度收益、参数寻优。
"""
import pandas as pd
import streamlit as st

from ui_components import guide, page_header

page_header("策略回测", "卖出规则独立配置 · 绩效与基准对比 · 参数寻优", icon="🧪")
guide("把选出的股票放进历史行情里「模拟交易」，看能不能赚钱：<b>① 选股票范围</b>（新手选「最近一次选股结果」）"
      "→ <b>② 选策略</b>（与选股页相同）→ <b>③ 配置卖出规则</b>（新手直接点下方「新手推荐预设」）→ "
      "<b>④ 点「开始回测」</b>，看年化收益、最大回撤和与沪深300 的对比。绿字为参考：年化跑赢基准且回撤可控才值得实盘跟踪。")

import hikyuu  # noqa: E402,F401

from ui_components import build_condition_from_spec, strategy_editor  # noqa: E402

st.subheader("1. 股票范围")
scope_mode = st.radio(
    "范围", ["最近一次选股结果", "全市场", "指定代码"],
    horizontal=True, key="bt_scope",
)
boards = None
if scope_mode == "全市场":
    from ui_components import board_selector

    boards = board_selector("bt_boards")
codes_text = ""
if scope_mode == "指定代码":
    codes_text = st.text_area(
        "股票代码（每行一个，如 sh600000 / sz000001）", height=120, key="bt_codes")
if scope_mode == "最近一次选股结果":
    import store

    strats = [r["strategy"] for r in store.distinct_scan_strategies()]
    if not strats:
        st.warning("暂无选股结果，请先到「选股」页运行一次选股。")
        st.stop()
    chosen = st.selectbox("选股策略", strats, key="bt_scan_strategy")
    last_rows = store.latest_scan(chosen, limit=100000)
    st.caption(f"该策略最近一次选股 {len(last_rows)} 只（{last_rows[0]['created_at'] if last_rows else ''}）")

st.subheader("2. 策略")
spec = strategy_editor("bt")

st.subheader("3. 回测参数")
c1, c2, c3, c4 = st.columns(4)
days = c1.slider("回测区间（最近交易日）", 100, 2000, 500, 100, key="bt_days")
init_cash = c2.number_input("初始资金", value=300000, step=10000, key="bt_cash")
n = c3.number_input("每次买入股数", value=100, step=100, key="bt_n")
cost = c4.checkbox("计入交易成本", value=True, key="bt_cost")

st.subheader("4. 卖出规则")
st.caption("不配置时按默认规则：买入条件失效即卖出。止损方式三选一。")
_preset1, _preset2, _preset3 = st.columns([1.2, 1.2, 3])
if _preset1.button("🎯 新手推荐预设", key="bt_preset_novice",
                   help="止损8% + 止盈20% + 最长持有20天，适合金叉脉冲类策略"):
    st.session_state["bt_stop_mode"] = "固定百分比止损"
    st.session_state["bt_stop_pct"] = 0.08
    st.session_state["bt_use_tp"] = True
    st.session_state["bt_tp_pct"] = 0.20
    st.session_state["bt_use_hold"] = True
    st.session_state["bt_hold_days"] = 20
    st.session_state["bt_sell_exit"] = False
    st.session_state["bt_use_sell_cond"] = False
    st.rerun()
if _preset2.button("🏃 趋势跟踪预设", key="bt_preset_trend",
                   help="移动止损15%（回溯20日）+ 不设止盈，让利润奔跑"):
    st.session_state["bt_stop_mode"] = "移动止损（吊灯）"
    st.session_state["bt_trail_n"] = 20
    st.session_state["bt_trail_pct"] = 0.15
    st.session_state["bt_use_tp"] = False
    st.session_state["bt_use_hold"] = False
    st.session_state["bt_sell_exit"] = False
    st.session_state["bt_use_sell_cond"] = False
    st.rerun()
_preset3.caption("点预设按钮自动填入下方所有卖出规则项。")
_MODE_MAP = {
    "不使用": "none", "固定百分比止损": "fixed",
    "移动止损（吊灯）": "trail", "安全线止损": "saftyloss",
}
with st.container(border=True):
    rc1, rc2, rc3, rc4 = st.columns(4)
    stop_mode = rc1.radio(
        "止损方式",
        ["不使用", "固定百分比止损", "移动止损（吊灯）", "安全线止损"],
        index=0, key="bt_stop_mode",
    )
    stop_pct = trail_pct = 0.0
    trail_n = 20
    if stop_mode == "固定百分比止损":
        stop_pct = rc2.slider("止损幅度", 0.01, 0.30, 0.08, 0.01,
                              format="%.0f%%", key="bt_stop_pct") / 100.0
    elif stop_mode == "移动止损（吊灯）":
        trail_n = rc2.slider("回溯周期（日）", 5, 120, 20, 5, key="bt_trail_n")
        trail_pct = rc3.slider("自高点回撤幅度", 0.05, 0.40, 0.15, 0.01,
                               format="%.0f%%", key="bt_trail_pct") / 100.0
    elif stop_mode == "安全线止损":
        rc2.caption("ST_Saftyloss(n1=10, n2=3, p=2.0)，见《走进我的交易室》")
    use_tp = rc4.checkbox("固定止盈", value=False, key="bt_use_tp")
    tp_pct = 0.0
    if use_tp:
        tp_pct = st.slider("止盈幅度", 0.05, 1.00, 0.20, 0.05,
                           format="%.0f%%", key="bt_tp_pct") / 100.0
    rd1, rd2, rd3 = st.columns(3)
    use_hold = rd1.checkbox("最大持有天数", value=False, key="bt_use_hold")
    hold_days = 0
    if use_hold:
        hold_days = rd1.number_input("持有天数", value=10, min_value=1, step=1, key="bt_hold_days")
    sell_on_exit = rd2.checkbox("买入条件失效时卖出", value=True, key="bt_sell_exit")
    use_sell_cond = rd3.checkbox("独立卖出条件", value=False, key="bt_use_sell_cond")
    sell_spec = None
    if use_sell_cond:
        sell_spec = strategy_editor("bt_sell")
    if use_tp and use_hold:
        st.caption("止盈与持有天数同时启用时，持有天数按自然日近似。")

run = st.button("开始回测", type="primary", use_container_width=True)
if run:
    from selector.scanner import get_universe  # noqa: F401
    from backtest.runner import backtest_portfolio, performance_summary, resolve_stocks
    from backtest.sell_rules import SellRules

    if scope_mode == "最近一次选股结果":
        stocks = resolve_stocks({"mode": "codes", "codes": [r["market_code"] for r in last_rows]})
    elif scope_mode == "全市场":
        stocks = get_universe(exclude_st=True, boards=boards)
    else:
        codes = [c.strip() for c in codes_text.splitlines() if c.strip()]
        if not codes:
            st.error("请输入股票代码")
            st.stop()
        stocks = resolve_stocks({"mode": "codes", "codes": codes})
    if not stocks:
        st.error("股票范围为空")
        st.stop()

    _mode_map = _MODE_MAP
    rules = SellRules(
        stop_mode=_mode_map[stop_mode],
        stop_pct=float(stop_pct),
        trail_n=int(trail_n),
        trail_pct=float(trail_pct),
        take_profit=float(tp_pct) if use_tp else None,
        max_hold_days=int(hold_days) if use_hold else None,
        sell_cond=build_condition_from_spec(sell_spec) if sell_spec else None,
        sell_on_signal_exit=bool(sell_on_exit),
    )
    cond = build_condition_from_spec(spec)
    rule_txt = rules.describe()
    st.caption(f"卖出规则：{rule_txt}")
    with st.status(f"组合回测中（{len(stocks)} 只股票, {days} 个交易日）...", expanded=True) as s:
        result = backtest_portfolio(
            cond, stocks, days=days, init_cash=float(init_cash), n=int(n), cost=cost, rules=rules)
        s.update(state="complete", label="回测完成")

    key_rows, report = performance_summary(result)
    perf = result["performance"]

    st.subheader("绩效概览")
    metric_cols = st.columns(min(5, len(key_rows)))
    for col, (k, v) in zip(metric_cols, key_rows[:5]):
        col.metric(k, f"{v}")

    # 资金曲线 + 风险指标 + 基准对比 + 分年度收益
    from backtest import benchmark, perf as bt_perf

    curve = bt_perf.funds_curve(result, stocks)
    if not curve.empty:
        metrics = bt_perf.risk_metrics(curve)
        if metrics:
            rm_cols = st.columns(5)
            for col, k in zip(rm_cols, ["年化收益率", "夏普比率", "卡玛比率", "索提诺比率", "最大回撤"]):
                v = metrics.get(k)
                col.metric(k, "—" if v is None or v != v else f"{v:.2f}" if "比率" in k else f"{v:.1%}")
            if metrics.get("回撤结束"):
                st.caption(f"最大回撤区间：{metrics['回撤开始']} ~ {metrics['回撤结束']}")

        with st.expander("资金曲线与沪深300 对比", expanded=True):
            try:
                bdf = benchmark.get_benchmark(
                    beg=curve["date"].iloc[0], end=curve["date"].iloc[-1])
                cmp_df = bt_perf.normalized_compare(curve, bdf)
                if cmp_df.empty:
                    st.info("基准数据暂不可用（网络拉取失败或区间无数据）。")
                else:
                    st.line_chart(cmp_df, height=340)
                    end_ret_s = cmp_df["策略"].iloc[-1] - 1
                    end_ret_b = cmp_df["沪深300"].iloc[-1] - 1
                    st.caption(
                        f"区间：策略 {end_ret_s:+.1%} ｜ 沪深300 {end_ret_b:+.1%}"
                        f" ｜ 超额 {end_ret_s - end_ret_b:+.1%}")
            except Exception as e:  # noqa: BLE001
                st.info(f"基准对比不可用：{e}")

        with st.expander("分年度收益", expanded=True):
            ydf = bt_perf.yearly_returns(curve)
            if not ydf.empty:
                ydf = ydf.style.format({"年度收益率": "{:.1%}", "年末资产": "{:,.0f}"})
                st.dataframe(ydf, use_container_width=True, hide_index=True)

    with st.expander("完整绩效报告", expanded=False):
        st.text(report)

    import store

    summary_extra = {"卖出规则": rule_txt}
    metrics = bt_perf.risk_metrics(curve) if not curve.empty else {}
    for k in ("夏普比率", "卡玛比率", "最大回撤"):
        if k in metrics and metrics[k] == metrics[k]:
            summary_extra[k] = round(float(metrics[k]), 4)
    store.save_backtest_result(
        strategy=spec["title"],
        scope=scope_mode + (f":{chosen}" if scope_mode == "最近一次选股结果" else ""),
        q_start=f"-{days}d",
        q_end="最新",
        summary=str({**{k: perf[k] for k in list(perf)[:8]}, **summary_extra}),
        performance=report,
    )
    st.caption("回测结果已保存，可在「结果导出」页查看历史。")

    st.subheader("交易明细")
    trades: pd.DataFrame = result["trades"]
    if trades.empty:
        st.info("回测区间内无交易发生。")
    else:
        from streamlit.column_config import NumberColumn, TextColumn

        _num_cols = {"实际成交价格": "%.2f", "止损价": "%.2f", "发生金额": "%.2f",
                     "手续费": "%.2f", "成交数量": "%.0f", "投资总额": "%.2f"}
        _txt_cols = ["业务名称", "证券代码", "证券名称", "发生日期", "信号来源", "备注"]
        cfg = {}
        for c in trades.columns:
            if c in _num_cols:
                cfg[c] = NumberColumn(c, format=_num_cols[c])
            elif c in _txt_cols:
                cfg[c] = TextColumn(c, width="small")
        st.dataframe(trades, use_container_width=True, height=380,
                     hide_index=True, column_config=cfg or None)
        st.download_button(
            "下载交易明细 CSV",
            trades.to_csv(index=False).encode("utf-8-sig"),
            file_name="backtest_trades.csv", mime="text/csv")

# ---------------- 参数寻优 ----------------
st.subheader("参数寻优")
st.caption("对内置策略的参数做网格扫描（固定其他回测设置），按年化收益率排名。股票范围较大时建议控制组合数。")
with st.expander("展开参数寻优", expanded=False):
    if spec is None or spec.get("kind") != "builtin":
        st.info("参数寻优仅支持「内置技术策略」，请在上方策略区选择内置策略。")
    else:
        from strategy.builtin import BUILTIN_STRATEGIES

        info = BUILTIN_STRATEGIES[spec["name"]]
        grid: dict[str, list] = {}
        gcols = st.columns(len(info["params"]))
        for col, (pname, (default, desc)) in zip(gcols, info["params"].items()):
            txt = col.text_input(
                f"{desc}（{pname}）", value=str(default), key=f"opt_{pname}",
                help="逗号分隔多个取值，如 5,10,20",
            )
            vals = [v.strip() for v in txt.split(",") if v.strip()] or [str(default)]
            if isinstance(default, float):
                grid[pname] = [float(v) for v in vals]
            else:
                grid[pname] = [int(float(v)) for v in vals]
        total = 1
        for v in grid.values():
            total *= len(v)
        st.caption(f"共 {total} 个组合")
        if total > 60:
            st.warning("组合数较多，回测耗时可能较长。")
        run_opt = st.button("开始寻优", key="bt_opt_run", type="primary")
        if run_opt:
            from backtest.optimizer import grid_search
            from backtest.sell_rules import SellRules as _SR

            if scope_mode == "最近一次选股结果":
                opt_stocks = resolve_stocks(
                    {"mode": "codes", "codes": [r["market_code"] for r in last_rows]})
            elif scope_mode == "全市场":
                opt_stocks = get_universe(exclude_st=True, boards=boards)
            else:
                opt_stocks = resolve_stocks(
                    {"mode": "codes", "codes": [c.strip() for c in codes_text.splitlines() if c.strip()]})
            if not opt_stocks:
                st.error("股票范围为空")
                st.stop()
            opt_rules = _SR(
                stop_mode=_mode_map[stop_mode], stop_pct=float(stop_pct),
                trail_n=int(trail_n), trail_pct=float(trail_pct),
                take_profit=float(tp_pct) if use_tp else None,
                max_hold_days=int(hold_days) if use_hold else None,
                sell_cond=build_condition_from_spec(sell_spec) if sell_spec else None,
                sell_on_signal_exit=bool(sell_on_exit),
            )
            bar = st.progress(0.0, text="寻优中...")
            df_opt = grid_search(
                spec["name"], grid, opt_stocks, days=days,
                init_cash=float(init_cash), n=int(n), cost=cost, rules=opt_rules,
                progress=lambda i, t: bar.progress(i / t, text=f"寻优中 {i}/{t}..."),
            )
            bar.empty()
            st.dataframe(
                df_opt.style.format(precision=4, na_rep="—"),
                use_container_width=True, height=360)
            if not df_opt.empty:
                st.download_button(
                    "下载寻优结果 CSV",
                    df_opt.to_csv(index=False).encode("utf-8-sig"),
                    file_name="param_grid_search.csv", mime="text/csv",
                    key="bt_opt_dl")
