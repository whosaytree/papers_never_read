# OpenAI Agent Improvement Loop 详细笔记

## 核心定位

这篇 OpenAI Cookbook 讲的是 agent 持续改进流程。

它不是论文，也不是提出一个全新的 agent evaluation 理论。它更像一个可运行的工程模板：用 OpenAI Agents SDK 跑 agent，记录 traces，引入 human feedback 和 LLM feedback，把反馈转成 evals，再用 HALO 生成下一轮 harness 改动建议，最后把 handoff 交给 Codex 或开发者实现。

核心流程可以写成：

```text
agent runs
  -> traces
  -> human feedback + LLM feedback
  -> generated Promptfoo evals
  -> eval gate
  -> HALO diagnosis
  -> codex_handoff.md
  -> harness changes
  -> rerun evals
```

这篇的价值不是某个组件本身新，而是把这些已有环节连成一个 agent improvement loop。

## Harness 是什么

`harness` 不是这篇文章新提出的概念。

在软件工程里，`test harness` 或 `eval harness` 通常指把被测对象包起来，使它能被稳定运行、观察和评估的一整套外围结构。

在这篇文章里，harness 是 agent 外围的完整运行契约，包括：

```text
instructions
tools
routing
output requirements
validation checks
eval metadata
```

所以可以这样理解：

```text
agent = 真正执行任务的模型/智能体
harness = 规定 agent 怎么执行、能用什么、必须输出什么、如何验证的一整套外壳
```

它不是 OpenAI 的单独产品名，也不是一个新库名。

## 为什么不是只说 Prompt

如果 agent 出错，最直接的反应通常是改 prompt。

但这篇文章强调，很多 agent failure 不一定是 prompt 一句话能解决的。问题可能出在：

- tool policy 不够严格。
- routing / control flow 不清楚。
- 必须输出的 artifact 没有被结构化约束。
- validator 只检查形式，不检查真实内容。
- eval suite 没有覆盖这类 failure。
- 没有把人工反馈沉淀成 regression test。

所以文章把改进对象从 prompt 扩大到 harness。

更准确的改进路径是：

```text
发现 bad case
  -> 分析是 harness 哪个部分薄弱
  -> 改 prompt / tools / validators / output schema / evals
  -> 用同一套 eval gate 复测
```

## 这篇到底新在哪里

单独看每个组件，都不是新东西：

- traces / logs
- human review
- LLM-as-judge
- evals
- regression tests
- CI gate
- coding agent
- prompt / tool / validator 修改

文章的新意主要在于工程组织方式。

它把人的一次性反馈变成可重复运行的 eval，把 eval result 变成 harness 诊断依据，再把诊断结果变成 Codex 可执行的 handoff。

旧流程更像：

```text
agent 出错
  -> 人看 log
  -> 人写 comment
  -> 人凭经验改 prompt 或代码
  -> 下次再看有没有变好
```

这篇的流程更像：

```text
agent 出错
  -> trace 记录真实行为
  -> 人指出业务问题
  -> 反馈转成 eval
  -> eval gate 固化预期行为
  -> HALO 排序下一轮 harness changes
  -> Codex 或开发者实现
  -> rerun evals
```

所以它不是理论突破，而是一个 OpenAI 生态里的 agent 持续改进流水线模板。

## 人的工作发生了什么变化

这篇文章里，人的工作不是完全消失，而是上移。

过去常见的人类工作是：

```text
直接改 prompt
直接改工具调用规则
直接写测试
直接修代码
```

这篇的思路是：

```text
构建可评估的 harness
审阅真实 traces
给出领域反馈
审核自动生成的 eval
审核 HALO 诊断
审核 Codex 改动
决定是否合并和部署
```

也就是说，人的两项核心工作是：

第一，先构建一个可被观察、评估和迭代的 harness。

第二，对整个 harness 的行为提供高质量反馈，并在关键节点把关。

这比只说“人类监督”更具体。

## 示例 Agent 做什么

Notebook 里的示例是一个 financial analyst agent。

它服务于虚构公司的 acquisition diligence 场景，需要阅读一批 dataroom 文件，包括：

- financial exports
- customer data
- contracts
- security notes
- board materials
- management narratives

这些材料故意设计成有冲突、有缺失、有部分支持的状态。这样 agent 才会暴露真实 failure modes。

agent 要回答投资团队的问题，并留下可审计 artifacts。

## Agent 需要输出哪些 Artifacts

文章要求 agent 输出一组 artifacts：

```text
summary_answer.md
investment_memo.md
risk_register.json
open_questions.md
citations.json
evidence_table.csv
```

这些文件的作用不是装饰，而是让 agent 的回答可审计。

例如：

- `summary_answer.md` 是给用户看的简短答案。
- `investment_memo.md` 是更完整的尽调 memo。
- `risk_register.json` 是结构化风险表。
- `open_questions.md` 保留未解决问题。
- `citations.json` 记录 claim 到 source file 的映射。
- `evidence_table.csv` 记录证据链。

这说明 harness 的一部分就是 output contract。

agent 不只是回答一句话，而是必须产出一组可检查的工程 artifacts。

## Failure Modes

Notebook 设计了一些常见 failure mode。

例如：

- 把 management narrative 当成官方指标。
- 在结构化财务数据和叙述性材料冲突时，没有优先使用结构化数据。
- 把 unsupported NRR estimate 当成 finance-validated metric。
- 没有把 customer concentration 聚合到 parent-account 层级。
- 把 SOC 2 Type I 说成 SOC 2 Type II。
- 最终答案看起来完整，但 citations、risk files 或 evidence artifacts 不完整。

这些 failure mode 很适合说明为什么只改 prompt 不够。

有些问题需要事实 ledger，有些需要 validator，有些需要 artifact schema，有些需要新的 regression eval。

## Trace 的作用

Trace 是闭环的起点。

没有 trace，人只能看到最终回答，很难判断：

- agent 读了哪些文件。
- agent 调用了哪些工具。
- agent 是否生成了要求的 artifacts。
- agent 是否先通过了 validator 再补写内容。
- agent 的错误来自 evidence selection、tool use、output formatting 还是 validation 不足。

文章默认运行 5 个 traced runs。

这些 traces 覆盖不同问题类型，例如 runway / burn、ARR source of truth、customer concentration、SOC 2 状态、unsupported metrics 等。

## Human Feedback 的作用

Human feedback 是最强的领域信号。

它负责告诉系统：

- 哪个回答在业务上不可接受。
- 哪个 claim 不能出现。
- 哪个指标必须引用更高优先级来源。
- 哪个答案缺少关键数值或限定。
- 哪个 artifact 不满足审计要求。

例如专家可以指出：

```text
SOC 2 Type I 不能被表述成 SOC 2 Type II。
ARR 必须以 finance-controlled source 为准。
unsupported NRR 和 CAC payback 不应该被当作官方指标。
```

这些反馈比普通 LLM critique 更有价值，因为它们来自领域标准。

## LLM Feedback 的作用

LLM feedback 用来补充模式观察。

它可以帮助发现：

- 哪些 answer 缺 caveat。
- 哪些 claim 证据不足。
- 哪些 unsupported metrics 被过度推广。
- 哪些风险在不同 traces 中重复出现。

但它的地位低于 human feedback。

这篇的合理理解是：

```text
human feedback = 领域判断
LLM feedback = 辅助观察
```

不能把 LLM feedback 当成最终真值。

## Feedback 如何变成 Evals

文章的关键步骤是把 feedback 转成 Promptfoo eval definitions。

每条 eval 包含类似字段：

```text
eval_id
title
scoring_method
expected_behavior
source_trace_id
rubric
deterministic_assertions
suggested_pass_example
suggested_fail_example
```

`scoring_method` 可以是：

```text
deterministic
llm_judge
hybrid
```

这一步的意义是：把一次性的 review comment 变成可重复运行的 regression test。

例如：

```text
反馈：不能把 SOC 2 Type I 说成 Type II
变成 eval：输出中不能声称 Type II completed；必须准确区分 Type I / Type II
```

以后每次改 harness，都可以重新跑这条 eval。

## Promptfoo Gate 做什么

Promptfoo gate 用来运行生成出来的 evals。

它可以做两类检查：

第一类是 deterministic assertions。

例如检查输出是否包含或不包含某些文本，是否引用特定事实，是否生成必要 artifact。

第二类是 LLM rubric judge。

例如判断回答是否满足 expected behavior，是否覆盖必要事实，是否避免 unsupported claim。

这篇示例里生成了 5 条 targeted evals，覆盖：

- runway / burn
- ARR source of truth
- customer concentration parent rollup
- SOC 2 precision
- unsupported metrics refusal

## HALO 做什么

HALO 是优化诊断环节。

它接收的输入包括：

```text
current harness config
SDK execution traces
human feedback
LLM feedback
generated eval definitions
Promptfoo row results
Promptfoo gate summary
```

它不是直接修改代码，而是诊断和排序。

它要判断：

- 哪些 requirement 缺失。
- 哪些 requirement 已经写了但 agent 没稳定遵守。
- 哪些问题属于 implementation / observability defect。
- 哪些修改最值得优先做。

文章里 HALO 输出的报告包括：

- executive summary
- top 3 changes
- ranked recommendation table
- supporting diagnosis and evidence
- detailed recommendations
- insights by feedback source
- machine-readable summary

## Codex Handoff 是什么

`codex_handoff.md` 是 HALO 生成的交接文件。

它面向 Codex 或开发者，告诉后者：

- 哪些地方要改。
- 为什么要改。
- 证据来自哪些 traces / feedback / evals。
- 预期怎么验证。
- 哪些改动优先级最高。

文章里前三类建议大致是：

- 增加 deterministic diligence fact ledger 和 domain checklist。
- 升级 validators，让它们审计真实输出 artifacts，而不只是看声称的 evidence coverage。
- 把生成的 5 条 evals 持久化进 regression suite。

这说明 Codex 的角色不是神秘地自己优化 agent，而是根据结构化 handoff 实现下一轮 harness changes。

## Human Gates

文章没有要求完全自动化。

它明确允许开发者在多个位置保留人工门禁：

- trace review
- eval refinement
- pull request approval
- merge
- deployment

所以更准确的说法不是：

```text
系统自动完成所有迭代更新
```

而是：

```text
系统自动生成可执行的下一轮改进方案，人保留反馈和审批权
```

自动化程度可以逐步提高，但不应该一开始就假设完全无人审核。

## 和 RAG Synthetic Evaluation 的区别

前面看的 RAG synthetic evaluation 文章主要解决：

```text
如何从文档生成 question / answer / context 测试集
```

例如：

- Red Hat SDG Hub 生成 `question / response / ground_truth_context`。
- Databricks 生成 `request / expected_facts / expected_retrieved_context`。
- AWS 生成 question、answer、source sentence，并用 critique agents 筛选。
- RAGAS 用 evolution 控制问题类型。
- Microsoft golden dataset 讲 silver 到 golden 的清洗过程。

OpenAI 这篇解决的是另一个问题：

```text
agent 已经跑起来以后，如何把真实行为和反馈持续转成 eval、诊断和工程改动
```

所以它更偏 agent operations / LLMOps / loop engineering。

## 价值

这篇最值得记的是三个点。

第一，feedback 要被固化。

不要让人工反馈停留在一次性 comment，要把它转成可重复运行的 eval。

第二，改进对象是 harness。

不要默认所有问题都靠 prompt tuning 解决，要考虑 tools、validators、artifact schema、routing 和 eval suite。

第三，人类工作上移。

人的核心职责是构建可评估的 harness，并对 harness 行为给出高质量领域反馈和审核。

## 局限

第一，这不是严格实验论文，而是 Cookbook 示例。

第二，示例数据是 fictional company dataroom，不是真实生产系统。

第三，自动生成 eval 仍然需要人审阅，否则可能把错误 rubric 固化成 regression test。

第四，HALO 的诊断能力需要结合具体场景验证，不能默认它总能给出正确修改方向。

第五，Codex handoff 只是让实施更顺畅，不等于自动改动一定正确。

## 我应该如何记这篇

可以把这篇记成：

```text
OpenAI 生态里的 agent eval-driven development loop。
```

它不是新概念发明，而是流程组合。

它的核心句式是：

```text
traces capture behavior
feedback defines what mattered
evals preserve expectations
HALO ranks harness changes
Codex implements the next pass
```

最终要记住的是：

```text
从改 prompt，转向改 harness。
从人工修局部，转向人工反馈和审核整个改进闭环。
```

## 关键记忆点

- `harness` 不是新概念，是 agent 外围运行契约。
- 这篇的 harness 包括 instructions、tools、routing、output requirements、validation checks 和 eval metadata。
- 文章的核心不是发明新评估指标，而是把 trace、feedback、eval、HALO、Codex handoff 串成持续改进闭环。
- trace 记录真实行为，feedback 说明什么问题重要，eval 固化预期行为。
- human feedback 是领域标准来源，LLM feedback 是辅助观察。
- Promptfoo evals 把反馈变成 regression tests。
- HALO 负责诊断和排序 harness changes。
- Codex handoff 负责把改进建议变成可实施任务。
- 人的工作上移为构建 harness、提供反馈和保留 human gates。
- 这篇适合放在 agent evaluation / LLMOps / loop engineering 这一组。
