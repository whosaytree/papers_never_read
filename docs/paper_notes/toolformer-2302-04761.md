# Toolformer 详细笔记

## 核心定位

Toolformer 的目标是让语言模型学会在生成文本时调用外部工具，包括 calculator、question answering、Wikipedia search、machine translation 和 calendar。它不是在线 RL，也不是用最终答案 reward 训练 tool-use policy，而是一个离线自监督数据构造方法：从普通文本中自动插入 API 调用，再用 loss-based filtering 保留真正能帮助预测原文后续 token 的调用。

这篇论文的关键价值在于证明：只要每个工具有少量 demonstration，模型可以在大规模自然文本中自举出一批 API-augmented training data，并通过普通 causal LM fine-tuning 学会何时调用工具、调用哪个工具、传入什么参数，以及如何把工具返回结果接回后续生成。

## 轨迹到底是什么

Toolformer 里的“轨迹”更准确地说是单次 API 调用标注样本，而不是多步 agent 交互轨迹。

它不是下面这种流程：

```text
模型生成一段 -> 执行工具 -> 根据观察继续生成下一段 -> 再执行工具 -> 最终答案判分
```

而是下面这种离线流程：

```text
已有普通文本 -> 找候选插入点 -> 采样 API 调用 -> 执行 API -> 用原文后续计算 loss 改善 -> 保留有用调用 -> 插回文本 -> SFT
```

也就是说，原文后续内容一开始就存在。Toolformer 并不让模型生成一个新答案再判断对错，而是检查某个工具返回结果是否让模型更容易预测这段已有文本的后续内容。

## 数据生成流程

给定普通文本语料 `C = {x1, ..., xn}`，Toolformer 对每个工具分别构造增强数据。流程可以拆成五步。

第一步是少量人工示范。作者为每个 API 手写几个 demonstrations，告诉模型 API 调用应该长什么样、可以插在文本什么位置。例如 calculator 的调用形式可以线性化为：

```text
<API> Calculator(13 + 29) -> 42 </API>
```

第二步是找候选插入位置。对一段文本中的每个位置 `i`，模型基于 prompt examples 和当前位置前缀计算生成 `<API>` 的概率：

```text
p_i = P(<API> | prompt, x_1 ... x_{i-1})
```

只保留概率超过阈值 `tau_s` 的位置；如果候选位置太多，就取 top-k。这个阶段只是判断“哪里可能值得插 API 调用”，不是最终筛选。

第三步是在每个候选位置采样 API 调用。模型只生成 API span，不继续生成完整文章或完整答案。对于同一个位置，它会采样多个候选调用，比如：

```text
<API> Calculator(13 + 29) </API>
<API> Calculator(13 * 29) </API>
<API> Calculator(29 - 13) </API>
```

没有正常结束、格式不合法或不满足工具约束的候选会被丢弃。

第四步是真实执行 API。候选调用会被送到对应工具，得到返回结果：

```text
<API> Calculator(13 + 29) -> 42 </API>
<API> Calculator(13 * 29) -> 377 </API>
<API> Calculator(29 - 13) -> 16 </API>
```

第五步是 loss-based filtering。对每个候选调用，Toolformer 比较三种条件下模型预测原文后续 token 的 loss：

- 不插入 API 的 loss。
- 插入 API 调用但不给返回结果的 loss。
- 插入 API 调用并给出返回结果的 loss。

只有当“调用 + 返回结果”相比前两种情况显著降低后续 token loss 时，这个调用才会保留。这样做是为了确认真正有用的是工具返回结果，而不是 API 调用文本本身碰巧给了模型提示。

## 一个具体例子

原始文本是：

```text
The store sold 13 red balls and 29 blue balls. It sold 42 balls in total.
```

模型可能在第一句之后提出候选调用：

```text
The store sold 13 red balls and 29 blue balls.
<API> Calculator(13 + 29) </API>
It sold 42 balls in total.
```

执行 calculator 后得到：

```text
<API> Calculator(13 + 29) -> 42 </API>
```

因为 `42` 能帮助模型预测原文后续的 `It sold 42 balls in total`，这个调用会让后续 token loss 明显下降，所以会被保留。

如果另一个候选是：

```text
<API> Calculator(13 * 29) -> 377 </API>
```

`377` 对预测后文的 `42` 没帮助，这个候选就会被过滤掉。

最终训练样本变成：

```text
The store sold 13 red balls and 29 blue balls.
<API> Calculator(13 + 29) -> 42 </API>
It sold 42 balls in total.
```

这个样本随后进入普通 causal LM fine-tuning。模型被训练去预测所有 token，包括 `<API>`、工具名、参数、返回结果和后续自然语言文本。

## 训练阶段不是 RL

Toolformer 的训练阶段是 SFT / LM fine-tuning，不是 RL。loss filtering 只发生在离线数据构造阶段，用来挑选哪些 API 调用值得写入训练数据。

训练时没有最终答案 reward、没有 verifier、没有 PPO/GRPO，也没有多轮环境 rollout。模型只是对 API-augmented corpus 继续做 next-token prediction。它学到的是工具调用格式和调用时机，而不是通过环境反馈直接优化最终答案正确率。

## 为什么用这个流程

作者这样设计主要有三个原因。

第一，人工标注成本低。每个 API 只需要少量 demonstration，不需要人工为大规模语料标注工具调用位置、参数和返回结果使用方式。

第二，可以直接复用普通预训练语料。由于方法只是在已有文本里插入 API 调用，它不依赖专门构造的问答、数学或检索数据集，也能保持文本分布接近原始 LM 训练分布。

第三，筛选信号和训练目标一致。最终训练目标是 next-token prediction，所以离线筛选时也用“是否降低后续 token prediction loss”作为标准。这不是严格的正确性监督，但和语言建模目标对齐。

## 效果与局限

Toolformer 在数学、日期和简单事实查询这类单次工具调用能直接补足信息的任务上收益明显。数学任务尤其受益于 calculator，因为正确计算结果经常直接出现在后文，loss filtering 很容易把这类样本捞出来。

但这个方法不能保证最终答案正确。它判断的是工具返回结果是否帮助预测原文后续，而不是最终答案是否等于 gold answer。如果原文本身错误、过时或与任务目标不一致，loss filtering 并不会发现这个问题。

它也不适合复杂多步工具使用。Toolformer 主要学习单次 API 调用，不具备后续 tool-use RL / web agent 中常见的多轮搜索、观察、改写 query、交叉验证和最终答案 verifier。对于复杂任务，后来的方法通常会引入明确问题、gold answer、环境反馈或 verifiable reward。

## 对后续研究的启发

Toolformer 适合作为 tool-use LLM 的早期基础工作来理解。它说明工具调用可以被表示成语言模型序列中的特殊 span，并且可以通过自监督方式从普通文本中挖掘训练信号。

但如果手里已经有数学题、QA 题或可验证任务，通常没有必要只用 Toolformer 的 LM-loss 过滤。更直接的路线是让模型生成工具调用轨迹，执行工具，抽取最终答案，然后用 gold answer 或 verifier 过滤正确轨迹做 SFT，或进一步用 RL 优化最终成功率。

因此，Toolformer 的核心价值不是提供一个强正确性训练框架，而是提供一个低标注成本的离线 bootstrapping 方法：先让模型学会工具调用的基本接口和触发模式，再由后续更强的 SFT/RL/verifier 方法提升复杂任务上的可靠性。

## 参考

- [arXiv:2302.04761](https://arxiv.org/abs/2302.04761)
- [Meta AI publication page](https://ai.meta.com/research/publications/toolformer-language-models-can-teach-themselves-to-use-tools/)
