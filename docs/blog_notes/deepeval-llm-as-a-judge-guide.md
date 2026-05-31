# DeepEval: LLM-as-a-Judge Evaluation

## 核心定位

这篇是 DeepEval 的官方工具指南，重点不是提出新的评估理论，而是说明如何在 DeepEval 里把 LLM-as-a-Judge 做成可重复运行的 metric。

它回答的是：

我已经有 test cases、RAG/agent outputs 或 production traces 了，应该用 DeepEval 的哪种 judge API 来评估？

它最重要的判断是：LLM-as-a-Judge 不等于“让 LLM 给个分”。不同任务应该选择不同 judge technique。

## 四类 Judge 形态

| 技术 | 适合场景 | DeepEval API | 主要特点 |
| --- | --- | --- | --- |
| G-Eval | 自定义、主观、单输出评估 | `GEval` | 最快定义 custom judge |
| DAG | 多条件、硬规则、分支判断 | `DAGMetric` | 更可控、更可追踪 |
| QAG-style built-ins | 常见 RAG / agent / safety 指标 | built-in metrics | 少写 prompt，使用框架默认算法 |
| Arena | 比较两个 prompt/model 版本 | `ArenaGEval` | pairwise judge，选择 winner |

我的理解是：

- `GEval` 是快速自定义指标。
- `DAGMetric` 是把宽泛指标工程化成 decision tree。
- QAG built-ins 是 DeepEval 已经封装好的常见评估算法。
- `ArenaGEval` 是做 A/B 或版本比较。

## LLMTestCase 是基础抽象

DeepEval 的基础评估样本是 `LLMTestCase`。

常见字段包括：

| 字段 | 含义 | 典型用途 |
| --- | --- | --- |
| `input` | 用户输入 | answer relevancy、helpfulness |
| `actual_output` | 模型真实输出 | 所有输出质量评估 |
| `expected_output` | gold answer / labelled answer | correctness、contextual recall |
| `context` | 独立 ground-truth context | hallucination / grounding |
| `retrieval_context` | RAG 检索到的 chunks | faithfulness、contextual relevancy |
| `expected_tools` | agent 应调用的工具 | tool correctness |

这篇强调：metric 是否 reference-based，不是由 metric 名字决定，而是由它用到哪些字段决定。

## Reference-Based vs Referenceless

| 类型 | 使用字段 | 适合场景 |
| --- | --- | --- |
| Reference-based | `expected_output`、`context`、`retrieval_context`、`expected_tools` | offline eval、golden dataset、RAG grounding、tool correctness |
| Referenceless | `input`、`actual_output` | production monitoring、helpfulness、answer relevancy、tone |

例子：

- `actual_output + expected_output` 判断 correctness，是 reference-based。
- `input + actual_output` 判断 helpfulness，是 referenceless。
- `actual_output + retrieval_context` 判断 faithfulness，是 reference-based。
- pairwise 比较两个 outputs，也可以 reference-based 或 referenceless，取决于 criteria 是否用 reference fields。

生产监控通常更依赖 referenceless metrics，因为线上请求一般没有人工 labelled `expected_output`。

## GEval 是什么

`GEval` 是 DeepEval 中最灵活的 custom LLM judge。

你需要定义：

- metric name。
- judging criteria 或 evaluation steps。
- judge 应该读取哪些 `LLMTestCase` fields。
- threshold。
- 可选 judge model、strict mode、verbose mode。

它适合：

- correctness。
- helpfulness。
- tone。
- coherence。
- policy compliance。
- summarization quality。
- domain-specific quality。

## Criteria vs Evaluation Steps

`GEval` 有两种定义方式。

| 方式 | 适合阶段 | 特点 |
| --- | --- | --- |
| `criteria` | 快速原型 | 用一句自然语言描述标准 |
| `evaluation_steps` | CI/CD 或生产监控 | 明确 judge 推理步骤，更稳定 |

例如，早期可以写：

```python
GEval(
    name="Helpfulness",
    criteria="Determine whether the actual output is helpful for answering the input.",
    evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
)
```

但如果这个 metric 要进 CI/CD，应该改成更明确的 steps：

```python
GEval(
    name="Correctness",
    evaluation_steps=[
        "Check whether the actual output contradicts the expected output.",
        "Penalize missing eligibility conditions that change the meaning.",
        "Do not penalize harmless wording differences.",
    ],
    evaluation_params=[
        SingleTurnParams.ACTUAL_OUTPUT,
        SingleTurnParams.EXPECTED_OUTPUT,
    ],
)
```

我的理解是：

`criteria` 是探索，`evaluation_steps` 是固化。

## GEval 的局限

`GEval` 的问题是：如果 criteria 太宽，它可能把多个硬条件揉成一个主观判断。

例如：

“回答是否好”可能同时包含：

- 是否 JSON 合法。
- 是否包含必需字段。
- 是否没有 hallucination。
- 是否语气合适。
- 是否回答用户问题。

如果全部塞进一个 `GEval`，judge 的分数会不稳定，也不容易 debug。

这时应该考虑：

- 拆成多个 GEval。
- 写更明确的 evaluation_steps。
- 用 built-in metrics。
- 或者改成 DAGMetric。

## DAGMetric 是什么

`DAGMetric` 是 DeepEval 中更确定、更可追踪的 judge 形式。

它把评估逻辑拆成 decision tree。

每个节点判断一个更小的问题，根据判断结果走不同路径，最后到达某个 score 或子 metric。

适合：

- 有 hard gates。
- 缺少某个必要条件就必须 fail。
- 不同错误类型有不同 penalty。
- 希望看到 judge 走了哪条 path。
- 想把宽泛 rubric 拆成明确分支。

## DAGMetric 示例逻辑

一个常见 DAG 可以是：

1. 判断输出是否是合法 JSON。
2. 如果不是合法 JSON，直接 0 分。
3. 如果是，判断是否包含必要字段。
4. 如果缺字段，给低分。
5. 如果字段完整，再进入 helpfulness / correctness GEval。

这比一个泛泛的 judge 更可控。

对 RAG / agent 也可以类似：

| Gate | 后续 |
| --- | --- |
| 是否调用了必要工具 | 没调用直接 fail |
| 参数是否有效 | 无效参数低分 |
| 是否引用检索上下文 | 没引用 fail |
| 是否完成用户目标 | 通过后再评质量 |

这和 Galtea 提到的 claim-level / condition-level rubric 很接近，只是 DeepEval 给了工程实现。

## GEval vs DAGMetric

| 问题 | 更适合 GEval | 更适合 DAGMetric |
| --- | --- | --- |
| 质量维度主要是主观判断 | 是 | 有时 |
| 有明确 hard failure | 有时 | 是 |
| 需要 inspect decision path | 有限 | 是 |
| 想快速定义 custom metric | 是 | 否 |
| 想要更确定的控制 | 有限 | 是 |

我的记法是：

- 先用 `GEval` 跑起来。
- 指标重要后改 `evaluation_steps`。
- 发现有硬规则或多条件分支后改 `DAGMetric`。

## QAG-Style Built-In Metrics

QAG 指 question-answer generation。

在 eval 里，它通常表示：把一个大判断拆成多个 closed-ended questions，再根据答案汇总分数。

DeepEval 很多 built-in metrics 都用了类似思路。

| Metric | 检查什么 | 是否需要 reference-like 字段 |
| --- | --- | --- |
| `AnswerRelevancyMetric` | `actual_output` 是否回答了 `input` | 不需要 |
| `FaithfulnessMetric` | `actual_output` 是否 grounded in retrieved context | 需要 `retrieval_context` |
| `ContextualRelevancyMetric` | retrieved chunks 是否和 input 相关 | 需要 `retrieval_context` |
| `ContextualRecallMetric` | retrieval 是否覆盖 expected answer 所需事实 | 需要 `expected_output` + `retrieval_context` |
| `ToolCorrectnessMetric` | agent 是否调用正确工具 | 需要 `expected_tools` |
| `TaskCompletionMetric` | agent 是否完成任务 | 视设置而定 |

如果 DeepEval 已经有对应 built-in metric，文章建议优先用 built-in，而不是自己写一个泛泛 custom judge。

## ArenaGEval

`ArenaGEval` 是 pairwise judge。

它不评估单个 output 的绝对分数，而是在多个 contestants 中选更好的。

适合：

- prompt v1 vs prompt v2。
- model A vs model B。
- retriever config A vs B。
- agent workflow A vs B。

Pairwise judge 适合回答“哪个版本更好”，但不一定回答“这个版本是否达到最低质量门槛”。

这和 LMSYS / Arena-Hard 那类 pairwise preference 思路相近。

## CI/CD Regression Testing

DeepEval 的一个工程价值是可以把 LLM judge 接入测试。

通过 `assert_test()`，可以像 pytest 一样写 regression test。

示例逻辑：

```python
def test_refund_answer():
    test_case = LLMTestCase(
        input="What if these shoes don't fit?",
        actual_output="We offer a 30-day full refund at no extra cost.",
        expected_output="You're eligible for a 30 day refund at no extra cost.",
    )
    metric = GEval(
        name="Correctness",
        criteria="Determine whether the actual output is correct based on the expected output.",
        evaluation_params=[
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.EXPECTED_OUTPUT,
        ],
        threshold=0.7,
    )
    assert_test(test_case, [metric])
```

然后运行：

```bash
deepeval test run test_refund_answer.py
```

这意味着它可以作为 prompt、retriever、model、tool schema 改动后的自动回归检查。

## Trace / Component-Level Evaluation

文章还提到可以在应用组件内部跑 eval。

例如：

- retriever。
- generator。
- reranker。
- agent planner。
- tool-calling step。
- final response。

通过 tracing / observe，可以把 metric 挂到某个 component 上，而不是只评最终答案。

这点和 Arize 的 trace-based evaluation 接近：agent / RAG 的问题往往不只出现在 final answer，还可能出在 retrieval、tool selection 或 intermediate step。

## Production Monitoring

DeepEval metric 也可以用于 production monitoring。

常见用途：

- 追踪 answer relevancy。
- 追踪 faithfulness。
- 追踪 task completion。
- 追踪 safety。
- 检测 prompt / retriever / model / tool 变更后的质量退化。
- 把低分 traces 采样进后续 regression dataset。
- 把可疑输出路由到 human annotation queue。

文章提醒：生产监控不要堆太多 LLM judges。

原因是：

- 成本高。
- 噪声大。
- 难解释。
- 指标之间可能互相重叠。

生产中应该先选少量 high-signal metrics。

## Debug Judge Scores

DeepEval metric 会返回：

- `metric.score`。
- `metric.reason`。

还可以开启：

- `verbose_mode=True`。

如果 judge 分数看起来不对，优先检查三件事：

1. Judge 是否看到了正确字段。
2. Metric 是否意外变成 reference-based。
3. Criteria 是否太宽。

对应修复：

- 检查 `evaluation_params`。
- 检查 `LLMTestCase`。
- 从 `criteria` 改到 `evaluation_steps`。
- 用 `DAGMetric` 拆分支。

## Human Annotation Check

文章没有把 LLM judge 当成绝对真值。

它建议用 human labels cross-check judge。

可以看四类结果：

| 类型 | 含义 |
| --- | --- |
| True positive | metric pass，human 也接受 |
| True negative | metric fail，human 也拒绝 |
| False positive | metric pass，但 human 拒绝 |
| False negative | metric fail，但 human 接受 |

其中 false positive 在高风险场景更危险。

因为它意味着坏输出被 judge 放过，团队会产生错误信心。

如果 false positive / false negative 太多，应该：

- 收紧 criteria。
- 写 explicit evaluation_steps。
- 调整 threshold。
- 使用 `strict_mode`。
- 拆成更确定的 `DAGMetric`。

## 和 Galtea 的关系

Galtea 讲的是：

- rubric 如何定义。
- claim-level evaluation 为什么重要。
- gold set 如何校准。
- 为什么不能只看 accuracy。
- judge-human alignment 如何验证。

DeepEval 这篇讲的是：

- 在工程框架里如何实现 judge。
- 如何选择 GEval / DAG / built-ins / Arena。
- 如何接入 CI/CD。
- 如何在 component trace 上跑评估。
- 如何 debug judge score。

所以 Galtea 更偏方法论，DeepEval 更偏执行工具。

## 和 Braintrust 的关系

Braintrust 那篇讲：

- production traces 如何进入 human review。
- reviewer 如何填写 `expected`。
- reviewed traces 如何 promote 到 golden dataset。
- human labels 如何校准 scorers。

DeepEval 这篇讲：

- 拿到 test cases 后怎么跑 metrics。
- reference fields 如何进入 judge。
- 如何在 CI/CD 和 production monitoring 里运行这些 judge。

所以 Braintrust 更像数据和审阅 workflow，DeepEval 更像 eval execution framework。

## 和 Arize 的关系

Arize 讲的是 production evaluator infrastructure：

- trace context。
- judge drift。
- human calibration。
- production monitoring。
- evaluator as measurement infrastructure。

DeepEval 这篇更具体到 Python API：

- `LLMTestCase`。
- `GEval`。
- `DAGMetric`。
- built-in metrics。
- `assert_test()`。
- `observe()`。

它们互补：Arize 讲架构原则，DeepEval 讲怎么写测试。

## 我应该如何记这篇

这篇可以记成一条升级路径：

1. 先用 built-in metrics 覆盖标准场景。
2. 没有合适 built-in 时，用 `GEval(criteria=...)` 快速起步。
3. 指标重要后，改成 `GEval(evaluation_steps=[...])`。
4. 如果存在 hard gate 或多条件分支，改成 `DAGMetric`。
5. 如果比较版本，用 `ArenaGEval`。
6. 如果要上线，接入 `assert_test()` 和 tracing。
7. 如果要信任 judge，用 human annotations 检查 false positive / false negative。

这比“写一个 1-10 分 judge”更适合工程落地。

## 关键记忆点

- LLM-as-a-Judge 不是一个单一技术，而是一组 judge patterns。
- `GEval` 适合快速 custom subjective metric。
- `evaluation_steps` 比泛泛 `criteria` 更适合重要指标。
- `DAGMetric` 适合 hard gate 和 branching logic。
- Built-in metrics 适合常见 RAG / agent / safety 场景。
- `ArenaGEval` 适合 pairwise prompt/model comparison。
- Reference-based 与否取决于使用哪些 `LLMTestCase` fields。
- Production monitoring 通常依赖 referenceless metrics。
- CI/CD 可以用 `assert_test()`。
- Trace-level eval 可以评组件，不只评最终答案。
- Debug judge 要看 `metric.reason` 和 `verbose_mode`。
- Human annotations 仍然是校验 judge 的必要环节。
