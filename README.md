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

构建时只会渲染 `status = approved` 的论文；草稿不会进入页面。

## 工作流

以后新增论文按这个流程走：

1. 你发来论文链接
2. 我先生成待审内容
3. 你确认后，我把内容写入 `data/library.json`
4. 运行构建脚本，重新生成静态页面

待审内容默认包括：

- 标题与链接
- 一级分类 / 二级分类建议
- 六维中文总结
- 关键词
- 代码仓库链接
- 你的备注

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
