# -*- coding: utf-8 -*-
"""报告对账：报告表格里的每个数字都必须能指回 data/*.csv。"""
from grid_bottleneck.verify import DEFAULT_DOC, check


def test_report_doc_exists():
    assert DEFAULT_DOC.exists(), "报告正文缺失：docs/电网瓶颈与颠覆性方向.md"


def test_every_table_number_traces_back():
    checked, bad, _skipped, _noobj = check()
    assert checked > 80, f"能对账的数字太少（{checked}），检查报告表格是否被改坏"
    assert not bad, "以下数字在 data/*.csv 中找不到对应指标：\n" + "\n".join(
        f"  L{ln} [{name}] {tok!r} 在格: {cell}" for ln, name, tok, cell in bad)


def _write_doc(tmp_path, body):
    p = tmp_path / "report.md"
    p.write_text(body, encoding="utf-8")
    return p


def test_prefixed_term_and_parenthetical_counts_resolve(tmp_path):
    """`词条：车网互动` 这类前缀行不能再被静默跳过，括号里的 96/34 也要校验。"""
    doc = _write_doc(tmp_path, "| 对象 | 份额同比 | 专利同比 |\n|---|---:|---:|\n"
                               "| 词条：车网互动 | 1.296 | 2.77×（96/34） |\n")
    checked, bad, _skipped, _noobj = check(doc=doc)
    assert not bad, bad
    assert checked >= 4, checked


def test_subtopic_prefix_resolves(tmp_path):
    doc = _write_doc(tmp_path, "| 对象 | 份额同比 | 专利同比 | 政策同比 |\n|---|---:|---:|---:|\n"
                               "| 子方向 4.1 电力市场机制 | 1.143 | 1.38 | 1.68 |\n")
    checked, bad, _skipped, _noobj = check(doc=doc)
    assert not bad, bad
    assert checked >= 3, checked


def test_parenthetical_count_mismatch_is_detected(tmp_path):
    doc = _write_doc(tmp_path, "| 对象 | 份额同比 | 专利同比 |\n|---|---:|---:|\n"
                               "| 词条：车网互动 | 1.296 | 2.77×（999/34） |\n")
    _checked, bad, _skipped, _noobj = check(doc=doc)
    assert any(tok == "999" for _ln, _name, tok, _cell in bad), bad
