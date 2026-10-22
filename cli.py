"""命令行入口：数据导入/更新/选股扫描（可脱离 UI 跑批）。

用法：
    python3 cli.py import [--start 2024-01-01]
                             导入行情（基础信息+K线+权息），K线自动增量
    python3 cli.py backfill [--start 2010-01-01]
                             历史回补：把已导入的短历史扩充为全历史（耗时较长）
    python3 cli.py update            增量更新（同 import，按库内最后日期续导）
    python3 cli.py import-finance    导入财务快照
    python3 cli.py import-blocks     导入板块信息（东方财富）
    python3 cli.py status            查看数据状态
    python3 cli.py scan --strategy macd_golden [--days 250] [--out csv路径]
    python3 cli.py scan --list       列出内置策略
"""
import argparse
import sys


def _cmd_import(args) -> None:
    from hikyuudata import importer

    if args.start:
        importer.import_base_info()
        importer.import_kdata(start_date=args.start)
        importer.import_weight()
    else:
        importer.import_all()


def _cmd_backfill(args) -> None:
    from hikyuudata import importer

    importer.import_kdata(start_date=args.start, backfill=True)


def _cmd_update(_args) -> None:
    from hikyuudata import importer

    importer.update_all()


def _cmd_import_finance(_args) -> None:
    from hikyuudata import importer

    importer.import_finance()


def _cmd_import_blocks(_args) -> None:
    from hikyuudata import importer

    importer.import_blocks()


def _cmd_status(_args) -> None:
    from hikyuudata import importer

    status = importer.data_status()
    print(f"数据库文件: {importer.get_db_path()} ({'存在' if status['db_exists'] else '不存在'})")
    print(f"有效股票数: {status['stock_count']}")
    print(f"h5 文件数: {status['h5_files']}")
    for table, count in status["tables"].items():
        print(f"表 {table}: {count}")


def _cmd_scan(args) -> None:
    if args.list:
        from strategy.builtin import BUILTIN_STRATEGIES

        for name, info in BUILTIN_STRATEGIES.items():
            params = ", ".join(f"{k}={v[0]}" for k, v in info["params"].items())
            print(f"{name}: {info['title']} - {info['description']} (参数: {params})")
        return

    if not args.strategy:
        print("请指定 --strategy，或用 --list 查看内置策略", file=sys.stderr)
        sys.exit(2)

    import time

    from selector.scanner import scan_builtin

    t0 = time.time()
    print(f"开始扫描: {args.strategy} (最近 {args.days} 个交易日数据) ...")
    rows = scan_builtin(
        args.strategy,
        days=args.days,
        progress=lambda cur, total: print(f"\r进度 {cur}/{total}", end="", flush=True),
    )
    print(f"\n扫描完成，耗时 {time.time() - t0:.1f}s，选中 {len(rows)} 只:")
    for r in rows:
        print(f"  {r['market_code']} {r['stock_name']} 收盘 {r['close']}")

    if args.out:
        import csv

        with open(args.out, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f, fieldnames=["market_code", "stock_code", "stock_name", "close", "detail"]
            )
            writer.writeheader()
            writer.writerows(rows)
        print(f"结果已保存: {args.out}")


def main() -> None:
    parser = argparse.ArgumentParser(description="hikyuu 选股软件命令行")
    sub = parser.add_subparsers(dest="command", required=True)

    p_import = sub.add_parser("import", help="导入行情（基础信息+K线+权息）")
    p_import.add_argument("--start", default=None, help="K线起始日期，如 2024-01-01")
    p_import.set_defaults(func=_cmd_import)

    p_bf = sub.add_parser("backfill", help="历史回补（扩充为全历史）")
    p_bf.add_argument("--start", default="2010-01-01", help="回补起始日期")
    p_bf.set_defaults(func=_cmd_backfill)

    sub.add_parser("update", help="增量更新").set_defaults(func=_cmd_update)
    sub.add_parser("import-finance", help="导入财务快照").set_defaults(func=_cmd_import_finance)
    sub.add_parser("import-blocks", help="导入板块信息").set_defaults(func=_cmd_import_blocks)
    sub.add_parser("status", help="数据状态").set_defaults(func=_cmd_status)

    p_scan = sub.add_parser("scan", help="全市场扫描")
    p_scan.add_argument("--strategy", help="内置策略名")
    p_scan.add_argument("--days", type=int, default=250, help="使用的最近交易日数")
    p_scan.add_argument("--out", help="结果输出 csv 路径")
    p_scan.add_argument("--list", action="store_true", help="列出内置策略")
    p_scan.set_defaults(func=_cmd_scan)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
