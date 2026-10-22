"""关于页：软件信息、技术栈、数据来源与免责声明。"""
import streamlit as st

from ui_components import page_header

page_header("关于本软件", "版本与基本信息", icon="ℹ️")

st.markdown(
    """
    <div class="hero" style="padding:26px 32px">
      <h1 style="font-size:24px">A 股量化选股工作台</h1>
      <p>本地化量化研究工具 · 版本 v2.0</p>
      <div class="chips">
        <span class="chip">🇨🇳 沪深京 A 股</span>
        <span class="chip">🗄 数据本地化</span>
        <span class="chip">🔬 仅供研究学习</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

lc, rc = st.columns([1.4, 1], gap="large")

with lc:
    st.markdown("#### 主要功能")
    st.markdown(
        """
        - **数据管理** — A 股全市场日线行情、分红送转权息、财务快照的一键导入与增量更新，支持断点续传
        - **选股扫描** — 22 个内置多因子策略（MACD/KDJ 组合、动量反转、量价形态等）、自定义指标条件组合、基本面筛选，支持板块过滤
        - **策略回测** — 止盈/止损/移动止损/持有天数独立配置，输出夏普、卡玛、分年度收益，沪深300 基准对比与参数寻优
        - **个股图表** — 选股结果点击即查 K 线、成交量、MACD、KDJ 四联图
        - **结果导出** — 选股与回测历史自动留档，一键导出 CSV
        """
    )

    st.markdown("#### 技术信息")
    st.markdown(
        """
        | 项目 | 说明 |
        |---|---|
        | 量化内核 | hikyuu 2.5.2（开源量化框架） |
        | 界面 | Streamlit + Plotly |
        | 行情数据 | 腾讯公开行情接口（日线） |
        | 财务数据 | 财经公开快照接口（PE/PB/市值/ROE） |
        | 存储 | 本地 h5 / SQLite，全部数据不出本机 |
        | 基准指数 | 沪深300（sh000300） |
        """
    )

with rc:
    st.markdown("#### 快速上手")
    st.markdown(
        """
        1. 进入 **数据管理**，执行「全量导入行情」（约 1 小时）
        2. 到 **选股** 选一个 ⭐ 推荐策略，点「运行选股」
        3. 点击结果行查看个股 K 线图
        4. 到 **回测** 点「新手推荐预设」后开始回测
        """
    )

    st.markdown("#### 免责声明")
    st.warning(
        "本软件仅供量化研究与学习交流使用，历史回测表现不代表未来收益。"
        "据此操作、投资产生的任何风险与损失由使用者自行承担，不构成任何投资建议。",
        icon="⚠️",
    )

st.caption("A 股量化选股工作台 v2.0 · 基于 hikyuu 量化框架构建")
