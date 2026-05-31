# Microsoft Golden Dataset for RAG Evaluation 详细笔记

## 核心定位

这篇 Data Science + AI at Microsoft 文章讨论的是如何为企业 RAG 项目构造可信 benchmark。它不是论文，而是 Microsoft / Azure Data 团队在客户项目中总结出来的实践方法，并配了一个公开 notebook。

它的核心判断是：RAG 系统评估不能直接套通用 LLM benchmark。因为企业 RAG 通常基于私有数据、领域数据或结构复杂的数据，问题分布、文档风格和答案要求都高度定制。因此每个项目都需要自己的 benchmark。

文章提出两阶段流程：

```text
raw documents
  -> chunks with metadata
  -> GPT-generated QA
  -> silver dataset
  -> AI-assisted metrics
  -> human expert review
  -> golden dataset
```

这里的关键词是 silver 和 golden。

Silver dataset 是自动生成的候选评测集。

Golden dataset 是对 silver 进一步检查、筛选、修正、补全、删除和确认之后得到的高可信评测集。

## 为什么需要 custom benchmark

文章指出，RAG 项目和普通 LLM 评估不一样。

LLM 可以用公开 benchmark 测通用能力，但 RAG 的效果强依赖：

- 私有数据内容。
- 文档结构。
- 文档风格。
- 文档模态。
- chunking 策略。
- embedding 和 retrieval index。
- 业务问题分布。

所以 RAG benchmark 至少应该包含：

```text
question
answer
source reference / context
```

文章建议 100 条 QA 是一个合理起点：足够有多样性，又不会让项目早期资源压力过大。

## Chunks 是什么

Chunk 是把原始长文档切成的小片段。

例如一份 30 页的财报电话会 transcript 太长，不能整篇塞进向量库或 LLM context，所以会切成很多段：

```text
chunk 1: 开场说明、免责声明
chunk 2: CEO 讲 Azure 增长
chunk 3: CFO 讲 revenue / margin
chunk 4: Q&A 中分析师问 AI capex
```

每个 chunk 通常带元数据：

```text
Ticker
Year
Quarter
PageNumber
LineNumber
Chunk
Embedding
```

所以 chunk 不是随便一段文本，而是 RAG 系统检索、引用、拼接 context 和诊断错误的基本单位。

如果 benchmark QA 是从 chunks 生成的，就能知道：

```text
这个问题的标准答案应该来自哪些 chunks
```

这能帮助后续区分三类失败：

- retriever 没找回 gold chunk。
- retriever 找回了 chunk，但 context 不够或噪声太多。
- LLM 拿到了正确 context，但生成答案失败。

## Silver dataset 怎么生成

Silver dataset 是自动生成的初始 QA 候选集。

公开 notebook 的数据来自 Microsoft financial transcripts。它先读取预处理后的：

```text
AnalyzedPDF/ChunksEmbedding.csv
```

这个 CSV 包含：

```text
Id
Ticker
Year
Quarter
Chunk
PageNumber
LineNumber
Embedding
```

生成流程是：

```text
1. 读取 chunks CSV
2. 随机选择 Ticker
3. 随机选择 Year
4. 随机选择 Quarter
5. 随机选择两个 PageNumber
6. 拼出 chunk1 和 chunk2
7. 把 chunks 和元数据放进 prompt
8. 调 Azure OpenAI / GPT 生成 10 组 QA
9. 解析成结构化行
```

这里的随机选择不是完全随便，而是在 ticker、year、quarter、page 这些 filter parameters 上抽样。这样可以让生成出来的问题覆盖不同财报时间段和不同文档位置。

## GPT 生成 QA 的 prompt 细节

公开 notebook 里的 prompt 比较轻量，但约束清楚。

输入包括：

```text
chunk_text1
chunk_text2
ticker
quarter
year
```

任务要求是：

- 给定两个 text chunks、ticker、quarter、year。
- 生成 10 个 relevant question-answer pairs。
- 问题应该基于两个 chunks 中的信息。
- 答案必须能从两个 chunks 中找到。
- 不要自己编答案。
- 如果答案不在文本中，写 N/A。
- 问题可以用不同方式表达财年和季度，例如 MSFT FY23 Q1、MSFT FY2023 1st quarter。
- 如果文本不相关，就跳过该 QA pair。

这套 prompt 的核心防线是：

```text
answer must be available in chunks
do not generate answers on your own
if unavailable, write N/A
```

也就是说，它希望 GPT 只做“从 chunk 中构造 QA”，而不是凭通用知识出题和回答。

## QA 输出和后处理

GPT 输出是普通文本格式：

```text
Question 1: ...
Answer 1: ...

Question 2: ...
Answer 2: ...
```

Notebook 里用简单 Python 解析：

```text
按换行切分
偶数行取 question
奇数行取 answer
组合成 dict
```

最终格式类似：

```json
{
  "chat_history": "[]",
  "question": "...",
  "answer": "..."
}
```

文章也提醒，实际生产中最好让 prompt 直接输出更适合保存的格式，或者把结果写入数据库。示例里保存成 CSV 是因为客户需求。

## Silver 的局限

Silver dataset 不能直接当作高可信 benchmark。

可能问题包括：

- 答案没有完全来自 chunks。
- 答案太笼统，不满足领域专家要求。
- 问题只依赖一个 chunk，没有真正利用两个 chunks。
- 问题业务相关性不够。
- 问题格式不稳定，解析困难。
- 答案虽然正确，但缺少关键数值、对比项或限定条件。

所以 silver 的定位是候选集：

```text
fast but not fully trusted
```

## Golden dataset 是什么

Golden dataset 是对 silver dataset 做进一步质量控制之后得到的可信评测集。

它不是完全重新生成一批数据，而是对 silver 做：

```text
检查
筛选
修正
补全
删除
确认
```

因此可以理解成：

```text
silver = AI-generated candidate QA
golden = verified QA benchmark
```

golden 才适合正式用于 RAG 系统评估和迭代。

## Golden 阶段怎么做

文章建议把 silver QA 和 source references 聚合起来，转成评测框架需要的格式，例如 CSV 或 JSON。

然后用 Azure AI Studio 或 RAGAS 这类工具做 AI-assisted metrics。

重点指标包括：

`Groundedness`：answer 中的 claims 是否被 source context 支持。

`Relevance`：answer 是否真正回答 question，有没有遗漏关键信息或包含无关信息。

`Coherence`：answer 是否语言连贯、自然、可读。

这里要注意：这些指标首先是在评估 benchmark QA 自身质量。

换句话说，不是先拿 silver QA 去评估 RAG，而是先问：

```text
这条 QA 本身能不能作为标准答案？
```

只有通过质量检查和专家审核后，它才进入 golden dataset。

## Human expert review

文章的 case study 使用 Microsoft earnings call transcripts 生成 100 条 QA，然后请 Microsoft 内部金融专家审核。

结果是：

```text
66 条无条件 greenlight
7 条 OK 但有保留
27 条不达专家标准
```

专家发现的问题通常不是简单的“事实错了”，而是“不够完整”。

例如一个财务问题的好答案可能需要：

- dollar amount
- percent change
- margin target
- actual landing
- relevant comparison

如果答案只说“增长了”或“表现好”，即使没有事实幻觉，也不一定满足 benchmark 标准。

这个点很关键：gold answer 不只是 factual，还要满足领域专家对 completeness 和 usefulness 的要求。

## Source location 的作用

文章强调要保留 source reference。

公开 notebook 里 chunk 表包含 page、line 等信息。这些字段可以支持后续计算：

```text
top-N retrieval rate
```

也就是：RAG 系统检索出来的 top-N chunks 里，是否包含 benchmark 标记的标准证据 chunk。

有了 source location，错误归因会更清楚：

```text
如果 top-N 没有 gold chunk：retrieval 失败
如果 top-N 有 gold chunk 但 answer 错：generation 或 prompt 失败
如果 gold answer 本身不完整：benchmark 数据质量问题
```

所以 source location 不只是引用来源，而是评估 retriever 和 generator 的分界线。

## 和前几篇的区别

RAGAS v0.1.21：

- 强调 evolution。
- 通过 simple、reasoning、multi_context 等类型控制问题分布。
- 更像 synthetic testset generation framework。

AWS Bedrock：

- 更像 prompt pipeline。
- 从 chunk 生成 question、answer、source sentence、evolved question。

Red Hat SDG Hub：

- 更像开源 YAML flow。
- 输出 question、response、ground_truth_context。

Label Studio：

- 更像 production human-in-the-loop 数据闭环。
- 评估 task-specific functional equivalence。

Microsoft 这篇：

- 强调 silver -> golden。
- 强调 chunk source location。
- 强调 AI metrics + domain expert review。
- 更贴近“项目早期如何快速获得可用 benchmark”。

## 局限

第一，这不是严格实验论文，而是实践文章和 case study。

第二，公开 notebook 的 QA generation prompt 很轻量，没有复杂 evolution、critic filtering 或自动 source sentence extraction。

第三，GPT 输出格式是普通文本，notebook 用简单 split 解析，生产环境需要更稳的 JSON / schema 输出。

第四，专家审核结果来自 financial transcripts case study，不能直接泛化到所有领域。

第五，AI-assisted metrics 只能辅助发现问题，不能替代领域专家对 completeness 和 usefulness 的判断。

## 我应该如何记这篇

这篇的核心是：

```text
不要把自动生成的 QA 直接当 gold。
先生成 silver，再用 AI metrics 和专家审核把它清洗成 golden。
```

它补充了 RAG 评测集构建里一个很实际的环节：自动生成只是第一步，真正决定 benchmark 可信度的是后面的质量控制。

## 关键记忆点

- 这篇是 Microsoft / Azure Data 的 RAG benchmark 构建实践。
- Chunk 是 RAG 检索、引用和诊断的基本文本单位。
- Silver dataset 是 GPT 从 selected chunks 自动生成的 QA 候选集。
- Golden dataset 是对 silver 做检查、筛选、修正、补全、删除和确认后的可信集。
- 公开 notebook 随机选 ticker/year/quarter/page，再取两个 chunks 生成 10 个 QA。
- Prompt 要求答案必须来自 chunks，不能编；没有答案就写 N/A。
- Source location 可用于计算 top-N retrieval rate，并区分 retrieval failure 和 generation failure。
- Golden 阶段用 groundedness、relevance、coherence 等指标辅助筛查 QA 自身质量。
- 专家审核发现很多失败不是事实错误，而是答案不够完整。
- 这篇适合放在 synthetic RAG evaluation / golden dataset construction 这一组。

