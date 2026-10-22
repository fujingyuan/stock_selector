"""首页：品牌首页 + 数据概览 + 功能导航。"""
import streamlit as st

from ui_components import page_header

page_header(
    "总览",
    "本地化 A 股量化工作台 · 技术面 × 基本面 · 选股到回测一站式",
    icon="🏠",
)

from hikyuudata import em_finance, importer  # noqa: E402  （顶部 import hikyuu 触发横幅，放页面渲染后）

# ---- 数据状态（先取值，供 hero 状态徽标与下方磁贴共用） ----
status = importer.data_status()
fin_count = len(em_finance.load_all())
fin_date = em_finance.data_date()
stock_n = status["stock_count"] or 0
weight_n = status["tables"].get("stockweight", 0) or 0
ready = bool(status["db_exists"] and stock_n)
state_chip = (
    '<span class="ok-chip">● 数据就绪</span>' if ready
    else '<span class="warn-chip">● 待导入数据</span>'
)

# ---- Hero ----
st.markdown(
    f"""
    <div class="hero">
      <h1>📈 A 股量化选股工作台</h1>
      <p>全市场技术指标扫描、多因子条件组合、独立卖出规则回测与参数寻优，数据全部本地化存储。</p>
      <div class="chips">
        <span class="chip">🇨🇳 沪深京 A 股全市场</span>
        <span class="chip">🧭 技术面 × 基本面双筛选</span>
        <span class="chip">🧪 回测 · 绩效 · 参数寻优</span>
        <span class="chip">{state_chip}</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---- 功能导航卡片 ----
st.markdown("#### 功能导航")
from strategy.builtin import BUILTIN_STRATEGIES  # noqa: E402

_n = len(BUILTIN_STRATEGIES)
cards = [
    ("🗄", "数据管理", "行情/权息/财务快照一键导入，增量更新、断点续传、限流自愈，数据状态一目了然。", "pages/1_data.py"),
    ("🎯", "选股扫描", f"{_n} 个内置多因子策略 · 自定义指标条件组合 · 基本面筛选；支持板块过滤与个股 K 线联查。", "pages/2_screener.py"),
    ("🧪", "策略回测", "止盈/止损/移动止损/持有天数独立配置；夏普·卡玛·分年度收益 + 沪深300 基准对比 + 参数寻优。", "pages/3_backtest.py"),
    ("📤", "结果导出", "选股与回测历史全留档，随时回溯对比，一键导出 CSV 交接分析。", "pages/4_export.py"),
]
cols = st.columns(4, gap="small")
for col, (ic, t, d, url) in zip(cols, cards):
    with col:
        st.markdown(
            f'<div class="fcard"><div class="ic">{ic}</div><div class="t">{t}</div>'
            f'<div class="d">{d}</div><div class="go"><a href="#">&nbsp;</a></div></div>',
            unsafe_allow_html=True,
        )
        st.page_link(url, label=f"进入「{t}」→")

# ---- 工作流程 ----
st.markdown("#### 标准工作流")
steps = [
    ("导入数据", "日线 / 权息 / 财务", ready),
    ("运行选股", "策略扫描 → 结果留档", ready),
    ("历史回测", "卖出规则 + 绩效对比", ready),
    ("导出结果", "CSV 下载 / 历史回溯", True),
]
html = ['<div class="step">']
for i, (t, d, done) in enumerate(steps):
    cls = "step done" if done else "step"
    html.append(
        f'<div class="{cls}"><div class="n">{i + 1}</div>'
        f'<div class="tx"><b>{t}</b><span>{d}</span></div></div>'
    )
    if i < len(steps) - 1:
        html.append('<div class="arrow">→</div>')
html.append("</div>")
st.markdown("".join(html), unsafe_allow_html=True)

# ---- 数据概览磁贴 ----
st.markdown("#### 数据概览")


def _fmt(v) -> str:
    try:
        return f"{int(v):,}"
    except (TypeError, ValueError):
        return str(v) if v else "—"


tiles = [
    ("var(--navy-600)", _fmt(stock_n), "有效股票数", "沪深京 A 股（剔除指数/基金/B股）"),
    ("var(--gold)", _fmt(status["h5_files"] or 0), "K 线数据文件", "本地 h5 日线库"),
    ("var(--up)", _fmt(weight_n), "权息记录", "分红送转 / 配股除权"),
    ("var(--down)", _fmt(fin_count), "财务快照", f"更新时间 {fin_date}" if fin_date else "尚未导入"),
]
tc = st.columns(4, gap="small")
for col, (color, v, l, s) in zip(tc, tiles):
    col.markdown(
        f'<div class="tile"><div class="bar" style="background:{color}"></div>'
        f'<div class="v">{v}</div><div class="l">{l}</div><div class="s">{s}</div></div>',
        unsafe_allow_html=True,
    )

if not ready:
    st.warning("数据尚未导入：请先进入「数据管理」页执行导入，或运行 `python3 cli.py import`。")

st.caption("本工具仅供量化研究，不构成任何投资建议。")
