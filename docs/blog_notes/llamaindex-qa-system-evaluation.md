# LlamaIndex QA System Evaluation 详细笔记

## 核心定位

这篇 LlamaIndex 早期技术博客讲的是如何构建并评估一个 QA / RAG 系统。它不是论文，也不是新的 benchmark，而是 LlamaIndex 在 2023 年提供的一套 label-free evaluation 教程。

它要解决的问题是：在没有人工标注 query-answer pairs 的情况下，开发者如何快速检查自己的文档问答系统是否大体可靠。

文章给出的流程是：

```text
1. Question Generation from document
2. QueryEngine generates answer and source nodes
3. LLM evaluator checks whether query, answer, and source nodes are aligned
```

这里的关键词是 label-free。它不要求人工先写标准答案，而是让 LLM 同时承担 question generator 和 evaluator。

## 公开资料和版本注意

这篇文章发表于 2023 年 5 月。对应代码处在 LlamaIndex 早期版本，文章里出现的 API 包括：

- `DatasetGenerator`
- `GPTVectorStoreIndex`
- `ResponseEvaluator`
- `QueryResponseEvaluator`
- `ServiceContext`

这些接口名和当前新版 LlamaIndex 已经不完全一致。当前 LlamaIndex evaluation 模块已经拆成更清楚的 evaluator，例如 Faithfulness、Relevancy、Correctness、Semantic Similarity、Guideline Adherence 等。

因此这篇不应该当作当前 API 使用教程，而应该当作早期 RAG evaluation 思路来看。

## 1. Question Generation

第一步是从文档中生成 synthetic questions。

文章中使用 `DatasetGenerator.from_documents(documents)`，然后调用 question generation 方法，从文档节点中生成一批问题。

这一步的目的不是生成 reference answer，而是生成输入 query。它解决的是 RAG evaluation 的第一个现实难点：没有足够多覆盖自己文档的问题。

和后来的 Red Hat / AWS 流程相比，这一步比较轻量：

- 它没有显式 topic extraction。
- 没有 question evolution。
- 没有 groundedness filtering。
- 没有 source sentence extraction。

它只是先生成一批可用于 query engine 的 questions。

## 2. QueryEngine Answering

第二步是建立 index，然后用 QueryEngine 回答这些 synthetic questions。

QueryEngine 输出的 `response` 对象里包含两个关键部分：

```text
response text
source_nodes
```

`response text` 是 RAG 系统生成的答案。`source_nodes` 是检索出来并用于回答的文档片段。

这一步非常关键，因为 LlamaIndex 的 evaluator 不是只看答案文本，而是把答案和 `source_nodes` 放在一起检查。

## 三类评估总览

文章把 evaluation 拆成三类：

第一类是 Response + Source Nodes。

- 旧版接口：`ResponseEvaluator.evaluate(response)`
- 输入：`response` + all source nodes
- 输出：单个 `YES/NO`
- 核心问题：答案是否被检索上下文支持

第二类是 Query + Response + Source Nodes。

- 旧版接口：`QueryResponseEvaluator.evaluate(query, response)`
- 输入：`query` + `response` + all source nodes
- 输出：单个 `YES/NO`
- 核心问题：答案和上下文是否回答了 query

第三类是 Query + Response + Individual Source Nodes。

- 旧版接口：`QueryResponseEvaluator.evaluate_source_nodes(query, response)`
- 输入：`query` + `response` + one source node each time
- 输出：每个 node 一个 `YES/NO`
- 核心问题：哪些 source nodes 真正支撑答案

这三类都是 prompt-driven LLM judge。它们不是 embedding 相似度，不是规则匹配，也不是人工标注评分。

## 3.1 Response + Source Nodes

这一类评估回答的问题是：

```text
response 是否被 source nodes 支持？
```

它不看原始 query。也就是说，只要 response 里的信息能在 retrieved source nodes 中找到支持，就会倾向判为 `YES`。

这适合做早期 hallucination / faithfulness check。比如：

```text
Query: 纽约美国革命期间发生了哪些战役？
Response: Battle of Long Island took place in New York City.
Source nodes: 包含 American Revolution 和 New York 相关段落。
```

Evaluator 会检查 response 这句话是否被 source nodes 支持。如果 source nodes 里完全没有这条信息，结果应该是 `NO`。

这一类评估的好处是简单，能发现答案脱离检索上下文的问题。

局限是它不看 query。一个 response 可能完全忠实于 source nodes，但并没有回答用户真正问的问题。这就是第二类评估存在的原因。

## 3.2 Query + Response + Source Nodes

这一类评估回答的问题是：

```text
query + response 是否和 source context 对齐？
```

它把 query 和 response 组合成一个待验证对象，再让 LLM judge 判断这组 query-response 是否被 context 支持。

它比第一类更完整，因为它同时检查两个关系：

- response 是否 grounded in source nodes。
- response 是否 answer the query。

举个典型失败情况：

```text
Query: What airports are in New York City?
Response: The Battle of Long Island was an American Revolutionary War battle.
Source nodes: 确实包含 Battle of Long Island 的信息。
```

第一类评估可能会说 response 被 source nodes 支持，因为它没有看 query。第二类评估会看到 query 问的是 airports，因此应该判为 `NO`。

所以第二类更接近后来的 response relevancy + faithfulness 混合判断。

## 3.3 Query + Response + Individual Source Nodes

第三类评估回答的问题是：

```text
每一个 source node 是否支撑当前 query-response？
```

这不是对整组 retrieved context 做一个总判断，而是逐个 source node 调 evaluator。

它的用途主要有两个：

第一，做 evidence attribution。RAG 系统可能检索了 3 个 source nodes，但真正支撑答案的只有其中 1 个。逐 node 判断可以知道应该引用哪一段。

第二，做 retrieval diagnostics。如果很多 retrieved nodes 都被判为 `NO`，说明 top-k 检索结果里混入了很多无关上下文。即使最终答案正确，检索模块也可能需要优化。

需要注意一个小细节：博客里的代码片段对第三类调用写得比较简略；根据 LlamaIndex v0.6.0 源码，`QueryResponseEvaluator.evaluate_source_nodes` 实际需要 `query` 和 `response` 两个输入。

## prompt 是否公开

是的，旧版源码里公开了默认 prompt 模板。

主要有四个：

```text
DEFAULT_EVAL_PROMPT
DEFAULT_REFINE_PROMPT
QUERY_RESPONSE_EVAL_PROMPT
QUERY_RESPONSE_REFINE_PROMPT
```

为了避免把源码 prompt 当作长文本复制，这里只总结它们的结构。

### ResponseEvaluator 的 prompt 结构

ResponseEvaluator 会把 RAG 生成的 answer 当成一段待验证 information，然后把 source nodes 当成 context。prompt 让 LLM 判断：

```text
这段 information 是否被 context 支持？
只能输出 YES 或 NO。
```

源码里的默认 prompt 还给了 apple pie 的正反例，教模型什么情况下输出 `YES`，什么情况下输出 `NO`。

这说明它不是让 LLM 做开放解释，而是做二元 entailment-style 判断：

```text
information = response
context = source nodes
judge(information, context) -> YES / NO
```

### QueryResponseEvaluator 的 prompt 结构

QueryResponseEvaluator 会把 query 和 response 拼成一个对象：

```text
Question: {query}
Response: {answer}
```

然后把 source nodes 作为 context，让 LLM 判断：

```text
这个 query-response 是否和 context information 一致？
只能输出 YES 或 NO。
```

这比 ResponseEvaluator 多了 query，因此能判断 answer 是否真的回答了用户问题。

### Refine prompt 怎么用

当 source nodes 不止一个时，旧版 evaluator 会把这些 nodes 建成一个 ListIndex，再用 QA/refine 机制逐步判断。

Refine prompt 的逻辑是：

```text
已有一个 YES/NO 判断。
现在给你更多 context。
如果已有判断已经是 YES，继续 YES。
如果新 context 支持该信息，也输出 YES。
否则输出 NO。
```

这意味着它的聚合逻辑偏向 existence check：只要任意 source node 支持信息，就可以变成 `YES`。

这对 faithfulness check 是合理的，因为答案只要能从某个证据节点得到支持，就可以认为不是凭空编造。但对 retrieval quality 评估来说，它不够细，因为它不会惩罚大量无关 source nodes。因此第三类 per-source evaluation 很重要。

## 和 AWS 那篇的区别

AWS Bedrock 那篇也有 critique agents，但公开 groundedness prompt 只输入 `context + question`，没有输入 generated answer。因此 AWS 那里的 groundedness 更像：

```text
question 是否能由 context 回答？
```

LlamaIndex 这篇不同。它的 evaluator 明确把 `response` 放入 prompt，所以更接近 answer-level evaluation：

```text
response 是否被 source nodes 支持？
query + response 是否被 source nodes 支持？
```

因此可以说：AWS 那篇更像 synthetic question quality filtering；LlamaIndex 这篇更像早期 RAG answer evaluation。

## 和 RAGAs / ARES 的关系

这篇可以看作 RAG evaluation 工具化的早期形态。

和 RAGAs 相比：

- LlamaIndex 这篇主要是 YES/NO judge。
- RAGAs 后来把 faithfulness、answer relevancy、context relevancy 等指标拆得更细。
- RAGAs 更像独立评估框架，而这篇更像 LlamaIndex 内部开发调试工具。

和 ARES 相比：

- LlamaIndex 这篇直接用 prompt-based judge。
- ARES 会生成 synthetic training data 微调 lightweight judges，并用少量人工标注做 Prediction-Powered Inference 校准。
- ARES 更适合正式系统级评估，LlamaIndex 这篇更适合快速 sanity check。

## 局限

第一，它没有人工 reference answer。好处是启动成本低，坏处是 judge 的可靠性没有锚点。

第二，它主要输出 `YES/NO`，没有细粒度分数。很多中间状态会被压成二元结果。

第三，它依赖 LLM judge。生成问题、生成答案和评估答案都可能由相近模型完成，存在 shared bias。

第四，ResponseEvaluator 不看 query，因此只能检查答案是否被上下文支持，不能保证答案回答了问题。

第五，它不直接评估 retrieval recall。即使某个 retrieved source node 支持答案，也不能说明系统找回了所有必要证据。

## 我应该如何记这篇

这篇的核心价值是把 RAG/QA 评估拆成三个对象：

```text
query
response
source nodes
```

不同评估方式就是看这三者之间的不同关系：

```text
response <-> source nodes
query + response <-> source nodes
query + response <-> each source node
```

这套拆分到今天仍然有用。后来的 faithfulness、answer relevancy、context relevancy、citation accuracy、source attribution，本质上都是沿着这三个对象继续细化。

## 关键记忆点

- 这篇是 LlamaIndex 早期 label-free RAG/QA evaluation 教程。
- 它先从文档生成 synthetic questions，再让 QueryEngine 回答并返回 source nodes。
- 三类评估都是 prompt-driven LLM judge，输出主要是 `YES/NO`。
- 第一类只看 response 是否被 source nodes 支持。
- 第二类加入 query，判断答案和上下文是否真正回答问题。
- 第三类逐个检查 source node，用于 evidence attribution 和 retrieval diagnostics。
- 它比 AWS Bedrock 那篇更接近 answer-level evaluation。
- 它比 RAGAs / ARES 更早期、更轻量，但缺少 reference answer、连续分数、人工校准和系统级统计可靠性。
