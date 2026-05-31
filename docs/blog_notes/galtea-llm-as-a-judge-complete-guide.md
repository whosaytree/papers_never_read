# Galtea LLM-as-a-Judge Complete Guide 详细笔记

## 核心定位

这篇 Galtea 文章是 LLM-as-a-Judge 的工程方法论指南。

它不是入门概念文，也不是提出新模型。它回答的是：

```text
什么时候该用 LLM judge？
应该用哪种 scoring mode？
rubric 怎么写才不会变成主观评分？
judge 如何用 labelled gold set 校准？
哪些指标能说明 judge-human agreement 真有意义？
生产系统里如何接入 judge？
什么时候不要用 judge？
```

和前两篇的关系：

```text
Humanloop: 基础分类和平台流程
Arize: production measurement infrastructure
Galtea: rubric + gold set calibration + deployment gate
```

这篇可以作为 LLM-as-a-Judge 组里的核心方法论文章之一。

## LLM-as-a-Judge 的定义

文章把 LLM-as-a-Judge 定义成：

```text
using one language model to evaluate another model's outputs against a written rubric
```

也就是：用一个模型按照书面 rubric 评估另一个模型的输出。

它可以返回：

- score。
- label。
- preference。

但文章强调，真正重要的不是模型调用本身，而是：

```text
prompt
rubric
gold set
judge-human agreement
production wiring
```

如果这些没有做好，judge 给出的数字只是看起来客观。

## 三种 Scoring Modes

文章区分三种 judging mode：

```text
pairwise comparison
single-answer grading with a rubric
reference-based grading
```

选择哪一种，会决定你的评估能回答什么问题。

## Pairwise Comparison

Pairwise comparison 是让 judge 比较两个回答。

输入是：

```text
prompt
response A
response B
criteria
```

输出是：

```text
A wins
B wins
tie
```

它适合：

- A/B test。
- 比较两个 prompt versions。
- 比较两个 model versions。
- 开发期快速选更好的候选方案。

它的优点是相对判断通常比绝对打分更可靠。

但它有一个关键限制：

```text
pairwise 不能给 absolute quality threshold
```

也就是说，B 可能赢过 A，但 B 仍然不可上线。

所以 pairwise 适合“哪个更好”，不适合“是否达标”。

## Single-Answer Grading with Rubric

Single-answer grading 是用明确 rubric 评估单个回答。

这是 Galtea 认为 production 最需要的模式。

因为每个回答都沿同一标准被评估，所以你可以设置：

```text
deployment gate
canary set threshold
regression test
minimum quality bar
```

例如：

```text
ship if faithfulness recall stays above 0.85 on the canary set
```

这类 gate 需要绝对判断，pairwise comparison 做不到。

## Reference-Based Grading

Reference-based grading 会给 judge 一个 known-good answer 或 source context。

它适合：

- translation。
- summarization against a gold summary。
- structured data extraction。
- RAG grounding。

它的问题是开放式任务里可能有很多正确答案。

如果 judge 过度依赖 reference answer，可能惩罚：

```text
correct but differently phrased answers
```

所以 reference-based grading 更适合 constrained outputs，而不是高度开放的对话任务。

## 生产中怎么组合

文章认为多数生产系统会这样组合：

```text
single-answer grading per criterion
pairwise comparison for development
reference-based grading when gold answer / source context exists
```

也就是：

- 生产主指标用 single-answer grading。
- 开发期版本选择用 pairwise。
- 有标准答案或证据文本时用 reference-based。

## 量表选择：最低够用精度

Galtea 强调，不要默认用 1-10 分。

量表应该选择最低够用精度。

可以按需求选择：

| 场景 | 推荐标签 |
|---|---|
| 只关心是否违反标准 | pass / fail |
| 失败程度影响 triage | fail / partial / pass |
| 需要细粒度排序且有 gold set 证明 judge 能稳定区分 | 1-5 或 1-10 |

细粒度分数的问题是：

```text
judge 会编造它无法稳定辩护的区别
```

比如 3 分和 4 分到底差在哪里，如果 rubric 没有明确定义，这个数字没有工程意义。

## Rubric 是什么

在这篇里，rubric 不是简单“评分标准”。

它是 judge 必须执行的一套判定程序。

Galtea 认为一个 working judge prompt 至少包含四个元素：

```text
1. criterion definition
2. explicit reasoning structure
3. scoring rule
4. edge-case handling
```

这四个元素缺一不可。

## Rubric 组件 1：Criterion Definition

Criterion definition 要用业务/领域自己的语言。

不要写：

```text
high quality
helpful
good answer
```

要写：

```text
faithful to the retrieved context
contains no unsupported factual claim
uses only evidence from the provided policy document
```

好的 criterion 让 judge 知道具体判断对象是什么。

坏的 criterion 只是在让 judge 发表主观感觉。

## Rubric 组件 2：Explicit Reasoning Structure

Galtea 强调要让 judge 先做结构化拆解。

例如：

```text
先列出 response 中的 factual claims
再逐条查找 context support
最后再给 verdict
```

对于 agent，可以让 judge 先列：

- required tool calls。
- actual tool calls。
- missing calls。
- invalid arguments。
- unsupported final claims。

这一步的作用是把 judge 从 vibes-based scoring 变成 semi-structured verification。

## Rubric 组件 3：Scoring Rule

Scoring rule 是把 reasoning result 映射到标签或分数。

不要写：

```text
Use your judgment.
```

要写：

```text
If any factual claim is not directly supported by the retrieved context, score 0.
If all factual claims are directly supported, score 1.
```

或者：

```text
pass: all required tool calls are present and arguments are valid
partial: required tool call exists but one non-critical argument is missing
fail: required tool call is missing or arguments are fabricated
```

Scoring rule 越明确，judge 越不容易凭语言流畅度乱判。

## Rubric 组件 4：Edge-Case Handling

生产里一定会有边界情况。

Rubric 要提前规定怎么判：

- truncated context。
- empty retrievals。
- partial answers。
- refusals。
- missing tool results。
- irrelevant context。
- multiple acceptable answers。

例如 RAG 场景：

```text
If the context is truncated, content beyond the provided context counts as unsupported.
If retrieval is empty, do not infer support from world knowledge.
```

Agent 场景：

```text
If required tool evidence is missing, do not mark the task as resolved.
```

这和 Arize 那篇的原则一致：证据不足不要强迫二分类猜测。

## RAG Faithfulness Worked Example

文章给了一个 RAG faithfulness judge 的例子。

它不是问：

```text
Is the answer faithful?
```

而是要求：

```text
1. Enumerate every factual claim in the response.
2. For each claim, find direct support in the provided context.
3. If any factual claim lacks direct support, verdict = unfaithful.
4. Truncated context provides zero support for missing material.
5. Output JSON verdict.
```

这个例子很重要，因为它体现了 Galtea 的核心思路：

```text
claim-level rubric > generic helpfulness score
```

## Generic Rubric 的问题

泛泛 rubric 的典型形式是：

```text
Rate the answer from 1 to 5 for helpfulness.
```

这种 rubric 的问题是：

- helpfulness 没定义。
- 不知道是否要检查事实。
- 不知道是否要检查 context support。
- 不知道缺失证据时怎么判。
- 数字分数没有可解释边界。

所以它很容易被语言流畅度、回答长度、语气影响。

Galtea 的观点是：generic rubric 给你的只是一个数字，不是一个可行动的测量。

## Judge Biases

文章列出常见 bias：

- position bias。
- verbosity bias。
- self-preference bias。

Position bias：

pairwise 比较时 judge 可能偏好 response A 或先出现的答案。

缓解方法：

```text
每个 pair 两种顺序都评一次，只保留 verdict 一致的结果。
```

这会让成本翻倍，但文章认为这是必要的。

Verbosity bias：

judge 可能偏好更长答案。

缓解方法：

```text
rubric 中明确写入 length neutrality
```

例如：

```text
At equivalent correctness, concise responses should score equal to or better than verbose responses.
```

Self-preference bias：

judge 可能偏好同模型家族生成的输出。

缓解方法：

- 用第三方模型做 judge。
- 关键比较用人工。
- 不要用 Model A 判断 Model A vs Model B。

## Criteria Drift

文章提到 criteria drift。

意思是：人类评估者在看到模型输出后，会调整自己对“好回答”的理解。

这不是坏事，而是实际 eval 设计的一部分。

因此：

```text
rubric written upfront should never be treated as final
```

Rubric 要随着 bad cases 和人工反馈持续修订。

但修订必须通过 gold set 和版本记录管理，否则会造成评估标准漂移不可控。

## 校准是什么

Calibration 是把 judge 和人工标注对齐的过程。

Galtea 的最低可行校准循环是：

```text
1. 构建 labelled gold set
2. 跑当前 judge prompt
3. 计算 judge-human agreement metrics
4. 找出表现最差的样本
5. 修改 prompt / rubric
6. 重新全量跑 gold set
7. 重复到 alignment plateau
```

文章强调：

```text
A judge prompt that looks reasonable on three examples will fail in production.
```

所以不能靠几个手写例子判断 judge 可用。

## Gold Set 要求

Gold set 是校准的基础。

它必须满足三个条件。

第一，来自真实评估分布：

```text
real queries
real retrieved contexts
real agent responses
```

不要只用作者自己写的“看起来合理”的 synthetic examples。

第二，覆盖 failure classes。

如果你的任务是抓 unfaithfulness，那么 gold set 里必须有 unfaithful 样本。

一个 100 条全是 faithful 的 gold set 不能证明 judge 会抓 hallucination。

第三，先测 human inter-rater agreement。

如果两个领域专家对超过 20% 的 labels 分歧，说明 rubric 本身含糊。

这时应该修 rubric，而不是继续调 judge。

## Gold Set 大小

文章给的范围是：

```text
30-200 examples
```

最低 30 个可以作为起点，但前提是 failure classes 覆盖良好。

生产部署门禁更稳妥的做法是：

```text
200+ examples
```

但重点不是数量本身，而是：

- 是否来自真实分布。
- 是否覆盖失败类型。
- 是否由领域专家标注。
- 人类之间是否一致。

## 为什么不能只看 Accuracy

文章明确说，只看 accuracy 是最常见错误。

原因是类别不平衡会欺骗你。

例如：

```text
90% 样本都是 pass
judge 全部预测 pass
accuracy = 0.90
```

但这个 judge 完全抓不住 failure。

所以必须看：

- per-class recall。
- confusion matrix。
- Cohen's Kappa。

尤其是 failure class recall。

## 校准指标

文章建议 baseline run 记录：

```text
accuracy
precision
recall
F1
Pearson correlation
Spearman correlation
Cohen's Kappa
```

各自作用：

| 指标 | 作用 |
|---|---|
| accuracy | 总体一致率，但容易被类别不平衡误导 |
| precision | judge 判为 positive 的样本中有多少真是 positive |
| recall | 某类真实样本有多少被 judge 抓住，尤其关键 failure class |
| F1 | precision 和 recall 的折中 |
| Pearson | 连续分数的线性相关 |
| Spearman | 排名相关，适合只相信排序不相信绝对分数时 |
| Cohen's Kappa | 扣除随机一致性后的 judge-human agreement |

Galtea 特别强调：

```text
0.9 accuracy + 0.1 Kappa 可能说明 judge 只是被类别分布抬高。
0.7 accuracy + 0.6 Kappa 反而可能说明 judge 真在推理。
```

## Prompt 优化循环

文章提到可以用 meta-LLM 做 prompt optimizer，类似 OPRO。

流程是：

```text
current prompt
+ worst-performing examples
+ full inputs / contexts / responses
+ error types
-> meta-LLM proposes candidate prompts
-> run every candidate on full gold set
-> keep best-scoring candidate
-> log all tested prompts and scores
-> repeat until alignment plateaus
```

候选 prompt 可以按不同策略生成：

- general improvement。
- fix false positives。
- fix false negatives。
- add explicit rubric。
- radical simplification。

关键不是让 meta-LLM 随便改，而是每次改完都必须在 full gold set 上重新测。

## Production Wiring

文章说生产接入需要考虑：

- batching。
- retry handling。
- malformed JSON handling。
- rate limits。
- timeouts。
- structured logging。
- judge prompt versioning。
- canary gold set regression detection。
- CI deployment gate。

这说明 judge 不是一个 notebook prompt，而是生产系统组件。

如果 judge 输出 JSON，必须处理 malformed JSON。

如果 judge API 超时，必须有 retry / fallback / fail-open or fail-closed decision。

如果 judge prompt 改了，必须记录版本，并在 canary set 上复测。

## Canary Gold Set

Canary gold set 是固定的一小组高价值测试样本。

用途是：

```text
每次修改 judge prompt / app prompt / model version / retrieval pipeline 后，检查关键 failure 是否回归。
```

它和普通 gold set 的区别是更稳定、更关键，通常用于 CI 或 deployment gate。

例如：

```text
if faithfulness recall on canary set < threshold:
    block deployment
```

## 什么时候不要用 LLM Judge

文章明确列出三类不要用 judge 的场景。

第一，有确定性 correctness check。

例如：

- SQL equivalence。
- JSON schema validation。
- regex matching。
- exact-string comparison。
- tool-call argument matching。

这些任务应该用程序检查。

LLM judge 只会增加 latency、cost 和错误概率。

第二，没有 labelled gold set。

没有 gold set，你不知道 judge 给出的分数是否有意义。

比如 judge 平均打 4.2/5，但随机 baseline 可能也能拿 4.0。

第三，missed failure 代价高于人工审核成本。

高风险领域里，不应让 judge 做最终门禁。

可以让 judge 做 triage filter：

```text
judge catches likely failures
humans review flagged cases
```

但最终裁决仍应由人类或确定性验证器完成。

## Triage Filter

Triage filter 的意思是：judge 不是最终裁判，而是筛选器。

例如：

```text
10000 条输出
judge 标记 1500 条可疑
人工重点审核这 1500 条
```

即使 judge 只能抓住 80% 失败，也能显著提升人工审核吞吐。

但它不能替代高风险场景中的人工最终判断。

## 和 Humanloop 的区别

Humanloop 主要讲：

- LLM-as-a-Judge 是什么。
- single output / pairwise / reference-guided 三类 evaluator。
- offline / online evaluator。
- 平台如何创建 evaluation run。

Galtea 主要讲：

- rubric 怎么写。
- claim-level judge 为什么比 generic score 可靠。
- gold set 怎么构建。
- 校准应该看哪些指标。
- 为什么 accuracy 不够。
- production wiring 和 deployment gate。
- 什么时候不要用 judge。

所以 Humanloop 是基础 taxonomy，Galtea 是工程方法论。

## 和 Arize 的区别

Arize 主要讲：

- code evaluator 和 LLM judge 分工。
- evaluation criteria。
- fixed labels。
- trace context。
- human calibration。
- agent trajectory evaluation。
- judge drift 和 monitoring。

Galtea 更强调：

- rubric 四要素。
- claim-level reasoning structure。
- gold set 的 failure class coverage。
- 七个校准指标。
- Cohen's Kappa。
- OPRO-style prompt optimization。
- canary set 和 CI gate。

二者互补。

可以这样分工记：

```text
Arize = evaluator 作为 production measurement infrastructure
Galtea = judge prompt / rubric / gold set calibration
```

## 和 OpenAI Agent Loop 的关系

OpenAI agent improvement loop 讲的是：

```text
traces -> feedback -> generated evals -> eval gate -> HALO -> Codex handoff
```

Galtea 这篇补的是：

```text
eval gate 里的 LLM judge 本身如何可靠
```

如果 generated eval 是 LLM judge，那么就需要 Galtea 的流程：

```text
write rubric
build gold set
calibrate judge
monitor judge
use canary set in CI
```

## 我应该如何记这篇

这篇最重要的句子是：

```text
Never trust a judge you have not measured against a labelled gold set.
```

以及：

```text
The judge is a tool, not a verdict.
```

我应该把它记成：

```text
生产级 LLM judge 的 rubric + calibration 方法论。
```

不是所有 eval 都应该交给 LLM judge。

如果要用 judge，就必须：

```text
明确 rubric
拆解 claims / conditions / tool calls
用 gold set 校准
看 per-class recall 和 Kappa
版本化并接入 canary / CI
```

## 关键记忆点

- LLM judge 是按 written rubric 评估输出，不是自动真值来源。
- 三种 scoring modes：pairwise、single-answer grading、reference-based grading。
- Production 更适合 single-answer grading with rubric。
- Pairwise 适合开发期比较，但没有 absolute quality threshold。
- Reference-based grading 适合 constrained outputs。
- 量表选择最低够用精度，不要默认 1-10。
- Rubric 要包含 criterion definition、reasoning structure、scoring rule、edge-case handling。
- Claim-level rubric 比 generic helpfulness score 更可靠。
- RAG faithfulness judge 应先枚举 factual claims，再逐条找 context support。
- Gold set 必须来自真实分布，覆盖 failure classes，由领域专家标注。
- 使用 gold set 前要测 human inter-rater agreement。
- 校准不能只看 accuracy，要看 precision、recall、F1、Pearson、Spearman、Cohen's Kappa。
- Per-class recall 尤其重要，因为 failure 漏检会被 aggregate accuracy 掩盖。
- Prompt/rubric 优化应基于 worst-performing examples 和 full gold set re-evaluation。
- 生产接入要处理 batching、retry、malformed JSON、rate limit、timeout、logging、versioning 和 CI gate。
- 有确定性 check 时不要用 LLM judge。
- 没有 labelled gold set 时不要把 judge 当 production signal。
- 高风险场景中 judge 应做 triage filter，而不是最终裁决。
