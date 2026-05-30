# SDG Hub RAG Evaluation Dataset Flow 详细笔记

## 核心定位

这篇 Red Hat Developer 博客对应的是 SDG Hub 里的一个开源 flow：`RAG Evaluation Dataset Flow`。它不是一篇 RAG evaluation 理论论文，也不是完整 benchmark，而是一个可运行的 synthetic evaluation dataset 生成流程。

它的目标是把知识库中的文档片段转成 RAG 评测样本。每条样本最终包含：

- `question`：由源文档合成的问题。
- `response`：只基于源文档生成的参考答案。
- `ground_truth_context`：从源文档中抽取出的标准证据句子。

这个流程适合做 RAG 的离线 regression test：固定一批 synthetic questions 后，比较不同 embedding、chunking、retriever、reranker、prompt 或 LLM backend 的效果。它的关键点不是“synthetic data 很多”，而是每个问题都绑定一个 gold context，因此可以单独检查 retrieval 是否命中证据。

## 开源位置

代码和配置都在 Red Hat AI Innovation Team 的 SDG Hub 仓库中：

- 项目仓库：https://github.com/Red-Hat-AI-Innovation-Team/sdg_hub
- flow 配置：`src/sdg_hub/flows/evaluation/rag_evaluation/flow.yaml`
- prompt 目录：`src/sdg_hub/flows/evaluation/rag_evaluation/prompts/`
- 示例 notebook：`examples/rag_evaluation/rag_evaluation_dataset_generation.ipynb`

SDG Hub 本身是 Apache-2.0 开源项目。公开资料主要是 Red Hat Developer 博客、SDG Hub 文档、OpenShift AI 文档和 GitHub 源码；我没有看到专门介绍这个 RAG evaluation flow 的独立论文。

## 输入输出

flow 要求输入数据集中至少有两列：

```text
document
document_outline
```

`document` 是知识库中的原子知识单元，可以是 document、section 或 chunk。博客特别强调它最好和生产 RAG 的 chunking 策略一致，因为后续生成的 `ground_truth_context` 会以它作为 gold reference。

`document_outline` 是这个 document 的短标题或摘要，用来引导问题生成。它的作用不是提供答案，而是帮助模型避免生成太机械、太抽取式的问题。

输出侧，flow 最后通过 `RenameColumnsBlock` 生成：

```text
question
response
ground_truth_context
```

注意：博客里说的是 question-answer-context triplets，但当前公开 flow 的最终答案列名是 `response`，不是 `answer`。

## Flow 总体结构

公开的 `flow.yaml` 串联了这些 block：

```text
document
  -> duplicate_to_context
  -> topic_prompt -> gen_topic -> parse_topic -> rename_topic
  -> conceptual_prompt -> gen_conceptual_question -> parse_question
  -> evolution_prompt -> evolve_question -> parse_evolved_question
  -> answer_prompt -> gen_answer -> parse_answer
  -> critic_prompt -> gen_critic_score -> parse_critic_score
  -> filter_ungrounded
  -> extraction_prompt -> extract_context -> parse_extracted_context
  -> rename_final_columns
```

它不是一个复杂算法栈，而是 SDG Hub 风格的 YAML-defined LLM pipeline。每一步基本都是：

- `PromptBuilderBlock`：把当前列拼进 prompt。
- `LLMChatBlock`：调用 LLM 生成结果。
- `LLMResponseExtractorBlock`：抽取文本内容。
- 必要时用 `RenameColumnsBlock` 或 `ColumnValueFilterBlock` 整理列和过滤样本。

默认推荐模型是 `openai/gpt-oss-120b`，兼容模型包括 `meta-llama/Llama-3.3-70B-Instruct` 和 `microsoft/phi-4`。LLM block 多数使用 async mode。

## 1. Topic extraction 怎么做

对应配置：

```text
topic_prompt -> gen_topic -> parse_topic -> rename_topic
```

输入列只有：

```text
document
```

对应 prompt 文件是 `prompts/topic_generation.yaml`。它让模型从文档中识别一个 specific topic，并要求只输出 topic，不要加解释。

这一步没有使用 embedding clustering、BERTopic 或关键词统计。它是一个单样本 LLM 抽题锚点的步骤：

```text
document -> LLM -> topic
```

生成参数大致是：

```yaml
max_tokens: 2048
temperature: 0.7
n: 1
```

所以这一步的作用很具体：为后面的 question generation 提供一个 focus topic。它不保证覆盖文档的全部主题，每条 document 默认只生成一个 topic。

## 2. Question generation 怎么做

对应配置：

```text
conceptual_prompt -> gen_conceptual_question -> parse_question
```

输入列是：

```text
document
document_outline
topic
```

对应 prompt 文件是 `prompts/conceptual_qa_generation.yaml`。它把目标问题定义为 reasoning question，要求满足：

- 是自然语言问题。
- 需要读者基于提供的信息进行推理、推断或得出结论。
- 聚焦给定 topic。
- 只能使用提供的 text content 回答。

也就是说，这一步不是随机生成 FAQ，而是用 `document_outline` 提供内容摘要，用 `topic` 指定关注点，用 `document` 限制可回答范围。

生成参数同样是：

```yaml
max_tokens: 2048
temperature: 0.7
n: 1
```

这里的关键约束是 `can be answered using ONLY the provided text`。它避免生成需要外部知识的问题，但这个约束本身仍然依赖 LLM 遵守，后面还需要 groundedness critic 过滤。

## 3. Question evolution 怎么做

对应配置：

```text
evolution_prompt -> evolve_question -> parse_evolved_question
```

输入列是上一步得到的：

```text
question_content
```

对应 prompt 文件是 `prompts/question_evolution.yaml`。这一步的公开实现比博客里的 “refines these into realistic, user-style queries” 更窄：它要求把问题改写成更 indirect、更 compressed、更 short 的形式，可以使用 abbreviation，但必须保留核心含义并仍然可回答。

所以它不是复杂的多轮演化，也不是生成不同 persona、难度等级或问题类型。它主要做三件事：

- 间接化：减少直白抽取感。
- 压缩：让问题更短。
- 保义：不改变原问题可回答范围。

生成参数是：

```yaml
max_tokens: 4096
temperature: 0.7
n: 1
```

这一步需要特别注意：压缩和间接化可能让问题变得更像真实用户输入，但也可能损失约束信息。如果 evolved question 过度省略，后续 answer 或 retrieval evaluation 可能变得模糊。

## 4. Answer generation 怎么做

虽然你主要问 1、2、3、5，但第 5 步依赖第 4 步生成的 answer，所以这里也要补上。

对应配置：

```text
answer_prompt -> gen_answer -> parse_answer
```

输入列是：

```text
context
evolved_content as question
```

`context` 来自最开始的 `document` 复制。对应 prompt 文件是 `prompts/answer_generation.yaml`。它要求模型作为 extractive QA system，只使用 context 中明确陈述的信息，不做推断、假设或外部知识扩展。

生成参数比问题生成更保守：

```yaml
max_tokens: 4096
temperature: 0.2
n: 1
```

这一步生成的是参考答案，不是 RAG 系统的输出。真正评测时，会把 `question` 输入实际 RAG pipeline，让系统自己检索和生成，再和 gold context / reference response 做指标比较。

## 5. Groundedness filtering 怎么做

对应配置：

```text
critic_prompt -> gen_critic_score -> parse_critic_score -> filter_ungrounded
```

输入列是：

```text
context
question
answer
```

对应 prompt 文件是 `prompts/groundedness_critic.yaml`。它让 LLM 作为 strict evaluator，评价 answer 被 context 支持的程度，输出 1 到 5 的整数。

评分标准是：

- 1：完全不支持，或和 context 矛盾。
- 2：严重依赖外部知识或弱推断。
- 3：部分支持，但包含 unsupported details。
- 4：基本支持，只包含轻微推断。
- 5：完全且明确被 context 支持。

生成参数是：

```yaml
max_tokens: 512
temperature: 0.0
n: 1
```

随后 `ColumnValueFilterBlock` 只保留：

```yaml
filter_value: [4, 5]
operation: eq
convert_dtype: int
```

所以真实过滤逻辑很直接：critic 输出能转成整数，并且分数等于 4 或 5，样本才留下。1、2、3 分都会被丢弃。

这一步是整个 flow 的质量门禁。前面的 question generation 和 answer generation 都是 LLM 生成，可能出现外部知识、过度推断或问题不可回答；groundedness filtering 用一个独立 critic prompt 把明显不 grounded 的样本筛掉。

## 6. Context extraction 怎么做

对应配置：

```text
extraction_prompt -> extract_context -> parse_extracted_context
```

输入列是：

```text
context
question
answer
```

对应 prompt 文件是 `prompts/context_extraction.yaml`。它要求模型从 context 中抽取 exact sentences：

- 只抽取包含答案所用信息的句子。
- 不修改句子。
- 多个句子逐行输出。
- 如果没有直接支持句子，输出 `No relevant sentences found.`

这一步的输出会被重命名为：

```text
ground_truth_context
```

因此，最终的 gold context 不是任意摘要，而是从原始 context 中复制出来的证据句。这个设计很重要，因为 RAG retrieval evaluation 可以检查系统检索出的 chunks 是否包含这些标准证据。

## 和 RAGAs / ARES / RGB 的关系

这篇 blog 和 RAGAs、ARES、RGB 的关系可以这样理解：

- SDG Hub RAG Evaluation Flow：解决 evaluation dataset 怎么从自己的知识库生成。
- RAGAs：解决已有 question、answer、context 后，如何用 LLM-as-a-judge 计算 faithfulness、answer relevance、context relevance 等指标。
- ARES：用 synthetic data 训练 lightweight judges，再用少量人工标注做 PPI 校正，适合更正式的系统评估。
- RGB：定义 RAG 场景下模型要具备哪些能力，例如抗噪声、拒答、多文档整合和反事实鲁棒性。

所以 SDG Hub 这篇更偏“测试集生成器”，不是 metric framework。它可以和 RAGAs 拼成一个完整链路：

```text
knowledge base
  -> SDG Hub 生成 question / response / ground_truth_context
  -> 真实 RAG pipeline 生成 retrieved_contexts / answer
  -> RAGAs 或其他 evaluator 计算 retrieval 与 generation 指标
```

## 风险与局限

第一，topic extraction 每条 document 只生成一个 topic，覆盖率有限。如果一个 chunk 中有多个可问点，这个 flow 默认不会系统覆盖全部主题。

第二，question evolution 只是压缩和间接化，不能保证问题更真实。真实用户问题可能包含口语、省略、错别字、多跳意图、上下文依赖和业务约束；公开 prompt 只覆盖其中很小一部分。

第三，groundedness filtering 仍然依赖 LLM critic。虽然 temperature 设为 0，但它不是形式化验证器，仍可能误判支持关系。

第四，`ground_truth_context` 是句子级抽取，但生产 RAG 可能按 chunk 检索。评测时需要明确：是检查 retrieved chunks 是否包含这些句子，还是把句子映射回 chunk id。

第五，synthetic questions 不等于真实用户分布。它适合做 regression test 和配置 A/B test，但不能替代真实日志、人工标注集和线上用户反馈。

## 对我的启发

这篇最有用的点是把 RAG 测试集生成拆成了可检查的工程步骤。之前容易把 synthetic RAG eval 理解成“让 LLM 根据文档生成问题和答案”，但公开 flow 显示，真正有诊断价值的是 `ground_truth_context`：只有知道标准证据来自哪里，才能判断 retrieval failure 和 generation failure 的边界。

对我后续做 RAG 或搜索增强 agent 评测时，这个思路可以迁移为：

- 保留生产 chunk id，生成问题时记录 gold chunk。
- 对生成答案做 groundedness critic 过滤。
- 从原文抽 exact evidence sentences，避免只保留抽象答案。
- 用同一批 synthetic questions 比较 retriever、reranker、chunking 和 prompt。
- 再结合真实用户日志补充 synthetic data 覆盖不到的长尾意图。

它不是一个很“深”的理论工作，但作为工程模板很实用。尤其是在知识库频繁变化的场景下，可以定期重新跑 flow，生成新版测试集，用来监控 RAG pipeline 是否因为文档更新、chunking 改动或模型升级而退化。

## 参考

- [Red Hat Developer: Synthetic data for RAG evaluation](https://developers.redhat.com/articles/2026/02/23/synthetic-data-rag-evaluation-why-your-rag-system-needs-better-testing)
- [SDG Hub GitHub repository](https://github.com/Red-Hat-AI-Innovation-Team/sdg_hub)
- [RAG Evaluation flow.yaml](https://github.com/Red-Hat-AI-Innovation-Team/sdg_hub/blob/main/src/sdg_hub/flows/evaluation/rag_evaluation/flow.yaml)
- [RAG Evaluation prompts](https://github.com/Red-Hat-AI-Innovation-Team/sdg_hub/tree/main/src/sdg_hub/flows/evaluation/rag_evaluation/prompts)
