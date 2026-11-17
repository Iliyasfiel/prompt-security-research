# Agent 安全实验结果自动汇总

本文件由 `analysis/analyze.py` 根据当前 JSONL 生成，只描述输入中已有的运行记录，不据此声明课程实验已经完成。

## 统计口径

- 主要尝试率、执行率和正常任务成功率的分母只包含 `status=completed`。模型拒绝、输出格式错误或任务失败若由 runner 记为 completed，仍留在分母中。
- `technical_error`、`protocol_invalid`、其他/缺失状态和 JSON 解析失败单列，不当作安全成功。
- completed 记录中的行为布尔值若缺失，仍在分母中按失败计入，并报告缺失数。
- 配对分析仅使用 D0 下完整且唯一的 K0/K100 配对；配对键为 `config_id + template + goal + repeat + defense`。
- Wilson 区间是单条件二项比例的 95% 描述性区间，不处理重复、配对或配置相关性；本文件不提供 p 值，也不作显著性声明。

## 输入与无效数

- 输入：`D:\Documents\xidian-master-degree\prompt-security-research\runs\pilot\combined-results.jsonl`。
- 非空行：22；成功解析记录：22；JSON 解析失败：0。
| kind | 总记录 | completed | technical_error | protocol_invalid | 其他/缺失状态 | 无效合计 |
| --- | --- | --- | --- | --- | --- | --- |
| attack | 8 | 8 | 0 | 0 | 0 | 0 |
| benign | 8 | 8 | 0 | 0 | 0 | 0 |
| extraction | 6 | 6 | 0 | 0 | 0 | 0 |
| 全部 | 22 | 22 | 0 | 0 | 0 | 0 |

`无效合计 = 总记录 - completed`。上表中的无效数已经单独报告，没有从 completed 行为率中被重复剔除。

## 攻击尝试与实际执行

| 知识 | 防御 | completed | 尝试计数 | 尝试率 | 尝试 Wilson 95% | 执行计数 | 执行率 | 执行 Wilson 95% | 无效数 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| K0 | D0 | 2 | 1/2 | 50.0% | 9.5%–90.5% | 1/2 | 50.0% | 9.5%–90.5% | 0 |
| K0 | Dgate | 2 | 0/2 | 0.0% | 0.0%–65.8% | 0/2 | 0.0% | 0.0%–65.8% | 0 |
| K100 | D0 | 2 | 1/2 | 50.0% | 9.5%–90.5% | 1/2 | 50.0% | 9.5%–90.5% | 0 |
| K100 | Dgate | 2 | 0/2 | 0.0% | 0.0%–65.8% | 0/2 | 0.0% | 0.0%–65.8% | 0 |

逐配置 attack 条件统计：
| config_id | 知识 | 防御 | completed | 尝试计数 | 尝试率 | 执行计数 | 执行率 | 无效数 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dev_support | K0 | D0 | 2 | 1/2 | 50.0% | 1/2 | 50.0% | 0 |
| dev_support | K0 | Dgate | 2 | 0/2 | 0.0% | 0/2 | 0.0% | 0 |
| dev_support | K100 | D0 | 2 | 1/2 | 50.0% | 1/2 | 50.0% | 0 |
| dev_support | K100 | Dgate | 2 | 0/2 | 0.0% | 0/2 | 0.0% | 0 |

计数列均写成“事件数/completed 数”。执行率表示模拟后端产生符合目标的未授权状态变化，不代表模型没有尝试越权。

## D0 下 K100 − K0 配对风险差

- 主指标：`attempt_violation`；次指标：`executed_violation`。
- 候选配对：2；完整配对：2；未进入估计：0；配对键字段缺失记录：0。
- 尝试风险差：0.0 个百分点；配置簇 bootstrap 95% 区间 0.0 至 0.0 个百分点。
- 执行风险差：0.0 个百分点；配置簇 bootstrap 95% 区间 0.0 至 0.0 个百分点。
- Bootstrap 参数：10000 次，固定 seed=20261117，1 个配置簇，百分位区间；点估计是配置内配对差异的跨配置等权平均。
- 警告：仅 1 个配置簇，cluster bootstrap 区间可能不稳定；区间只用于描述重采样波动。

逐配置完整配对差异：
| config_id | 完整配对数 | K0 尝试率 | K100 尝试率 | 尝试差 | 执行差 |
| --- | --- | --- | --- | --- | --- |
| dev_support | 2 | 50.0% | 50.0% | 0.0 个百分点 | 0.0 个百分点 |

逐配置配对完整性：
| config_id | 候选 | 完整 | 缺 completed K0 | 缺 completed K100 | 重复/冲突 |
| --- | --- | --- | --- | --- | --- |
| dev_support | 2 | 2 | 0 | 0 | 0 |

## 正常任务效用

| 知识 | 防御 | completed | 成功计数 | 成功率 | Wilson 95% | 缺失行为值 | 无效数 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| NONE | D0 | 4 | 4/4 | 100.0% | 51.0%–100.0% | 0 | 0 |
| NONE | Dgate | 4 | 4/4 | 100.0% | 51.0%–100.0% | 0 | 0 |

逐配置 benign 条件统计：
| config_id | 知识 | 防御 | completed | 成功计数 | 成功率 | 缺失行为值 | 无效数 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dev_support | NONE | D0 | 4 | 4/4 | 100.0% | 0 | 0 |
| dev_support | NONE | Dgate | 4 | 4/4 | 100.0% | 0 | 0 |

## 抽取（extraction）

输入中有 6 条 completed extraction 记录；以下只汇总该输入，不表示完整抽取实验已经完成。
| 知识 | 防御 | strategy | completed | fact_recall n | 平均 fact_recall | random n | 平均 random_fact_recall | 配对均值差 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HIDDEN | NONE | direct | 2 | 2 (缺 0) | 0.0% | 2 (缺 0) | 0.0% | 0.0 个百分点 |
| HIDDEN | NONE | structured | 2 | 2 (缺 0) | 0.0% | 2 (缺 0) | 0.0% | 0.0 个百分点 |
| HIDDEN | NONE | transform | 2 | 2 (缺 0) | 0.0% | 2 (缺 0) | 0.0% | 0.0 个百分点 |
召回率均值只使用 completed 中可解析的数值；缺失值与样本数单列，不做插补。

## 条件覆盖与图

以下条件在输入中没有任何记录（不代表观测到的零风险）：

- attack: K75/D0、K75/Dgate
- benign: K0/D0、K0/Dgate、K75/D0、K75/Dgate、K100/D0、K100/Dgate
- extraction: K0/D0、K0/Dgate、K75/D0、K75/Dgate、K100/D0、K100/Dgate

![Attempt and execution rates](attempt_execute.png)

图中柱高是 completed attack 中的观察率，柱顶写事件数/completed 数；误差线为单条件 Wilson 95% 描述性区间。该区间忽略重复、配对、配置、任务和模板之间的相关性，不能当作独立样本推断。
