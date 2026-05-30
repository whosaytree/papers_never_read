# RAGAS v0.1.21 Testset Generation 详细笔记

## 核心定位

这篇是 RAGAS v0.1.21 的官方概念文档，主题是 synthetic test data generation。它不是论文，也不是普通博客，而是 RAGAS 早期 testset generation 机制的说明。

它要解决的问题是：手工为 RAG 系统构造几百条 `question-context-answer` 样本很慢，而且人工问题往往集中在简单问法上，不一定覆盖真实生产场景里的复杂 query。

RAGAS v0.1.21 的方案是 evolutionary generation：

```text
documents
  -> chunks / nodes
  -> keyphrases
  -> seed question
  -> evolved questions
  -> filtering
  -> relevant context selection
  -> ground truth answer
  -> testset
```

这个机制的重点不是只生成更多 QA，而是控制问题类型和难度分布。

## 版本边界

这篇对应的是 v0.1.21。它和后来 RAGAS v0.2+ / v0.4+ 的文档不完全一样。

后续 RAGAS 更强调 Knowledge Graph based testset generation，把文档、实体、关系、scenario 和 sample generation 拆得更清楚。v0.1.21 这篇更适合理解 RAGAS 早期的 evolution 思路。

因此入库时应把它记成：

```text
RAGAS early evolutionary testset generation
```

而不是当前最新版 RAGAS 的全部机制。

## 输入和初始化

RAGAS v0.1.21 支持两类文档输入：

- LangChain documents
- LlamaIndex documents

典型代码是：

```python
from ragas.testset.generator import TestsetGenerator
from ragas.testset.evolutions import simple, reasoning, multi_context
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

generator_llm = ChatOpenAI(model="gpt-3.5-turbo-16k")
critic_llm = ChatOpenAI(model="gpt-4")
embeddings = OpenAIEmbeddings()

generator = TestsetGenerator.from_langchain(
    generator_llm,
    critic_llm,
    embeddings
)
```

这里有两个 LLM 角色。

`generator_llm` 负责生成：

- keyphrases
- seed questions
- evolved questions
- relevant context selection
- ground truth answers

`critic_llm` 负责质量控制：

- NodeFilter
- QuestionFilter
- EvolutionFilter

默认 docstore 会用 `TokenTextSplitter` 切文档，默认 chunk size 是 1024，chunk overlap 是 0。切好的 chunks 会被放入 `InMemoryDocumentStore`，并用 embedding 支持相似 node 查找。

## 输出数据结构

源码中的 `DataRow` 包含：

```text
question
contexts
ground_truth
evolution_type
metadata
```

导出到 pandas 后，就是一批可用于 RAG 评估的样本。

其中：

- `question` 是生成或演化后的问题。
- `contexts` 是可用于回答该问题的上下文片段。
- `ground_truth` 是 RAGAS 基于 relevant context 生成的标准答案。
- `evolution_type` 记录问题来自哪种 evolution。
- `metadata` 保留源文档元信息。

## 问题类型分布

RAGAS 允许用户控制不同问题类型的比例。

文档示例是：

```python
distributions = {
    simple: 0.5,
    multi_context: 0.4,
    reasoning: 0.1
}
```

如果用户不传 distribution，v0.1.21 源码默认是：

```python
DEFAULT_DISTRIBUTION = {
    simple: 0.5,
    reasoning: 0.25,
    multi_context: 0.25
}
```

这点很重要。RAGAS 不只是生成 N 条问题，而是让测试集在“简单问题、多步推理问题、多 context 问题”等类型之间有可控比例。

## Simple evolution

`simple` 是基础问题生成。

流程是：

```text
random node
  -> NodeFilter
  -> keyphrase
  -> seed_question_prompt
  -> QuestionFilter
  -> DataRow
```

它会先随机取一个 node。然后 NodeFilter 判断这个 node 是否适合出题。如果 context 质量不行，就换一个 node。

通过后，RAGAS 会从该 node 的 keyphrases 里选一个 keyphrase，再用 seed question prompt 生成一个问题。

seed question prompt 的核心要求是：

```text
Generate a question that can be fully answered from given context.
The question should be formed using topic.
```

然后 QuestionFilter 判断这个问题是否清楚、独立、可回答。

所以 `simple` 不是无约束问答生成，它已经有 context 质量过滤和 question 质量过滤。

## Reasoning evolution

`reasoning` 不是直接从文档生成难题，而是先调用 simple evolution 得到一个基础问题，然后把它复杂化。

流程是：

```text
simple question
  -> reasoning_question_prompt
  -> QuestionFilter
  -> compress_question_prompt
  -> EvolutionFilter
  -> DataRow
```

reasoning prompt 的目标是把原问题改写成 multi-hop reasoning question。它要求回答问题时需要读者基于 context 做多步逻辑连接或推断。

同时它要求：

- 问题必须完全能由 context 回答。
- 问题不超过 15 个词。
- 问题清晰、不歧义。
- 不允许出现 `based on the provided context` 之类措辞。

生成后还会经过 QuestionFilter。如果不合格，RAGAS 会尝试根据 feedback 和 context 重写问题。

然后会用 compress prompt 把问题改得更短、更间接。最后 EvolutionFilter 判断 evolved question 和原 simple question 是否真的不同。

## Multi-context evolution

`multi_context` 的目标是生成需要多个相关 chunks 才能回答的问题。

流程是：

```text
simple question
  -> get similar node
  -> multi_context_question_prompt(context1, context2)
  -> QuestionFilter
  -> compress_question_prompt
  -> EvolutionFilter
  -> DataRow
```

源码里会先生成一个 simple question，然后基于当前 node 的 embedding 找一个 similar node。接着把 `context1` 和 `context2` 一起放进 prompt，让模型改写问题，使其必须同时依赖两个 context 才能回答。

multi-context prompt 的约束包括：

- 问题不要太长。
- 问题要合理、能被人理解。
- 问题必须完全能由 context1 和 context2 回答。
- 回答需要同时利用两个 contexts。
- 不要出现 `provided context` / `according to the context` 这类措辞。

这类问题对 RAG 很重要，因为很多真实问题不能靠单个 chunk 回答，需要检索器找回多个相关片段，再让生成模型综合。

## Conditional evolution

`conditional` 也是在 simple question 基础上改写。

流程和 reasoning 类似：

```text
simple question
  -> conditional_question_prompt
  -> QuestionFilter
  -> compress_question_prompt
  -> EvolutionFilter
  -> DataRow
```

conditional prompt 的目标是加入一个 condition 或 scenario，让问题变复杂。

它要求：

- 改写后问题不超过 25 个词。
- 问题合理、可理解。
- 问题仍然完全能由 context 回答。
- 不出现 `provided context` 等显式上下文提示。

这类问题测试的是 RAG 系统对条件约束的处理能力。

## Conversational evolution

文档提到 conversational：一部分问题可以在 evolution 后被转成 conversational samples，模拟 chat-based question-and-follow-up interaction。

v0.1.21 源码里也有 `conversational_question_prompt`，它会把一个问题改成两个对话式问题：

```text
first_question
second_question
```

不过官方文档主示例没有重点使用 conversational distribution，因此入库时只把它作为补充能力记录，不作为主线。

## Filtering 总览

RAGAS v0.1.21 的 filtering 主要有三层：

```text
NodeFilter
QuestionFilter
EvolutionFilter
```

它们都由 critic LLM 驱动，但用途不同。

## NodeFilter 细节

NodeFilter 判断一个 context / node 是否适合拿来出题。

它使用的 prompt 是 `context_scoring_prompt`，要求 critic LLM 对 context 按四个维度打 1-3 分：

- `clarity`
- `depth`
- `structure`
- `relevance`

含义如下：

`clarity` 判断信息是否清楚、精确、易理解。

`depth` 判断内容是否有足够深度，是否只是浅层事实。

`structure` 判断内容组织是否清楚、有逻辑。

`relevance` 判断内容是否紧扣主题、是否有太多无关内容。

如果 node 太碎、太浅、太乱，RAGAS 会换一个 node 重新尝试。这个步骤用于避免从低质量 chunk 里生成低质量 question。

## QuestionFilter 细节

QuestionFilter 判断生成出来的问题是否可用。

它使用的 prompt 是 `filter_question_prompt`，核心标准有两个：

第一是 Independence。问题是否可以独立理解，不依赖“上文”“表 1”“这个研究”等外部引用。

第二是 Clear Intent。问题是否明确表达想问什么，答案类型是否清楚。

输出是 JSON：

```json
{
  "feedback": "...",
  "verdict": 1
}
```

`verdict = 1` 表示问题通过。

`verdict = 0` 表示问题不通过。此时 RAGAS 会尝试用 feedback 和 context 重写问题。

重写流程是：

```text
invalid question
  -> feedback
  -> question_rewrite_prompt(context, question, feedback)
  -> new question
  -> QuestionFilter again
```

如果重写后仍然不通过，就换新的 node 重试。

## EvolutionFilter 细节

EvolutionFilter 用在 reasoning、multi_context、conditional 这些复杂 evolution 后。

它输入两条问题：

```text
question1 = original simple question
question2 = evolved / compressed question
```

它判断两者是否本质相同。标准是：

- 是否有相同 constraints / requirements。
- 是否有相同 depth / breadth of inquiry。

输出也是 JSON，包含 reason 和 verdict。

如果两个问题本质一样，说明 evolution 没有成功增加复杂度，RAGAS 会换 node 或重试。

所以 EvolutionFilter 的目的不是判断问题是否可回答，而是判断 evolution 是否有效。

## Answer generation 总览

通过 filtering 后，RAGAS 会生成 `ground_truth`。

源码里的流程是：

```text
question
  + current nodes
  -> find relevant contexts
  -> merge selected contexts
  -> question_answer_prompt
  -> JSON answer + verdict
  -> DataRow
```

这一步包括两个关键子步骤：选择 relevant contexts 和生成 answer。

## Relevant context selection

RAGAS 会把当前 nodes 编号，然后交给 generator LLM。

输入形态类似：

```text
question: ...
contexts:
1. ...
2. ...
3. ...
```

使用的 prompt 是 `find_relevant_context_prompt`，目标是找出最相关、能回答问题的 contexts。

输出是 JSON：

```json
{
  "relevant_contexts": [1, 2]
}
```

如果模型没有返回有效编号，RAGAS 会退回使用当前全部 nodes。

这一步对 multi_context 特别重要，因为当前 nodes 可能不止一个。RAGAS 先让 LLM 选出真正相关的 context，再用这些 context 生成 ground truth。

## Ground truth answer generation

选出 relevant contexts 后，RAGAS 会把这些 contexts 合并成一个 context，然后调用 `question_answer_prompt`。

prompt 的核心要求是：

```text
Answer the question using the information from the given context.
Output verdict as 1 if answer is present, -1 if answer is not present in the context.
```

输出格式是 JSON：

```json
{
  "answer": "...",
  "verdict": 1
}
```

如果 context 里没有答案，输出类似：

```json
{
  "answer": "The answer to given question is not present in context",
  "verdict": -1
}
```

源码里如果 `verdict == -1`，最终 `ground_truth` 会被设成 `NaN`。

所以 answer generation 不是盲目生成 reference answer，而是带有 answer presence verdict。

## 为什么这套机制重要

这套机制比简单“从文档生成 QA”多了几层控制：

- 先过滤 context，避免垃圾 chunk 出题。
- 再过滤 question，避免问题不清楚或依赖外部上下文。
- 对复杂 evolution 做有效性判断，避免改写后问题没有真正变难。
- 生成答案前选择 relevant contexts。
- 答案生成时判断答案是否确实存在于 context。

这解释了为什么 RAGAS v0.1.21 的 testset generation 更像一个小型数据生成 pipeline，而不是单 prompt QA generator。

## 和前几篇的区别

AWS Bedrock 也有 prompt pipeline，但更像：

```text
chunk -> question -> answer -> source sentence -> evolved question -> critique
```

RAGAS 更强调问题类型分布和 evolution strategy。

Red Hat SDG Hub 公开了 YAML flow 和 prompts，输出 `question / response / ground_truth_context`，质量控制重点是 groundedness critic 和 context extraction。

Label Studio 更偏生产任务闭环，评估的是 XML config 的 functional equivalence。

RAGAS v0.1.21 的特色是：把问题难度和检索形态做成可配置 distribution，并把生成过程拆成 seed question、evolution、filter、answer generation。

## 局限

第一，这是旧版机制。新版 RAGAS 已经更强调 Knowledge Graph based generation。

第二，生成和过滤都依赖 LLM，质量受 generator / critic 模型影响。

第三，`ground_truth` 仍然是 LLM 生成答案，不是人工参考答案。

第四，filter 的阈值和行为在文档里没有完全展开，需要结合源码理解。

第五，multi_context 依赖 embedding 找 similar node，但 similar node 不一定真的构成合理的多跳证据链。

## 我应该如何记这篇

这篇的核心是：

```text
RAG 测试集不应该只有普通单跳问题。
应该显式控制问题类型，让测试集覆盖 simple、reasoning、multi_context、conditional 等场景。
```

RAGAS v0.1.21 提供的贡献不是一个新评测指标，而是一个 synthetic testset construction strategy。

## 关键记忆点

- 这是 RAGAS v0.1.21 的早期 synthetic testset generation 文档。
- 核心思想是 evolutionary generation，灵感来自 Evol-Instruct。
- 输出字段是 `question`、`contexts`、`ground_truth`、`evolution_type`、`metadata`。
- `generator_llm` 负责生成，`critic_llm` 负责过滤。
- NodeFilter 评估 context 质量。
- QuestionFilter 评估问题清晰度、独立性和可回答性。
- EvolutionFilter 评估 evolved question 是否真的不同。
- Answer generation 会先找 relevant contexts，再生成带 `verdict` 的 ground truth answer。
- 用户可以显式控制不同 evolution 类型的比例。
- 这套机制要和新版 Knowledge Graph based RAGAS testset generation 区分开。

