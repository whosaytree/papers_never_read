# 在线网页

https://whosaytree.github.io/papers_never_read/

# 大海捞针

`大海捞针` 是一个按两级目录组织的个人静态论文库，目标仓库为 `whosaytree/papers_never_read`。

页面设计参考 `ICLR2026-Guide-CN`，但数据结构和维护流程已经改成个人长期维护版：

- 保留两级导航、搜索、展开摘要、六维中文总结
- 改成手工增量入库，而不是整届会议批量抓取
- 明确采用“先审阅、后入库”的工作流
- 额外保留 `我的备注`、`关键词`、`代码仓库链接`

## 数据结构

主数据文件：`data/library.json`
待审字段模板：`data/review_template.json`

每篇论文字段约定：

- `id`: 本地唯一 ID，建议用短 slug
- `title`: 论文标题
- `paper_url`: 论文链接
- `authors`: 作者列表
- `venue`: 发表 venue 或来源
- `year`: 年份
- `primary_area`: 一级分类
- `category`: 二级分类
- `keywords`: 关键词列表
- `labels`: 你自己的标签列表
- `tldr`: 一句话定位
- `abstract`: 摘要
- `summary_cn`: 六维中文总结
- `note`: 你的备注
- `code_url`: 代码仓库链接
- `status`: `approved` 或其他状态
- `added_at`: 入库时间

`note` 字段只记录人工补充的个人备注。新增论文时默认留空字符串；只有用户明确提供“我的备注”内容，或要求把某段观察写入备注时，才填入该字段。

构建时只会渲染 `status = approved` 的论文；草稿不会进入页面。

## 新增论文工作流

新增论文必须严格分成“预审”和“入库发布”两个阶段。用户只发论文题目或链接时，默认只进入预审阶段；只有用户明确说“确认”“加入网页”“入库”“发布”等指令后，才进入入库发布阶段。

### 1. 预审阶段

输入可以是论文链接，也可以是论文标题。先查找论文公开信息，生成一份面向人工审阅的“预写入版”。

预审阶段必须遵守：

- 不修改 `data/library.json`
- 不运行构建脚本
- 不提交、不推送
- 用 Markdown 渲染给用户看，不直接输出 JSON 作为主要审阅格式
- 内容必须按网页实际展示字段组织，方便用户直接修改

预写入版必须包括：

- 标题
- 论文链接
- 一级分类 / 二级分类
- 作者 / venue / 年份
- TL;DR
- 六维中文总结：
  - 研究动机
  - 解决问题
  - 现象分析
  - 主要方法
  - 数据集与实验
  - 主要贡献
- 标签
- 关键词
- 代码仓库
- 我的备注
- Abstract

### 2. 入库发布阶段

只有用户确认预写入版后，才执行入库发布。

入库发布阶段必须完成：

1. 将确认后的内容写入 `data/library.json`
2. 将 `status` 设为 `approved`
3. 设置 `added_at` 为当天日期
4. 运行 `python3 -m json.tool data/library.json` 检查 JSON
5. 运行 `python3 scripts/build_site.py` 本地构建
6. 检查 `dist/index.html` 中能搜索到新增论文
7. 提交并推送到 `main`
8. 等待 GitHub Actions `Deploy Pages` 成功
9. 最后回复线上链接、提交信息和部署状态

只有完成推送并确认 GitHub Pages 部署成功，才算“新增到线上网页”。

## Prompt 模板

参考项目把 prompt 写死在脚本中；这里已经拆成独立文件，便于后续维护：

- `prompts/summary_system.txt`
- `prompts/summary_user_template.txt`
- `prompts/category_system.txt`
- `prompts/category_user_template.txt`

## 本地构建

```bash
python3 scripts/build_site.py
open dist/index.html
```

## GitHub Pages

仓库内包含 GitHub Actions 工作流。推送到 `main` 后会：

1. 运行 `python3 scripts/build_site.py`
2. 上传 `dist/`
3. 部署到 GitHub Pages

首次启用时，在 GitHub 仓库设置里将 Pages source 设为 `GitHub Actions`。
