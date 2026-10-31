# 电网能源领域：关键瓶颈与潜在颠覆性方向

用「学术注意力」与「产业化节奏」的背离，定位电力系统转型中的**真瓶颈**与**潜在颠覆方向**。

**这不是一份文献综述**：每个结论都绑定到可复算的份额/增速指标，`clone` 下来跑一行命令
就能把报告里的 92 个数字全部回溯到 CSV。

📄 **正文**：[docs/电网瓶颈与颠覆性方向.md](docs/电网瓶颈与颠覆性方向.md)

---

## 结论摘要

| | 内容 |
|---|---|
| **3 个关键瓶颈**（全部通过判据） | 长时储能（1.2）、电力电子化系统的稳定性（6.2）、氢能储运（7.6） |
| **6 个潜在颠覆方向** | 构网型控制、电-氢-碳耦合、AI 进电网（观察项）、钠电/固态、聚变/SMR（长周期）、市场机制 |
| **4 类伪前沿** | 已产业化的主体技术、学术热产业冷、论文与产业双退、通用方法迁入 |

一句话：**转型的卡点不在器件，而在长时储能的经济性、电力电子系统的稳定性理论、氢的储—运；
最可能改变格局的是构网型控制、电-氢-碳耦合与市场机制。**

判据（详见 [docs/METHOD.md](docs/METHOD.md)）：

```
瓶颈         = 子方向三年提及量 ≥ 3000 ∧ 份额同比 ≤ 1.05 ∧ 专利同比 ≥ 0.95
颠覆（候选） = 词条级 emerging/potential ∧ 跨源校验：专利同比 ≥ max(1.25, 份额同比²)
伪前沿       = 学术热产业冷（份额 ≥1.00 ∧ 专利 <0.95）| 双退（份额 <1.00 ∧ 专利 <0.95）
```

---

## 快速开始

```bash
git clone https://github.com/Liangyl0428/grid-bottleneck-report.git
cd grid-bottleneck-report
python -m pip install -e '.[dev]'        # 无运行时依赖，只有 pytest 是 dev 依赖

grid-bottleneck summary                   # 打印瓶颈/伪前沿归类
grid-bottleneck subtopics                 # 从 data/ 复算子方向指标
grid-bottleneck verify                    # 报告数字逐格回溯 CSV（CI 用，失败退出码 1）
grid-bottleneck show 构网型逆变器          # 查单条词条的全部指标
pytest                                    # 15 条测试：口径、互斥、快照字节级可复现、上游 pin 一致性
```

不装包也能跑：

```bash
PYTHONPATH=src python -m grid_bottleneck verify
PYTHONPATH=src python -m pytest tests
```

---

## 这个仓库能复现什么、不能复现什么

| | 能 | 不能 |
|---|---|---|
| 子方向指标 | ✅ 从 `data/` 复算，`data/subtopic_report.csv` 与工具输出**逐字节一致** | |
| 报告数字 | ✅ 92 个表格数字逐格回溯（`grid-bottleneck verify`） | |
| 判定归类 | ✅ 门槛在 `config/subtopic_rules.json`，改门槛即可重跑 | |
| 词条级指标 | | ❌ 需要原始语料（OpenAlex + 专利 + 政策，数 GB），不在本仓库 |
| 换语料/换窗口 | | ❌ 只能用 `data/` 快照 |

原始语料与词条级流水线在上游 [energy-topic-hotspots](https://github.com/Liangyl0428/energy-topic-hotspots)；
本仓库是**分析快照 + 判定层 + 对账工具**，并**自 v2 起独立负责子方向聚合**（上游已不再产出 `subtopic_report.csv`）。
`data/run_meta.json` 的 `upstream_pin` 记录了 `terms_report.csv` / `dict_snapshot.csv` 的 sha256，
上游重新生成产物时可据此发现快照漂移（`pytest` 会失败告警）。
这样做的理由：结论必须能被别人验证，而验证不需要几个 GB 的语料——需要的是
"当时用的数字是什么、它们怎么算出来的"。

---

## 目录

```
data/                    派生数据快照（8 个文件，约 5.8MB，无原文）
docs/
  电网瓶颈与颠覆性方向.md   正文（含判据、证据表、外部交叉验证、附录）
  METHOD.md              方法、窗口、口径、门槛、限制
  数据字典.md             每个 CSV 的列含义
src/grid_bottleneck/
  windows.py             分析窗口（冻结）
  subtopic.py            子方向聚合与互斥归类
  verify.py              报告数字对账
  data.py / cli.py       快照读取 / 命令行
config/
  subtopic_rules.json    子方向判定门槛
  subtopic_review.json   人工复核（非技术子方向排除、性质改判，必须写理由）
tests/                   15 条测试
```

---

## 设计上刻意的三个选择

1. **±5% 噪声带，双向对称**：停滞是 `≤1.05`，产业没撤是 `≥0.95`。用 1.00 硬阈值会让
   1.010 与 1.000 这 1% 之差决定成败——那是抽样噪声，不是信号。
2. **专利增速必须年化后再比**：专利是"近两年 ÷ 前两年"的两年比率，份额同比是一年比率。
   比较时用 `yoy²` 对齐，否则等于拿两年增速比一年增速，天然把东西判成"颠覆"。
3. **一个子方向只归一类，性质改判必须留痕**：互斥优先级 `瓶颈 > 学术热产业冷 > 双退`；
   算法看不见的性质（如"已在工程优化阶段"）只能写进 `config/subtopic_review.json` 并附理由，
   报告正文必须引用该理由。

---

## 数据与许可

- 代码：MIT
- 文档与派生数据：CC BY 4.0
- 上游语料：OpenAlex（论文）、专利公开数据、政策全文语料；**不含原文**

见 [NOTICE.md](NOTICE.md)（数据来源、粒度、引用方式、免责声明）。

> 结论是"注意力与产业化节奏"的统计证据，**不是技术可行性判断**，不构成投资建议。
