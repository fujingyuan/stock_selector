# hikyuu A 股选股软件实现计划

## Context
用户要在空目录 `/home/fu/stock-slector` 从零开发一个基于 hikyuu 的 A 股选股软件。已确认需求：
- **Web 界面**（不用 PyQt）→ 选型 **Streamlit**（"参数配置→长任务→表格展示"形态，`st.cache_resource` 缓存 hikyuu 全局单例，开发成本最低）
- **数据来源**：hikyuu 网络在线导入（pytdx 网络行情服务器，无需通达信本地文件；板块走东方财富接口）
- **策略**：内置技术指标策略 + 自定义条件组合 + 基本面筛选
- **回测**：选股 + 用 hikyuu System/Portfolio 回测并输出收益/胜率等绩效

已核实关键 API（hikyuu==2.8.3，PyPI 有 manylinux wheel，兼容 Python 3.10）：
- 初始化：`hikyuu.load_hikyuu(start_spot=False, lazy_preload=True)` 读 `~/.hikyuu/hikyuu.ini`，再 `hikyuu.StockManager.instance()`（勿用旧版 init_from_file）
- 导入：`from hikyuu.data.pytdx_to_h5 import import_data`（pytdx API 连接后逐市场/周期导入）；财务快照 `pytdx_import_finance_to_sqlite`；历史财务仿照官方 `ImportHistoryFinanceTask`（gpcw.txt 清单 + MD5 增量下载 zip）
- 指标：`MA/CLOSE/VOL/MACD/KDJ/CROSS/REF` 等直接调用，多结果指标用 `get_result(0/1/2)`
- 选股器：`from hikyuu.trade_sys import SelectorBase`，子类实现 `_calculate()/get_selected(dt)/_clone()`
- 回测：`SYS_Simple(tm=crtTM(...), sg=SG_Bool/CN_Bool, mm=MM_FixedCount...)`；组合 `PF_WithoutAF(tm, se=SE_Signal(...), adjust_mode="day")`；绩效 `tm.get_performance()`、`pf.performance()`
- 复权用 `Query.EQUAL_BACKWARD`（前复权有未来函数问题）

## 项目结构
```
stock-slector/
├── app.py                    # Streamlit 入口（多页导航）
├── pages/
│   ├── 1_数据管理.py          # 全量/增量导入、进度展示、数据状态
│   ├── 2_选股.py              # 策略选择/条件组合编辑 → 选股 → 结果表
│   ├── 3_回测.py              # 策略回测 → 绩效报告 + 交易明细
│   └── 4_结果导出.py          # 历史/回测结果管理与 CSV 导出
├── hikyuudata/
│   ├── importer.py           # 首次全量 + 增量导入（K线/权息/板块/财务）
│   └── initializer.py        # load_hikyuu 封装（供 st.cache_resource）
├── strategy/
│   ├── builtin.py            # 内置策略 → SG_Bool/CN_Bool 映射
│   ├── dsl.py                # 界面条件(指标+算子+对象) → Indicator 表达式编译
│   └── fundamental.py        # 财务字段筛选（get_finance_info / get_history_finance）
├── selector/
│   └── dsl_selector.py       # SelectorBase 子类（供 PF 回测）
├── backtest/
│   └── runner.py             # SYS/PF 回测与绩效导出
├── store/
│   └── results.db            # 选股/回测结果 sqlite
├── cli.py                    # 命令行：import / update / scan（可脱离 UI 跑批）
└── requirements.txt
```

## 数据层设计
- 数据目录 `~/.hikyuu`（hikyuu.ini + stock.db + h5 文件）。程序生成默认 hikyuu.ini
- **首次全量**：`cli.py import` 逐市场（sh/sz/be）× 周期（DAY）调 `import_data(conn, market, "DAY", ["stock"], api, datadir, start_date, progress_cb)`；板块用 `hikyuu.data.em_block_to_sqlite`（东方财富源，隔离在 importer 单模块）
- **财务数据**：快照 `pytdx_import_finance_to_sqlite`；历史财务首次较慢（几十个 zip），一次性后台执行
- **日常增量**：按 `get_last_date` 取库内最后日期仅导新数据；UI 按钮 + 可选 crontab
- pytdx 服务器列表轮换 + 失败重试

## 策略引擎设计
- **内置策略**（strategy/builtin.py）：MACD金叉、均线多头排列、KDJ金叉、放量突破等，每条预定义为 SG_Bool/CN_Bool 表达式模板（含可调参数）
- **自定义条件组合**（strategy/dsl.py）：界面配置「指标(参数) + 算子(>/>=/</CROSS/REF偏移) + 对象(常量/另一指标)」多行 AND/OR 组合，编译为 hikyuu Indicator 0/1 序列表达式 → 包 `SG_Bool(买,卖)` 或 `CN_Bool(cond)`
- **基本面筛选**（strategy/fundamental.py）：`stk.get_finance_info()`（PE、市值=现价×总股本）+ `stk.get_history_finance()` 配合 `sm.get_history_finance_field_index(name)` 取 ROE 等历史字段
- **全市场扫描**：遍历 `sm.get_stock_list()`，对每只取 `get_kdata(Query(-N, ktype=Query.DAY, recover_type=Query.EQUAL_FORWARD))` 算指标末值过滤；C++ 引擎性能足够，选股结果缓存 `st.cache_data` + 落库 results.db

## 回测设计
- 单票调试：`SYS_Simple(tm=crtTM(init_cash=300000), sg=..., mm=MM_FixedCount(n), tp=..., sp=...)`，`sys.run(stock, Query(-500))`
- 组合回测：`PF_WithoutAF(tm, se=SE_Signal(...), adjust_mode="day", adjust_cycle=1)`，`pf.run(Query(-500))`
- 绩效输出：`tm.get_performance()`（胜率、年均收益率、累计收益等 `names()` 全表）、`tm.get_trade_list().to_pandas()` 交易明细、`pf.performance()` 组合级

## 分阶段实现步骤
1. **环境搭建**：pip 安装 hikyuu/streamlit/pandas/h5py（numpy 升 1.26.4），验证 `load_hikyuu` 可初始化
2. **数据层**：hikyuudata/（importer + initializer）+ cli.py，跑通全量导入并验证 `sm['sz000001'].get_kdata(Query(-10))`
3. **策略+选股引擎**：builtin.py + dsl.py + 全市场扫描，抽样对比手工计算验证指标正确性
4. **基本面筛选**：fundamental.py + 财务数据导入
5. **回测引擎**：dsl_selector.py + backtest/runner.py，输出绩效表与交易明细
6. **Streamlit UI 整合**：app.py + pages/，数据管理/选股/回测/导出四页，整合联调

## 风险与注意
- Streamlit 每次交互 rerun 全脚本：hikyuu 全局 init 只能一次，所有页面共用 `get_sm()`（st.cache_resource）；长任务用后台线程 + st.status 进度
- 东方财富 em_block 接口变动风险：隔离在 importer 单模块便于修复
- 历史财务首次导入耗时长：提示用户一次性后台执行
- 避免同机多进程并发 init hikyuu
- pytdx 网络服务器不稳：多服务器轮换

## 验证方式
- 数据层：`cli.py import` 后 `cli.py scan --strategy macd_golden` 能出结果；抽查 000001 平安银行 K 线与行情软件一致
- 策略层：对若干股票手工用公式复算 MACD/MA 值对比选股引擎输出
- 回测：跑 PF 回测输出绩效表（胜率/收益），交易明细笔数与 SG 信号数合理匹配
- UI：`streamlit run app.py` 走通 数据导入→选股→回测→导出 全流程（浏览器实测）
