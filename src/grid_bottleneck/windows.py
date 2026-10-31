# -*- coding: utf-8 -*-
"""分析窗口（与上游流水线冻结一致；改窗口等于换结论，必须同步 docs/METHOD.md）。"""
from __future__ import annotations


def _all_quarters():
    return [f"{y}Q{q}" for y in range(2020, 2031) for q in range(1, 5)]


def window_quarters(start_y, start_q, end_y, end_q):
    all_q = _all_quarters()
    i = all_q.index(f"{start_y}Q{start_q}")
    return all_q[i:i + (end_y - start_y) * 4 + (end_q - start_q) + 1]


HISTORY_Q = window_quarters(2021, 3, 2026, 2)   # 2021-07-01 .. 2026-06-30，20 个季度
CORE_Q = window_quarters(2023, 3, 2026, 2)      # 近三年，12 个季度
RECENT_Q = window_quarters(2025, 3, 2026, 2)    # 近一年，4 个季度
PREV_Q = window_quarters(2024, 3, 2025, 2)      # 上一年，4 个季度

EPS = 0.5   # 与上游一致的平滑项，避免极小量比率的抖动
