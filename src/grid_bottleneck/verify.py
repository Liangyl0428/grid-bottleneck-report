# -*- coding: utf-8 -*-
"""报告数字对账：把 `docs/电网瓶颈与颠覆性方向.md` 里表格中的数字逐格回溯到快照 CSV。

解析"第一格是词条名或子方向编号"的表格行，并去掉 `词条：` / `子方向 ` 前缀；
括号里的原始计数（如 `2.77×（96/34）`）也逐个数回溯，不再只校验括号外的倍数。
说明性文字（整格规约不成数字且没有括号计数）才整格跳过。

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
    "df_recent", "df_3y_sum", "hits_3y", "hits_recent", "hits_prev", "hits_base",
    "patents_recent", "patents_base", "policies_recent", "policies_base",
    "share_yoy_median", "declining_share", "patent_growth_annualized",
]

# 文档里不会回溯到快照的数字（外部资料、算法常数、年份、窗口篇数等）
ALLOW_LITERALS = {
    "1.275", "1.2", "0.3", "0.5", "2021", "2022", "2023", "2024", "2025", "2026",
    "8", "12", "15", "10", "33", "1811", "1,811", "175", "44.5", "6,621",
    "423,464", "332,096", "1,043,978", "18", "98", "2.5", "0.0", "1.0",
}

NUM = re.compile(r"[-+]?\d+(?:\.\d+)?")
# 行首前缀：`词条：车网互动` / `子方向 4.1 电力市场机制` / `词条 车网互动`
PREFIX = re.compile(r"^(?:词条|子方向)\s*[：:]?\s*")
# 中文括号里的原始计数：`（123/38）`、`（88,623 / 92,068，产业没撤 ✓）`
PAREN = re.compile(r"（([^）]*)）")


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


def _paren_tokens(cell: str) -> list:
    """括号内的数字 token（去掉千分位逗号）。"""
    out = []
    for m in PAREN.finditer(cell):
        out += NUM.findall(m.group(1).replace(",", ""))
    return out


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
    # 报告里的"需 ≥X"是颠覆门槛 max(1.25, yoy²)；把 yoy² / 专利² 也放进可回溯集合
    for k in ("yoy", "share_yoy", "patent_growth"):
        try:
            out |= _fmts(float(row[k]) ** 2)
        except (KeyError, TypeError, ValueError):
            pass
    try:
        out |= _fmts(max(1.25, float(row["yoy"]) ** 2))
    except (KeyError, TypeError, ValueError):
        pass
    return out


def resolve(name: str, terms: dict, subs: dict):
    for cand in (name.strip(), PREFIX.sub("", name, count=1).strip()):
        if not cand:
            continue
        if cand in terms:
            return terms[cand]
        m = re.match(r"(\d+\.\d+)", cand)
        if m and m.group(1) in subs:
            return subs[m.group(1)]
    return None


def check(doc: Path = DEFAULT_DOC, allow: set | None = None) -> tuple:
    """返回 (checked, bad, skipped, noobj)；bad 为 [(行号, 对象, 数字, 原格)]。"""
    allow = ALLOW_LITERALS | (allow or set())
    allow_norm = {a.replace(",", "") for a in allow}
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
            parens = _paren_tokens(cell)
            if cleaned is None and not parens:
                skipped += 1
                continue
            tokens = [] if cleaned is None else [t.replace(",", "") for t in NUM.findall(cleaned)]
            tokens += parens
            for tok in tokens:
                if tok in allow_norm or tok in pool:
                    checked += 1
                else:
                    bad.append((lineno, cells[0][:24], tok, cell[:40]))
    return checked, bad, skipped, noobj
