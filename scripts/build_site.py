from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "library.json"
OUTPUT_DIR = ROOT / "dist"
OUTPUT_FILE = OUTPUT_DIR / "index.html"

DIMENSIONS = [
    ("研究动机", "研究动机"),
    ("解决问题", "解决问题"),
    ("现象分析", "现象分析"),
    ("主要方法", "主要方法"),
    ("数据集与实验", "数据集与实验"),
    ("主要贡献", "主要贡献"),
]


CSS = """
:root{
  --bg:#f5f7fa;
  --surface:#ffffff;
  --surface-soft:#eef3f8;
  --line:#d7dee7;
  --text:#1e2933;
  --muted:#637282;
  --accent:#0f766e;
  --accent-soft:#d9f1ee;
  --accent-deep:#0d5b55;
  --note:#fff7dd;
  --note-line:#d0a82f;
  --shadow:0 10px 24px rgba(18,32,47,.06);
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{
  font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans SC",sans-serif;
  background:
    linear-gradient(180deg, rgba(15,118,110,.05), transparent 24%),
    repeating-linear-gradient(135deg, rgba(15,118,110,.03) 0, rgba(15,118,110,.03) 1px, transparent 1px, transparent 16px),
    var(--bg);
  color:var(--text);
  line-height:1.7;
}
a{color:inherit}
.container{display:flex;min-height:100vh}
.sidebar{
  width:320px;
  padding:24px 18px;
  border-right:1px solid var(--line);
  background:rgba(255,255,255,.9);
  backdrop-filter:blur(12px);
  position:sticky;
  top:0;
  height:100vh;
  overflow-y:auto;
}
.brand{
  padding:14px 14px 16px;
  background:linear-gradient(180deg, rgba(15,118,110,.1), rgba(255,255,255,.7));
  border:1px solid rgba(15,118,110,.12);
  border-radius:8px;
  margin-bottom:16px;
}
.brand h1{font-size:22px;line-height:1.2;margin-bottom:6px}
.brand p{font-size:12px;color:var(--muted)}
.brand .repo{display:inline-block;margin-top:10px;font-size:12px;color:var(--accent)}
.sidebar input[type=search]{
  width:100%;
  padding:10px 12px;
  border:1px solid var(--line);
  border-radius:8px;
  background:#fff;
  margin-bottom:14px;
  font-size:13px;
  outline:none;
}
.sidebar input[type=search]:focus{
  border-color:var(--accent);
  box-shadow:0 0 0 3px rgba(15,118,110,.15);
}
.stat-grid{
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:8px;
  margin-bottom:16px;
}
.stat-box{
  border:1px solid var(--line);
  border-radius:8px;
  padding:10px;
  background:var(--surface);
  box-shadow:var(--shadow);
  font-size:11px;
  color:var(--muted);
}
.stat-box b{
  display:block;
  color:var(--accent-deep);
  font-size:17px;
  margin-bottom:2px;
}
.nav-tree{font-size:13px}
.nav-pri{margin-bottom:4px}
.nav-pri-head{
  display:flex;
  gap:8px;
  align-items:center;
  padding:8px 10px;
  background:var(--surface);
  border:1px solid var(--line);
  border-radius:8px;
  cursor:pointer;
  user-select:none;
  transition:background .15s ease,border-color .15s ease;
}
.nav-pri-head:hover{background:var(--surface-soft);border-color:#b8c6d6}
.nav-pri-head .arrow{font-size:10px;color:#7a8998;transition:transform .18s ease}
.nav-pri.expanded>.nav-pri-head .arrow{transform:rotate(90deg)}
.nav-pri-head .name{flex:1;font-weight:600}
.nav-pri-head .count{
  min-width:28px;
  text-align:center;
  padding:1px 8px;
  border-radius:999px;
  background:var(--accent-soft);
  color:var(--accent-deep);
  font-size:11px;
}
.nav-sub-list{display:none;padding:6px 0 8px 18px}
.nav-pri.expanded>.nav-sub-list{display:block}
.nav-sub-list a{
  display:flex;
  align-items:center;
  gap:8px;
  padding:5px 8px;
  border-radius:6px;
  color:var(--muted);
  text-decoration:none;
}
.nav-sub-list a:hover{background:rgba(15,118,110,.08);color:var(--accent-deep)}
.nav-sub-list .name{flex:1}
.nav-sub-list .count{font-size:11px}
.main{
  flex:1;
  padding:34px 42px 56px;
  max-width:calc(100% - 320px);
}
.main-header{
  margin-bottom:30px;
  padding-bottom:18px;
  border-bottom:1px solid var(--line);
}
.main-header h1{font-size:30px;line-height:1.15;margin-bottom:10px}
.main-header p{font-size:14px;color:var(--muted);max-width:900px}
.main-header .meta{margin-top:14px;font-size:12px;color:var(--muted)}
.filter-row{
  display:flex;
  gap:8px;
  flex-wrap:wrap;
  margin-top:18px;
}
.filter-chip{
  display:inline-flex;
  align-items:center;
  padding:6px 12px;
  border-radius:999px;
  border:1px solid var(--line);
  background:var(--surface);
  color:var(--muted);
  font-size:12px;
  font-weight:600;
  cursor:pointer;
}
.filter-chip.active{
  color:#fff;
  border-color:var(--accent-deep);
  background:linear-gradient(180deg, var(--accent), var(--accent-deep));
}
h2.pri-title{
  font-size:24px;
  color:var(--accent-deep);
  border-bottom:2px solid var(--accent);
  padding-bottom:9px;
  margin:40px 0 12px;
  scroll-margin-top:20px;
}
h2.pri-title small,
h3.sub-title small{font-size:12px;color:var(--muted);font-weight:500;margin-left:8px}
h3.sub-title{
  font-size:18px;
  margin:22px 0 14px;
  padding:5px 12px;
  background:linear-gradient(90deg, rgba(15,118,110,.12), rgba(255,255,255,0));
  border-left:4px solid var(--accent);
  border-radius:0 6px 6px 0;
  scroll-margin-top:20px;
}
.paper{
  background:var(--surface);
  border:1px solid var(--line);
  border-radius:8px;
  padding:18px 20px;
  margin-bottom:14px;
  box-shadow:var(--shadow);
}
.paper-title{
  font-size:17px;
  font-weight:700;
  line-height:1.45;
  margin-bottom:8px;
}
.paper-title a{text-decoration:none}
.paper-title a:hover{color:var(--accent);text-decoration:underline}
.paper-meta{
  font-size:12px;
  color:var(--muted);
  margin-bottom:10px;
}
.badge{
  display:inline-block;
  padding:2px 8px;
  margin-right:6px;
  margin-bottom:4px;
  border-radius:999px;
  font-size:11px;
  font-weight:600;
  background:var(--surface-soft);
  color:var(--accent-deep);
}
.paper-tldr{
  background:var(--note);
  border-left:3px solid var(--note-line);
  padding:9px 12px;
  border-radius:0 6px 6px 0;
  font-size:13px;
  color:#6c5400;
  margin-bottom:12px;
}
.dim{display:flex;gap:10px;align-items:flex-start;margin:8px 0;font-size:13.5px}
.dim-label{
  width:90px;
  flex-shrink:0;
  color:var(--accent-deep);
  font-size:12.5px;
  font-weight:700;
}
.dim-content{flex:1}
.paper-extra{
  margin-top:12px;
  padding-top:10px;
  border-top:1px dashed var(--line);
  display:grid;
  gap:8px;
}
.extra-row{
  display:flex;
  gap:10px;
  align-items:flex-start;
  font-size:12.5px;
}
.extra-row .label{
  width:90px;
  flex-shrink:0;
  color:var(--muted);
  font-weight:700;
}
.extra-row .value{flex:1}
.toggle-abs{
  display:inline-block;
  margin-top:12px;
  padding:4px 8px;
  border-radius:6px;
  font-size:12px;
  color:var(--accent-deep);
  cursor:pointer;
  user-select:none;
}
.toggle-abs:hover{background:rgba(15,118,110,.08)}
.full-abs{
  display:none;
  margin-top:10px;
  padding:12px 14px;
  border-radius:8px;
  border:1px solid var(--line);
  background:var(--surface-soft);
  font-size:12.5px;
  color:#44515e;
}
.paper.expanded .full-abs{display:block}
.paper.expanded .toggle-abs::before{content:"▾ "}
.paper:not(.expanded) .toggle-abs::before{content:"▸ "}
.empty{
  padding:36px 26px;
  border:1px dashed #9ab6b0;
  border-radius:8px;
  background:linear-gradient(180deg, rgba(15,118,110,.07), rgba(255,255,255,.65));
  color:#46605d;
  font-size:14px;
}
.hidden{display:none !important}
footer{
  margin-top:42px;
  color:var(--muted);
  font-size:12px;
}
@media (max-width: 960px){
  .container{display:block}
  .sidebar{
    width:100%;
    height:auto;
    position:relative;
    border-right:none;
    border-bottom:1px solid var(--line);
  }
  .main{
    max-width:none;
    padding:22px 18px 40px;
  }
  .dim,.extra-row{display:block}
  .dim-label,.extra-row .label{width:auto;margin-bottom:3px}
}
"""


JS = """
const search = document.getElementById('search');
const cards = document.querySelectorAll('.paper');
const subSecs = document.querySelectorAll('section.sub-sec');
const priSecs = document.querySelectorAll('section.pri-sec');
const chips = document.querySelectorAll('.filter-chip');
let activeFilter = '__all__';

document.querySelectorAll('.nav-pri-head').forEach(head => {
  head.addEventListener('click', () => {
    head.parentElement.classList.toggle('expanded');
  });
});

function applyFilters() {
  const q = (search.value || '').trim().toLowerCase();
  cards.forEach(card => {
    const haystack = (card.dataset.search || '').toLowerCase();
    const hasCode = card.dataset.hasCode === 'true';
    const hasNote = card.dataset.hasNote === 'true';
    const matchesSearch = !q || haystack.includes(q);
    const matchesFilter =
      activeFilter === '__all__' ||
      (activeFilter === 'with-code' && hasCode) ||
      (activeFilter === 'with-note' && hasNote);
    card.classList.toggle('hidden', !(matchesSearch && matchesFilter));
  });

  subSecs.forEach(sec => {
    const visible = sec.querySelectorAll('.paper:not(.hidden)').length;
    sec.classList.toggle('hidden', visible === 0);
    const link = document.querySelector('.nav-sub-list a[href="#' + sec.id + '"]');
    if (link) {
      const count = link.querySelector('.count');
      if (count) count.textContent = '(' + visible + ')';
      link.classList.toggle('hidden', visible === 0 && (q || activeFilter !== '__all__'));
    }
  });

  priSecs.forEach(sec => {
    const visible = sec.querySelectorAll('.paper:not(.hidden)').length;
    const nav = document.getElementById('nav-' + sec.id);
    sec.classList.toggle('hidden', visible === 0 && (q || activeFilter !== '__all__'));
    if (nav) {
      const count = nav.querySelector('.nav-pri-head .count');
      if (count) count.textContent = visible;
      if ((q || activeFilter !== '__all__') && visible > 0) nav.classList.add('expanded');
      if (!q && activeFilter === '__all__') nav.classList.remove('expanded');
    }
  });
}

search.addEventListener('input', applyFilters);
chips.forEach(chip => {
  chip.addEventListener('click', () => {
    activeFilter = chip.dataset.filter;
    chips.forEach(item => item.classList.toggle('active', item === chip));
    applyFilters();
  });
});
"""


def load_library() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def slug(value: str) -> str:
    return quote(value, safe="")


def safe_text(value: str | None, default: str = "未提供") -> str:
    cleaned = (value or "").strip()
    return cleaned if cleaned else default


def search_blob(paper: dict) -> str:
    parts = [
        paper.get("title", ""),
        " ".join(paper.get("authors", [])),
        paper.get("venue", ""),
        paper.get("primary_area", ""),
        paper.get("category", ""),
        " ".join(paper.get("keywords", [])),
        paper.get("note", ""),
        paper.get("abstract", ""),
        paper.get("code_url", ""),
    ]
    return " ".join(part for part in parts if part)


def summary_html(summary: dict) -> str:
    rows = []
    for key, label in DIMENSIONS:
        content = safe_text(summary.get(key), "待补充")
        rows.append(
            f'<div class="dim"><div class="dim-label">{escape(label)}</div>'
            f'<div class="dim-content">{escape(content)}</div></div>'
        )
    return "".join(rows)


def paper_card(paper: dict) -> str:
    title = escape(safe_text(paper.get("title"), "未命名论文"))
    paper_url = escape(safe_text(paper.get("paper_url"), "#"))
    authors = escape(", ".join(paper.get("authors", [])) or "作者待补充")
    venue = escape(safe_text(paper.get("venue")))
    year = escape(str(paper.get("year", "")) or "年份待补充")
    primary = escape(safe_text(paper.get("primary_area")))
    category = escape(safe_text(paper.get("category")))
    keywords = paper.get("keywords", [])
    note = safe_text(paper.get("note"), "暂无备注")
    code_url = (paper.get("code_url") or "").strip()
    abstract = escape(safe_text(paper.get("abstract"), "暂无摘要"))
    tldr = escape(safe_text(paper.get("tldr"), "待补充一句话定位"))
    summary = paper.get("summary_cn") or {}
    keyword_html = "".join(f'<span class="badge">{escape(item)}</span>' for item in keywords)
    code_html = (
        f'<a href="{escape(code_url)}" target="_blank" rel="noreferrer">{escape(code_url)}</a>'
        if code_url
        else "暂无代码链接"
    )
    return f"""
<article class="paper" data-search="{escape(search_blob(paper))}" data-has-code="{str(bool(code_url)).lower()}" data-has-note="{str(bool((paper.get('note') or '').strip())).lower()}">
  <div class="paper-title"><a href="{paper_url}" target="_blank" rel="noreferrer">{title}</a></div>
  <div class="paper-meta">
    <span class="badge">{primary}</span>
    <span class="badge">{category}</span>
    <span>{authors}</span> · <span>{venue}</span> · <span>{year}</span>
  </div>
  <div class="paper-tldr"><b>TL;DR</b> {tldr}</div>
  {summary_html(summary)}
  <div class="paper-extra">
    <div class="extra-row"><div class="label">关键词</div><div class="value">{keyword_html or "暂无关键词"}</div></div>
    <div class="extra-row"><div class="label">代码仓库</div><div class="value">{code_html}</div></div>
    <div class="extra-row"><div class="label">我的备注</div><div class="value">{escape(note)}</div></div>
  </div>
  <span class="toggle-abs" onclick="this.parentElement.classList.toggle('expanded')">查看 Abstract</span>
  <div class="full-abs">{abstract}</div>
</article>
"""


def render_sections(library: dict) -> tuple[str, str]:
    taxonomy = library["taxonomy"]
    papers = library["papers"]
    grouped: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for paper in papers:
        primary = paper.get("primary_area") or "(未分类)"
        category = paper.get("category") or "其他"
        grouped[primary][category].append(paper)

    nav_blocks = []
    main_blocks = []
    has_papers = False

    for primary_entry in taxonomy:
        primary = primary_entry["primary_area"]
        subcategories = primary_entry["subcategories"]
        primary_id = f"pri-{slug(primary)}"
        primary_count = sum(len(grouped[primary][sub]) for sub in subcategories)
        nav_sub_links = []
        sub_sections = []

        for sub in subcategories:
            section_id = f"sub-{slug(primary)}-{slug(sub)}"
            items = grouped[primary][sub]
            nav_sub_links.append(
                f'<a href="#{section_id}"><span class="name">{escape(sub)}</span><span class="count">({len(items)})</span></a>'
            )
            if items:
                has_papers = True
                cards = "".join(paper_card(item) for item in items)
                sub_sections.append(
                    f'<section id="{section_id}" class="sub-sec"><h3 class="sub-title">{escape(sub)}<small>{len(items)} 篇</small></h3>{cards}</section>'
                )

        nav_blocks.append(
            f'<div id="nav-{primary_id}" class="nav-pri"><div class="nav-pri-head"><span class="arrow">▶</span><span class="name">{escape(primary)}</span><span class="count">{primary_count}</span></div><div class="nav-sub-list">{"".join(nav_sub_links)}</div></div>'
        )

        body = "".join(sub_sections) if sub_sections else ""
        main_blocks.append(
            f'<section id="{primary_id}" class="pri-sec"><h2 class="pri-title">{escape(primary)}<small>{primary_count} 篇</small></h2>{body}</section>'
        )

    if not has_papers:
        main_blocks.insert(
            0,
            """
<section class="pri-sec">
  <div class="empty">
    论文库还没有正式内容。后续你每发来一篇论文链接，我会先生成待审版本：
    分类建议、六维总结、关键词、代码链接和你的备注。
    你确认后，它才会进入这个页面。
  </div>
</section>
""",
        )

    return "".join(nav_blocks), "".join(main_blocks)


def render_page(library: dict) -> str:
    site = library["site"]
    papers = [
        paper for paper in library["papers"]
        if (paper.get("status") or "approved") == "approved"
    ]
    library = {**library, "papers": papers}
    nav_html, main_html = render_sections(library)
    counter = Counter()
    counter["all"] = len(papers)
    counter["with_code"] = sum(1 for item in papers if (item.get("code_url") or "").strip())
    counter["with_note"] = sum(1 for item in papers if (item.get("note") or "").strip())
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(site['name'])}</title>
  <meta name="description" content="{escape(site['description'])}">
  <style>{CSS}</style>
</head>
<body>
  <div class="container">
    <aside class="sidebar">
      <div class="brand">
        <h1>{escape(site['name'])}</h1>
        <p>{escape(site['description'])}</p>
        <a class="repo" href="https://github.com/{escape(site['repo'])}" target="_blank" rel="noreferrer">{escape(site['repo'])}</a>
      </div>
      <input id="search" type="search" placeholder="搜索标题 / 关键词 / 备注 / abstract">
      <div class="stat-grid">
        <div class="stat-box"><b>{len(papers)}</b>论文总数</div>
        <div class="stat-box"><b>{len(library['taxonomy'])}</b>一级分类</div>
        <div class="stat-box"><b>{counter['with_code']}</b>含代码链接</div>
        <div class="stat-box"><b>{counter['with_note']}</b>含个人备注</div>
      </div>
      <div class="nav-tree">{nav_html}</div>
    </aside>
    <main class="main">
      <header class="main-header">
        <h1>{escape(site['name'])}</h1>
        <p>这是一个按两级目录组织的个人静态论文库。页面结构延续参考项目，但数据、分类入库和审阅流程改成了长期维护型版本：先审阅，再入库。</p>
        <div class="filter-row">
          <button class="filter-chip active" data-filter="__all__">全部 {counter['all']} 篇</button>
          <button class="filter-chip" data-filter="with-code">含代码 {counter['with_code']} 篇</button>
          <button class="filter-chip" data-filter="with-note">含备注 {counter['with_note']} 篇</button>
        </div>
        <div class="meta">总结维度固定为：研究动机 / 解决问题 / 现象分析 / 主要方法 / 数据集与实验 / 主要贡献。最近构建时间：{generated_at}</div>
      </header>
      {main_html}
      <footer>GitHub Pages 目标仓库：{escape(site['repo'])}</footer>
    </main>
  </div>
  <script>{JS}</script>
</body>
</html>
"""


def main() -> None:
    library = load_library()
    ensure_output_dir()
    OUTPUT_FILE.write_text(render_page(library), encoding="utf-8")
    print(f"Built {OUTPUT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
