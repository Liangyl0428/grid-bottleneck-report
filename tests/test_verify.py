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


def test_annotated_term_names_resolve(tmp_path):
    """`器件大盘：X`、`X（背景）` 这类带注记的首格不能整行跳过。"""
    doc = _write_doc(tmp_path, "| 词条 | DF | 份额同比 | 专利同比 |\n|---|---:|---:|---:|\n"
                               "| 器件大盘：直流-直流变换器 | 1.972% | 1.073 | 0.84 |\n"
                               "| 锂离子电池（背景） | 3.047% | 0.924 | 0.82 |\n")
    checked, bad, _skipped, _noobj = check(doc=doc)
    assert not bad, bad
    assert checked >= 6, checked


def test_annotated_term_wrong_value_is_detected(tmp_path):
    """注入 0.84（实际 0.82）必须被抓到。"""
    doc = _write_doc(tmp_path, "| 词条 | 专利同比 |\n|---|---:|\n"
                               "| 锂离子电池（背景） | 0.84 |\n")
    _checked, bad, _skipped, _noobj = check(doc=doc)
    assert any(tok == "0.84" for _ln, _name, tok, _cell in bad), bad


def test_two_objects_in_one_row(tmp_path):
    """`二极管 / 电容器` 一行两对象：指标取并集，逐个数校验。"""
    doc = _write_doc(tmp_path, "| 对象 | DF | 份额同比 | 专利同比 |\n|---|---:|---:|---:|\n"
                               "| 器件大盘：二极管 / 电容器 | 0.796% / 0.837% | 0.806 / 0.863 | 0.90 / 0.89 |\n")
    checked, bad, _skipped, _noobj = check(doc=doc)
    assert not bad, bad
    assert checked >= 6, checked


def test_evidence_block_context_is_checked(tmp_path):
    """`证据（子方向 1.2）` 后的指标行按该子方向对账。"""
    doc = _write_doc(tmp_path, "| 证据（子方向 1.2） | 数值 |\n|---|---|\n"
                               "| 三年提及量 | 727,147 |\n"
                               "| 专利同比 | 0.96（88,623 / 92,068） |\n")
    checked, bad, _skipped, _noobj = check(doc=doc)
    assert not bad, bad
    assert checked >= 4, checked


def test_evidence_block_wrong_value_is_detected(tmp_path):
    doc = _write_doc(tmp_path, "| 证据（子方向 1.2） | 数值 |\n|---|---|\n"
                               "| 三年提及量 | 727,148 |\n")
    _checked, bad, _skipped, _noobj = check(doc=doc)
    assert any(tok == "727148" for _ln, _name, tok, _cell in bad), bad


def test_unresolved_row_with_numbers_is_reported(tmp_path):
    """解析不了、但一行有 ≥2 个纯数字格的行，要进 noobj 而不是静默丢弃。"""
    doc = _write_doc(tmp_path, "| 对象 | a | b |\n|---|---:|---:|\n"
                               "| 无法识别的对象名 | 1.234 | 5.678 |\n")
    _checked, _bad, _skipped, noobj = check(doc=doc)
    assert any("无法识别" in x for x in noobj), noobj
