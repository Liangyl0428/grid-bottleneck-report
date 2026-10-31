# -*- coding: utf-8 -*-
"""命令行入口。

    python -m grid_bottleneck subtopics            # 复算子方向指标，打印归类
    python -m grid_bottleneck subtopics --out x.csv # 写 CSV（默认写回 data/，谨慎）
    python -m grid_bottleneck verify               # 报告数字对账（CI 用，失败退出码 1）
    python -m grid_bottleneck summary              # 只打印瓶颈/伪前沿归类清单
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from . import data
from .subtopic import CLASS_LABEL, COLUMNS, aggregate
from .verify import DEFAULT_DOC, check, metrics_of


def _fmt(v):
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, float):
        return f"{v:.6g}"
    return v


def build_rows():
    terms = data.load_terms()
    papers_q = data.load_papers_quarter()
    corpus = data.load_corpus()
    return aggregate(terms, papers_q, corpus, data.load_rules(), data.load_review())


def write_csv(rows, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(COLUMNS)
        for r in rows:
            w.writerow([_fmt(r.get(c, "")) for c in COLUMNS])
    return path


def print_classes(rows):
    by = {}
    for r in rows:
        by.setdefault(r["class_primary"], []).append(r)
    for cls in ("bottleneck", "mature_industry", "academic_hot_industry_cold", "both_declining"):
        got = by.get(cls, [])
        if not got:
            continue
        print(f"\n[{CLASS_LABEL.get(cls, cls)}] {len(got)} 个")
        for r in got:
            print(f"  {r['subtopic']}  份额 {r['share_yoy']:.3f}  专利 {r['patent_growth']:.2f}"
                  f"  提及量 {r['hits_3y']:,.0f}")
            if r["class_note"]:
                print(f"    注：{r['class_note']}")
    excluded = [r for r in rows if not r["class_primary"]]
    print(f"\n[未归类/不参与判定] {len(excluded)} 个")


def cmd_subtopics(args):
    rows = build_rows()
    if args.out:
        path = write_csv(rows, Path(args.out))
        print(f"已写 {path}（{len(rows)} 个子方向）")
    print_classes(rows)
    return 0


def cmd_summary(args):
    print_classes(build_rows())
    return 0


def cmd_verify(args):
    checked, bad, skipped, noobj = check(Path(args.doc), set(args.allow or []))
    total = checked + len(bad)
    print(f"文档: {Path(args.doc).name}")
    print(f"可回溯数字 {checked}/{total}；说明性格子跳过 {skipped}")
    if noobj:
        ids = sorted(noobj)
        shown = "、".join(ids[:8]) + (" …" if len(ids) > 8 else "")
        print(f"未纳入逐格校验的表格行 {len(noobj)} 个（arXiv 外部计数、汇总表等非词条行；"
              f"`词条：`/`子方向` 前缀与`器件大盘：`/`（背景）`注记已识别）: " + shown)
    if bad:
        print(f"\n无法回溯的数字 {len(bad)} 处：")
        for lineno, name, tok, cell in bad:
            print(f"  L{lineno} [{name}] {tok!r}  在格: {cell}")
        return 1
    print("全部数字都能在 data/*.csv 中找到对应指标。")
    return 0


def cmd_show(args):
    """看单条词条/子方向的全部指标（排查用）。"""
    terms = data.load_terms()
    for t in terms:
        if t["term"] == args.name:
            for k, v in t.items():
                print(f"{k:>22}: {v}")
            return 0
    rows = build_rows()
    for r in rows:
        if r["code"] == args.name or r["subtopic"] == args.name:
            for k, v in r.items():
                print(f"{k:>22}: {v}")
            return 0
    print(f"没找到 {args.name}", file=sys.stderr)
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="grid-bottleneck", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("subtopics", help="复算子方向指标与归类")
    p.add_argument("--out", help="写 CSV 的路径（不写则只打印）")
    p.set_defaults(func=cmd_subtopics)
    p = sub.add_parser("summary", help="只打印归类清单")
    p.set_defaults(func=cmd_summary)
    p = sub.add_parser("verify", help="报告数字对账")
    p.add_argument("--doc", default=str(DEFAULT_DOC))
    p.add_argument("--allow", nargs="*", default=[], help="额外豁免的字面量")
    p.set_defaults(func=cmd_verify)
    p = sub.add_parser("show", help="查看单条词条/子方向的指标")
    p.add_argument("name")
    p.set_defaults(func=cmd_show)
    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        ap.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
