# -*- coding: utf-8 -*-
"""报告数字对账：把 `docs/电网瓶颈与颠覆性方向.md` 里表格中的数字逐格回溯到快照 CSV。

解析"第一格是词条名或子方向编号"的表格行，并在解析前做归一化：

- 去掉 `词条：` / `子方向 ` 前缀；
- 去掉尾部注记，如 `锂离子电池（背景）`、`制氢（已在工程化）`；
- 去掉说明性前缀，如 `器件大盘：`、`控制/惯量：`、`储运：`、`单点补丁：`；
- 一行两个对象（`二极管 / 电容器`）时按 ` / ` 拆开，指标取两个对象的并集；
- 对象写在第二格时（`| 已进入产业化的主体技术 | 子方向 7.2 太阳能发电 | …`）从第二格取；
- 证据表上下文：`证据（子方向 5.1）` 之后紧跟的 `三年提及量` / `份额同比` / `专利同比` /
  `政策同比` / `季度份额斜率` 行，按该子方向对账。

括号里的原始计数（如 `2.77×（96/34）`）也逐个数回溯，不再只校验括号外的倍数；
以数字开头、后接注记的格子（如 `0.947 / 1.01，DF 39.7%`）取前导数字部分。

仍然无法解析、但一行里有 ≥2 个纯数字格的行，会记入 `noobj` 并在 CLI 中列出，
不再静默丢弃。

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
# 尾部注记：`（背景）` / `(在退)`
ANNOT = re.compile(r"\s*[（(][^）)]*[）)]\s*$")
# 中文括号里的原始计数：`（123/38）`、`（88,623 / 92,068，产业没撤 ✓）`
PAREN = re.compile(r"（([^）]*)）")
# 括号里只认整数计数（`+2.4%`、`−12.8%` 这类百分比注记不算原始计数）
PAREN_NUM = re.compile(r"(?<![\d.])\d[\d,]*(?![\d.])")
# 证据表上下文：`证据（子方向 1.2）`
CTX = re.compile(r"子方向\s*(\d+\.\d+)")
# 行内对象：`子方向 7.2 太阳能发电`
SUBOBJ = re.compile(r"^\s*子方向\s*(\d+\.\d+)\b")
# 证据表里的指标行（归属同一子方向）
METRIC_LABELS = {"三年提及量", "份额同比", "专利同比", "政策同比", "季度份额斜率"}


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
    """括号内的整数计数 token（去掉千分位逗号）。"""
    out = []
    for m in PAREN.finditer(cell):
        out += [t.replace(",", "") for t in PAREN_NUM.findall(m.group(1))]
    return out


def _leading_tokens(cell: str) -> list:
    """取以数字开头、后接纯记号的格子的前导数字：`0.947 / 1.01，DF 39.7%` → 0.947、1.01。

    只接受第一分句里全是 数字/斜杠/空白/百分号/正负号 的写法；碰上中文说明就放弃，
    避免把 `1.2 份额 0.944` 这类叙述句误当数据。
    """
    s = re.sub(r"（[^）]*）", "", cell).strip()
    if not NUM.match(s.lstrip("*").strip()):
        return []
    first = re.split(r"[，；。、]", s, maxsplit=1)[0]
    probe = first.replace("**", "").replace("×", "").replace("%", "").strip()
    probe = probe.strip("+- ").strip()
    if not probe or not re.fullmatch(r"\d[\d,.\s/]*", probe):
        return []
    return [t for t in NUM.findall(first.replace(",", ""))]


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


def _norm_name(name: str) -> str:
    """去掉加粗、尾部注记与说明性前缀，得到可能的词条/子方向名。"""
    h = name.strip().strip("*` ").replace("**", "").strip()
    for _ in range(2):                      # 允许 `X（注记）（补充）`
        h2 = ANNOT.sub("", h)
        if h2 == h:
            break
        h = h2.strip()
    if "：" in h or ":" in h:
        h = re.split(r"[：:]", h)[-1].strip()
    return h


def _lookup(cand: str, terms: dict, subs: dict):
    if not cand:
        return None
    if cand in terms:
        return terms[cand]
    m = re.match(r"(\d+\.\d+)", cand)
    if m and m.group(1) in subs:
        return subs[m.group(1)]
    return None


def _resolve_many(name: str, terms: dict, subs: dict) -> list:
    """返回 0 个、1 个或多个对象（一行两个对象时返回两个）。"""
    for cand in (name.strip(), PREFIX.sub("", name, count=1).strip(), _norm_name(name)):
        obj = _lookup(cand, terms, subs)
        if obj is not None:
            return [obj]
    base = _norm_name(name)
    if " / " in base:
        parts = [p.strip() for p in base.split(" / ") if p.strip()]
        got = [_lookup(p, terms, subs) for p in parts]
        if parts and all(g is not None for g in got):
            return got
    return []


def resolve(name: str, terms: dict, subs: dict):
    """单对象版本（保留原 API）；一行多对象时返回第一个。"""
    got = _resolve_many(name, terms, subs)
    return got[0] if got else None


def _pure_numeric_cells(cells: list) -> int:
    return sum(1 for c in cells if _clean_cell(c) is not None)


def check(doc: Path = DEFAULT_DOC, allow: set | None = None) -> tuple:
    """返回 (checked, bad, skipped, noobj)；bad 为 [(行号, 对象, 数字, 原格)]。"""
    allow = ALLOW_LITERALS | (allow or set())
    allow_norm = {a.replace(",", "") for a in allow}
    terms, subs = load_pool()
    bad, checked, skipped, noobj = [], 0, 0, set()
    ctx = None
    for lineno, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        head = cells[0]
        m = CTX.search(head)
        if m and head.startswith(("证据", "词条组")):
            ctx = subs.get(m.group(1))
        objs = _resolve_many(head, terms, subs)
        skip_idx: set = set()
        if not objs:
            # 对象写在第二格：`| 已进入产业化的主体技术 | 子方向 7.2 太阳能发电 | …`
            for idx, cell in enumerate(cells[1:], 1):
                mm = SUBOBJ.match(cell)
                if mm and mm.group(1) in subs:
                    objs = [subs[mm.group(1)]]
                    skip_idx.add(idx)
                    break
        if not objs and ctx is not None and _norm_name(head) in METRIC_LABELS:
            objs = [ctx]
        if not objs:
            if _pure_numeric_cells(cells[1:]) >= 2:
                noobj.add(head[:26])
            continue
        pool: set = set()
        for obj in objs:
            pool |= metrics_of(obj)
        for idx, cell in enumerate(cells[1:], 1):
            if idx in skip_idx:
                continue
            cleaned = _clean_cell(cell)
            parens = _paren_tokens(cell)
            if cleaned is not None:
                tokens = NUM.findall(cleaned.replace(",", ""))
            elif parens:
                tokens = _leading_tokens(cell)
            else:
                tokens = _leading_tokens(cell)
            if cleaned is None and not parens and not tokens:
                skipped += 1
                continue
            tokens = tokens + parens
            for tok in tokens:
                if tok in allow_norm or tok in pool:
                    checked += 1
                else:
                    bad.append((lineno, cells[0][:24], tok, cell[:40]))
    return checked, bad, skipped, noobj
