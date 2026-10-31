# -*- coding: utf-8 -*-
"""报告数字对账：把 `docs/电网瓶颈与颠覆性方向.md` 里表格中的数字逐格回溯到快照 CSV。

只解析"第一格是词条名或子方向编号"的表格行；说明性文字（规约不成纯数字的格子）整格跳过。

它不是"证明结论正确"，而是"证明没有手抄错数字，且每个数字都能指到某张表"。
退出码：有任何一个数字无法回溯 → 1（可直接放进 CI）。
"""
from __future__ import annotations

import csv
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from .data import DATA, ROOT

DEFAULT_DOC = ROOT / "docs" / "电网瓶颈与颠覆性方向.md"

# 一个对象上可被引用的指标（列名来自 terms_report.csv / subtopic_report.csv）
METRIC_KEYS = [
    "yoy", "share_yoy", "patent_growth", "policy_growth", "slope",
    "df_recent", "df_3y_sum", "hits_3y", "patents_recent", "policies_recent",
    "share_yoy_median", "declining_share", "patent_growth_annualized",
]

# 文档里不会回溯到快照的数字（外部资料、算法常数、年份、窗口篇数等）
ALLOW_LITERALS = {
    "1.275", "1.2", "0.3", "0.5", "2021", "2022", "2023", "2024", "2025", "2026",
    "8", "12", "15", "10", "33", "1811", "1,811", "175", "44.5", "7,070", "6,592",
    "423,464", "332,096", "1,043,978", "18", "98", "2.5", "0.0", "1.0",
}

NUM = re.compile(r"[-+]?\d+(?:\.\d+)?")


def _fmts(v: float) -> set:
    """一个指标允许的写法：常见保留位数 + 百分数；四舍五入两种规则都接受
    （3.125 写成 3.12 或 3.13 都算对，避免把舍入约定当成数据错误）。"""
    out = set()
    for nd in (3, 2, 1, 0):
        q = Decimal(1).scaleb(-nd)
        out.add(str(Decimal(repr(v)).quantize(q, rounding=ROUND_HALF_UP)))
        out.add(f"{v:.{nd}f}")
        p = v * 100
        out.add(str(Decimal(repr(p)).quantize(q, rounding=ROUND_HALF_UP)))
        out.add(f"{p:.{nd}f}")
    out |= {f"{v:+.3f}", f"{v:+.2f}"}
    return out


def _clean_cell(cell: str):
    """规约成"纯数字"再扫描；规约不掉的（说明性文字）返回 None。"""
    s = re.sub(r"（[^）]*）", "", cell)          # 去中文括号（内是注记）
    for ch in ("**", "×", "\u2212", "≥", "<", ">"):
        s = s.replace(ch, "-" if ch == "\u2212" else "")
    s = s.strip().rstrip("%").strip()
    return s if re.fullmatch(r"[-+]?\d[\d,]*(?:\.\d+)?", s) else None


def load_pool():
    terms, subs = {}, {}
    with open(DATA / "terms_report.csv", encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            terms[r["term"]] = r
    with open(DATA / "subtopic_report.csv", encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            subs[r["code"]] = r
    return terms, subs


def metrics_of(row: dict) -> set:
    out = set()
    for k in METRIC_KEYS:
        v = row.get(k)
        if v in (None, ""):
            continue
        try:
            out |= _fmts(float(v))
        except ValueError:
            continue
    return out


def resolve(name: str, terms: dict, subs: dict):
    if name in terms:
        return terms[name]
    m = re.match(r"(\d+\.\d+)", name)
    if m and m.group(1) in subs:
        return subs[m.group(1)]
    return None


def check(doc: Path = DEFAULT_DOC, allow: set | None = None) -> tuple:
    """返回 (checked, bad, skipped, noobj)；bad 为 [(行号, 对象, 数字, 原格)]。"""
    allow = ALLOW_LITERALS | (allow or set())
    terms, subs = load_pool()
    bad, checked, skipped, noobj = [], 0, 0, set()
    for lineno, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        obj = resolve(cells[0], terms, subs)
        if obj is None:
            if any(ch.isdigit() for ch in cells[0]):
                noobj.add(cells[0][:26])
            continue
        pool = metrics_of(obj)
        for cell in cells[1:]:
            cleaned = _clean_cell(cell)
            if cleaned is None:
                skipped += 1
                continue
            for tok in NUM.findall(cleaned):
                tok = tok.replace(",", "")
                if tok in allow or tok in pool:
                    checked += 1
                else:
                    bad.append((lineno, cells[0][:24], tok, cell[:40]))
    return checked, bad, skipped, noobj
