# Braintrust: How to improve your golden datasets with human review

## 核心定位

这篇文章解决的问题不是“如何生成 synthetic QA”，也不是“如何写 LLM-as-a-Judge prompt”，而是：

真实线上产生的 traces，如何经过人工审阅，变成可复用、可回归、可校准 scorer 的 golden dataset。

它适合和 Galtea、Arize、Humanloop 放在一起看：

| 文章 | 主要回答的问题 |
| --- | --- |
| Humanloop LLM-as-a-Judge | LLM judge 有哪些基本类型 |
| Arize Production Evaluators | 生产中的 evaluator 如何接 trace、监控和校准 |
| Galtea Complete Guide | rubric 和 judge-human calibration 怎么设计 |
| Braintrust Human Review | gold set 从哪里来、如何从 production traces 持续维护 |

这篇的关键词不是“模型评估分数”，而是“人工审阅工作流”。

## 总流程

文章给出的闭环可以概括为：

| 阶段 | 具体动作 | 产出 |
| --- | --- | --- |
| Capture behavior | 从 production logs / traces 捕获真实交互、失败、边界样本 | 原始 traces |
| Categorize | 按 failure mode、intent、sentiment 等维度聚类或打标签 | 可筛选的 trace groups |
| Label with expertise | SME / reviewer 填写 `expected`、`is_correct`、`failure_type`、notes | 人工确认 ground truth |
| Promote to dataset | 把 reviewed traces 放入 golden dataset / regression suite | 长期测试样本 |
| Score in evals | 用 heuristic scorer 或 LLM judge 跑这些样本 | 自动评估指标 |
| Ship / fix / block | 根据 eval 结果决定上线、修复或阻断 | 工程决策 |
| Refresh | 新 failure 回流，旧样本去重和清理 | 持续演化的 golden set |

所以这不是一次性构造数据集，而是一种 eval dataset flywheel。

## 为什么需要 Human Review

AI 产品里很多质量标准不是 prompt、heuristic 或模型 confidence 能完全定义的。

例如：

- 某个回答是否满足真实业务 policy。
- 某个工具调用是否符合内部流程。
- 某个客服回答是否符合客户预期。
- 某个 RAG answer 是否虽然有引用但仍然误导。
- 某个失败是否应该归因于 retrieval、tool misuse、policy 还是 formatting。

这些判断需要 domain knowledge、policy expertise 和 customer expectation。

Human review 的作用不是“人工看所有数据”，而是让专家判断进入 eval system，形成可复用的 ground truth。

## Production Traces 是什么

这里的 trace 指线上 AI 应用的一次真实运行记录。

它通常可能包含：

- 用户输入。
- 模型输出。
- prompt / system instruction。
- 检索到的 context。
- tool calls。
- tool responses。
- intermediate spans。
- latency、cost、token usage。
- metadata，例如用户类型、业务场景、版本号。

Braintrust 这篇强调的是：golden dataset 不应该只来自人工脑补的测试题，也可以来自真实生产失败。

这和 synthetic QA 文章的区别很大：

| 数据来源 | 优点 | 风险 |
| --- | --- | --- |
| Synthetic QA | 覆盖快、便宜、可控 | 可能偏离真实用户分布 |
| Production traces | 真实、贴近业务、包含边界问题 | 需要筛选、去噪、人工标注 |

Braintrust 的立场更偏 production-driven eval。

## Topics 的作用

文章提到，在真实生产规模下，reviewer 不可能一条条浏览所有 trace。

因此需要先做自动分类，例如按：

- failure mode。
- user intent。
- sentiment。
- task category。
- business area。

Braintrust 的 Topics 功能就是做这件事：把 production traces 聚类成有名字的类别，并把分类作为可 SQL 查询的 labels 存在 trace 上。

这一步的价值是：

1. Reviewer 不用从零开始翻所有 trace。
2. 可以按某类问题批量审阅。
3. 可以把某个 failure type 分发给对应 owner。
4. 可以找到代表性样本，而不是随机挑样本。

我的理解是：Topics 是 human review 前的 routing / clustering 层。

## `expected` 是什么

`expected` 是这篇最重要的概念。

它表示人类专家认为模型应该输出什么。

它可以是：

- 完整目标回答。
- 某个结构化返回值。
- 某个 JSON object。
- 某个分类标签。
- 某个工具调用期望结果。

核心是：`expected` 必须是 clean target output。

它不是：

- 背景材料。
- source context。
- reviewer 的理由。
- long rationale。
- 审阅过程备注。
- 所有可能相关信息的大杂烩。

这些 supporting details 应该放在 metadata、reference fields 或 notes 里。

## 为什么 `expected` 要干净

如果把 rationale、source material、context 都塞进 `expected`，会带来几个问题：

1. Scorer 不知道到底要比较什么。
2. 不同 reviewer 写出来的 expected 很难比较。
3. 评分噪声会增大。
4. 正确答案和解释材料混在一起，后续无法稳定回归。
5. LLM judge 可能被多余内容干扰。

所以 `expected` 的边界应该非常清楚：

| 字段 | 应该放什么 |
| --- | --- |
| `expected` | 模型应该输出的目标答案或目标值 |
| metadata | 业务场景、trace 来源、用户类型、版本 |
| reference | 支撑 expected 的资料、文档、source context |
| notes | reviewer 的解释、疑问、标注理由 |

## 写 `expected` 的具体要求

文章给出的要求可以整理为：

| 要求 | 含义 |
| --- | --- |
| 包含完整目标答案或具体返回值 | 不要只写“应该更好” |
| 对齐生产格式 | tone、schema、citation、安全行为都要符合真实产品 |
| 尽量 deterministic | 明确 JSON keys 比“helpful answer”更容易评分 |
| 单样本测单行为 | 如果一个 trace 同时测多个能力点，最好拆成多条 row |
| 不猜测 | 不确定时找 SME 或缩小任务，而不是硬填 |

这里最关键的是 deterministic target。

例如：

| 不适合的 expected | 更适合的 expected |
| --- | --- |
| 回答要 helpful | 返回包含 `answer`、`citations`、`confidence` 的 JSON |
| 不要幻觉 | 所有事实 claim 必须被 retrieved context 支持 |
| 语气要好 | 使用正式语气，不使用道歉模板，包含下一步操作 |

## Multiple Correct Outputs 怎么办

如果某个任务有多个正确答案，不能简单地把其中一个答案当作唯一 gold answer。

文章建议有两种处理方式：

1. 缩小任务定义，让 expected 更具体。
2. 用 rubric-based judge 或 scorer 编码可接受变体。

例如开放式客服回答可能有很多正确表达。

这时可以把 expected 写成关键条件：

- 必须说明 refund policy。
- 必须给出下一步操作。
- 不得承诺不符合政策的退款。
- 必须引用订单状态。

然后用 rubric judge 检查这些条件，而不是 exact match。

## Human Review Workflow

文章给出的人工审阅流程可以拆成四步：

1. 选择 bad / interesting trace。
2. Copy / promote 到目标 dataset。
3. Reviewer 填写 `expected`。
4. 后续 eval against expected。

bad / interesting trace 通常包括：

- 明显失败。
- 边界案例。
- 高频失败模式。
- Topics cluster 中的代表样本。
- 新版本上线后出现的新问题。

这一步的关键是：不要把所有线上样本都放进 golden dataset。

Golden dataset 应该是高价值、可复用、可解释、可回归的样本集合。

## Review Rubric 设计

Braintrust 建议先在 project level 定义 review scores。

常见字段类型包括：

| 字段类型 | 用途 | 例子 |
| --- | --- | --- |
| Pass/fail | 快速、清晰的判断 | `is_correct`, `needs_fix` |
| Categorical | 固定 failure taxonomy | `hallucination`, `retrieval_miss`, `tool_misuse`, `policy`, `formatting` |
| Slider | 主观连续维度 | `helpfulness`, `tone`, `groundedness` |
| Freeform text | 解释、备注、rationale | `notes` |

文章建议 rubric 一开始要短。

原因是：

- 字段越多，reviewer 越慢。
- 字段越多，一致性越差。
- 很多字段早期未必能映射到动作。
- 长 rubric 容易让 reviewer 填表，而不是做判断。

更好的做法是：

1. 先定义少量高价值字段。
2. 每个字段写清楚 good / bad example。
3. 每个字段都能映射到 action。
4. 等 reviewer 稳定后再扩充。

## 字段必须映射到动作

文章里一个很实用的要求是：review field 应该能驱动 action。

例如：

| 字段 | 后续动作 |
| --- | --- |
| `needs_fix = true` | 进入 triage / owner 分配 |
| `failure_type = retrieval_miss` | 交给 retrieval / indexing owner |
| `failure_type = tool_misuse` | 交给 agent tool-use owner |
| `is_correct = false` | 加入 regression dataset |
| `groundedness < 3` | 进入 RAG faithfulness investigation |

如果一个字段填了之后没有任何人使用，它就会增加审阅成本而不增加 eval 价值。

## 三类 Review Queue

文章提出了三类队列。

### Triage Queue

目标是快速判断：

- ignore。
- needs review。
- duplicate。

它不是深度标注队列，而是过滤器。

当 Topics 已经自动聚类后，triage queue 往往是在确认或修正 Topics 标签。

### SME Queue

SME queue 是真正补 ground truth 的地方。

领域专家要填写：

- `expected`。
- `is_correct`。
- `failure_type`。
- 必要 notes。

这里质量要求最高。

如果 SME 无法根据现有资料确定 expected，就不应该硬填。

### Calibration Queue

Calibration queue 是为了让多个 reviewer 周期性审同一批样本。

它要回答：

- Reviewer 之间是否一致？
- Rubric 是否清楚？
- 某些字段是否容易产生分歧？
- 是否需要调整 field definition？

这和 Galtea 文章强调的 human inter-rater agreement 是同一个逻辑。

如果人类之间都无法一致，自动 judge 更不可能稳定可靠。

## Promote to Golden Dataset

Reviewed traces 不会自动等于 golden dataset。

需要从已审阅样本中筛选值得长期保留的样本，再 promote。

筛选条件可以包括：

- human review score。
- Topics label。
- failure type。
- 是否代表高频问题。
- 是否代表严重失败。
- 是否覆盖关键业务场景。
- 是否能形成清楚 expected。

Promote 后，这些样本可以进入：

- golden dataset。
- regression suite。
- CI eval。
- experiment comparison。
- deployment gate。

我的理解是：review 是标注过程，promote 是数据集治理过程。

## Golden Dataset 不是静态资产

文章特别强调 golden dataset 要持续更新。

维护动作包括：

- 持续加入新的 reviewed failures。
- 定期删除重复样本。
- 清理 stale cases。
- 重新检查过时 expected。
- 把高频人工判断模式转成 automated scorers。

这点很重要。

很多团队的问题是：早期做了一个 gold set，后续产品变了、数据分布变了、policy 变了，但 gold set 没变。

这种 stale golden dataset 反而会给团队错误安全感。

## Scorer 如何从 Human Review 中变强

有了 reviewed dataset 后，可以构建自动 scorer。

| 问题类型 | Scorer |
| --- | --- |
| JSON schema 是否正确 | schema validation |
| 是否包含固定字段 | exact match / regex |
| 两个结构化对象差异 | diff |
| citation 是否符合格式 | regex / parser |
| answer 是否 grounded | LLM-as-a-Judge |
| tone 是否合适 | LLM-as-a-Judge |
| task completion 是否达成 | rubric judge |

文章的核心思想是：human review 先提供 ground truth，scorer 再学习或对齐这个 ground truth。

长期看，human review 会从主要评估机制，转变成 automated eval 的高质量校准信号。

## Judge-Human Alignment

如果使用 LLM-as-a-Judge scorer，就必须持续跟踪 judge 与 human review 的一致性。

需要关注：

- judge 是否仍然匹配 human labels。
- prompt 或 threshold 是否需要调整。
- 产品数据分布变化后 judge 是否漂移。
- 某些 failure class 是否被 judge 漏掉。

这和 Galtea、Arize 的观点一致：

LLM judge 不是 ground truth，它需要被 human-labelled data 校准。

## Custom Trace Views

文章还提到 Braintrust 支持 custom trace views。

这类 view 是面向 reviewer 的专门界面，把 raw traces 重新组织成更适合审阅的形式。

Reviewer 不一定适合直接看：

- nested spans。
- raw JSON。
- tool call logs。
- retrieval payloads。

Custom trace view 可以只展示和 reviewer 相关的：

- inputs。
- outputs。
- tool calls。
- retrieved context。
- business metadata。
- annotation fields。

它的价值是降低审阅认知负担，让不同 persona 看到不同上下文。

例如：

| Reviewer | 应看到的内容 |
| --- | --- |
| RAG SME | question、answer、retrieved chunks、citations |
| Policy reviewer | user request、model response、policy labels |
| Tool-use owner | tool calls、arguments、tool responses、failure logs |
| Product owner | user task、final answer、business outcome |

## 反模式 1：Dataset 里没有 `expected`

这是文章强调的最大反模式。

如果只是把 trace copy 到 dataset，但不填 `expected`，那它只是一个收藏样本。

它不能稳定回答：

- 模型应该输出什么？
- 新版本是否变好了？
- scorer 应该如何判断？
- CI 是否应该 block？

所以没有 `expected` 的 trace 不能算可靠 regression test。

## 反模式 2：把 Context 塞进 `expected`

另一个常见错误是把 reference material、context、rationale 都写进 expected。

这会导致：

- expected 变得冗长。
- reviewer 输出不可比。
- scorer 不知道目标输出边界。
- 正确答案和解释材料混淆。

正确做法是：

| 内容 | 放置位置 |
| --- | --- |
| 模型目标输出 | expected |
| 支撑证据 | reference fields |
| 业务上下文 | metadata |
| reviewer 解释 | notes |

## 反模式 3：拖延 Workflow 设计

文章还警告不要等到“以后再设计 review workflow”。

如果没有提前定义：

- rubric。
- owner。
- review cadence。
- queue routing。
- promote criteria。

团队会积累很多有趣 traces，但它们不会自动变成 eval dataset。

这类数据会变成观察素材，而不是可执行测试资产。

## 和 Synthetic Data 文章的关系

前面看过几篇 synthetic data / RAG evaluation 文章，它们通常关心：

- 怎么从 documents/chunks 生成 questions。
- 怎么生成 ground truth answer。
- 怎么用 critic/filter 检查 QA pair。
- 怎么扩展 coverage。

Braintrust 这篇关心的是另一条路线：

- 从真实生产 trace 出发。
- 用 Topics 找 pattern。
- 用 SME 补 expected。
- 用 reviewed examples 做 regression。
- 用 human labels 校准 scorer。

两条路线可以互补：

| 路线 | 适合阶段 |
| --- | --- |
| Synthetic QA | 冷启动、覆盖更多文档、快速构造初始 eval |
| Human-reviewed traces | 生产后、捕获真实 failure、维护 regression set |

我的理解是：初期可以用 synthetic data 起步，但长期必须让 production failures 回流。

## 和 Galtea 的关系

Galtea 强调：

- rubric 要 claim-level。
- judge 要和 labelled gold set 对齐。
- gold set 要覆盖 failure classes。
- 不能只看 accuracy。

Braintrust 补充的是：

- labelled gold set 可以来自 production traces。
- human review queue 负责生成 expected。
- calibration queue 负责保持 reviewer 一致性。
- reviewed traces 可以不断 promote 到 golden dataset。

也就是说：

Galtea 讲 gold set 应该满足什么标准。

Braintrust 讲 gold set 怎么运营出来。

## 和 Arize 的关系

Arize 强调 evaluator 要接入 trace context、production monitoring 和 human calibration。

Braintrust 更具体地讲：

- trace 如何被选中。
- 如何被 reviewer 审阅。
- 如何填 expected。
- 如何进入 dataset。
- 如何变成 scorer alignment signal。

两篇合起来就是 production evaluator 的闭环。

## 我应该如何记这篇

这篇最重要的记忆点是：

Golden dataset 不是一个文件，而是一个工作流。

这个工作流包括：

1. 从真实 production traces 捕获失败。
2. 自动聚类和路由。
3. 人类专家填写 clean expected。
4. 把高价值样本 promote 到 dataset。
5. 用 dataset 跑 eval 和 CI。
6. 用 human labels 校准 automated scorers。
7. 持续加入新 failure，清理旧样本。

如果只有 trace，没有 expected，不算 golden dataset。

如果只有 expected，没有 review workflow，dataset 会很快变旧。

## 关键记忆点

- `expected` 是 clean target output，不是证据包。
- Supporting context 应放 metadata / reference，不应塞进 expected。
- Bad / interesting production traces 是 golden dataset 的重要来源。
- Topics 是 review 前的聚类和路由层。
- Triage queue 负责快速过滤。
- SME queue 负责产生 ground truth。
- Calibration queue 负责保持 reviewer 一致。
- Golden dataset 要持续维护，不是一次性资产。
- Objective checks 用 heuristic scorers。
- Subjective checks 可用 LLM judge，但必须和 human review 对齐。
- 最大坑是 dataset row 没有 `expected`。
