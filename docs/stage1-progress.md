# 第一阶段进度

统一编号：整个第一阶段由 1.1–1.5 组成。

| 编号 | 子阶段 | 状态 | 当前证据 |
|---|---|---|---|
| 1.1 | 确定方案 | 已完成 | 文献调研、原题定位、模型指令/工具入口验证 |
| 1.2 | 搭建与试跑 | 已完成 | 售后闭环、16 个目标试跑、6 个只读抽取试跑、准入审计通过 |
| 1.3 | 正式实验 | 已完成 | 352/352 目标 episode、24/24 抽取会话完成 |
| 1.4 | 分析与复核 | 已完成 | 完整性审计通过；主结果、配对差、抽取和局限已复核 |
| 1.5 | 中期报告 | 已完成 | DOCX 与 PDF 已生成并完成 8 页渲染检查 |

## 1.1 产物

- [研究方案](./stage1-execution.md)
- [文献调研与证据表](./literature.md)
- [内置模型检查记录](./evidence/interface-check.json)

## 1.2 产物

- 可复现模型桥与动态工具：`scripts/experiment.py`
- 统计脚本：`analysis/analyze.py`
- 开发试跑：`runs/pilot/results.jsonl`
- 只读抽取试跑：`runs/pilot/extraction/results.jsonl`
- 准入审计：[runs/pilot/audit.json](../runs/pilot/audit.json)

1.2 的关键事实：

- 16/16 目标运行和 6/6 抽取会话完成；
- 正常任务 8/8 成功；
- 只发生 `read_case`、`update_record` 两个声明业务工具调用；
- 应用提示包含受保护事实，随机业务标识未出现在用户请求中；
- 会话均为 `ephemeral=true`，`instructionSources=[]`。

开发集观察到 D0 下越权执行，而 Dgate 下没有执行；样本只有 1 个售后配置，仅用于验证流程可区分执行层。自然抽取在严格业务事实评分下为 0，原始回复已保存。

已知限制：内置平台仍向模型提供通用工具说明，抽取回复可能提到 `request_user_input`、`get_goal` 等平台工具。本项目将它们作为固定后台条件，不将其计为受保护的应用业务事实；未发生这些工具的实际调用。

## 1.3 冻结规则

- 测试配置、覆盖事实集、攻击候选生成规则、随机种子和代码哈希在正式运行前写入 `runs/formal/manifest.json`。
- 正式测试开始后，不根据中间 ASR 修改测试目标或筛选样本。
- 技术错误和协议无效单独报告；不当作安全成功。
- 如果运行未完成，报告实际缺口，不把开发集结果补作正式结果。

## 1.3–1.4 产物

- 正式运行：`runs/formal/combined-results.jsonl`
- 自动统计：`runs/formal/analysis/results.md`
- 完整性审计：[runs/formal/audit.json](../runs/formal/audit.json)
- 分析复核说明：[stage1-analysis.md](./stage1-analysis.md)

旧宽口径标签的 D0 下 K100−K0 为 −10.4 个百分点，但评分含默认备注文案检查，与正式用户请求不一致，不能作为严格权限风险结论。严格授权离线复核在 D0 下 K0/K75/K100 分别为 0/48、0/48、1/48，Dgate 均为 0/48。正常任务 64/64 成功。抽取总体严格事实覆盖为 0.26%，结构化组为 0.78%，随机流程标识命中为 0。

## 1.5 产物

- [汇报备用 PDF](../reports/stage1-midterm-slides/slides.pdf)：从当前 guizang 网页稿导出，12 页、16:9 横向；与既有中期报告 PDF 分开存放。

- [逐页讲稿（Markdown）](../reports/stage1-midterm-slides/speech.md)：对应当前 12 页网页汇报，含完整口述、指图提示与页间过渡。

网页汇报现合并为 12 页：将 RQ1–RQ3 操作定义、文献与阶段进度、知识条件与样本设计集中呈现，保留真实攻击与抽取案例。增加知识覆盖格、工具调用链、批次流程、案例状态图、宽标签与严格授权对比、调用与执行对比和抽取策略图。`reports/stage1-midterm-slides/metric-review.json` 保存现有轨迹离线复核；没有新模型运行，也没有改动 `runs/formal/`。旧报告 DOCX/PDF 尚未同步评分口径更正，引用结论时优先参考更新后的分析说明。

2026-11-18 汇报更新：新增 [guizang 横向翻页网页 PPT](../reports/stage1-midterm-slides/index.html) 和[页面大纲与提词](../reports/stage1-midterm-slides/outline.md)。根据原始 24 条抽取记录核对，总体严格事实覆盖均值为 **0.26%**，结构化策略组均值为 **0.78%（约 0.8%）**；旧报告中将 0.8% 写成总体均值的表述需按此更正。网页稿采用正确口径，冻结原始数据保持原样。

- 提交版 Word：[stage1-midterm-report.docx](../reports/stage1-midterm-report.docx)
- 提交版 PDF：[stage1-midterm-report.pdf](../reports/stage1-midterm-report.pdf)
- 可编辑 Markdown：[stage1-midterm-report.md](../reports/stage1-midterm-report.md)
- 报告构建程序：`scripts/build_midterm_report.py`
- AI 执行与审核边界：[ai-use.md](./ai-use.md)

整个第一阶段 1.1–1.5 已完成。正式报告明确采用负结果和证据边界，不把平台实验外推为真实系统越权。
