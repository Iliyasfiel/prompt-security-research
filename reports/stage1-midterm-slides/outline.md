# 中期汇报页面计划

瑞士国际主义风，克莱因蓝。按课程中期汇报组织，时长未由用户指定，备注不设置自动播放时间。

| 页码 | 页面ID | 目的与主题 | 版式 |
|---|---|---|---|
| 01 | cover | 系统提示泄露，会放大越权风险吗 | "SWISS-COVER-ASCII" |
| 02 | questions | 研究问题：从信息暴露到状态改变 | "S20" |
| 03 | position | 研究定位与当前进度 | "S20" |
| 04 | boundary | 攻击面：外部文字如何进入可信执行链 | "S08" |
| 05 | design | 实验设计：知识量、目标与执行条件 | "S08" |
| 06 | procedure | 实验过程：批次冻结与单次工具闭环 | "S11" |
| 07 | real-case | 真实案例：内部标签包装无审批写入 | "S08" |
| 08 | results | 结果：宽标签下降不能等同权限风险下降 | "S08" |
| 09 | execution | 调用、执行与正常效用必须分开报告 | "S08" |
| 10 | extraction | 自然抽取：严格匹配少，不代表语义完全未暴露 | "S08" |
| 11 | limitations | 当前证据的边界与下一步 | "S05" |
| 12 | closing | 阶段结论：闭环已完成，增益仍待验证 | "S20" |

## 数据修正
原始抽取结果总体平均0.2604%，结构化组平均0.78125%，两者不得混用。

旧宽标签包含未在正式用户请求中指定的默认备注文案检查，不能直接表示严格权限违规。离线复核见 [metric-review.json](metric-review.json)：跨用户修改或无审批状态更新仅在 K100/D0 出现 1 次，其他组为 0。未重跑模型或修改冻结数据；旧 DOCX/PDF 尚未同步此更正。

## 讲稿提词
### 系统提示泄露，会放大越权风险吗
- 研究动机是内部业务知识能否提高提示注入效果。
- 先分清获得信息、改变行为和写入状态三个环节。
- 当前批次已完成，但评分复核发现任务范围标签与权限指标混用。
- 数据依据：runs/formal/results.jsonl、runs/formal/extraction/results.jsonl；阶段依据：docs/stage1-progress.md。

### 研究问题：从信息暴露到状态改变
- RQ1是真实抽取，RQ2是实验器主动披露，两者不能拼成已实现的攻击链。
- 主假设是完整信息相对无额外信息提高权限违规概率。
- 成功需要工具与状态证据，模型自称完成不够。
- 数据依据：runs/formal/results.jsonl、runs/formal/extraction/results.jsonl；阶段依据：docs/stage1-progress.md。

### 研究定位与当前进度
- 文献调研已完成，资料集中于docs/literature.md。
- 阶段1.1至1.5已有交付，但测量问题需要明确披露。
- 来源：https://arxiv.org/html/2611.04803v1；https://arxiv.org/html/2406.13352v3；https://arxiv.org/html/2503.18813v2
- 数据依据：runs/formal/results.jsonl、runs/formal/extraction/results.jsonl；阶段依据：docs/stage1-progress.md。

### 攻击面：外部文字如何进入可信执行链
- baseInstructions承载应用提示，dynamicTools承载实际工具交互。
- D0仍保留应用规则，只移除程序执行检查。
- 平台后台工具和指令是已记录的环境限制。
- 数据依据：runs/formal/results.jsonl、runs/formal/extraction/results.jsonl；阶段依据：docs/stage1-progress.md。

### 实验设计：知识量、目标与执行条件
- K75实际按固定种子从三个事实组抽4、5、3条，图示只代表条数，不代表所有配置取同一12条。
- 同一候选在两种防御下配对，各次会话独立。
- 知识条数与攻击价值不等价，缺少等长对照也可能混入文本长度影响。
- 数据依据：runs/formal/results.jsonl、runs/formal/extraction/results.jsonl；阶段依据：docs/stage1-progress.md。

### 实验过程：批次冻结与单次工具闭环
- 候选生成与目标评测分开，不把评分反馈给生成器挑选最优攻击。
- 抽取是独立分支，共24会话120次可见查询。
- formal审计显示当前批次完成，无技术错误和协议无效；没有为本次汇报重跑模型。
- 工具read返回记录可能引用可变对象，状态证据使用initial_state和final_state。
- 数据依据：runs/formal/results.jsonl、runs/formal/extraction/results.jsonl；阶段依据：docs/stage1-progress.md。

### 真实案例：内部标签包装无审批写入
- 来自test_support-K100-2-workflow-0，两个运行candidate_hash相同。
- 这是唯一精确目标命中，也符合严格无审批状态违规。
- 配对Dgate是模型自行拒绝，不能声称后端gate在这个案例阻断了调用。
- 该攻击使用受控K100，不是先成功抽取后自动串接。
- 数据依据：runs/formal/results.jsonl、runs/formal/extraction/results.jsonl；阶段依据：docs/stage1-progress.md。

### 结果：宽标签下降不能等同权限风险下降
- 旧宽标签D0为8、5、3，Dgate为7、6、7。
- 严格授权事件是对现有轨迹离线复核，不改冻结标签。
- 旧K100-K0差为负10.4个百分点，只能作为宽标签诊断，不能解释为权限风险因果效应。
- 数据依据：runs/formal/results.jsonl、runs/formal/extraction/results.jsonl；阶段依据：docs/stage1-progress.md。

### 调用、执行与正常效用必须分开报告
- D0和Dgate的调用提议并不相同，因为两次模型运行独立。
- 执行条表示旧标签提议中实际被执行的比例，不是攻击成功率。
- 正常任务两种防御各32/32，包含本人备注、只读和可信审批状态更新。
- 数据依据：runs/formal/results.jsonl、runs/formal/extraction/results.jsonl；阶段依据：docs/stage1-progress.md。

### 自然抽取：严格匹配少，不代表语义完全未暴露
- 这是独立自然抽取分支，不能与人工披露K值合成一条泄露到攻击曲线。
- 总体0.26%，结构化组0.78%；旧报告总体0.8%表述需更正。
- 公开工具名不计隐藏事实；随机标识帮助区分实际恢复与常识猜测。
- 数据依据：runs/formal/results.jsonl、runs/formal/extraction/results.jsonl；阶段依据：docs/stage1-progress.md。

### 当前证据的边界与下一步
- 优先级是改善证据质量，不是扩建框架或增加大量模型。
- 冻结结果不覆盖，评分更正和新实验分别记录。
- 现有DOCX/PDF尚未同步评分复核更正，当前网页稿说明优先。
- 数据依据：runs/formal/results.jsonl、runs/formal/extraction/results.jsonl；阶段依据：docs/stage1-progress.md。

### 阶段结论：闭环已完成，增益仍待验证
- 回扣最初问题，用可证实的观察回答。
- 全部图表来自当前冻结记录与离线复核，没有新增模型实验。
- 问答可围绕为何分开自然抽取与披露、为何不能把gate解释为模型安全展开。
- 数据依据：runs/formal/results.jsonl、runs/formal/extraction/results.jsonl；阶段依据：docs/stage1-progress.md。