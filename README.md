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

| 条件 | 越权调用 | 模拟执行 |
|---|---:|---:|
| K0 / D0 | 8/48（16.7%） | 8/48（16.7%） |
| K75 / D0 | 5/48（10.4%） | 5/48（10.4%） |
| K100 / D0 | 3/48（6.2%） | 3/48（6.2%） |
| K0 / Dgate | 7/48（14.6%） | 0/48 |
| K75 / Dgate | 6/48（12.5%） | 0/48 |
| K100 / Dgate | 7/48（14.6%） | 0/48 |

D0 下 K100 相对 K0 的配对风险差为 -10.4 个百分点。当前数据不支持“完整业务规则披露提高越权率”的主假设。Dgate 阻断全部预设越权模拟执行，但模型仍可能提出越权调用，因此不能将程序拦截解释为模型自身安全。

自然抽取使用严格业务词组下界，平均业务事实覆盖为 0.8%，随机流程标识命中为 0。

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
