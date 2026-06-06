from __future__ import annotations

import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "library.json"
BLOG_FILE = ROOT / "data" / "blogs.json"
PROJECT_FILE = ROOT / "data" / "projects.json"
ASSET_DIR = ROOT / "assets"
OUTPUT_DIR = ROOT / "dist"
OUTPUT_FILE = OUTPUT_DIR / "index.html"
BLOG_KEY_POINTS_LIMIT = 5

DIMENSIONS = [
    ("研究动机", "研究动机"),
    ("解决问题", "解决问题"),
    ("现象分析", "现象分析"),
    ("主要方法", "主要方法"),
    ("数据集与实验", "数据集与实验"),
    ("主要贡献", "主要贡献"),
]

BLOG_SITE_LINKS = [
    {
        "name": "LMSYS Blog",
        "url": "https://www.lmsys.org/blog/",
        "note": "大模型系统、Chatbot Arena、SGLang 等方向的技术分享",
    },
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
.view-tabs{
  display:grid;
  grid-template-columns:repeat(3,minmax(0,1fr));
  gap:8px;
  margin-bottom:14px;
}
.view-tab{
  border:1px solid var(--line);
  border-radius:8px;
  background:var(--surface);
  color:var(--muted);
  padding:9px 10px;
  font-size:13px;
  font-weight:700;
  cursor:pointer;
}
.view-tab.active{
  border-color:var(--accent-deep);
  color:#fff;
  background:linear-gradient(180deg, var(--accent), var(--accent-deep));
}
.view-panel.hidden,
.sidebar-panel.hidden,
.filter-row.hidden{display:none}
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
.badge.label{
  background:#ffe6d8;
  color:#8a3b12;
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
.key-figure{
  margin:12px 0;
  padding:12px;
  border:1px solid var(--line);
  border-radius:8px;
  background:#fbfcfd;
}
.key-figure img{
  width:100%;
  max-height:520px;
  object-fit:contain;
  background:#fff;
  border:1px solid var(--line);
  border-radius:6px;
}
.key-figure-label{
  font-size:12px;
  font-weight:700;
  color:var(--accent-deep);
  margin:10px 0 5px;
}
.key-figure-caption{
  font-size:12.5px;
  color:#44515e;
}
.key-figure-caption-cn{
  margin-top:6px;
  font-size:12.5px;
  color:#263642;
}
.key-figure-meta{
  margin-top:8px;
  font-size:11.5px;
  color:var(--muted);
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
.extra-row a{color:var(--accent-deep);font-weight:600}
.note-link{
  display:inline-flex;
  align-items:center;
  gap:6px;
  color:var(--accent-deep);
  font-weight:700;
  text-decoration:none;
}
.note-link:hover{text-decoration:underline}
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
.blog-list,
.project-list{
  display:grid;
  gap:14px;
}
.blog-source-links{
  background:var(--surface);
  border:1px solid var(--line);
  border-radius:8px;
  margin-bottom:14px;
  padding:16px 18px;
  box-shadow:var(--shadow);
}
.blog-source-links h3{
  font-size:15px;
  color:var(--accent-deep);
  margin-bottom:10px;
}
.blog-source-grid{
  display:grid;
  gap:8px;
}
.blog-source-item{
  display:flex;
  gap:10px;
  align-items:flex-start;
  justify-content:space-between;
  padding:9px 10px;
  border:1px solid var(--line);
  border-radius:8px;
  background:var(--surface-soft);
}
.blog-source-item a{
  color:var(--accent-deep);
  font-weight:750;
  text-decoration:none;
}
.blog-source-item a:hover{text-decoration:underline}
.blog-source-item span{
  color:var(--muted);
  font-size:12.5px;
}
.blog,
.project{
  background:var(--surface);
  border:1px solid var(--line);
  border-radius:8px;
  padding:18px 20px;
  box-shadow:var(--shadow);
}
.blog-title,
.project-title{
  font-size:18px;
  font-weight:750;
  line-height:1.4;
  margin-bottom:8px;
}
.blog-title a,
.project-title a{text-decoration:none}
.blog-title a:hover,
.project-title a:hover{color:var(--accent);text-decoration:underline}
.blog-meta,
.project-meta{
  font-size:12px;
  color:var(--muted);
  margin-bottom:10px;
}
.blog-summary,
.project-summary{
  font-size:13.5px;
  color:#34424f;
  margin:10px 0 12px;
}
.blog-block,
.project-block{
  margin-top:12px;
  display:grid;
  gap:7px;
}
.blog-block h4,
.project-block h4{
  font-size:13px;
  color:var(--accent-deep);
}
.blog-points,
.project-points{
  padding-left:18px;
  font-size:13px;
}
.blog-points li,
.project-points li{margin:4px 0}
.project-links{
  display:flex;
  gap:6px;
  flex-wrap:wrap;
}
.project-links a{text-decoration:none}
.blog-table{
  width:100%;
  border-collapse:collapse;
  font-size:12.5px;
  overflow:hidden;
  border:1px solid var(--line);
  border-radius:8px;
}
.blog-table th,
.blog-table td{
  text-align:left;
  vertical-align:top;
  padding:8px 10px;
  border-bottom:1px solid var(--line);
}
.blog-table th{
  background:var(--surface-soft);
  color:var(--accent-deep);
  font-size:12px;
}
.blog-table tr:last-child td{border-bottom:none}
.blog-table .term{
  width:170px;
  font-weight:700;
  color:#34424f;
}
.quote-row{
  border-left:3px solid var(--accent);
  background:var(--surface-soft);
  padding:9px 12px;
  border-radius:0 6px 6px 0;
  font-size:12.5px;
}
.quote-row .quote-note{
  color:var(--muted);
  margin-top:4px;
}
.related-links{
  display:flex;
  gap:6px;
  flex-wrap:wrap;
}
.related-links a{
  text-decoration:none;
}
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


NOTE_CSS = """
:root{
  --bg:#f5f7fa;
  --surface:#ffffff;
  --line:#d7dee7;
  --text:#1e2933;
  --muted:#637282;
  --accent:#0f766e;
  --accent-deep:#0d5b55;
  --note:#fff7dd;
}
*{box-sizing:border-box}
body{
  margin:0;
  font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans SC",sans-serif;
  background:var(--bg);
  color:var(--text);
  line-height:1.75;
}
main{max-width:920px;margin:0 auto;padding:42px 22px 72px}
article{
  background:var(--surface);
  border:1px solid var(--line);
  border-radius:8px;
  padding:30px;
  box-shadow:0 10px 24px rgba(18,32,47,.06);
}
a{color:var(--accent-deep)}
.back{
  display:inline-block;
  margin-bottom:18px;
  color:var(--accent-deep);
  font-weight:700;
  text-decoration:none;
}
.back:hover{text-decoration:underline}
h1{font-size:28px;line-height:1.25;margin:0 0 18px}
h2{font-size:20px;margin:30px 0 10px;color:var(--accent-deep)}
h3{font-size:16px;margin:22px 0 8px}
p{margin:10px 0}
ul{padding-left:22px;margin:8px 0 12px}
li{margin:6px 0}
code{background:#eef3f8;border-radius:5px;padding:1px 5px}
pre{background:#17212b;color:#eef6f6;border-radius:8px;padding:14px;overflow:auto}
pre code{background:transparent;color:inherit;padding:0}
blockquote{
  margin:14px 0;
  padding:10px 14px;
  border-left:3px solid var(--accent);
  background:var(--note);
  color:#5d4a05;
}
"""


JS = """
const search = document.getElementById('search');
const cards = document.querySelectorAll('.paper');
const blogCards = document.querySelectorAll('.blog');
const projectCards = document.querySelectorAll('.project');
const subSecs = document.querySelectorAll('section.sub-sec');
const priSecs = document.querySelectorAll('section.pri-sec');
const chips = document.querySelectorAll('.filter-chip');
const viewTabs = document.querySelectorAll('.view-tab');
const viewPanels = document.querySelectorAll('.view-panel');
const sidebarPanels = document.querySelectorAll('.sidebar-panel');
const filterRows = document.querySelectorAll('.filter-row');
let activeFilter = '__all__';
let activeView = 'papers';

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
    const hasKeyFigure = card.dataset.hasKeyFigure === 'true';
    const matchesSearch = !q || haystack.includes(q);
    const matchesFilter =
      activeFilter === '__all__' ||
      (activeFilter === 'with-code' && hasCode) ||
      (activeFilter === 'with-note' && hasNote) ||
      (activeFilter === 'with-key-figure' && hasKeyFigure);
    card.classList.toggle('hidden', !(matchesSearch && matchesFilter));
  });
  blogCards.forEach(card => {
    const haystack = (card.dataset.search || '').toLowerCase();
    const hasRelated = card.dataset.hasRelated === 'true';
    const hasQuotes = card.dataset.hasQuotes === 'true';
    const hasKeyFigure = card.dataset.hasKeyFigure === 'true';
    const matchesSearch = !q || haystack.includes(q);
    const matchesFilter =
      activeFilter === '__all__' ||
      (activeFilter === 'with-related' && hasRelated) ||
      (activeFilter === 'with-quotes' && hasQuotes) ||
      (activeFilter === 'with-key-figure' && hasKeyFigure);
    card.classList.toggle('hidden', !(matchesSearch && matchesFilter));
  });
  projectCards.forEach(card => {
    const haystack = (card.dataset.search || '').toLowerCase();
    const hasLinks = card.dataset.hasLinks === 'true';
    const hasRelated = card.dataset.hasRelated === 'true';
    const matchesSearch = !q || haystack.includes(q);
    const matchesFilter =
      activeFilter === '__all__' ||
      (activeFilter === 'with-links' && hasLinks) ||
      (activeFilter === 'with-related' && hasRelated);
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
    if (chip.dataset.view !== activeView) return;
    activeFilter = chip.dataset.filter;
    chips.forEach(item => {
      if (item.dataset.view === activeView) item.classList.toggle('active', item === chip);
    });
    applyFilters();
  });
});
viewTabs.forEach(tab => {
  tab.addEventListener('click', () => {
    activeView = tab.dataset.view;
    activeFilter = '__all__';
    search.value = '';
    search.placeholder = activeView === 'papers'
      ? '搜索论文标题 / 关键词 / 备注 / abstract'
      : activeView === 'blogs'
        ? '搜索技术分享标题 / 标签 / 主要内容 / 关键语句'
        : '搜索代码项目名称 / 标签 / 技术栈 / 使用场景';
    viewTabs.forEach(item => item.classList.toggle('active', item === tab));
    viewPanels.forEach(panel => panel.classList.toggle('hidden', panel.dataset.view !== activeView));
    sidebarPanels.forEach(panel => panel.classList.toggle('hidden', panel.dataset.view !== activeView));
    filterRows.forEach(row => row.classList.toggle('hidden', row.dataset.view !== activeView));
    chips.forEach(item => item.classList.toggle('active', item.dataset.view === activeView && item.dataset.filter === '__all__'));
    applyFilters();
  });
});
"""


def load_library() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def load_blogs() -> dict:
    if not BLOG_FILE.exists():
        return {"posts": []}
    return json.loads(BLOG_FILE.read_text(encoding="utf-8"))


def load_projects() -> dict:
    if not PROJECT_FILE.exists():
        return {"projects": []}
    return json.loads(PROJECT_FILE.read_text(encoding="utf-8"))


def ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def copy_assets() -> None:
    target = OUTPUT_DIR / "assets"
    if target.exists():
        shutil.rmtree(target)
    if ASSET_DIR.exists():
        shutil.copytree(ASSET_DIR, target)


def slug(value: str) -> str:
    return quote(value, safe="")


def safe_text(value: str | None, default: str = "未提供") -> str:
    cleaned = (value or "").strip()
    return cleaned if cleaned else default


def inline_markdown(text: str) -> str:
    escaped = escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    return re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda match: f'<a href="{escape(match.group(2))}" target="_blank" rel="noreferrer">{escape(match.group(1))}</a>',
        escaped,
    )


def markdown_to_html(markdown: str) -> str:
    html: list[str] = []
    paragraph: list[str] = []
    in_list = False
    in_code = False
    code_lines: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            html.append(f"<p>{inline_markdown(' '.join(paragraph))}</p>")
            paragraph = []

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            html.append("</ul>")
            in_list = False

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_code:
                html.append(f"<pre><code>{escape(chr(10).join(code_lines))}</code></pre>")
                code_lines = []
                in_code = False
            else:
                flush_paragraph()
                close_list()
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not stripped:
            flush_paragraph()
            close_list()
            continue
        if stripped.startswith("# "):
            flush_paragraph()
            close_list()
            html.append(f"<h1>{inline_markdown(stripped[2:].strip())}</h1>")
            continue
        if stripped.startswith("## "):
            flush_paragraph()
            close_list()
            html.append(f"<h2>{inline_markdown(stripped[3:].strip())}</h2>")
            continue
        if stripped.startswith("### "):
            flush_paragraph()
            close_list()
            html.append(f"<h3>{inline_markdown(stripped[4:].strip())}</h3>")
            continue
        if stripped.startswith("- "):
            flush_paragraph()
            if not in_list:
                html.append("<ul>")
                in_list = True
            html.append(f"<li>{inline_markdown(stripped[2:].strip())}</li>")
            continue
        if stripped.startswith("> "):
            flush_paragraph()
            close_list()
            html.append(f"<blockquote>{inline_markdown(stripped[2:].strip())}</blockquote>")
            continue
        paragraph.append(stripped)

    if in_code:
        html.append(f"<pre><code>{escape(chr(10).join(code_lines))}</code></pre>")
    flush_paragraph()
    close_list()
    return "\n".join(html)


def build_note_pages(items: list[dict], default_title: str = "论文笔记", back_label: str = "返回论文库") -> None:
    for item in items:
        note = item.get("analysis_note") or {}
        source = safe_text(note.get("source"), "")
        url = safe_text(note.get("url"), "")
        if not source or not url:
            continue
        source_path = ROOT / source
        output_path = OUTPUT_DIR / url
        if not source_path.exists():
            continue
        output_path.parent.mkdir(parents=True, exist_ok=True)
        markdown = source_path.read_text(encoding="utf-8")
        title = escape(safe_text(note.get("title"), item.get("title") or default_title))
        html = markdown_to_html(markdown)
        output_path.write_text(
            f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>{NOTE_CSS}</style>
</head>
<body>
  <main>
    <a class="back" href="../index.html">{escape(back_label)}</a>
    <article>{html}</article>
  </main>
</body>
</html>
""",
            encoding="utf-8",
        )


def search_blob(paper: dict) -> str:
    parts = [
        paper.get("title", ""),
        " ".join(paper.get("authors", [])),
        paper.get("venue", ""),
        paper.get("primary_area", ""),
        paper.get("category", ""),
        " ".join(paper.get("keywords", [])),
        " ".join(paper.get("labels", [])),
        paper.get("note", ""),
        paper.get("abstract", ""),
        paper.get("code_url", ""),
        (paper.get("analysis_note") or {}).get("title", ""),
        (paper.get("key_figure") or {}).get("caption", ""),
    ]
    return " ".join(part for part in parts if part)


def blog_search_blob(post: dict) -> str:
    quote_parts = []
    for quote in post.get("quotes", []):
        quote_parts.extend([quote.get("text", ""), quote.get("note", "")])
    parts = [
        post.get("title", ""),
        post.get("url", ""),
        post.get("source", ""),
        " ".join(post.get("tags", [])),
        post.get("summary", ""),
        " ".join(post.get("key_points", [])),
        " ".join(
            " ".join([item.get("name", ""), item.get("description", "")])
            for item in post.get("standards", [])
        ),
        " ".join(quote_parts),
        post.get("my_note", ""),
        (post.get("analysis_note") or {}).get("title", ""),
        (post.get("key_figure") or {}).get("caption", ""),
        " ".join(post.get("related_papers", [])),
    ]
    return " ".join(part for part in parts if part)


def project_search_blob(project: dict) -> str:
    parts = [
        project.get("name", ""),
        project.get("repo_url", ""),
        project.get("homepage_url", ""),
        project.get("docs_url", ""),
        project.get("demo_url", ""),
        project.get("source", ""),
        project.get("project_type", ""),
        project.get("domain", ""),
        " ".join(project.get("tags", [])),
        " ".join(project.get("stack", [])),
        project.get("summary", ""),
        " ".join(project.get("highlights", [])),
        " ".join(project.get("use_cases", [])),
        project.get("setup_note", ""),
        " ".join(project.get("practice_notes", [])),
        project.get("license", ""),
        project.get("maintenance", ""),
        project.get("my_note", ""),
        " ".join(project.get("related_papers", [])),
        " ".join(project.get("related_blogs", [])),
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


def key_figure_html(item: dict) -> str:
    key_figure = item.get("key_figure") or {}
    path = safe_text(key_figure.get("path"), "")
    if not path:
        return ""
    fig_type = safe_text(key_figure.get("type"), "Figure")
    name = safe_text(str(key_figure.get("name", "")), "")
    page = safe_text(str(key_figure.get("page", "")), "")
    caption = safe_text(key_figure.get("caption"), "暂无图注")
    caption_cn = safe_text(key_figure.get("caption_cn"), "")
    confidence = key_figure.get("confidence")
    review = bool(key_figure.get("needs_manual_review"))
    label = " ".join(part for part in [fig_type, name] if part).strip() or "Key figure"
    meta_parts = []
    if page:
        meta_parts.append(f"第 {escape(page)} 页")
    if isinstance(confidence, (int, float)):
        meta_parts.append(f"置信度 {confidence:.2f}")
    if review:
        meta_parts.append("建议人工复核")
    meta = " · ".join(meta_parts)
    return f"""
  <figure class="key-figure">
    <img src="{escape(path)}" alt="{escape(label)}">
    <figcaption>
      <div class="key-figure-label">{escape(label)}</div>
      <div class="key-figure-caption">{escape(caption)}</div>
      {f'<div class="key-figure-caption-cn">{escape(caption_cn)}</div>' if caption_cn else ''}
      {f'<div class="key-figure-meta">{meta}</div>' if meta else ''}
    </figcaption>
  </figure>
"""


def paper_card(paper: dict) -> str:
    title = escape(safe_text(paper.get("title"), "未命名论文"))
    paper_url = escape(safe_text(paper.get("paper_url"), "#"))
    authors = escape(", ".join(paper.get("authors", [])) or "作者待补充")
    venue = escape(safe_text(paper.get("venue")))
    year = escape(str(paper.get("year", "")) or "年份待补充")
    primary = escape(safe_text(paper.get("primary_area")))
    category = escape(safe_text(paper.get("category")))
    keywords = paper.get("keywords", [])
    labels = paper.get("labels", [])
    note = safe_text(paper.get("note"), "暂无备注")
    analysis_note = paper.get("analysis_note") or {}
    analysis_note_url = (analysis_note.get("url") or "").strip()
    analysis_note_title = safe_text(analysis_note.get("title"), "详细笔记")
    code_url = (paper.get("code_url") or "").strip()
    abstract = escape(safe_text(paper.get("abstract"), "暂无摘要"))
    tldr = escape(safe_text(paper.get("tldr"), "待补充一句话定位"))
    summary = paper.get("summary_cn") or {}
    key_figure = paper.get("key_figure") or {}
    keyword_html = "".join(f'<span class="badge">{escape(item)}</span>' for item in keywords)
    label_html = "".join(f'<span class="badge label">{escape(item)}</span>' for item in labels)
    code_html = (
        f'<a href="{escape(code_url)}" target="_blank" rel="noreferrer">{escape(code_url)}</a>'
        if code_url
        else "暂无代码链接"
    )
    analysis_note_html = (
        f'<a class="note-link" href="{escape(analysis_note_url)}" target="_blank" rel="noreferrer">{escape(analysis_note_title)}</a>'
        if analysis_note_url
        else "暂无详细笔记"
    )
    return f"""
<article class="paper" data-search="{escape(search_blob(paper))}" data-has-code="{str(bool(code_url)).lower()}" data-has-note="{str(bool((paper.get('note') or '').strip())).lower()}" data-has-key-figure="{str(bool((key_figure.get('path') or '').strip())).lower()}">
  <div class="paper-title"><a href="{paper_url}" target="_blank" rel="noreferrer">{title}</a></div>
  <div class="paper-meta">
    <span class="badge">{primary}</span>
    <span class="badge">{category}</span>
    <span>{authors}</span> · <span>{venue}</span> · <span>{year}</span>
  </div>
  <div class="paper-tldr"><b>TL;DR</b> {tldr}</div>
  {key_figure_html(paper)}
  {summary_html(summary)}
  <div class="paper-extra">
    <div class="extra-row"><div class="label">标签</div><div class="value">{label_html or "暂无标签"}</div></div>
    <div class="extra-row"><div class="label">关键词</div><div class="value">{keyword_html or "暂无关键词"}</div></div>
    <div class="extra-row"><div class="label">代码仓库</div><div class="value">{code_html}</div></div>
    <div class="extra-row"><div class="label">详细笔记</div><div class="value">{analysis_note_html}</div></div>
    <div class="extra-row"><div class="label">我的备注</div><div class="value">{escape(note)}</div></div>
  </div>
  <span class="toggle-abs" onclick="this.parentElement.classList.toggle('expanded')">查看 Abstract</span>
  <div class="full-abs">{abstract}</div>
</article>
"""


def blog_card(post: dict, papers_by_id: dict[str, dict]) -> str:
    title = escape(safe_text(post.get("title"), "未命名技术分享"))
    url = escape(safe_text(post.get("url"), "#"))
    source = escape(safe_text(post.get("source"), "来源待补充"))
    published_at = escape(safe_text(post.get("published_at"), "发布时间待补充"))
    added_at = escape(safe_text(post.get("added_at"), "入库时间待补充"))
    summary = escape(safe_text(post.get("summary"), "主要内容待补充"))
    my_note = escape(safe_text(post.get("my_note"), "暂无备注"))
    tags = post.get("tags", [])
    key_points = post.get("key_points", [])[:BLOG_KEY_POINTS_LIMIT]
    standards = post.get("standards", [])
    quotes = post.get("quotes", [])
    related_papers = post.get("related_papers", [])
    key_figure = post.get("key_figure") or {}
    analysis_note = post.get("analysis_note") or {}
    analysis_note_url = (analysis_note.get("url") or "").strip()
    analysis_note_title = safe_text(analysis_note.get("title"), "详细笔记")
    tag_html = "".join(f'<span class="badge">{escape(item)}</span>' for item in tags)
    points_html = "".join(f"<li>{escape(item)}</li>" for item in key_points)
    standards_html = "".join(
        f'<tr><td class="term">{escape(safe_text(item.get("name"), "标准待补充"))}</td>'
        f'<td>{escape(safe_text(item.get("description"), "说明待补充"))}</td></tr>'
        for item in standards
    )
    quote_html = "".join(
        f'<div class="quote-row"><div>{escape(safe_text(item.get("text"), "关键语句待补充"))}</div>'
        f'<div class="quote-note">{escape(safe_text(item.get("note"), "暂无说明"))}</div></div>'
        for item in quotes
    )
    related_html = []
    for paper_id in related_papers:
        paper = papers_by_id.get(paper_id, {})
        label = paper.get("title") or paper_id
        related_html.append(
            f'<a class="badge label" href="{escape(safe_text(paper.get("paper_url"), "#"))}" target="_blank" rel="noreferrer">{escape(label)}</a>'
        )
    analysis_note_html = (
        f'<a class="note-link" href="{escape(analysis_note_url)}" target="_blank" rel="noreferrer">{escape(analysis_note_title)}</a>'
        if analysis_note_url
        else "暂无详细笔记"
    )
    return f"""
<article class="blog" data-search="{escape(blog_search_blob(post))}" data-has-related="{str(bool(related_papers)).lower()}" data-has-quotes="{str(bool(quotes)).lower()}" data-has-key-figure="{str(bool((key_figure.get('path') or '').strip())).lower()}">
  <div class="blog-title"><a href="{url}" target="_blank" rel="noreferrer">{title}</a></div>
  <div class="blog-meta">{source} · 发布：{published_at} · 入库：{added_at}</div>
  <div>{tag_html or '<span class="badge">未打标签</span>'}</div>
  <div class="blog-summary">{summary}</div>
  {key_figure_html(post)}
  <div class="blog-block">
    <h4>关键要点</h4>
    <ul class="blog-points">{points_html or '<li>待补充</li>'}</ul>
  </div>
  {f'<div class="blog-block"><h4>难度标准</h4><table class="blog-table"><thead><tr><th>标准</th><th>含义</th></tr></thead><tbody>{standards_html}</tbody></table></div>' if standards_html else ''}
  <div class="blog-block">
    <h4>关键语句</h4>
    {quote_html or '<div class="quote-row">暂无关键语句</div>'}
  </div>
  <div class="blog-block">
    <h4>我的备注</h4>
    <div class="blog-summary">{my_note}</div>
  </div>
  <div class="blog-block">
    <h4>详细笔记</h4>
    <div class="related-links">{analysis_note_html}</div>
  </div>
  <div class="blog-block">
    <h4>关联论文</h4>
    <div class="related-links">{"".join(related_html) or "暂无关联论文"}</div>
  </div>
</article>
"""


def project_card(project: dict, papers_by_id: dict[str, dict], blogs_by_id: dict[str, dict]) -> str:
    name = escape(safe_text(project.get("name"), "未命名代码项目"))
    repo_url = (project.get("repo_url") or "").strip()
    homepage_url = (project.get("homepage_url") or "").strip()
    docs_url = (project.get("docs_url") or "").strip()
    demo_url = (project.get("demo_url") or "").strip()
    source = escape(safe_text(project.get("source"), "来源待补充"))
    added_at = escape(safe_text(project.get("added_at"), "入库时间待补充"))
    project_type = escape(safe_text(project.get("project_type"), "类型待补充"))
    domain = escape(safe_text(project.get("domain"), "领域待补充"))
    summary = escape(safe_text(project.get("summary"), "项目简介待补充"))
    setup_note = escape(safe_text(project.get("setup_note"), "暂无安装或使用备注"))
    license_name = escape(safe_text(project.get("license"), "许可证待补充"))
    maintenance = escape(safe_text(project.get("maintenance"), "维护状态待补充"))
    my_note = escape(safe_text(project.get("my_note"), "暂无备注"))
    tags = project.get("tags", [])
    stack = project.get("stack", [])
    highlights = project.get("highlights", [])
    use_cases = project.get("use_cases", [])
    practice_notes = project.get("practice_notes", [])
    related_papers = project.get("related_papers", [])
    related_blogs = project.get("related_blogs", [])
    title_url = repo_url or homepage_url or docs_url or demo_url or "#"
    tag_html = "".join(f'<span class="badge">{escape(item)}</span>' for item in tags)
    stack_html = "".join(f'<span class="badge label">{escape(item)}</span>' for item in stack)
    highlights_html = "".join(f"<li>{escape(item)}</li>" for item in highlights)
    use_cases_html = "".join(f"<li>{escape(item)}</li>" for item in use_cases)
    practice_notes_html = "".join(f"<li>{escape(item)}</li>" for item in practice_notes)
    link_items = []
    for label, url in [
        ("Repo", repo_url),
        ("Homepage", homepage_url),
        ("Docs", docs_url),
        ("Demo", demo_url),
    ]:
        if url:
            link_items.append(
                f'<a class="badge" href="{escape(url)}" target="_blank" rel="noreferrer">{escape(label)}</a>'
            )
    related_items = []
    for paper_id in related_papers:
        paper = papers_by_id.get(paper_id, {})
        label = paper.get("title") or paper_id
        related_items.append(
            f'<a class="badge label" href="{escape(safe_text(paper.get("paper_url"), "#"))}" target="_blank" rel="noreferrer">{escape(label)}</a>'
        )
    for blog_id in related_blogs:
        post = blogs_by_id.get(blog_id, {})
        label = post.get("title") or blog_id
        related_items.append(
            f'<a class="badge label" href="{escape(safe_text(post.get("url"), "#"))}" target="_blank" rel="noreferrer">{escape(label)}</a>'
        )
    return f"""
<article class="project" data-search="{escape(project_search_blob(project))}" data-has-links="{str(bool(homepage_url or docs_url or demo_url)).lower()}" data-has-related="{str(bool(related_papers or related_blogs)).lower()}">
  <div class="project-title"><a href="{escape(title_url)}" target="_blank" rel="noreferrer">{name}</a></div>
  <div class="project-meta">{source} · 入库：{added_at} · {project_type} · {domain}</div>
  <div>{tag_html or '<span class="badge">未打标签</span>'} {stack_html}</div>
  <div class="project-summary">{summary}</div>
  <div class="project-block">
    <h4>项目链接</h4>
    <div class="project-links">{"".join(link_items) or "暂无项目链接"}</div>
  </div>
  <div class="project-block">
    <h4>亮点</h4>
    <ul class="project-points">{highlights_html or '<li>待补充</li>'}</ul>
  </div>
  <div class="project-block">
    <h4>适用场景</h4>
    <ul class="project-points">{use_cases_html or '<li>待补充</li>'}</ul>
  </div>
  <div class="project-block">
    <h4>使用备注</h4>
    <div class="project-summary">{setup_note}</div>
  </div>
  <div class="project-block">
    <h4>实践案例</h4>
    <ul class="project-points">{practice_notes_html or '<li>待补充</li>'}</ul>
  </div>
  <div class="project-block">
    <h4>维护信息</h4>
    <div class="project-summary">许可证：{license_name} · 维护状态：{maintenance}</div>
  </div>
  <div class="project-block">
    <h4>我的备注</h4>
    <div class="project-summary">{my_note}</div>
  </div>
  <div class="project-block">
    <h4>关联内容</h4>
    <div class="project-links">{"".join(related_items) or "暂无关联内容"}</div>
  </div>
</article>
"""


def render_blog_section(posts: list[dict], papers: list[dict]) -> str:
    approved_posts = [
        post for post in posts
        if (post.get("status") or "approved") == "approved"
    ]
    papers_by_id = {paper.get("id"): paper for paper in papers if paper.get("id")}
    source_links_html = "".join(
        (
            f'<div class="blog-source-item"><a href="{escape(item["url"])}" '
            f'target="_blank" rel="noreferrer">{escape(item["name"])}</a>'
            f'<span>{escape(item["note"])}</span></div>'
        )
        for item in BLOG_SITE_LINKS
    )
    source_section = f"""
<section class="blog-source-links">
  <h3>常用 Blog 网址</h3>
  <div class="blog-source-grid">{source_links_html}</div>
</section>
"""
    if not approved_posts:
        return f"""
{source_section}
<section>
  <div class="empty">
    技术分享库还没有正式内容。之后你发来网页链接时，我会先生成待审版本：主要内容、关键要点、关键语句、标签和关联论文建议；你确认后再入库发布。
  </div>
</section>
"""
    cards_html = "".join(blog_card(post, papers_by_id) for post in approved_posts)
    return f'{source_section}<section class="blog-list">{cards_html}</section>'


def render_project_section(projects: list[dict], papers: list[dict], posts: list[dict]) -> str:
    approved_projects = [
        project for project in projects
        if (project.get("status") or "approved") == "approved"
    ]
    papers_by_id = {paper.get("id"): paper for paper in papers if paper.get("id")}
    blogs_by_id = {post.get("id"): post for post in posts if post.get("id")}
    if not approved_projects:
        return """
<section>
  <div class="empty">
    代码项目库还没有正式内容。之后你发来 GitHub 或项目链接时，我会先生成待审版本：项目定位、技术栈、亮点、适用场景、使用备注和关联论文/技术分享；你确认后再入库发布。
  </div>
</section>
"""
    cards_html = "".join(project_card(project, papers_by_id, blogs_by_id) for project in approved_projects)
    return f'<section class="project-list">{cards_html}</section>'


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
    taxonomy_primary_names = {entry["primary_area"] for entry in taxonomy}
    ordered_primary_entries = [
        *taxonomy,
        *(
            {"primary_area": primary, "subcategories": []}
            for primary in sorted(grouped)
            if primary not in taxonomy_primary_names
        ),
    ]

    for primary_entry in ordered_primary_entries:
        primary = primary_entry["primary_area"]
        subcategories = primary_entry["subcategories"]
        primary_id = f"pri-{slug(primary)}"
        extra_subcategories = sorted(sub for sub in grouped[primary] if sub not in subcategories)
        display_subcategories = [
            *(sub for sub in subcategories if grouped[primary][sub]),
            *extra_subcategories,
        ]
        primary_count = sum(len(grouped[primary][sub]) for sub in display_subcategories)
        if primary_count == 0:
            continue
        nav_sub_links = []
        sub_sections = []

        for sub in display_subcategories:
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


def render_page(library: dict, blogs: dict, projects_data: dict) -> str:
    site = library["site"]
    papers = [
        paper for paper in library["papers"]
        if (paper.get("status") or "approved") == "approved"
    ]
    posts = [
        post for post in blogs.get("posts", [])
        if (post.get("status") or "approved") == "approved"
    ]
    projects = [
        project for project in projects_data.get("projects", [])
        if (project.get("status") or "approved") == "approved"
    ]
    library = {**library, "papers": papers}
    nav_html, main_html = render_sections(library)
    blog_html = render_blog_section(posts, papers)
    project_html = render_project_section(projects, papers, posts)
    counter = Counter()
    counter["all"] = len(papers)
    counter["with_code"] = sum(1 for item in papers if (item.get("code_url") or "").strip())
    counter["with_note"] = sum(1 for item in papers if (item.get("note") or "").strip())
    counter["with_key_figure"] = sum(
        1 for item in papers
        if ((item.get("key_figure") or {}).get("path") or "").strip()
    )
    counter["blogs"] = len(posts)
    counter["blogs_with_related"] = sum(1 for item in posts if item.get("related_papers"))
    counter["blogs_with_quotes"] = sum(1 for item in posts if item.get("quotes"))
    counter["blogs_with_key_figure"] = sum(
        1 for item in posts
        if ((item.get("key_figure") or {}).get("path") or "").strip()
    )
    counter["projects"] = len(projects)
    counter["projects_with_links"] = sum(
        1 for item in projects
        if (item.get("homepage_url") or item.get("docs_url") or item.get("demo_url"))
    )
    counter["projects_with_related"] = sum(
        1 for item in projects
        if item.get("related_papers") or item.get("related_blogs")
    )
    counter["project_stack"] = len({tech for project in projects for tech in project.get("stack", [])})
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
      <div class="view-tabs">
        <button class="view-tab active" data-view="papers">论文库</button>
        <button class="view-tab" data-view="blogs">技术分享</button>
        <button class="view-tab" data-view="projects">代码项目</button>
      </div>
      <input id="search" type="search" placeholder="搜索论文标题 / 关键词 / 备注 / abstract">
      <div class="sidebar-panel" data-view="papers">
        <div class="stat-grid">
          <div class="stat-box"><b>{len(papers)}</b>论文总数</div>
          <div class="stat-box"><b>{len(library['taxonomy'])}</b>一级分类</div>
          <div class="stat-box"><b>{counter['with_code']}</b>含代码链接</div>
          <div class="stat-box"><b>{counter['with_note']}</b>含个人备注</div>
          <div class="stat-box"><b>{counter['with_key_figure']}</b>含关键图</div>
        </div>
        <div class="nav-tree">{nav_html}</div>
      </div>
      <div class="sidebar-panel hidden" data-view="blogs">
        <div class="stat-grid">
          <div class="stat-box"><b>{counter['blogs']}</b>技术分享</div>
          <div class="stat-box"><b>{counter['blogs_with_quotes']}</b>含关键语句</div>
          <div class="stat-box"><b>{counter['blogs_with_related']}</b>关联论文</div>
          <div class="stat-box"><b>{counter['blogs_with_key_figure']}</b>含关键图</div>
          <div class="stat-box"><b>{len({tag for post in posts for tag in post.get('tags', [])})}</b>标签数</div>
        </div>
      </div>
      <div class="sidebar-panel hidden" data-view="projects">
        <div class="stat-grid">
          <div class="stat-box"><b>{counter['projects']}</b>代码项目</div>
          <div class="stat-box"><b>{counter['projects_with_links']}</b>含文档/Demo</div>
          <div class="stat-box"><b>{counter['projects_with_related']}</b>关联内容</div>
          <div class="stat-box"><b>{counter['project_stack']}</b>技术栈</div>
        </div>
      </div>
    </aside>
    <main class="main">
      <header class="main-header">
        <h1>{escape(site['name'])}</h1>
        <p>这是一个按两级目录组织的个人静态论文库，并补充记录网上读到的技术分享与代码项目。所有内容都采用先审阅、再入库的长期维护流程。</p>
        <div class="filter-row" data-view="papers">
          <button class="filter-chip active" data-view="papers" data-filter="__all__">全部 {counter['all']} 篇</button>
          <button class="filter-chip" data-view="papers" data-filter="with-code">含代码 {counter['with_code']} 篇</button>
          <button class="filter-chip" data-view="papers" data-filter="with-note">含备注 {counter['with_note']} 篇</button>
          <button class="filter-chip" data-view="papers" data-filter="with-key-figure">含关键图 {counter['with_key_figure']} 篇</button>
        </div>
        <div class="filter-row hidden" data-view="blogs">
          <button class="filter-chip active" data-view="blogs" data-filter="__all__">全部 {counter['blogs']} 篇</button>
          <button class="filter-chip" data-view="blogs" data-filter="with-quotes">含关键语句 {counter['blogs_with_quotes']} 篇</button>
          <button class="filter-chip" data-view="blogs" data-filter="with-related">关联论文 {counter['blogs_with_related']} 篇</button>
          <button class="filter-chip" data-view="blogs" data-filter="with-key-figure">含关键图 {counter['blogs_with_key_figure']} 篇</button>
        </div>
        <div class="filter-row hidden" data-view="projects">
          <button class="filter-chip active" data-view="projects" data-filter="__all__">全部 {counter['projects']} 个</button>
          <button class="filter-chip" data-view="projects" data-filter="with-links">含文档/Demo {counter['projects_with_links']} 个</button>
          <button class="filter-chip" data-view="projects" data-filter="with-related">关联内容 {counter['projects_with_related']} 个</button>
        </div>
        <div class="meta">论文总结维度固定为：研究动机 / 解决问题 / 现象分析 / 主要方法 / 数据集与实验 / 主要贡献。技术分享记录主要内容、关键要点、关键语句和个人备注。代码项目记录技术栈、亮点、适用场景和关联内容。最近构建时间：{generated_at}</div>
      </header>
      <div class="view-panel" data-view="papers">{main_html}</div>
      <div class="view-panel hidden" data-view="blogs">{blog_html}</div>
      <div class="view-panel hidden" data-view="projects">{project_html}</div>
      <footer>GitHub Pages 目标仓库：{escape(site['repo'])}</footer>
    </main>
  </div>
  <script>{JS}</script>
</body>
</html>
"""


def main() -> None:
    library = load_library()
    blogs = load_blogs()
    projects = load_projects()
    ensure_output_dir()
    copy_assets()
    build_note_pages(library.get("papers", []), default_title="论文笔记", back_label="返回论文库")
    build_note_pages(blogs.get("posts", []), default_title="技术分享笔记", back_label="返回论文库")
    OUTPUT_FILE.write_text(render_page(library, blogs, projects), encoding="utf-8")
    print(f"Built {OUTPUT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
