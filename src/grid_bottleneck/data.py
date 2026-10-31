# -*- coding: utf-8 -*-
"""数据快照读取：`data/*.csv`（派生统计，不含原文）。

设计原则：只用标准库，克隆后 `python -m grid_bottleneck subtopics` 即可复算子方向指标。
快照里没有原始语料（OpenAlex 论文库 / 专利 CSV / 政策 JSONL），因此**不能**从本仓库
重算词条级指标；词条级快照由上游流水线产出，见 docs/METHOD.md。
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
CONFIG = ROOT / "config"


def _read(name: str) -> List[dict]:
    path = DATA / name
    if not path.exists():
        raise SystemExit(f"缺少数据快照 {path}（仓库应自带 data/ 目录）")
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _f(v, default=0.0) -> float:
    if v in (None, ""):
        return default
    return float(v)


def load_terms() -> List[dict]:
    """词条级快照（terms_report.csv）。键用 `term`（词典内唯一）。"""
    rows = _read("terms_report.csv")
    out = []
    for r in rows:
        out.append({
            "term": r["term"],
            "term_en": r.get("term_en", ""),
            "subtopic": r["subtopic"],
            "hotspot_class": r.get("hotspot_class", ""),
            "hits_3y": _f(r.get("hits_3y")),
            "hits_recent": _f(r.get("hits_recent")),
            "hits_prev": _f(r.get("hits_prev")),
            "yoy": _f(r.get("yoy")),
            "df_recent": _f(r.get("df_recent")),
            "slope": _f(r.get("slope")),
            "patents_recent": _f(r.get("patents_recent")),
            "patents_base": _f(r.get("patents_base")),
            "patent_growth": _f(r.get("patent_growth")),
            "policies_recent": _f(r.get("policies_recent")),
            "policies_base": _f(r.get("policies_base")),
            "policy_growth": _f(r.get("policy_growth")),
            "pass_potential": r.get("pass_potential", "") == "1",
        })
    return out


def load_corpus() -> Dict[str, float]:
    return {r["quarter"]: _f(r["docs"]) for r in _read("corpus_totals.csv")}


def load_papers_quarter() -> Dict[str, Dict[str, float]]:
    """{term: {quarter: 命中篇数}}，含 year-only 均摊权重（float）。"""
    out: Dict[str, Dict[str, float]] = {}
    for r in _read("papers_by_quarter.csv"):
        out.setdefault(r["term"], {})[r["quarter"]] = _f(r["papers"])
    return out


def load_rules() -> dict:
    path = CONFIG / "subtopic_rules.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_review() -> dict:
    path = CONFIG / "subtopic_review.json"
    if not path.exists():
        return {"exclude_from_screening": {}, "override": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def load_run_meta() -> dict:
    path = DATA / "run_meta.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
