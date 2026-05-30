# Databricks Synthetic Agent Evaluation 详细笔记

## 核心定位

Databricks 这篇技术分享介绍的是 Mosaic AI Agent Evaluation 里的 synthetic data generation API。它的目标是从企业文档中快速生成 agent / RAG agent 的 evaluation dataset，并直接接入 MLflow / Databricks Agent Evaluation。

它不是论文，也不是开源生成算法。当前可验证资料主要来自：

- Databricks Blog：`Streamline AI Agent Evaluation with New Synthetic Data Capabilities`
- Databricks Docs：`Synthesize evaluation sets`
- Databricks Agents Python SDK：`databricks.agents.evals.generate_evals_df`

需要特别注意：Databricks 公开的是 API 合同、输入输出 schema、调用示例和少量控制参数；内部 synthetic generation pipeline、内部 prompt、过滤逻辑没有公开。因此这篇不能像 Red Hat SDG Hub 那样逐步复原 topic generation、question evolution、critic filtering 等内部细节。

## 它生成的是 QA 对吗

严格说，不是传统 `question + reference answer` QA 对。

更准确的结构是：

```text
synthetic user input
  + expected_facts
  + expected_retrieved_context
```

在 MLflow 3 输出 schema 中，核心字段是：

```text
request_id
inputs
expectations.expected_facts
expectations.expected_retrieved_context
```

其中：

- `inputs` 是合成出来的用户请求，采用 Chat Completion API messages 格式。
- `expected_facts` 是回答中应该覆盖的事实点列表。
- `expected_retrieved_context` 是生成该 eval 所依据的源文档内容和 `doc_uri`。

所以它更像生成一种事实型 rubric / checklist，而不是完整标准答案。评测时不要求模型逐字匹配 reference answer，而是检查回答是否覆盖 expected facts。

## 为什么说它像 rubric

传统 rubric 通常是多维评分标准，例如：

```text
Accuracy: 1-5
Completeness: 1-5
Clarity: 1-5
Groundedness: 1-5
```

Databricks 的 `expected_facts` 不是这种多维 rubric。它更像事实 checklist：

```text
问题：What is Spark SQL used for in Apache Spark?

expected_facts:
- Spark SQL is used for SQL processing in Apache Spark.
- Spark SQL is used for structured data processing in Apache Spark.
```

如果 agent 回答覆盖了这些事实，Correctness scorer 更容易判断它是正确的。这样比完整 reference answer 更灵活，因为自然语言答案可以有多种表达方式，只要关键事实被覆盖即可。

因此可以把它理解成：

```text
expected_facts = factual rubric / answer checklist
```

但不要把它理解成完整评分表，也不要理解成人工定义的多维评分细则。

## 输入数据

官方文档要求输入是 Pandas DataFrame 或 Spark DataFrame，至少包含两列：

```text
content
doc_uri
```

`content` 是已经解析好的文档正文。它可以来自网页、PDF、产品文档或企业知识库，关键是要以字符串形式进入 DataFrame。

`doc_uri` 是文档来源 URI。它不是只为了展示链接，而是让生成出来的 eval 能追溯到源文档。后续输出的 `expected_retrieved_context` 会包含文档内容和 `doc_uri`，用于判断 agent 是否检索到了正确证据。

示例输入形态：

```python
docs = pd.DataFrame.from_records([
    {
        "content": "Apache Spark is a unified analytics engine for large-scale data processing...",
        "doc_uri": "https://spark.apache.org/docs/3.5.2/"
    },
    {
        "content": "Spark's primary abstraction is a distributed collection of items called a Dataset...",
        "doc_uri": "https://spark.apache.org/docs/3.5.2/quick-start.html"
    }
])
```

## 生成 API

核心调用是：

```python
from databricks.agents.evals import generate_evals_df

evals = generate_evals_df(
    docs,
    num_evals=10,
    agent_description=agent_description,
    question_guidelines=question_guidelines,
)
```

这里公开的可控参数主要有三个。

`num_evals` 控制总生成数量。它不是每个文档生成几条，而是整个文档集合总共生成多少条。Databricks 文档说明，函数会尝试根据文档大小在所有 documents 之间分配 evals，以保持近似的问题覆盖率。如果 `num_evals` 小于文档数，一些文档不会被覆盖。

`agent_description` 是 agent 的任务描述。它告诉生成器这个 agent 是做什么的、应该回答什么范围的问题、什么问题算 irrelevant。

`question_guidelines` 是问题生成指南。官方文档明确说这是 free-form string，会用于 prompt generation。它可以包含用户 persona、示例问题、问题风格和额外要求。

示例：

```python
agent_description = """
The Agent is a RAG chatbot that answers questions about using Spark on Databricks.
Questions outside of this scope are considered irrelevant.
"""

question_guidelines = """
# User personas
- A developer who is new to the Databricks platform
- An experienced, highly technical Data Scientist or Data Engineer

# Example questions
- what API lets me parallelize operations over rows of a delta table?
- Which cluster settings will give me the best performance when using Spark?

# Additional Guidelines
- Questions should be succinct, and human-like
"""
```

这说明 Databricks 给用户开放了 prompt-like 控制入口，但没有开放内部 prompt 模板。

## 有没有公开内部 prompt

没有看到公开内部 prompt。

公开代码里有：

- `generate_evals_df(...)` 调用代码。
- `agent_description` 示例。
- `question_guidelines` 示例。
- 输出 schema 和示例输出。

没有看到：

- 内部如何从文档生成问题。
- 如何从问题生成 expected facts。
- 是否有 critic / filtering。
- 是否有 groundedness check。
- 是否有 question evolution。
- 内部 prompt 模板。

所以和 Red Hat SDG Hub 的区别很大。Red Hat 公开了 `flow.yaml` 和 prompts，可以看到每一步 prompt；Databricks 是托管 API，只能看到输入输出合同。

## 输出结构

MLflow 3 下，`generate_evals_df` 输出：

```text
request_id
inputs
expectations
```

`expectations` 里有两个字段：

```text
expected_facts
expected_retrieved_context
```

MLflow 2 下，输出字段更扁平：

```text
request_id
request
expected_facts
expected_retrieved_context
```

官方示例中，输入文档讲 Spark SQL、pandas API on Spark、MLlib、GraphX、Structured Streaming 等。生成结果包括：

```text
inputs.messages[0].content:
What are some high-level tools supported by Apache Spark, and what purposes do they serve?

expectations.expected_facts:
- Spark SQL for SQL and structured data processing.
- pandas API on Spark for handling pandas workloads.
- MLlib for machine learning.
- GraphX for graph processing.
- Structured Streaming for incremental computation and stream processing.
```

这正好说明 `expected_facts` 的性质：它不是答案段落，而是期望回答覆盖的关键事实。

## num_evals 怎么控制覆盖

`num_evals` 是总 eval 数量。Databricks 文档说明，函数会在文档之间分配这些 evals，并尝试考虑文档大小差异，使每页或每段文档获得近似的问题覆盖。

如果 `num_evals` 小于输入文档数量，一些文档不会生成 eval。返回 DataFrame 中会包含 `source_doc_ids`，可以用它 join 回原始 DataFrame，找出未覆盖的文档，再补生成。

Databricks 还提供：

```python
from databricks.agents.evals import estimate_synthetic_num_evals

num_evals = estimate_synthetic_num_evals(
    docs,
    eval_per_x_tokens=1000
)
```

这个函数用于按 token 覆盖率估算 eval 数量。例如 `eval_per_x_tokens=1000` 表示希望每 1000 tokens 生成 1 条 eval。

## 评测如何接上

生成 eval set 后，可以直接用于 MLflow GenAI evaluation：

```python
import mlflow
from mlflow.genai.scorers import Correctness

predict_fn = mlflow.genai.to_predict_fn(
    "endpoints:/databricks-meta-llama-3-1-405b-instruct"
)

results = mlflow.genai.evaluate(
    predict_fn=predict_fn,
    scorers=[Correctness()],
    data=evals
)
```

这时 `Correctness` scorer 会利用 eval set 中的 expectations 来判断模型回答是否正确。对于 RAG / agent 场景，`expected_facts` 提供事实覆盖要求，`expected_retrieved_context` 提供 gold context 来源。

完整链路可以写成：

```text
documents(content, doc_uri)
  -> generate_evals_df
  -> inputs + expected_facts + expected_retrieved_context
  -> agent/model 生成回答
  -> mlflow.genai.evaluate + Correctness scorer
  -> MLflow UI / Databricks UI 查看结果
```

## 和 Red Hat SDG Hub 的区别

Red Hat SDG Hub 的特点是透明：

```text
document + outline
  -> topic_generation prompt
  -> conceptual_qa_generation prompt
  -> question_evolution prompt
  -> answer_generation prompt
  -> groundedness_critic prompt
  -> context_extraction prompt
```

Databricks 的特点是平台化：

```text
content + doc_uri
  -> generate_evals_df proprietary service
  -> inputs + expected_facts + expected_retrieved_context
  -> MLflow / Agent Evaluation
```

两者的差别：

- Red Hat 适合研究和改造，因为 flow 和 prompts 可见。
- Databricks 适合平台内快速落地，因为 API、MLflow、Agent Evaluation、Databricks workspace 集成度高。
- Red Hat 输出更像 `question / response / ground_truth_context`。
- Databricks 输出更像 `request / expected_facts / expected_retrieved_context`。
- Red Hat 可以看见 groundedness critic。
- Databricks 只能知道有 expected facts，但不知道 facts 如何生成和过滤。

## 和 RAGAs / ARES / RGB 的关系

Databricks 这篇和 RAGAs、ARES、RGB 可以这样放：

- Databricks synthetic eval：从企业文档生成 agent evaluation dataset。
- RAGAs：给定 question、answer、contexts 后，评估 faithfulness、answer relevance、context relevance。
- ARES：用合成数据训练轻量 judge，再用少量人工标注做 PPI 校正。
- RGB：定义 RAG 场景中的能力缺陷，例如抗噪声、拒答、多文档整合和反事实鲁棒性。

Databricks 这篇不是新 metric，而是让用户在 Databricks 平台中快速生成可评测数据，并接入已有 scorers。

## 使用边界

官方文档给出几个边界：

- Synthetic data service 可能使用 third-party services，包括 Azure OpenAI operated by Microsoft。
- 对 Azure OpenAI，Databricks 已 opt out of Abuse Monitoring，因此 prompts 或 responses 不会存储在 Azure OpenAI。
- EU workspace 使用 EU-hosted models，其他区域使用 US-hosted models。
- 关闭 Partner-powered AI features 会阻止 synthetic data service 调用 partner-powered models。
- 发送给 synthetic data service 的数据不会用于模型训练。
- Synthetic data 用于评估 agent applications，不应该用于训练、改进或微调 LLM。

这些边界说明它是 evaluation data generation service，不是训练数据生成服务。

## 对我的启发

这篇最值得记录的是 `expected_facts` 的设计。它介于标准答案和 rubric 之间：

- 比完整 reference answer 更灵活。
- 比单个 correctness label 更可诊断。
- 比多维人工 rubric 更容易从文档自动生成。
- 可以和 LLM judge 结合，判断回答是否覆盖关键事实。

对 RAG / agent evaluation 来说，这是一个很实用的数据结构。尤其当用户问题没有唯一标准表述时，`expected_facts` 可以降低对答案措辞的依赖，把评估焦点放在“关键事实有没有说到”上。

但它的问题也很明显：如果内部生成器抽错 facts、漏掉关键 facts，或者生成过窄的 expected facts，评测就会偏。由于内部 prompt 不公开，用户很难审计这一步。因此生产使用时仍然需要抽样人工检查 synthetic eval set，尤其检查：

- 问题是否符合真实用户意图。
- expected facts 是否完整且忠实于文档。
- expected_retrieved_context 是否确实支持 facts。
- 是否覆盖了重要文档和长尾场景。

## 参考

- [Databricks Blog: Streamline AI Agent Evaluation with New Synthetic Data Capabilities](https://www.databricks.com/blog/streamline-ai-agent-evaluation-with-new-synthetic-data-capabilities)
- [Databricks Docs: Synthesize evaluation sets](https://docs.databricks.com/aws/en/generative-ai/agent-evaluation/synthesize-evaluation-set)
- [Databricks Agents Python SDK: Agent Evaluation](https://api-docs.databricks.com/python/databricks-agents/latest/databricks_agent_eval.html)
