# AWS Bedrock Synthetic RAG Evaluation 详细笔记

## 核心定位

这篇 AWS Machine Learning Blog 介绍的是一个用 Amazon Bedrock、Anthropic Claude 3 Haiku 和 LangChain 生成 RAG evaluation dataset 的工程流程。它不是 RAG evaluation 理论论文，也不是新的 benchmark，而是一份可运行的 notebook-style pipeline。

它解决的问题是：在 RAG 系统早期还没有真实用户日志和人工标注 QA 时，如何从自己的知识库中合成一批可以用于离线回归测试的问题、参考答案和证据句。

公开资料主要有两个：

- AWS Blog：`Generate synthetic data for evaluating RAG systems using Amazon Bedrock`
- AWS Samples GitHub notebook：`generating-synthetic-datasets-for-evaluating-retrieval-augmented-generation-systems`

和 Databricks 那篇相比，它不是托管黑盒 API，主要 prompt 模板都在博客和 notebook 中展示。和 Red Hat SDG Hub 相比，它不是一个通用 flow 框架，而是更轻量的 Bedrock + LangChain 示例。

## 最终生成什么

它最终生成的不是单纯的 `question + answer`，而更接近：

```text
chunk
question
answer
source sentence
evolved question
groundedness score
relevance score
```

其中：

- `chunk` 是从源文档切出来的上下文。
- `question` 是基于 chunk 生成的初始问题。
- `answer` 是只基于 chunk 生成的参考答案。
- `source sentence` 是从 chunk 中抽取出的证据句。
- `evolved question` 是被压缩、间接化后的用户式问题。
- `groundedness score` 和 `relevance score` 是 critique agents 对合成样本的质量判断。

因此，这个流程的关键不是“生成很多问题”，而是把每个问题绑定到一个可追溯的 source sentence 上，再用 LLM judge 做初步筛选。

## 总体流程

AWS 文章给出的流程是：

```text
1. Load data
2. Chunk data
3. Generate question from chunk
4. Generate answer from question + context
5. Extract source sentence from context
6. Evolve question into user-like style
7. Use critique agents to score/filter generated samples
```

示例数据是 Amazon shareholder letters。目标应用是一个面向金融和商业分析师的股东信问答系统。

## 1. Load data 怎么做

示例用 LangChain 的 `PyPDFDirectoryLoader` 读取 PDF 文档。这里的 PDF 是 Amazon shareholder letters。

这一步本身没有复杂算法。它的重点是让后续 synthetic questions 来自目标 RAG 系统真实会检索的文档集合，而不是来自通用网络知识。

## 2. Chunk data 怎么做

示例用 LangChain 的 `RecursiveCharacterTextSplitter` 切分文档。博客中说明这个 splitter 会尽量在保持语义连续性的前提下把长文本切成固定大小片段。

文章后面给出的性能统计提到，示例中每个 context 大约是 1,500-2,000 tokens。这样做有两个目的：

- chunk 足够长，能够包含可回答问题的上下文。
- chunk 又不能太长，否则生成成本和 prompt 噪声都会上升。

这个点对 RAG evaluation 很重要：如果 synthetic dataset 的 chunking 和线上 RAG 的 chunking 完全不一致，后续评测检索命中率时就会出现口径偏差。

## 3. Question generation 怎么做

question generation 的输入是一个 `context` chunk。

prompt 的核心约束可以概括为：

- 生成一个真实用户可能会问的问题。
- 问题必须可以脱离 context 被理解。
- 问题必须只能用 context 中的信息回答。
- 问题应来自 context 中重要或相关的信息。
- 问题可以基于文本、表格或代码中的信息。
- 答案不应要求输出链接。
- 难度适中。
- 问题少于 10 个词。
- 避免使用 `and`，防止生成复合问题。
- 模型先识别 context 中最重要或最相关的部分，再围绕它出题。
- 最终只输出问题本身。

这里的设计目标是避免两类坏问题：

- 太宽泛的问题：例如“Amazon 的战略是什么？”
- 太机械的抽取题：例如“文中第几句提到了什么？”

但这个 prompt 也有一个明显取舍：少于 10 个词会让问题更像真实搜索 query，却也可能让约束信息丢失，所以后续需要 groundedness / relevance judge 筛选。

## 4. Answer generation 怎么做

answer generation 的输入是：

```text
context
question
```

prompt 要求模型只使用 context 中的信息回答，不要引入外部知识。输出应该精确、简洁，并且只回答当前问题。文章示例中，问题是 2021 年 AWS revenue 的 YoY growth，答案是一句话：AWS revenue 在 2021 年同比增长 37%。

注意这里生成的是参考答案，不是被评测 RAG 系统的输出。后续真正评测 RAG 系统时，会把 question 或 evolved question 输入 RAG pipeline，然后比较系统的检索和回答表现。

## 5. Source sentence extraction 怎么做

source sentence extraction 的输入是：

```text
context
question
answer
```

它要求 LLM 从 context 中抽取能够回答问题的 exact sentence。关键约束是：

- 只能复制 context 里的原句。
- 不要改写。
- 不要解释。
- 每行一个句子。
- 不要输出额外字符。

这一步很关键，因为它把 synthetic QA 从“模型自己说的答案”重新拉回到原文证据上。

如果只有 question 和 answer，评测时很难知道 retrieval 应该命中什么。如果有 source sentence，就可以检查 retriever 是否把包含证据的片段找回来，也可以做更细粒度的 groundedness / citation evaluation。

## 6. Question evolution 怎么做

question evolution 的输入是原始 question。

prompt 要求把问题改写成：

- 更间接。
- 更短。
- 尽可能使用缩写。

文章示例是：

```text
What was the YoY growth of AWS revenue in 2021?
-> AWS rev YoY growth in '21?
```

这一步是为了模拟真实用户表达。真实用户经常不会写完整、规范、长句式问题，而是用缩写、省略、口语化表达。

不过这一步也会带来风险：问题压缩后可能变得含糊。例如上下文里如果同时有 AWS revenue、Consumer revenue、North America revenue，过度缩写的问题可能让答案边界变得不清楚。因此 evolved question 之后仍然需要质量筛选。

## 7. Critique agents 怎么做

AWS 这篇用了两个 critique agents：

```text
groundedness critic
relevance critic
```

它们都是 LLM-as-a-judge，用来给合成样本打 1-5 分，并输出一小段理由。

### Groundedness critic

公开 prompt 的输入是：

```text
context
question
```

它要求 judge 判断：这个 question 能否只用 context 中的信息回答。

评分含义是：

| 分数 | 含义 |
| --- | --- |
| 1 | context 完全不能回答这个问题 |
| 2 | context 只有很少相关信息 |
| 3 | context 能部分回答 |
| 4 | context 能回答大部分方面 |
| 5 | context 包含完整且明确的答案信息 |

这里需要特别注意一个口径问题：AWS 文章正文说两个指标之一是 `answer groundedness`，但展示的 prompt 没有把生成的 `answer` 传进去。也就是说，公开代码实际评估的是：

```text
question 是否 answerable from context
```

而不是：

```text
generated answer 是否 faithful to context
```

如果要真正评 answer faithfulness，judge prompt 至少应该输入：

```text
context
question
generated_answer
```

然后判断 answer 中每个 claim 是否被 context 支持、有没有幻觉、有没有过度推断。AWS 这篇展示的 critique agents 没有完成这一步。

所以在理解这篇时，我应把 groundedness critic 记成 question-level groundedness / answerability filter，而不是完整的答案忠实性评测。

### Relevance critic

relevance critic 的输入只有：

```text
question
```

它要求 judge 假设目标用户是研究 Amazon shareholder letters 的华尔街金融和商业分析师，然后判断这个问题是否有用。

prompt 让 judge 从五个角度考虑：

| 标准 | 含义 |
| --- | --- |
| Relevance | 问题是否和目标工作直接相关 |
| Practicality | 是否对应分析师会遇到的实际问题或用例 |
| Clarity | 问题是否清楚、边界明确 |
| Depth | 是否需要有实质内容的回答，而不是浅层事实 |
| Applicability | 回答是否能用于真实公司评估任务 |

这一步可以过滤掉“虽然能从 context 回答，但业务上没有意义”的问题。

例如，如果某个问题只是问股东信里某个普通词出现了几次，它可能是 grounded 的，但对金融分析师没有价值。relevance critic 就是为了处理这种情况。

## Critique agents 的局限

这套 critique 有三个明显局限：

第一，groundedness 没有真正评 answer。它只能判断 question 是否可由 context 回答，不能保证生成出来的 answer 没有幻觉。

第二，relevance 是强 domain-specific 的。示例 prompt 绑定了 Amazon shareholder letters 和华尔街分析师。如果换成医疗、法律、客服或内部知识库，必须重写目标用户和 relevance 标准。

第三，它仍然依赖同类 LLM 做 judge。生成和筛选都用 LLM，可能出现 shared bias。AWS 的 best practices 里也提醒，生成 synthetic dataset 时最好选择和实际 RAG generation 不同的模型，以减少 self-enhancement bias。

## 和 Red Hat / Databricks 的区别

这三篇都在讲 synthetic evaluation dataset generation，但位置不同。

| 方案 | 透明度 | 形态 | 输出重点 |
| --- | --- | --- | --- |
| Red Hat SDG Hub | 高 | 开源 YAML flow + prompts | `question`, `response`, `ground_truth_context` |
| Databricks | 低到中 | 托管 API | `inputs`, `expected_facts`, `expected_retrieved_context` |
| AWS Bedrock | 高 | Blog + GitHub notebook | `question`, `answer`, `source sentence`, `evolved question`, critique scores |

AWS 这篇的特点是容易改造。它没有要求使用某个完整平台，只要有 Bedrock 调用能力和 LangChain，就可以把 prompt pipeline 改到自己的文档上。

Databricks 的特点是平台集成更强，直接接入 MLflow / Agent Evaluation，但内部流程不透明。

Red Hat SDG Hub 的特点是 flow 更工程化、可复用，且 groundedness filtering 真正输入了 `context + question + answer`，更接近 answer-level groundedness。

## 我应该怎么使用这篇

如果后续我要做自己的 RAG evaluation dataset，可以把 AWS 这篇作为一个最小可实现版本：

```text
1. 用和生产 RAG 一致的 chunking 策略切文档。
2. 对每个 chunk 生成 1-N 个候选问题。
3. 对每个问题生成 reference answer。
4. 从原文抽 source sentence / gold context。
5. 把问题改写成更真实的用户表达。
6. 用 question answerability critic 筛掉不可回答问题。
7. 用 domain relevance critic 筛掉没业务价值的问题。
8. 额外补一个 answer faithfulness critic，检查 generated answer 是否被 context 支持。
```

其中第 8 步是我认为 AWS 示例里缺失但实际生产中很需要的部分。

## 关键记忆点

- 这篇是可运行的 Bedrock + LangChain synthetic RAG eval notebook，不是论文。
- 主要产物是 `question / answer / source sentence / evolved question`。
- source sentence extraction 是关键，因为它把合成问题绑定到原文证据。
- question evolution 用来模拟真实用户的短 query、缩写和间接表达。
- critique agents 主要用于筛 question 的可回答性和业务相关性。
- AWS 文中的 `answer groundedness` 表述需要谨慎理解；公开 prompt 没有输入 answer，因此不是完整 answer faithfulness evaluation。
- 如果要用于严肃 RAG 评测，应补充 answer-level faithfulness judge，或者接入 RAGAs / ARES 等更完整评测框架。

