# -*- coding: utf-8 -*-
"""子方向（subtopic）级聚合：把词条级指标汇总到 33 个子方向，一行一方向。

口径（与 docs/METHOD.md 一一对应）
--------------------------------
- **命中数**：成员词条命中数之和。等于子方向的"总提及量"，不是去重后的文档数
  （成员词条常在同一篇论文里共现）。因此它**不能**当"子方向有多少篇论文"读，
  但它的比值（同比、斜率、专利/政策增速）是份额比，可以放心用。
- **份额同比**：(Σ近一年 + EPS) ÷ 近一年语料，除以 (Σ上一年 + EPS) ÷ 上一年语料。
  **必须除以语料**：近一年语料同比 1.275，只用 Σ命中 相比会把"语料膨胀"记成"方向在涨"。
- **中位数 / 25 分位 / 在退占比**：成员词条 yoy 的分布，用来判断"整体在退"是普遍现象
  还是少数大词条拖动的。**只作稳健性列，不参与判定**。
- **斜率**：12 个季度 Σ命中 ÷ 季度语料 的 log OLS，与词条级 slope 同算法。
- **专利/政策增速**：(Σ近端 +1) ÷ (Σ基准 +1)，与词条级同算法（专利 2024–2025 vs 2022–2023；
  政策 2024–2026 vs 2021–2023，政策侧只作诊断）。

判定（门槛见 config/subtopic_rules.json）
---------------------------------------
    瓶颈          = 规模 ∧ 份额同比 ≤ 1.05 ∧ 专利同比 ≥ 0.95
    学术热产业冷  = 规模 ∧ 份额同比 ≥ 1.00 ∧ 专利同比 < 0.95
    双退          = 规模 ∧ 份额同比 < 1.00 ∧ 专利同比 < 0.95

一个子方向只进一类，优先级 `瓶颈 > 学术热产业冷 > 双退`；性质类改判只能来自
config/subtopic_review.json，且必须写理由（报告正文必须引用该理由）。
"""
from __future__ import annotations

import math
from typing import Dict, Iterable, List

from .windows import CORE_Q, EPS, PREV_Q, RECENT_Q


def log_slope(values: Iterable[float], xs: Iterable[int] | None = None) -> float:
    """对数最小二乘斜率；有效点 < 8 时返回 0（不足以下结论）。"""
    vals = list(values)
    pts = [(x, math.log(v)) for x, v in enumerate(vals) if v > 0] if xs is None else \
          [(x, math.log(v)) for x, v in zip(xs, vals) if v > 0]
    if len(pts) < 8:
        return 0.0
    n = len(pts)
    xb = sum(p[0] for p in pts) / n
    yb = sum(p[1] for p in pts) / n
    cov = sum((x - xb) * (y - yb) for x, y in pts)
    var = sum((x - xb) ** 2 for x, _ in pts)
    return cov / var if var else 0.0


def _quantile(sorted_vals: List[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = q * (len(sorted_vals) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] * (1 - pos + lo) + sorted_vals[hi] * (pos - lo)


def _median(vals: List[float]) -> float:
    return _quantile(sorted(vals), 0.5)


def _code(name: str) -> str:
    return name.split(" ")[0]


def _sort_key(name: str):
    code = _code(name)
    parts = code.split(".")
    return (len(parts), [int(p) if p.isdigit() else 0 for p in parts], name)


def aggregate(terms: List[dict], papers_q: Dict[str, Dict[str, float]],
              doc_totals: Dict[str, float], cfg: dict | None = None,
              review: dict | None = None) -> List[dict]:
    """按 subtopic 聚合。`terms` 为词条级快照行，`papers_q` 为 {term: {quarter: hits}}。"""
    cfg = (cfg or {}).get("subtopic", cfg or {})
    review = review or {}
    exclude = review.get("exclude_from_screening", {}) or {}
    overrides = review.get("override", {}) or {}

    d_recent = sum(doc_totals.get(q, 0.0) for q in RECENT_Q)
    d_prev = sum(doc_totals.get(q, 0.0) for q in PREV_Q)
    d_core = sum(doc_totals.get(q, 0.0) for q in CORE_Q)
    if not (d_recent and d_prev and d_core):
        raise SystemExit("corpus_totals.csv 缺少窗口语料分母，无法计算份额")

    groups: Dict[str, List[dict]] = {}
    for t in terms:
        groups.setdefault(t["subtopic"], []).append(t)

    rows: List[dict] = []
    for name in sorted(groups, key=_sort_key):
        members = groups[name]
        with_hits = [m for m in members if m["hits_3y"] > 0]

        hits_3y = sum(m["hits_3y"] for m in members)
        hits_recent = sum(m["hits_recent"] for m in members)
        hits_prev = sum(m["hits_prev"] for m in members)
        share_recent = (hits_recent + EPS) / d_recent
        share_prev = (hits_prev + EPS) / d_prev
        share_yoy = share_recent / share_prev if share_prev else 0.0

        yoys = [m["yoy"] for m in with_hits if m["yoy"] > 0]
        declining = (sum(1 for y in yoys if y < 1.0) / len(yoys)) if yoys else 0.0

        q_share = []
        for q in CORE_Q:
            tot = sum(papers_q.get(m["term"], {}).get(q, 0.0) for m in members)
            dq = doc_totals.get(q, 0.0)
            q_share.append(tot / dq if dq else 0.0)
        slope = log_slope(q_share)

        pat_recent = sum(m["patents_recent"] for m in members)
        pat_base = sum(m["patents_base"] for m in members)
        pat_growth = (pat_recent + 1.0) / (pat_base + 1.0)
        pol_recent = sum(m["policies_recent"] for m in members)
        pol_base = sum(m["policies_base"] for m in members)
        pol_growth = (pol_recent + 1.0) / (pol_base + 1.0)
        df_3y = hits_3y / d_core

        rows.append({
            "code": _code(name),
            "subtopic": name,
            "n_terms": len(members),
            "n_terms_hits": len(with_hits),
            "hits_3y": hits_3y,
            "df_3y_sum": df_3y,
            "hits_recent": hits_recent,
            "hits_prev": hits_prev,
            "share_recent": share_recent,
            "share_prev": share_prev,
            "share_yoy": share_yoy,
            "share_yoy_median": _median(yoys) if yoys else 0.0,
            "share_yoy_p25": _quantile(sorted(yoys), 0.25) if yoys else 0.0,
            "declining_share": declining,
            "slope": slope,
            "patents_recent": pat_recent,
            "patents_base": pat_base,
            "patent_growth": pat_growth,
            "patent_growth_annualized": math.sqrt(pat_growth) if pat_growth > 0 else 0.0,
            "policies_recent": pol_recent,
            "policies_base": pol_base,
            "policy_growth": pol_growth,
            "pass_scale": hits_3y >= cfg.get("scale_hits_3y_min", 3000.0),
            "pass_stagnant": share_yoy <= cfg.get("stagnant_yoy_max", 1.05),
            "pass_industry_hold": pat_growth >= cfg.get("industry_patent_min", 0.95),
            "pass_small_base": df_3y <= cfg.get("disrupt_df_max", 0.003),
            "pass_academic_hot": (share_yoy >= cfg.get("academic_hot_yoy_min", 1.0)
                                  and pat_growth < cfg.get("industry_patent_min", 0.95)),
        })

    for r in rows:
        r["class_note"] = ""
        if r["pass_scale"] and r["pass_stagnant"] and r["pass_industry_hold"]:
            r["class_primary"] = "bottleneck"
        elif r["pass_scale"] and r["pass_academic_hot"]:
            r["class_primary"] = "academic_hot_industry_cold"
        elif r["pass_scale"] and r["share_yoy"] < 1.0 and r["patent_growth"] < cfg.get(
                "industry_patent_min", 0.95):
            r["class_primary"] = "both_declining"
        else:
            r["class_primary"] = ""
        name = r["subtopic"]
        if name in exclude:
            r["class_primary"], r["class_note"] = "", f"排除：{exclude[name]}"
        elif name in overrides:
            ov = overrides[name]
            r["class_primary"] = ov.get("class", r["class_primary"])
            r["class_note"] = f"人工复核：{ov.get('reason', '')}"
    return rows


COLUMNS = [
    "code", "subtopic", "n_terms", "n_terms_hits", "hits_3y", "df_3y_sum",
    "hits_recent", "hits_prev", "share_recent", "share_prev", "share_yoy",
    "share_yoy_median", "share_yoy_p25", "declining_share", "slope",
    "patents_recent", "patents_base", "patent_growth", "patent_growth_annualized",
    "policies_recent", "policies_base", "policy_growth",
    "pass_scale", "pass_stagnant", "pass_industry_hold", "pass_small_base",
    "pass_academic_hot", "class_primary", "class_note",
]

CLASS_LABEL = {
    "bottleneck": "瓶颈",
    "academic_hot_industry_cold": "伪前沿·学术热产业冷",
    "both_declining": "伪前沿·双退",
    "mature_industry": "伪前沿·已产业化",
    "": "",
}
