# Towards Better RL Training Data Utilization via Second-Order Rollout 详细笔记

## 核心定位

这篇论文提出 GC-RL（Generation and Critique RL），目标是在同一批数学 RLVR 训练题上同时训练解题能力和答案评价能力。它把普通答题 rollout 扩展成两类训练信号：

- `q -> response`：训练模型直接解题。
- `<q, response> -> critique`：训练模型评价已有回答的正误。

两类 rollout 更新同一个 policy model。论文的 generation benchmark 仍采用单次直接答题流程，收益主要体现为训练后参数中的判断能力促进直接推理表现。

## 训练流程

GC-RL 的一次训练步骤可以拆成四段：

- 从训练集采样一批数学题，让 policy model 为每题生成多个回答，这是一阶 rollout。
- 用 rule-based verifier 判断每个回答最终答案是否正确。
- 将一阶回答送入 data filter；只有同一题同时出现正确回答和错误回答时，才各采一个 `<问题, 回答>` 放入 question-response cache。
- 从 cache 采样 `<问题, 回答>`，让同一个 policy model 生成多条 critique，这就是二阶 rollout。

随后，answer rollout 和 critique rollout 被混合起来，分别计算 reward 与 advantage，并通过 GRPO 更新同一个 policy model。

## Critique 的输入与 reward

Critique 阶段的输入包含题目和一个已有回答，不给标准答案。形式接近：

```text
Question: q
Response: r
Please critique the above response.
```

模型需要生成分析，并在结尾输出 `right/wrong` 一类最终判断。训练时的 reward 主要看最终判断是否匹配 verifier 对原回答的真实正误：

- 原回答正确，critique 判断为 right，给 reward。
- 原回答错误，critique 判断为 wrong，给 reward。
- 判断不匹配，给 0。

论文明确承认 critique 中间推理步骤难以自动验证，因此主 reward 是 outcome-based binary reward。这个设计会产生噪声：模型可能中间分析质量一般，但最终二分类判断命中。

## Cold Start

作者没有把 prompt-only critique 作为正式可用方案。论文指出 base model 直接进入 critique RL 时会遇到格式跟随弱、critique 中间步骤质量低的问题，因此先做 cold-start SFT：

- 从 DAPO-MATH-17k 中抽 1k 条作为 cold-start 种子。
- 用 GPT-5 按固定 prompt 生成 critique 数据。
- 初始生成 1,885 条 critique。
- 过滤格式错误和最终判断错误样本。
- 保留 1,339 条高质量 critique 样本做 SFT。

这个阶段让模型先学会“逐步验证 + 末尾输出 right/wrong 判断”的行为格式，再进入 C-RL、G-RL 或 GC-RL。

## 推理阶段

论文主表里的 generation accuracy 来自普通单次解题：

```text
题目 -> 模型生成解题过程和最终答案 -> verifier 判断最终答案
```

主结果没有使用显式的 self-correction pipeline。也就是说，报告的数学准确率主要反映训练后的参数收益。模型在单次生成中可能自发进行检查、重算或修正，这属于训练诱导出的生成行为。

Critique capability 的单独评测使用另一种输入：

```text
题目 + 已有回答 -> critique + right/wrong 判断
```

评价指标是最终判断的 accuracy。

## 数据集与指标

训练主要使用 DAPO-MATH-17k：

- 1k 用于 cold-start critique SFT。
- 16k 用于 RL。

Generation evaluation 覆盖：

- Math-500
- GSM8K
- Minerva
- AMC23
- OlympiadBench

Critique evaluation 由这些数学评测集构造而来。作者用多个 Qwen2.5-Instruct 模型为题目采样回答，过滤格式不合格样本，再为每题保留一个正确回答和一个错误回答，构造 1:1 balanced 的 `<question, response>` 判断集。

主表里 critique capability 使用 accuracy。论文后续 reward shaping 分析中额外报告 precision、recall 和 F1。

## 联合优化证据

论文的关键 baseline 是：

- G-RL：只做 first-order rollout，专门训练解题。
- C-RL：只做 second-order rollout，专门训练 critique。
- GC-RL：混合 answer rollout 和 critique rollout，联合训练。

有效性的核心证据是：GC-RL 在 generation 上超过 G-RL，同时在 critique 上超过 C-RL。以 Qwen2.5-7B 为例：

- Generation average accuracy：G-RL 56.7，GC-RL 59.3。
- Critique accuracy：C-RL 73.8，GC-RL 78.6。

这个结果支持同一模型中 generation 与 critique 能力存在正迁移。

## 风险与限制

论文识别了几个重要风险：

- Label imbalance：一阶 rollout 中错误回答常常更多，critique 训练容易偏向判错。Data filter 通过同题一正一错缓解这个问题。
- Reward noise：critique 的中间分析难以验证，最终二分类 reward 会奖励一部分低质量分析。作者用 self-correction 采样策略做 reward denoising。
- Reward hacking：只训练 critique 且使用 dynamic data 时，模型可能利用数据分布投机。GC-RL 保留 generation reward 后，这条投机路径受到约束。
- Compute cost：二阶 rollout 增加额外生成成本，论文也报告 GC-RL 收敛更慢。
- Domain scope：实验集中在数学推理和可规则验证答案的任务，开放域长答案、多维 rubric 评价仍需要额外设计。

## 复现状态

目前没有看到官方 GC-RL 代码、cold-start 数据或模型 checkpoint。论文说明实验基于 `verl` 框架和 GRPO，给出了部分超参。可行的复现路径是基于 `verl` 增加二阶 rollout、question-response cache、data filter、critique reward 和混合训练逻辑。

严格复现论文表格会受到几类因素影响：

- GPT-5 蒸馏的 cold-start critique 数据分布。
- 数学答案 verifier 与 `boxed{}` 抽取规则。
- Critique 最终 `right/wrong` 判断抽取规则。
- Cache 更新节奏、采样比例和 rollout 混合细节。
- 二阶 rollout 带来的计算预算差异。

## 对后续研究的启发

这篇论文最有价值的启发在于：训练时可以把“回答”转化成新的可验证任务，让同一批原始题目产生更多训练信号。对于 agent/RL 方向，这提示我们可以围绕已有轨迹构造二阶任务，例如评价回答、诊断错误、判断工具调用是否有效、预测下一步修正方向，并把这些任务作为训练时辅助目标。

这类方法的关键工程点在于 reward 设计和数据分布控制。辅助目标需要有可靠的自动验证信号，也需要避免样本分布诱导模型走向保守判断、默认否定或其他投机策略。

## 参考

- [arXiv:2602.22765](https://arxiv.org/abs/2602.22765)
- [OpenReview submission](https://openreview.net/forum?id=pSz8fhrA9A)
