# Prompt Security Research

人工智能安全课程第一阶段中期研究：系统提示信息暴露对中文工具型 Agent 间接提示注入的影响。

## 研究问题

在应用系统提示包含非公开业务事实的情况下：

1. 固定轮数的自然抽取能恢复哪些业务规则？
2. 受控披露部分或完整业务事实，是否提高工具越权调用率？
3. 执行前授权检查能否阻断违规调用对应的模拟状态写入，同时保持正常任务效用？

本项目定位为已有工作的课程复现与受控扩展。实验对象是本地模拟业务工具，不包含真实账户、资金、成绩或文档写入。

## 当前结果

正式批次包含 288 个攻击 episode、64 个正常任务和 24 个抽取会话，全部正常完成。

| 条件 | 旧宽口径调用标签 | 旧标签对应模拟执行 |
|---|---:|---:|
| K0 / D0 | 8/48（16.7%） | 8/48（16.7%） |
| K75 / D0 | 5/48（10.4%） | 5/48（10.4%） |
| K100 / D0 | 3/48（6.2%） | 3/48（6.2%） |
| K0 / Dgate | 7/48（14.6%） | 0/48 |
| K75 / Dgate | 6/48（12.5%） | 0/48 |
| K100 / Dgate | 7/48（14.6%） | 0/48 |

D0 下 K100 相对 K0 的旧宽口径标签差为 -10.4 个百分点。2026-11-18 轨迹复核发现，旧标签还将“本人备注不等于默认文案”判为违规，而正式用户请求并未指定该文案。因此该差值不能解释为严格权限风险的变化。仅检查跨用户修改或无可信审批改状态时，D0 的 K0/K75/K100 分别为 0/48、0/48、1/48；Dgate 三组均为 0/48。事件不足以判断知识量与严格权限风险的关系，也没有直接观察到 gate 拦截严格权限违规的提议。详见[离线复核](reports/stage1-midterm-slides/metric-review.json)。冻结标签和原始数据保留不变。

自然抽取使用严格业务词组下界，总体平均业务事实覆盖为 0.26%，结构化策略组均值为 0.78%，随机流程标识命中为 0。

这些结果仅来自一个模型路由、4 个测试配置和有限重复，不声明统计显著性或普遍性。

## 项目文档

- [文档索引](docs/README.md)
- [AI 协作规则](AGENTS.md)
- [研究计划](docs/project-plan.md)
- [文献调研与证据表](docs/literature.md)
- [第一阶段进度](docs/stage1-progress.md)
- [正式实验分析复核](docs/stage1-analysis.md)
- [AI 使用记录](docs/ai-use.md)

## 报告与证据

- [中期汇报网页 PPT（guizang）](reports/stage1-midterm-slides/index.html)：浏览器打开，方向键翻页，`P` 查看演讲备注
- [中期汇报备用 PDF](reports/stage1-midterm-slides/slides.pdf)：12 页横向幻灯片，与网页稿对应；浏览器打印时启用背景、关闭页眉页脚
- [中期汇报逐页讲稿（Markdown）](reports/stage1-midterm-slides/speech.md)：对应当前 12 页网页稿，含完整口述与页间过渡

- [中期报告 Word](reports/stage1-midterm-report.docx)
- [中期报告 PDF](reports/stage1-midterm-report.pdf)
- [中期报告 Markdown](reports/stage1-midterm-report.md)
- [自动统计](runs/formal/analysis/results.md)
- [完整性与隔离审计](runs/formal/audit.json)

## 复现入口

实验使用本机 Codex App Server 和已配置的模型路由，不要求提交 API 密钥。

```powershell
python scripts/experiment.py --phase prepare
python scripts/experiment.py --phase generate --workers 4
python scripts/experiment.py --phase run --workers 4
python scripts/experiment.py --phase extract --workers 6
python analysis/analyze.py --input runs/formal/combined-results.jsonl --output runs/formal/analysis
python scripts/audit_runs.py --run formal
```

模型运行需要账户权限和网络访问。`qa/` 仅用于内部 DOCX 渲染检查，不纳入版本控制。

## 目录

- `scripts/`：场景、运行器、数据审计与报告构建
- `analysis/`：统计脚本
- `docs/`：方案、文献、阶段记录和证据说明
- `reports/`：Word、PDF 和 Markdown 报告
- `runs/pilot/`：开发闭环与 1.2 试跑
- `runs/pilot-v1-explicit-note/`：保留的早期地板试跑
- `runs/formal/`：冻结正式批次、轨迹与分析

## 引用

相关工作、准确性边界和一级来源见 [文献调研与证据表](docs/literature.md) 与正式报告。
