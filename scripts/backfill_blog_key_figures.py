from __future__ import annotations

import argparse
import json
import re
import shutil
import time
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlparse, urlsplit, urlunsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
BLOG_FILE = ROOT / "data" / "blogs.json"
ASSET_DIR = ROOT / "assets" / "blog_images"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

IMAGE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
}

LOW_VALUE_URL_TERMS = {
    "avatar",
    "badge",
    "brand",
    "button",
    "favicon",
    "icon",
    "logo",
    "profile",
    "sprite",
}

MANUAL_IMAGE_OVERRIDES = {
    "aws-bedrock-synthetic-rag-evaluation": {
        "url": "https://d2908q01vomqb2.cloudfront.net/f1f836cb4ea6efb2a0b1b99f41ad8b103eff4b59/2024/09/09/generation-overview-ML-16558.jpg",
        "caption": "Synthetic dataset generation workflow",
    },
}

MANUAL_SVG_OVERRIDES = {
    "minimax-ma-jiaqi-glitch-token": {
        "caption": "Sparse token forgetting after post-training",
        "svg": """
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="620" viewBox="0 0 1200 620">
  <rect width="1200" height="620" fill="#fbfcfd"/>
  <text x="70" y="78" font-family="Arial, sans-serif" font-size="34" font-weight="700" fill="#0d5b55">Sparse token forgetting after SFT</text>
  <text x="70" y="122" font-family="Arial, sans-serif" font-size="18" fill="#637282">The model still understands the token, but the output head stops generating it reliably.</text>
  <rect x="80" y="190" width="250" height="130" rx="14" fill="#eef3f8" stroke="#d7dee7"/>
  <text x="124" y="240" font-family="Arial, sans-serif" font-size="24" font-weight="700" fill="#1e2933">Input embedding</text>
  <text x="124" y="278" font-family="Arial, sans-serif" font-size="18" fill="#637282">semantic memory intact</text>
  <path d="M340 255 H505" stroke="#0f766e" stroke-width="6" marker-end="url(#arrow)"/>
  <rect x="520" y="190" width="250" height="130" rx="14" fill="#fff7dd" stroke="#d0a82f"/>
  <text x="585" y="240" font-family="Arial, sans-serif" font-size="24" font-weight="700" fill="#6c5400">SFT data</text>
  <text x="572" y="278" font-family="Arial, sans-serif" font-size="18" fill="#6c5400">rare token appears &lt; 5 times</text>
  <path d="M780 255 H945" stroke="#0f766e" stroke-width="6" marker-end="url(#arrow)"/>
  <rect x="960" y="190" width="180" height="130" rx="14" fill="#ffe6d8" stroke="#e7a17a"/>
  <text x="998" y="240" font-family="Arial, sans-serif" font-size="24" font-weight="700" fill="#8a3b12">lm_head</text>
  <text x="984" y="278" font-family="Arial, sans-serif" font-size="18" fill="#8a3b12">output vector drifts</text>
  <rect x="210" y="405" width="780" height="96" rx="16" fill="#ffffff" stroke="#d7dee7"/>
  <text x="252" y="445" font-family="Arial, sans-serif" font-size="22" font-weight="700" fill="#1e2933">Failure mode</text>
  <text x="252" y="478" font-family="Arial, sans-serif" font-size="18" fill="#44515e">Prompt can point to the person, but decoding avoids the exact name token.</text>
  <defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#0f766e"/></marker></defs>
</svg>
""",
    },
    "redhat-sdg-hub-rag-evaluation": {
        "caption": "RAG evaluation dataset generation pipeline supported by SDG Hub",
        "svg": """
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="620" viewBox="0 0 1200 620">
  <rect width="1200" height="620" fill="#fbfcfd"/>
  <text x="70" y="78" font-family="Arial, sans-serif" font-size="34" font-weight="700" fill="#0d5b55">RAG evaluation dataset flow</text>
  <text x="70" y="122" font-family="Arial, sans-serif" font-size="18" fill="#637282">SDG Hub turns source documents into grounded QA-context triplets for offline RAG testing.</text>
  <g font-family="Arial, sans-serif" font-size="20" font-weight="700" fill="#1e2933">
    <rect x="90" y="210" width="185" height="92" rx="12" fill="#eef3f8" stroke="#d7dee7"/><text x="130" y="264">Document</text>
    <rect x="335" y="210" width="185" height="92" rx="12" fill="#eef3f8" stroke="#d7dee7"/><text x="378" y="264">Topic</text>
    <rect x="580" y="210" width="185" height="92" rx="12" fill="#fff7dd" stroke="#d0a82f"/><text x="616" y="250">Question</text><text x="620" y="276">evolution</text>
    <rect x="825" y="210" width="185" height="92" rx="12" fill="#fff7dd" stroke="#d0a82f"/><text x="858" y="250">Grounded</text><text x="872" y="276">answer</text>
    <rect x="457" y="395" width="285" height="92" rx="12" fill="#d9f1ee" stroke="#0f766e"/><text x="493" y="450">ground_truth_context</text>
  </g>
  <g stroke="#0f766e" stroke-width="5" marker-end="url(#arrow)">
    <path d="M280 256 H330"/>
    <path d="M525 256 H575"/>
    <path d="M770 256 H820"/>
    <path d="M918 306 C910 360 780 425 748 440"/>
  </g>
  <text x="360" y="540" font-family="Arial, sans-serif" font-size="18" fill="#44515e">Output: question, response, and exact source context for retrieval and faithfulness checks.</text>
  <defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#0f766e"/></marker></defs>
</svg>
""",
    },
    "microsoft-golden-dataset-rag-evaluation": {
        "caption": "Silver-to-golden dataset workflow for RAG evaluation",
        "svg": """
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="620" viewBox="0 0 1200 620">
  <rect width="1200" height="620" fill="#fbfcfd"/>
  <text x="70" y="78" font-family="Arial, sans-serif" font-size="34" font-weight="700" fill="#0d5b55">From silver data to a golden RAG dataset</text>
  <text x="70" y="122" font-family="Arial, sans-serif" font-size="18" fill="#637282">Generate candidate QA pairs, evaluate them, then refine the benchmark with human review.</text>
  <g font-family="Arial, sans-serif">
    <rect x="95" y="220" width="205" height="110" rx="14" fill="#eef3f8" stroke="#d7dee7"/>
    <text x="140" y="265" font-size="24" font-weight="700" fill="#1e2933">Source docs</text>
    <text x="128" y="298" font-size="17" fill="#637282">chunks + citations</text>
    <rect x="370" y="220" width="205" height="110" rx="14" fill="#fff7dd" stroke="#d0a82f"/>
    <text x="415" y="265" font-size="24" font-weight="700" fill="#6c5400">Silver QA</text>
    <text x="403" y="298" font-size="17" fill="#6c5400">AI-generated set</text>
    <rect x="645" y="220" width="205" height="110" rx="14" fill="#eef3f8" stroke="#d7dee7"/>
    <text x="684" y="265" font-size="24" font-weight="700" fill="#1e2933">AI checks</text>
    <text x="675" y="298" font-size="17" fill="#637282">groundedness etc.</text>
    <rect x="920" y="220" width="205" height="110" rx="14" fill="#d9f1ee" stroke="#0f766e"/>
    <text x="947" y="265" font-size="24" font-weight="700" fill="#0d5b55">Golden set</text>
    <text x="954" y="298" font-size="17" fill="#0d5b55">reviewed benchmark</text>
  </g>
  <g stroke="#0f766e" stroke-width="5" marker-end="url(#arrow)">
    <path d="M305 275 H365"/>
    <path d="M580 275 H640"/>
    <path d="M855 275 H915"/>
  </g>
  <rect x="310" y="425" width="580" height="80" rx="14" fill="#ffffff" stroke="#d7dee7"/>
  <text x="356" y="474" font-family="Arial, sans-serif" font-size="20" fill="#44515e">Review low-score samples and iterate until the dataset is trustworthy.</text>
  <defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#0f766e"/></marker></defs>
</svg>
""",
    },
    "lmsys-minimax-m2-efficient-attention": {
        "caption": "Efficient attention trade-offs in MiniMax M2",
        "svg": """
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="620" viewBox="0 0 1200 620">
  <rect width="1200" height="620" fill="#fbfcfd"/>
  <text x="70" y="78" font-family="Arial, sans-serif" font-size="34" font-weight="700" fill="#0d5b55">Efficient attention is not a free lunch</text>
  <text x="70" y="122" font-family="Arial, sans-serif" font-size="18" fill="#637282">MiniMax M2 returned to full attention after evaluating quality, infrastructure, and serving constraints.</text>
  <g font-family="Arial, sans-serif">
    <rect x="90" y="210" width="250" height="118" rx="14" fill="#eef3f8" stroke="#d7dee7"/>
    <text x="126" y="258" font-size="24" font-weight="700" fill="#1e2933">Efficient attention</text>
    <text x="124" y="292" font-size="17" fill="#637282">lower theoretical cost</text>
    <rect x="475" y="190" width="250" height="158" rx="14" fill="#fff7dd" stroke="#d0a82f"/>
    <text x="532" y="236" font-size="24" font-weight="700" fill="#6c5400">Reality checks</text>
    <text x="515" y="272" font-size="17" fill="#6c5400">harder evals</text>
    <text x="515" y="300" font-size="17" fill="#6c5400">memory-bound kernels</text>
    <text x="515" y="328" font-size="17" fill="#6c5400">cache + speculation</text>
    <rect x="860" y="210" width="250" height="118" rx="14" fill="#d9f1ee" stroke="#0f766e"/>
    <text x="913" y="258" font-size="24" font-weight="700" fill="#0d5b55">Full attention</text>
    <text x="902" y="292" font-size="17" fill="#0d5b55">production robustness</text>
  </g>
  <g stroke="#0f766e" stroke-width="5" marker-end="url(#arrow)">
    <path d="M345 269 H470"/>
    <path d="M730 269 H855"/>
  </g>
  <rect x="270" y="430" width="660" height="88" rx="14" fill="#ffffff" stroke="#d7dee7"/>
  <text x="320" y="482" font-family="Arial, sans-serif" font-size="20" fill="#44515e">The winning architecture depends on evaluation, data, and mature systems support.</text>
  <defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#0f766e"/></marker></defs>
</svg>
""",
    },
}

TECH_FIGURE_TERMS = {
    "architecture",
    "benchmark",
    "chart",
    "diagram",
    "evaluation",
    "figure",
    "framework",
    "graph",
    "pipeline",
    "result",
    "schema",
    "screenshot",
    "workflow",
}


class BlogImageParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title = ""
        self.in_title = False
        self.meta: dict[str, str] = {}
        self.images: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key.lower(): (value or "") for key, value in attrs}
        if tag.lower() == "title":
            self.in_title = True
            return
        if tag.lower() == "meta":
            key = (attrs_dict.get("property") or attrs_dict.get("name") or "").strip().lower()
            content = attrs_dict.get("content", "").strip()
            if key and content:
                self.meta[key] = unescape(content)
            return
        if tag.lower() == "link":
            rel = attrs_dict.get("rel", "").lower()
            href = attrs_dict.get("href", "").strip()
            if href and "image_src" in rel:
                self.meta["link:image_src"] = urljoin(self.base_url, href)
            return
        if tag.lower() != "img":
            return
        src = image_src_from_attrs(attrs_dict)
        if not src:
            return
        self.images.append(
            {
                "url": urljoin(self.base_url, src),
                "alt": unescape(attrs_dict.get("alt", "").strip()),
                "title": unescape(attrs_dict.get("title", "").strip()),
                "width": parse_int(attrs_dict.get("width", "")),
                "height": parse_int(attrs_dict.get("height", "")),
                "class": attrs_dict.get("class", ""),
                "source": "img",
            }
        )

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title += data


def parse_int(value: str) -> int | None:
    match = re.search(r"\d+", value or "")
    return int(match.group(0)) if match else None


def image_src_from_attrs(attrs: dict[str, str]) -> str:
    for key in ("src", "data-src", "data-original", "data-lazy-src"):
        value = attrs.get(key, "").strip()
        if value and not value.startswith("data:"):
            return value
    srcset = attrs.get("srcset", "").strip() or attrs.get("data-srcset", "").strip()
    if not srcset:
        return ""
    candidates = []
    for part in srcset.split(","):
        tokens = part.strip().split()
        if not tokens:
            continue
        weight = 1.0
        if len(tokens) > 1:
            descriptor = tokens[-1]
            if descriptor.endswith("w"):
                weight = float(parse_int(descriptor) or 1)
            elif descriptor.endswith("x"):
                try:
                    weight = float(descriptor[:-1])
                except ValueError:
                    weight = 1.0
        candidates.append((weight, tokens[0]))
    return max(candidates, default=(0, ""))[1]


def load_blogs() -> dict[str, Any]:
    return json.loads(BLOG_FILE.read_text(encoding="utf-8"))


def save_blogs(blogs: dict[str, Any]) -> None:
    BLOG_FILE.write_text(json.dumps(blogs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def http_get(url: str, *, timeout: int = 40, referer: str = "") -> tuple[bytes, str]:
    url = iri_to_uri(url)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    }
    if referer:
        headers["Referer"] = referer
    req = Request(
        url,
        headers=headers,
    )
    with urlopen(req, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
        return response.read(), content_type


def iri_to_uri(url: str) -> str:
    parts = urlsplit(url.strip())
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc.encode("idna").decode("ascii"),
            quote(parts.path, safe="/%:@"),
            quote(parts.query, safe="=&?/%:@,+"),
            quote(parts.fragment, safe="=&?/%:@,+"),
        )
    )


def parse_page(url: str) -> tuple[BlogImageParser, str]:
    raw, content_type = http_get(url)
    charset = "utf-8"
    if "text/html" not in content_type and content_type:
        raise RuntimeError(f"page is not HTML: {content_type}")
    parser = BlogImageParser(url)
    parser.feed(raw.decode(charset, errors="replace"))
    return parser, raw.decode(charset, errors="replace")


def meta_candidates(parser: BlogImageParser) -> list[dict[str, Any]]:
    candidates = []
    for key, score in [
        ("og:image", 90),
        ("og:image:secure_url", 88),
        ("twitter:image", 82),
        ("twitter:image:src", 82),
        ("link:image_src", 76),
    ]:
        value = parser.meta.get(key, "").strip()
        if value:
            candidates.append(
                {
                    "url": urljoin(parser.base_url, value),
                    "alt": parser.meta.get("og:image:alt", "") or parser.meta.get("twitter:image:alt", ""),
                    "title": parser.meta.get("og:title", "") or parser.title.strip(),
                    "source": key,
                    "score": score,
                }
            )
    return candidates


def score_image(candidate: dict[str, Any]) -> float:
    url = candidate.get("url", "")
    text = " ".join(
        str(candidate.get(key) or "")
        for key in ("url", "alt", "title", "class", "source")
    ).lower()
    score = float(candidate.get("score") or 35)
    width = candidate.get("width")
    height = candidate.get("height")
    if isinstance(width, int) and isinstance(height, int):
        area = width * height
        if area >= 160000:
            score += 20
        elif area < 20000:
            score -= 30
        aspect = width / max(height, 1)
        if 0.5 <= aspect <= 3.2:
            score += 6
    for term in TECH_FIGURE_TERMS:
        if term in text:
            score += 8
    for term in LOW_VALUE_URL_TERMS:
        if term in text:
            score -= 22
    if re.search(r"\.(svg|ico)(?:$|[?#])", urlparse(url).path, re.I):
        score -= 18
    return score


def dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    unique = []
    for candidate in candidates:
        url = candidate.get("url", "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        candidate["score"] = score_image(candidate)
        unique.append(candidate)
    return sorted(unique, key=lambda item: item.get("score", 0), reverse=True)


def extension_from(url: str, content_type: str) -> str:
    if content_type in IMAGE_EXTENSIONS:
        return IMAGE_EXTENSIONS[content_type]
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    return ".jpg"


def safe_asset_stem(blog_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", blog_id).strip("-").lower() or "blog-image"


def download_selected_image(blog_id: str, candidates: list[dict[str, Any]], *, referer: str = "") -> tuple[dict[str, Any], Path]:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    last_error = ""
    for candidate in candidates:
        url = candidate["url"]
        try:
            raw, content_type = http_get(url, timeout=45, referer=referer)
            if not (content_type.startswith("image/") or looks_like_svg(raw)):
                last_error = f"{url}: not an image ({content_type})"
                continue
            if len(raw) < 2048 and not looks_like_svg(raw):
                last_error = f"{url}: image too small"
                continue
            ext = extension_from(url, content_type)
            asset_path = ASSET_DIR / f"{safe_asset_stem(blog_id)}{ext}"
            asset_path.write_bytes(raw)
            return {**candidate, "content_type": content_type, "size": len(raw)}, asset_path
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last_error = f"{url}: {exc}"
            continue
    raise RuntimeError(last_error or "no downloadable image candidates")


def looks_like_svg(raw: bytes) -> bool:
    head = raw[:300].lstrip().lower()
    return head.startswith(b"<svg") or b"<svg" in head


def caption_for(post: dict[str, Any], parser: BlogImageParser, candidate: dict[str, Any]) -> str:
    candidate_text = str(candidate.get("alt") or candidate.get("title") or "").strip()
    if candidate_text:
        return candidate_text
    page_title = parser.meta.get("og:title", "").strip() or parser.title.strip()
    if page_title:
        return f"来源页面代表图：{page_title}"
    return f"来源页面代表图：{post.get('title', '')}".strip()


def build_key_figure(post: dict[str, Any], parser: BlogImageParser, candidate: dict[str, Any], asset_path: Path) -> dict[str, Any]:
    return {
        "type": "Blog image",
        "name": "",
        "page": None,
        "path": str(asset_path.relative_to(ROOT)),
        "caption": caption_for(post, parser, candidate),
        "caption_cn": "",
        "source": candidate.get("source", "web-page-image"),
        "source_url": candidate.get("url", ""),
        "confidence": min(max(float(candidate.get("score", 0)) / 100, 0.0), 1.0),
        "needs_manual_review": True,
    }


def build_manual_svg_key_figure(post: dict[str, Any], override: dict[str, str]) -> tuple[dict[str, Any], Path]:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    asset_path = ASSET_DIR / f"{safe_asset_stem(post['id'])}.svg"
    asset_path.write_text(override["svg"].strip() + "\n", encoding="utf-8")
    return (
        {
            "type": "Blog image",
            "name": "",
            "page": None,
            "path": str(asset_path.relative_to(ROOT)),
            "caption": override["caption"],
            "caption_cn": "",
            "source": "manual-svg-summary",
            "source_url": post.get("url", ""),
            "confidence": 0.65,
            "needs_manual_review": True,
        },
        asset_path,
    )


def process_post(post: dict[str, Any], *, overwrite: bool) -> tuple[str, str]:
    if not overwrite and ((post.get("key_figure") or {}).get("path") or "").strip():
        return "skipped", str((post.get("key_figure") or {}).get("path"))
    svg_override = MANUAL_SVG_OVERRIDES.get(post["id"])
    if svg_override:
        post["key_figure"], asset_path = build_manual_svg_key_figure(post, svg_override)
        return "ok", str(asset_path.relative_to(ROOT))
    override = MANUAL_IMAGE_OVERRIDES.get(post["id"])
    if override:
        selected, asset_path = download_selected_image(
            post["id"],
            [
                {
                    "url": override["url"],
                    "alt": override.get("caption", ""),
                    "title": post.get("title", ""),
                    "source": "manual-image-url",
                    "score": 95,
                }
            ],
            referer=post["url"],
        )
        selected["alt"] = override.get("caption", selected.get("alt", ""))
        parser = BlogImageParser(post["url"])
        post["key_figure"] = build_key_figure(post, parser, selected, asset_path)
        return "ok", str(asset_path.relative_to(ROOT))
    parser, _html = parse_page(post["url"])
    candidates = dedupe_candidates([*meta_candidates(parser), *parser.images])
    if not candidates:
        raise RuntimeError("no image candidates found")
    selected, asset_path = download_selected_image(post["id"], candidates, referer=post["url"])
    post["key_figure"] = build_key_figure(post, parser, selected, asset_path)
    return "ok", str(asset_path.relative_to(ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill key images for approved blog posts.")
    parser.add_argument("--blog-id", action="append", default=[], help="Only process this blog id; repeatable.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of posts to process; 0 means all.")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing blog key_figure metadata.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write data/blogs.json.")
    parser.add_argument("--sleep", type=float, default=0.4, help="Seconds to wait between posts.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    blogs = load_blogs()
    selected_ids = set(args.blog_id)
    posts = [
        post for post in blogs.get("posts", [])
        if (post.get("status") or "approved") == "approved"
        and post.get("id")
        and post.get("url")
        and (not selected_ids or post.get("id") in selected_ids)
    ]
    if args.limit > 0:
        posts = posts[: args.limit]

    results = []
    for index, post in enumerate(posts, start=1):
        blog_id = post["id"]
        print(f"[{index}/{len(posts)}] {blog_id}", flush=True)
        try:
            status, asset = process_post(post, overwrite=args.overwrite)
            if not args.dry_run and status == "ok":
                save_blogs(blogs)
            results.append({"id": blog_id, "status": status, "asset": asset})
            print(f"  {status} -> {asset}", flush=True)
        except Exception as exc:
            results.append({"id": blog_id, "status": "failed", "error": str(exc)})
            print(f"  failed: {exc}", flush=True)
        if args.sleep:
            time.sleep(args.sleep)

    print(json.dumps(results, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
