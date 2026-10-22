"""Streamlit 页面共享组件与工具。"""
import streamlit as st

# 注意：strategy.builtin / strategy.dsl 依赖 hikyuu，这里不顶部 import，
# 改在 strategy_editor() 内延迟加载，避免主题/状态条等基础功能被 hikyuu 加载失败拖垮。

# ---------------- 全局主题 ----------------
# 设计基调：深海军蓝（专业终端感）+ A股红作主行动色 + 金色点缀；浅色主区保证数据可读性。

_THEME_CSS = """
<style>
:root {
  --navy-900:#0b1f33; --navy-700:#143454; --navy-600:#1c4468;
  --ink:#1c2b3a; --muted:#6b7a8c; --line:#e3e9f0; --bg:#f5f7fa;
  --up:#e05252; --down:#26a69a; --gold:#c9a15c;
  --card:#ffffff; --radius:14px;
}
html, body, [class*="css"] { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", "Segoe UI", sans-serif; }
#MainMenu, footer { visibility: hidden; }
[data-testid="stHeader"] { background: transparent; }
/* 注意：stToolbar 不能整体隐藏——侧边栏折叠后的「展开按钮」就在它内部 */
[data-testid="stDecoration"], [data-testid="stAppDeployButton"],
[data-testid="stStatusWidget"] { display: none; }
[data-testid="stToolbar"] { background: transparent; }
[data-testid="stAppViewContainer"] { background: var(--bg); }

/* 侧边栏：深色终端风 */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, var(--navy-900) 0%, var(--navy-700) 100%);
  border-right: none;
}
[data-testid="stSidebar"] * { color: #dfe7ef; }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,.12); }
[data-testid="stSidebar"] .stRadio label, [data-testid="stSidebar"] .stCheckbox label { color:#dfe7ef; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color:#b9c6d4; }
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-baseweb="input"] { background:rgba(255,255,255,.08); border-color:rgba(255,255,255,.15); }
[data-testid="stSidebar"] [data-baseweb="select"] input::placeholder,
[data-testid="stSidebar"] [data-baseweb="input"] input { color:#eef3f8; }
[data-testid="stSidebar"] span[data-testid="stIconMaterial"] { color:#8fb3d9; }

/* 侧边栏折叠/展开按钮：折叠后左上角必须可见（深色底白图标，常显不依赖 hover） */
[data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapseButton"] {
  display: flex !important; visibility: visible !important; opacity: 1 !important;
  background: var(--navy-700) !important; border-radius: 8px; padding: 6px 8px;
  box-shadow: 0 2px 10px rgba(11,31,51,.35); z-index: 1000000; position: relative;
  min-width: 36px; min-height: 36px; align-items: center; justify-content: center;
}
[data-testid="stExpandSidebarButton"] *, [data-testid="stSidebarCollapseButton"] * { color:#fff !important; }
[data-testid="stExpandSidebarButton"]:hover, [data-testid="stSidebarCollapseButton"]:hover { filter: brightness(1.15); }

/* 侧边栏导航：VSCode 活动栏风（窄栏 + 大图标 + 小标签）
   88px 宽度仅作用于展开态（aria-expanded=true）；折叠时恢复 Streamlit 自身的
   min/max-width:0，否则 section 会在 flex 布局中残留 88px 空隙把主内容顶偏。
   transition-property 只保留 transform：避免载入时 min-width 从默认 336px 渐变到 88px 的中间帧 */
[data-testid="stSidebar"][aria-expanded="true"],
[data-testid="stSidebar"][aria-expanded="true"] > div:first-child {
  min-width: 88px !important; max-width: 88px !important; width: 88px !important;
}
[data-testid="stSidebar"] { transition-property: transform !important; }
[data-testid="stSidebar"] [data-testid="stSidebarResizeHandle"] { display: none; }
[data-testid="stSidebar"] [data-testid="stSidebarContent"] { padding: 0 6px; }
[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {
  justify-content: center; padding: 6px 4px 2px;
}
[data-testid="stSidebarHeader"] [data-testid="stSidebarCollapseButton"] {
  min-width: 32px; min-height: 32px; padding: 4px 6px;
}
[data-testid="stSidebarNav"] ul { padding-top: 4px; gap: 4px; display: flex; flex-direction: column; }
[data-testid="stSidebarNav"] li a {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 3px; border-radius: 10px; padding: 10px 2px 8px; margin: 0;
  transition: background .12s ease; text-align: center;
}
[data-testid="stSidebarNav"] li a:hover { background: rgba(255,255,255,.09); }
[data-testid="stSidebarNav"] li a span[data-testid="stIconMaterial"] {
  font-size: 26px; color: #9db4ca; line-height: 1;
}
[data-testid="stSidebarNav"] li a span:not([data-testid="stIconMaterial"]),
[data-testid="stSidebarNav"] li a p {
  font-size: 11px; color: #b9c6d4; line-height: 1.2; letter-spacing: .5px;
}
[data-testid="stSidebarNav"] li a[aria-current="page"] {
  background: rgba(255,255,255,.13); box-shadow: inset 3px 0 0 var(--gold);
}
[data-testid="stSidebarNav"] li a[aria-current="page"] span[data-testid="stIconMaterial"],
[data-testid="stSidebarNav"] li a[aria-current="page"] span,
[data-testid="stSidebarNav"] li a[aria-current="page"] p { color: #fff !important; }
/* 导航以下其余侧边栏内容恢复常规排版（防止窄栏挤压其它组件） */
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] { min-width: 0; }

/* 主区排版：紧凑密度（专业终端感） */
.block-container { padding-top: 4.4rem; padding-bottom: 2rem; max-width: 1280px; }
[data-testid="stVerticalBlock"] { gap: .55rem; }
[data-testid="stHorizontalBlock"] { gap: .7rem; }
h1, h2, h3 { color: var(--ink); letter-spacing: .2px; }

/* 控件密度：标签更小、输入更矮、按钮更紧凑 */
[data-testid="stWidgetLabel"] p { font-size: 13px; margin-bottom: 2px; }
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-primary"] {
  padding-top: .3rem; padding-bottom: .3rem;
}
[data-testid="stCaptionContainer"] { margin-top: -2px; }
[data-testid="stAlert"] { padding: .6rem 1rem; }
[data-testid="stMarkdownContainer"] h5 { margin: .4em 0 .3em; font-size: 15.5px; }

/* 页头 */
.ph { display:flex; align-items:center; gap:14px; margin:0 0 6px; }
.ph-ico { width:46px; height:46px; border-radius:12px; display:flex; align-items:center; justify-content:center;
  font-size:24px; background:linear-gradient(135deg, var(--navy-700), var(--navy-600)); box-shadow:0 4px 12px rgba(11,31,51,.18); }
.ph-title { font-size:26px; font-weight:700; color:var(--ink); line-height:1.2; }
.ph-sub { color:var(--muted); font-size:13.5px; margin:2px 0 10px; }

/* 章节标题：左侧金条 */
[data-testid="stMarkdownContainer"] h2 {
  border-left: 4px solid var(--gold); padding-left: 10px; margin-top: .9em;
}

/* 卡片与指标 */
[data-testid="stMetric"] {
  background: var(--card); border:1px solid var(--line); border-radius: var(--radius);
  padding: 14px 18px 12px; box-shadow: 0 1px 3px rgba(16,42,67,.05);
}
[data-testid="stMetric"] label { color: var(--muted) !important; }
[data-testid="stMetric"] [data-testid="stMetricValue"] { color: var(--navy-700); font-weight:700; }

[data-testid="stExpander"] { border:1px solid var(--line); border-radius: var(--radius);
  background: var(--card); box-shadow: 0 1px 3px rgba(16,42,67,.04); }
[data-testid="stDataFrame"] { border:1px solid var(--line); border-radius: var(--radius); overflow:hidden; }

/* 按钮：主行动=A股红 */
[data-testid="stBaseButton-primary"] {
  background: linear-gradient(135deg, #d64545, #b93232); border:none;
  box-shadow: 0 4px 12px rgba(214,69,69,.28); font-weight:600;
}
[data-testid="stBaseButton-primary"]:hover { filter: brightness(1.06); }
[data-testid="stBaseButton-secondary"] { border-color: var(--line); color: var(--navy-700); }

/* Tabs */
[data-testid="stTabs"] [data-baseweb="tab-list"] { gap: 6px; border-bottom: 1px solid var(--line); }
[data-testid="stTabs"] [data-baseweb="tab"] { padding: 8px 16px; border-radius: 10px 10px 0 0; }
[data-testid="stTabs"] [aria-selected="true"] {
  background: var(--navy-700); color:#fff !important;
}
[data-testid="stTabs"] [aria-selected="true"] p { color:#fff !important; }
[data-testid="stTabs"] [data-baseweb="tab-highlight"] { display:none; }

/* 表单控件聚焦色 */
[data-baseweb="input"]:focus-within, [data-baseweb="select"]:focus-within { border-color: var(--navy-600) !important; }

/* 首页组件 */
.hero {
  background: linear-gradient(120deg, var(--navy-900) 0%, var(--navy-700) 55%, #205583 100%);
  border-radius: 18px; padding: 34px 38px; color: #eef4fa; position: relative; overflow: hidden;
  box-shadow: 0 10px 30px rgba(11,31,51,.25);
}
.hero::after { content:""; position:absolute; right:-70px; top:-70px; width:260px; height:260px;
  border-radius:50%; background: radial-gradient(circle, rgba(224,82,82,.35), transparent 65%); }
.hero::before { content:""; position:absolute; right:80px; bottom:-90px; width:220px; height:220px;
  border-radius:50%; background: radial-gradient(circle, rgba(201,161,92,.28), transparent 65%); }
.hero h1 { color:#fff; font-size:30px; margin:0 0 8px; }
.hero p { color:#c3d2e0; margin:0; font-size:14.5px; }
.chips { display:flex; gap:10px; margin-top:18px; flex-wrap:wrap; }
.chip { background:rgba(255,255,255,.1); border:1px solid rgba(255,255,255,.18);
  padding:5px 14px; border-radius:999px; font-size:12.5px; color:#e8eef5; }

.fcard {
  background: var(--card); border:1px solid var(--line); border-radius: var(--radius);
  padding: 20px 20px 16px; height:100%; box-shadow: 0 2px 8px rgba(16,42,67,.06);
  transition: transform .15s ease, box-shadow .15s ease;
}
.fcard:hover { transform: translateY(-3px); box-shadow: 0 8px 20px rgba(16,42,67,.12); }
.fcard .ic { font-size:26px; }
.fcard .t { font-size:16.5px; font-weight:700; color:var(--ink); margin:8px 0 6px; }
.fcard .d { font-size:13px; color:var(--muted); line-height:1.65; min-height:66px; }
.fcard .go a { color: var(--navy-600); font-weight:600; font-size:13px; text-decoration:none; }

.tile { background: var(--card); border:1px solid var(--line); border-radius: var(--radius);
  padding: 18px 20px; box-shadow: 0 1px 4px rgba(16,42,67,.05); }
.tile .v { font-size:26px; font-weight:800; color:var(--navy-700); line-height:1.1; }
.tile .l { font-size:13px; color:var(--muted); margin-top:4px; }
.tile .s { font-size:11.5px; color:#9aa8b6; margin-top:6px; }
.tile .bar { height:3px; width:34px; border-radius:2px; margin-bottom:12px; }

.step { display:flex; align-items:center; gap:0; }
.step .n { width:34px; height:34px; border-radius:50%; background:var(--navy-700); color:#fff;
  display:flex; align-items:center; justify-content:center; font-weight:700; font-size:14px; flex:none; }
.step .done .n { background: var(--up); }
.step .tx { margin-left:10px; }
.step .tx b { display:block; font-size:14px; color:var(--ink); }
.step .tx span { font-size:12px; color:var(--muted); }
.step .arrow { margin: 0 18px; color:#c3ccd6; font-size:18px; }

.ok-chip, .warn-chip { display:inline-block; padding:3px 12px; border-radius:999px; font-size:12px; font-weight:600; }
.ok-chip { background:#e7f4ee; color:#1f7a4d; border:1px solid #bfe3d0; }
.warn-chip { background:#fdf3e7; color:#a3660a; border:1px solid #f2d9b0; }

/* 新手引导条 */
.guide {
  background: linear-gradient(90deg, #eef4fb, #f7f9fc); border:1px solid #dbe6f2;
  border-left: 4px solid var(--navy-600); border-radius: 10px;
  padding: 8px 16px; margin: 0 0 10px; font-size: 13.5px; color:#33475c; line-height:1.65;
}
.guide b { color: var(--navy-700); }

/* 空状态引导卡 */
.es {
  background: var(--card); border:1px dashed #c9d5e2; border-radius: var(--radius);
  padding: 30px 24px; text-align: center; margin: 8px 0;
}
.es .ic { font-size: 34px; }
.es .t { font-size: 16px; font-weight:700; color: var(--ink); margin: 10px 0 6px; }
.es .d { font-size: 13px; color: var(--muted); line-height:1.7; }

/* 预设按钮行 */
.preset-row { display:flex; gap:8px; margin: 4px 0 10px; flex-wrap:wrap; }
.preset-chip { background:#fff; border:1px solid var(--line); border-radius:999px;
  padding: 4px 12px; font-size:12px; color:var(--navy-700); }

/* 顶部状态条：玻璃质感，左边缘与内容区对齐（随侧边栏展开/折叠切换 left） */
[data-testid="stHeader"] { min-height: 0; }
.app-topbar {
  position: fixed; top: 0; left: 88px; right: 0; height: 52px; z-index: 999980;
  width: min(1280px, 100%); margin: 0 auto;
  display: flex; align-items: center; gap: 14px; padding: 0 24px;
  background: rgba(250,251,253,.72);
  -webkit-backdrop-filter: saturate(180%) blur(14px);
  backdrop-filter: saturate(180%) blur(14px);
  border-bottom: 1px solid rgba(227,233,240,.9);
  box-shadow: 0 1px 2px rgba(11,31,51,.03), 0 8px 24px -14px rgba(11,31,51,.18);
  pointer-events: none;
  transition: left .22s cubic-bezier(.4,0,.2,1), padding-left .22s cubic-bezier(.4,0,.2,1);
}
/* 折叠态：回到视口左缘，并让出左上角「展开」按钮的位置 */
[data-testid="stAppViewContainer"]:has([data-testid="stSidebar"][aria-expanded="false"]) .app-topbar {
  left: 0; padding-left: 62px;
}
.app-topbar .tb-brand { display: inline-flex; align-items: center; gap: 9px; flex: 0 0 auto; }
.app-topbar .tb-logo {
  width: 26px; height: 26px; border-radius: 8px; display: inline-flex;
  align-items: center; justify-content: center;
  background: linear-gradient(135deg, #1c4468 0%, #0b1f33 100%);
  box-shadow: 0 2px 6px rgba(11,31,51,.22), inset 0 1px 0 rgba(255,255,255,.18);
}
.app-topbar .tb-name {
  font-size: 14px; font-weight: 500; letter-spacing: .02em; color: var(--navy-900);
  white-space: nowrap;
}
.app-topbar .tb-sep { width: 1px; height: 18px; background: var(--line); flex: 0 0 auto; }
.app-topbar .tb-chips { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.app-topbar .tb-chip {
  font-size: 11.5px; font-weight: 500; padding: 4px 10px 4px 8px; border-radius: 999px;
  line-height: 1.45; display: inline-flex; align-items: center; gap: 6px; white-space: nowrap;
  font-variant-numeric: tabular-nums; letter-spacing: .01em;
  border: 1px solid transparent;
}
.app-topbar .tb-chip .tb-dot { width: 6px; height: 6px; border-radius: 50%; flex: 0 0 auto; }
.app-topbar .tb-chip b { font-weight: 600; }
.app-topbar .tb-chip.c-date { background: rgba(28,68,104,.06); border-color: rgba(28,68,104,.08); color:#2c4a6b; }
.app-topbar .tb-chip.c-date .tb-dot { background:#4a90c9; box-shadow: 0 0 0 3px rgba(74,144,201,.14); }
.app-topbar .tb-chip.c-stock { background: rgba(38,166,154,.09); border-color: rgba(38,166,154,.14); color:#17786f; }
.app-topbar .tb-chip.c-stock .tb-dot { background:#26a69a; box-shadow: 0 0 0 3px rgba(38,166,154,.14); }
.app-topbar .tb-chip.c-kline { background: rgba(201,161,92,.11); border-color: rgba(201,161,92,.18); color:#8a6d2a; }
.app-topbar .tb-chip.c-kline .tb-dot { background: var(--gold); box-shadow: 0 0 0 3px rgba(201,161,92,.16); }
.app-topbar .tb-chip.warn { background: rgba(201,161,92,.16); border-color: rgba(201,161,92,.26); color:#8a6d2a; }
.app-topbar .tb-chip.warn .tb-dot { background: var(--gold); }
/* 折叠按钮在顶部 toolbar，层级必须高于状态条 */
[data-testid="stToolbar"] { z-index: 999999 !important; }
</style>
"""


def inject_theme():
    """注入全局主题（在 app.py 入口调用一次即可覆盖所有页面）。"""
    st.markdown(_THEME_CSS, unsafe_allow_html=True)


@st.cache_data(ttl=60, show_spinner=False)
def _get_topbar_status() -> dict:
    """获取顶部状态条需要的数据（缓存 60 秒，避免每次 rerun 查库）。"""
    try:
        from hikyuudata.em_finance import data_date
        from hikyuudata.importer import data_status
        fin_date = data_date()
        st = data_status()
        return {"fin_date": fin_date, "stock_count": st["stock_count"], "h5_files": st["h5_files"]}
    except Exception:
        return {"fin_date": None, "stock_count": 0, "h5_files": 0}


def top_status_bar():
    """顶部状态条：应用名 + 数据状态徽章（常驻所有页面上方，与内容区左缘对齐）。"""
    s = _get_topbar_status()
    fin = s["fin_date"] or "未导入"
    fin_warn = not s["fin_date"]
    stock = f"{s['stock_count']:,}" if s["stock_count"] else "—"
    h5 = s["h5_files"]
    logo = (
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" '
        'stroke="#ffffff" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" '
        'aria-hidden="true"><path d="M3 17l5-6 4 3.5L17 7l4 4.5"/>'
        '<circle cx="17" cy="7" r="1.4" fill="#ffffff" stroke="none"/></svg>'
    )
    chips = [
        f'<span class="tb-chip c-date {"warn" if fin_warn else ""}">'
        f'<span class="tb-dot"></span>财务快照 {fin}</span>',
        f'<span class="tb-chip c-stock"><span class="tb-dot"></span><b>{stock}</b> 只股票</span>',
        f'<span class="tb-chip c-kline"><span class="tb-dot"></span><b>{h5}</b> 个 K线文件</span>',
    ]
    st.markdown(
        f'<div class="app-topbar">'
        f'<span class="tb-brand"><span class="tb-logo">{logo}</span>'
        f'<span class="tb-name">A股量化选股工作台</span></span>'
        f'<span class="tb-sep"></span>'
        f'<span class="tb-chips">{"".join(chips)}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str = "", icon: str = "📊"):
    """统一页头：图标方块 + 标题 + 副标题。"""
    st.markdown(
        f'<div class="ph"><div class="ph-ico">{icon}</div>'
        f'<div class="ph-title">{title}</div></div>'
        + (f'<div class="ph-sub">{subtitle}</div>' if subtitle else ""),
        unsafe_allow_html=True,
    )


def guide(text: str):
    """页头下的新手引导条（一句话讲清本页怎么用）。"""
    st.markdown(f'<div class="guide">💡 <b>怎么用</b>｜{text}</div>', unsafe_allow_html=True)


def empty_state(icon: str, title: str, desc: str, page: str | None = None, label: str | None = None):
    """空状态引导卡：解释为什么空、下一步去哪。page 传 st.Page 的文件路径。"""
    st.markdown(
        f'<div class="es"><div class="ic">{icon}</div><div class="t">{title}</div>'
        f'<div class="d">{desc}</div></div>',
        unsafe_allow_html=True,
    )
    if page and label:
        st.page_link(page, label=label)


def init_page(title: str, icon: str = "📊"):
    st.set_page_config(page_title=f"A股量化选股 - {title}", page_icon=icon, layout="wide")


def board_selector(key: str) -> list[str]:
    """板块范围多选（默认全选；只选主板 = 保留「沪主板/深主板」）。"""
    from selector.scanner import ALL_BOARDS

    boards = st.multiselect(
        "板块范围", list(ALL_BOARDS), default=list(ALL_BOARDS), key=key,
        help="只选主板：保留「沪主板」「深主板」，去掉创业板/科创板/北交所",
    )
    if not boards:
        st.warning("未选择任何板块，结果将为空。")
    return boards


# ---------------- 个股 K 线图（K线/成交量/MACD/KDJ） ----------------


@st.cache_data(ttl=3600, show_spinner=False)
def _load_kline_df(market_code: str, days: int):
    """读取个股前复权日线并计算 MA/MACD/KDJ（pandas 实现，与内置策略公式一致）。"""
    import pandas as pd
    from hikyuu import Query

    from hikyuudata.initializer import get_sm

    stk = get_sm()[market_code]
    name = stk.name if stk and stk.valid else market_code
    kd = stk.get_kdata(Query(-int(days), ktype=Query.DAY, recover_type=Query.EQUAL_FORWARD))
    rows = [
        (str(kd[i].datetime)[:10], kd[i].open, kd[i].high, kd[i].low,
         kd[i].close, kd[i].volume)
        for i in range(len(kd))
    ]
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    if df.empty:
        return name, df

    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]
    for n in (5, 10, 20):
        df[f"ma{n}"] = c.rolling(n).mean()
    df["vol_ma5"] = v.rolling(5).mean()

    dif = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    dea = dif.ewm(span=9, adjust=False).mean()
    df["dif"], df["dea"], df["macd"] = dif, dea, 2 * (dif - dea)

    low9 = l.rolling(9).min()
    high9 = h.rolling(9).max()
    rsv = (c - low9) / (high9 - low9) * 100
    k = rsv.ewm(alpha=1 / 3, adjust=False).mean()  # hikyuu SMA(x,3,1) 等价
    d = k.ewm(alpha=1 / 3, adjust=False).mean()
    df["kdj_k"], df["kdj_d"], df["kdj_j"] = k, d, 3 * k - 2 * d
    return name, df


def stock_chart_panel(market_code: str, days: int = 250):
    """个股四联图：K线+均线 / 成交量 / MACD / KDJ（A股红涨绿跌）。"""
    from plotly.subplots import make_subplots

    name, df = _load_kline_df(market_code, days)
    if df.empty:
        st.warning(f"{market_code} 无 K 线数据")
        return

    up = df["close"] >= df["open"]
    vol_colors = ["#ef5350" if u else "#26a69a" for u in up]
    macd_colors = ["#ef5350" if x >= 0 else "#26a69a" for x in df["macd"]]

    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.02,
        row_heights=[0.46, 0.14, 0.20, 0.20],
        subplot_titles=(f"{name} {market_code}（前复权，近{len(df)}日）", "成交量", "MACD(12,26,9)", "KDJ(9,3,3)"),
    )
    fig.add_candlestick(
        x=df["date"], open=df["open"], high=df["high"], low=df["low"], close=df["close"],
        increasing_line_color="#ef5350", decreasing_line_color="#26a69a",
        name="K线", row=1, col=1,
    )
    for n, color in ((5, "#f6c342"), (10, "#5b9bd5"), (20, "#ab7bd8")):
        fig.add_scatter(x=df["date"], y=df[f"ma{n}"], mode="lines", name=f"MA{n}",
                        line=dict(width=1, color=color), row=1, col=1)
    fig.add_bar(x=df["date"], y=df["volume"], marker_color=vol_colors, name="VOL", row=2, col=1)
    fig.add_scatter(x=df["date"], y=df["vol_ma5"], mode="lines", name="MA5量",
                    line=dict(width=1, color="#f6c342"), row=2, col=1)
    fig.add_bar(x=df["date"], y=df["macd"], marker_color=macd_colors, name="MACD", row=3, col=1)
    fig.add_scatter(x=df["date"], y=df["dif"], mode="lines", name="DIF",
                    line=dict(width=1, color="#f6c342"), row=3, col=1)
    fig.add_scatter(x=df["date"], y=df["dea"], mode="lines", name="DEA",
                    line=dict(width=1, color="#5b9bd5"), row=3, col=1)
    fig.add_scatter(x=df["date"], y=df["kdj_k"], mode="lines", name="K",
                    line=dict(width=1, color="#f6c342"), row=4, col=1)
    fig.add_scatter(x=df["date"], y=df["kdj_d"], mode="lines", name="D",
                    line=dict(width=1, color="#5b9bd5"), row=4, col=1)
    fig.add_scatter(x=df["date"], y=df["kdj_j"], mode="lines", name="J",
                    line=dict(width=1, color="#ab7bd8"), row=4, col=1)
    fig.update_layout(
        height=780, showlegend=False, margin=dict(l=10, r=10, t=30, b=10),
        xaxis_rangeslider_visible=False, hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True, key=f"kline_{market_code}")


def strategy_editor(key_prefix: str = "se") -> dict | None:
    """策略选择编辑器（内置策略 / 自定义条件组合）。

    返回 {"kind": "builtin", "name", "params", "title"}
       或 {"kind": "dsl", "conditions", "logic", "title"}
       或 None（用户未选择）。
    """
    mode = st.radio("策略类型", ["内置技术策略", "自定义条件组合"], horizontal=True, key=f"{key_prefix}_mode")
    if mode == "内置技术策略":
        from strategy.builtin import BUILTIN_STRATEGIES
        _rec = {"macd_above_zero_kdj_golden", "pullback_ma_bull"}  # 新手推荐
        name = st.selectbox(
            "选择策略",
            list(BUILTIN_STRATEGIES),
            format_func=lambda n: (
                f"⭐ {BUILTIN_STRATEGIES[n]['title']}（新手推荐）- {BUILTIN_STRATEGIES[n]['description']}"
                if n in _rec else
                f"{BUILTIN_STRATEGIES[n]['title']} - {BUILTIN_STRATEGIES[n]['description']}"
            ),
            key=f"{key_prefix}_name",
        )
        info = BUILTIN_STRATEGIES[name]
        params = {}
        with st.expander("策略参数", expanded=True):
            cols = st.columns(len(info["params"]))
            for col, (pname, (default, desc)) in zip(cols, info["params"].items()):
                if isinstance(default, float):
                    params[pname] = col.number_input(desc, value=float(default), step=0.1, key=f"{key_prefix}_p_{pname}")
                else:
                    params[pname] = col.number_input(desc, value=int(default), step=1, key=f"{key_prefix}_p_{pname}")
        title = info["title"] + (f" {params}" if params else "")
        return {"kind": "builtin", "name": name, "params": params, "title": title}

    # 自定义条件组合
    from strategy.dsl import OPERATORS, describe
    if f"{key_prefix}_conds" not in st.session_state:
        st.session_state[f"{key_prefix}_conds"] = [
            {"left": {"kind": "indicator", "name": "MA", "params": [5], "ref": 0},
             "op": ">=",
             "right": {"kind": "indicator", "name": "MA", "params": [20], "ref": 0},
             "logic": "AND"}
        ]
    conds = st.session_state[f"{key_prefix}_conds"]
    with st.container(border=True):
        for i, c in enumerate(conds):
            cols = st.columns([3, 1.2, 3, 0.4])
            with cols[0]:
                _operand_editor(c["left"], f"{key_prefix}_l{i}")
            with cols[1]:
                c["op"] = st.selectbox(
                    "算子", list(OPERATORS),
                    index=list(OPERATORS).index(c["op"]),
                    format_func=lambda o: OPERATORS[o][0],
                    key=f"{key_prefix}_op{i}", label_visibility="collapsed",
                )
            with cols[2]:
                _operand_editor(c["right"], f"{key_prefix}_r{i}", op=c["op"])
            with cols[3]:
                if st.button("✕", key=f"{key_prefix}_del{i}", help="删除该条件") and len(conds) > 1:
                    conds.pop(i)
                    st.rerun()
        if st.button("＋ 添加条件", key=f"{key_prefix}_add"):
            conds.append({
                "left": {"kind": "indicator", "name": "CLOSE", "params": [], "ref": 0},
                "op": ">",
                "right": {"kind": "const", "value": 0},
                "logic": "AND",
            })
            st.rerun()
        logic = st.radio("条件组合方式", ["AND（同时满足）", "OR（任一满足）"], horizontal=True, key=f"{key_prefix}_logic")
    logic = "OR" if logic.startswith("OR") else "AND"
    desc = " 且 ".join(describe(c) for c in conds) if logic == "AND" else " 或 ".join(describe(c) for c in conds)
    st.caption(f"条件: {desc}")
    return {"kind": "dsl", "conditions": [dict(c) for c in conds], "logic": logic, "title": f"自定义({desc[:40]}…)" if len(desc) > 40 else f"自定义({desc})"}


def _operand_editor(spec: dict, key: str, op: str | None = None):
    """编辑单个操作数（指标或常量）；op 为 between 时右侧渲染上下界两个输入。"""
    from strategy.dsl import INDICATORS
    kind = st.selectbox(
        "类型", ["indicator", "const"],
        index=0 if spec["kind"] == "indicator" else 1,
        format_func=lambda k: "指标" if k == "indicator" else "常量",
        key=f"{key}_kind", label_visibility="collapsed",
    )
    if kind == "const":
        spec["kind"] = "const"
        if op == "between":
            v = spec.get("value")
            lo, hi = (v if isinstance(v, (list, tuple)) and len(v) == 2 else (0.0, 100.0))
            c1, c2 = st.columns(2)
            lo_v = c1.number_input("下界", value=float(lo), key=f"{key}_lo", label_visibility="collapsed")
            hi_v = c2.number_input("上界", value=float(hi), key=f"{key}_hi", label_visibility="collapsed")
            spec["value"] = [float(lo_v), float(hi_v)]
        else:
            spec["value"] = st.number_input(
                "常量值", value=float(spec["value"]) if not isinstance(spec.get("value"), (list, tuple)) else 0.0,
                key=f"{key}_val", label_visibility="collapsed",
            )
        return
    spec["kind"] = "indicator"
    name = st.selectbox(
        "指标", list(INDICATORS),
        index=list(INDICATORS).index(spec.get("name", "CLOSE")) if spec.get("name") in INDICATORS else 0,
        format_func=lambda n: f"{n} ({INDICATORS[n][1]})",
        key=f"{key}_name", label_visibility="collapsed",
    )
    spec["name"] = name
    params_text = st.text_input(
        "参数(逗号分隔)",
        value=",".join(str(p) for p in spec.get("params") or []),
        key=f"{key}_params", label_visibility="collapsed",
        placeholder="参数",
    )
    spec["params"] = [p.strip() for p in params_text.split(",") if p.strip()] if params_text else []
    ref = st.number_input(
        "前移N日", value=int(spec.get("ref", 0)), min_value=0, max_value=250, step=1,
        key=f"{key}_ref", label_visibility="collapsed",
    )
    spec["ref"] = int(ref)


def build_condition_from_spec(spec: dict):
    """按 strategy_editor 的返回构建 hikyuu 条件指标。"""
    from strategy.builtin import build_condition
    from strategy.dsl import compile_conditions

    if spec["kind"] == "builtin":
        return build_condition(spec["name"], **spec["params"])
    return compile_conditions(spec["conditions"], spec["logic"])
