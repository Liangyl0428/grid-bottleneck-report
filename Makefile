.PHONY: help test verify subtopics check clean

PY ?= python3
export PYTHONPATH := src

help:
	@echo "make check       # 测试 + 报告对账（CI 跑的就是这个）"
	@echo "make test        # pytest"
	@echo "make verify      # 报告数字逐格回溯 CSV"
	@echo "make subtopics   # 复算子方向并打印归类"
	@echo "make clean       # 清缓存"

check: test verify

test:
	$(PY) -m pytest tests

verify:
	$(PY) -m grid_bottleneck verify

subtopics:
	$(PY) -m grid_bottleneck subtopics

clean:
	rm -rf .pytest_cache *.egg-info
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
