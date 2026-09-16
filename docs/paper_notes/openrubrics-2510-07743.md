# OpenRubrics：训练监督与实验对照

来源：[ACL 正式论文](https://aclanthology.org/2026.acl-long.791/) · [arXiv（2025 年首发）](https://arxiv.org/abs/2510.07743) · [同题演讲](https://doi.org/10.48448/69jw-cr34) · [模型与数据](https://huggingface.co/OpenRubrics)

## 各阶段的监督关系

- 数据生成与筛选：输入与目标：从问题和优劣回答生成 Rubric、分析与判断；监督信号 / 更新对象：已有偏好标签用于筛选；不更新教师参数
- Rubric 生成器 SFT：输入与目标：问题 → Rubric；监督信号 / 更新对象：筛选后的教师 Rubric 文本；更新生成器参数
- Judge SFT：输入与目标：问题＋Rubric＋回答对 → 分析与胜负；监督信号 / 更新对象：教师分析与通过筛选的偏好判断；更新 Judge 参数
- 策略模型 DPO：输入与目标：问题＋chosen/rejected 回答；监督信号 / 更新对象：Rubric-RM 产生的偏好关系；更新策略模型参数

教师数据生成使用 GPT-4.1-Mini 和 Gemini-2.5-Flash-Lite；学生生成器与 Judge 基于 Qwen3。Rubric 条目没有显式的可学习数值权重，其优先级和综合判断通过提示词及 Judge 学到的行为体现。

## 实验对照

- 奖励模型主表平均分：对照：最强 7B 基线 61.7；结果：Rubric-RM-8B 70.1
- 未微调与微调后的 Rubric＋Judge：对照：Qwen3-8B：57.7；结果：70.1
- Judge 多数投票：对照：单次判断 70.1；结果：voting@5：73.0
- DPO 后策略模型 IFEval 平均分：对照：原模型 77.3；结果：79.5
- DPO 后策略模型 HealthBench 分数：对照：原模型 21.6；结果：23.8

摘要所称“提升 8.4%”，对应主表平均分增加 8.4 个百分点。其中 Rubric-RM-8B 使用一个 8B 生成器和一个 8B Judge，成本比较需要考虑两个组件。

实验支持整套流程的有效性，但尚不足以分别归因于对比生成、一致性筛选或某个模型的微调。进一步判断 Rubric 本身是否改善，需要控制数据量比较筛选前后效果、固定 Judge 比较不同生成器，并在新回答及独立评估者上检验泛化。论文主要验证成对判断与离线 DPO，未证明持续循环训练或绝对打分的效果。

## 关键图

[OpenRubrics 原文 Figure 1](../assets/paper_images/openrubrics-2510-07743-figure-1.png)

原文编号与页码：Figure 1；PDF 第 3 页，论文页码 17419。

中文图注：OpenRubrics 的合成 Rubric 流程。先构造带优劣标签的回答对，再通过对比提炼硬性要求与质量原则，最后利用 Rubric 判断与已有偏好标签的一致性筛选训练数据。

选择理由：该图直观展示了标准从哪里来、如何筛选。图中描述的是离线数据构造过程；后续两个模型的监督微调及 DPO 训练由正文补充。

原文与原图依据 ACL 的 [CC BY 4.0 授权](https://aclanthology.org/faq/copyright/)展示。
