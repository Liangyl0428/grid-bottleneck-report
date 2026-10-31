# -*- coding: utf-8 -*-
"""子方向聚合层回归测试：口径同构、语料增长必须被扣掉、归类互斥。"""
import pytest

from grid_bottleneck.subtopic import COLUMNS, aggregate
from grid_bottleneck.windows import CORE_Q, HISTORY_Q, PREV_Q, RECENT_Q

NO_REVIEW = {"exclude_from_screening": {}, "override": {}}


def totals(growth=0.0):
    """语料每季度涨 growth（默认不涨），用于构造"纯语料膨胀"。"""
    return {q: 100_000.0 * (1.0 + growth * i) for i, q in enumerate(HISTORY_Q)}


def term(term, subtopic, hits_recent, hits_prev, patents=(0, 0), yoy=None):
    return {
        "term": term, "subtopic": subtopic,
        "hits_3y": 12 * max(hits_recent, hits_prev) / 4.0,
        "hits_recent": hits_recent, "hits_prev": hits_prev,
        "yoy": yoy if yoy is not None else (hits_recent + 0.5) / (hits_prev + 0.5),
        "patents_recent": patents[0], "patents_base": patents[1],
        "policies_recent": 0.0, "policies_base": 0.0,
    }


def papers_q_of(terms):
    out = {}
    for t in terms:
        q = {c: 0.0 for c in CORE_Q}
        for c in RECENT_Q:
            q[c] = t["hits_recent"] / 4.0
        for c in PREV_Q:
            q[c] = t["hits_prev"] / 4.0
        out[t["term"]] = q
    return out


def rules(**over):
    base = {"subtopic": {
        "scale_hits_3y_min": 3000.0,
        "stagnant_yoy_max": 1.05,
        "industry_patent_min": 0.95,
        "disrupt_df_max": 0.003,
        "academic_hot_yoy_min": 1.0,
    }}
    base["subtopic"].update(over)
    return base


def run(terms, doc_totals, cfg=None, review=None):
    return aggregate(terms, papers_q_of(terms), doc_totals, cfg or rules(),
                     review if review is not None else NO_REVIEW)


def test_share_yoy_divides_out_corpus_growth():
    """份额不变的子方向，在语料涨 27.5% 时必须算出 ≈1.0，而不是 ≈1.275。"""
    d = totals()
    for q in RECENT_Q:
        d[q] *= 1.275
    row = run([term("a", "1.1 测试方向", 1275.0, 1000.0)], d)[0]
    assert row["share_yoy"] == pytest.approx(1.0, abs=0.01)


def test_real_decline_detected():
    d = totals()
    for q in RECENT_Q:
        d[q] *= 1.275
    row = run([term("a", "1.1 测试方向", 1200.0, 1000.0)], d)[0]
    assert row["share_yoy"] < 1.0          # 命中涨 20%，但份额在退
    assert row["pass_stagnant"]


def test_paper_and_patent_side_use_the_same_sum():
    d = totals()
    terms = [
        term("big", "1.1 测试方向", 1000.0, 1000.0, patents=(900, 100)),
        term("small", "1.1 测试方向", 10.0, 10.0, patents=(10, 10)),
    ]
    row = run(terms, d)[0]
    assert row["patents_recent"] == 910.0
    assert row["patents_base"] == 110.0
    assert row["patent_growth"] == pytest.approx(911.0 / 111.0)
    assert row["hits_recent"] == 1010.0
    assert row["share_yoy"] == pytest.approx(1.0, abs=0.001)


def _four_subtopics():
    d = totals()
    terms = [
        term("bt", "6.2 瓶颈方向", 1000.0, 1020.0, patents=(500, 500)),
        term("ac", "6.1 学术热方向", 1200.0, 1000.0, patents=(80, 100)),
        term("bd", "9.1 双退方向", 800.0, 1000.0, patents=(70, 100)),
        term("gr", "1.1 增长方向", 2000.0, 1500.0, patents=(500, 400)),
    ]
    return terms, d


def test_classes_are_mutually_exclusive_and_match_gates():
    terms, d = _four_subtopics()
    rows = {r["code"]: r for r in run(terms, d)}
    assert rows["6.2"]["class_primary"] == "bottleneck"
    assert rows["6.1"]["class_primary"] == "academic_hot_industry_cold"
    assert rows["9.1"]["class_primary"] == "both_declining"
    assert rows["1.1"]["class_primary"] == ""
    for r in rows.values():
        assert r["class_primary"] in ("", "bottleneck", "academic_hot_industry_cold",
                                      "both_declining", "mature_industry")
        if r["class_primary"] == "bottleneck":
            assert r["pass_scale"] and r["pass_stagnant"] and r["pass_industry_hold"]


def test_review_excludes_and_overrides_with_reason():
    terms, d = _four_subtopics()
    review = {
        "exclude_from_screening": {"6.2 瓶颈方向": "表征/测试手段，不是技术方向"},
        "override": {"6.1 学术热方向": {"class": "mature_industry", "reason": "已进工程优化阶段"}},
    }
    rows = {r["code"]: r for r in run(terms, d, review=review)}
    assert rows["6.2"]["class_primary"] == ""
    assert "排除" in rows["6.2"]["class_note"]
    assert rows["6.1"]["class_primary"] == "mature_industry"
    assert "工程优化" in rows["6.1"]["class_note"]


def test_small_base_flag_uses_share_not_hits():
    """『基数小』按份额判：求和会因共现虚高，不能用绝对提及量。"""
    d = totals()
    small = run([term("a", "1.1 测试方向", 1000.0, 1000.0)], d)[0]
    assert small["pass_small_base"] is True
    big = run([term("a", "1.1 测试方向", 6000.0, 6000.0)], d)[0]
    assert big["pass_small_base"] is False


def test_csv_columns_cover_every_row_key():
    terms, d = _four_subtopics()
    for r in run(terms, d):
        assert set(COLUMNS) <= set(r)
