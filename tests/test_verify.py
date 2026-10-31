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
