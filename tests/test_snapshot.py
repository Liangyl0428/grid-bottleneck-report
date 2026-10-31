# -*- coding: utf-8 -*-
"""快照一致性：仓库自带的 data/subtopic_report.csv 必须能由工具从 data/ 复算出来。

这是本仓库最强的可复现性保证——别人 clone 下来跑一遍，除了字节级一致外没有别的解释。
"""
import csv
import io
from pathlib import Path

from grid_bottleneck import data
from grid_bottleneck.cli import _fmt, build_rows
from grid_bottleneck.subtopic import COLUMNS

DATA = Path(__file__).resolve().parents[1] / "data"


def _render(rows):
    buf = io.StringIO()
    buf.write("\ufeff")           # 与写文件时一致（utf-8-sig）
    w = csv.writer(buf)
    w.writerow(COLUMNS)
    for r in rows:
        w.writerow([_fmt(r.get(c, "")) for c in COLUMNS])
    return buf.getvalue().replace("\r\n", "\n")


def test_snapshot_is_reproducible_byte_for_byte():
    # 两者都用 utf-8-sig 读：BOM 不参与比较，其余必须逐字节一致
    committed = (DATA / "subtopic_report.csv").read_text(encoding="utf-8-sig")
    assert _render(build_rows()).lstrip("\ufeff") == committed


def test_three_bottlenecks_and_their_numbers():
    rows = {r["code"]: r for r in build_rows()}
    got = [c for c, r in rows.items() if r["class_primary"] == "bottleneck"]
    assert got == ["1.2", "6.2", "7.6"]
    assert round(rows["1.2"]["share_yoy"], 3) == 0.944
    assert round(rows["1.2"]["patent_growth"], 2) == 0.98
    assert round(rows["6.2"]["share_yoy"], 3) == 1.024
    assert round(rows["6.2"]["patent_growth"], 2) == 1.00
    assert round(rows["7.6"]["share_yoy"], 3) == 0.925
    assert round(rows["7.6"]["patent_growth"], 2) == 1.28


def test_classes_partition_all_subtopics():
    rows = build_rows()
    assert len(rows) == 33
    for r in rows:
        assert r["class_primary"] in ("", "bottleneck", "academic_hot_industry_cold",
                                      "both_declining", "mature_industry")
    assert sum(1 for r in rows if r["class_primary"] == "mature_industry") == 1
    assert sum(1 for r in rows if r["class_primary"] == "academic_hot_industry_cold") == 5
    assert sum(1 for r in rows if r["class_primary"] == "both_declining") == 3


def test_excluded_subtopics_are_not_classified():
    """非技术子方向（表征与测试、战略规划、地区实践）必须在 config 里排除。"""
    rows = {r["code"]: r for r in build_rows()}
    for code in ("9.4", "3.1", "2.1"):
        assert rows[code]["class_primary"] == ""
        assert "排除" in rows[code]["class_note"]


def test_corpus_windows_are_frozen():
    """窗口是结论的一部分：近一年语料 423,464 篇、上一年 332,096 篇，同比 1.275。"""
    corpus = data.load_corpus()
    from grid_bottleneck.windows import PREV_Q, RECENT_Q
    recent = sum(corpus[q] for q in RECENT_Q)
    prev = sum(corpus[q] for q in PREV_Q)
    assert round(recent) == 423464
    assert round(prev) == 332096
    assert round(recent / prev, 3) == 1.275
