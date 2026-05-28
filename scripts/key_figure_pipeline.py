from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from html import unescape
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "library.json"
ASSET_DIR = ROOT / "assets" / "paper_images"
DEFAULT_ENDPOINT = "http://localhost:5001/api/extract"
USER_AGENT = "papers-database-key-figure/0.1"
PDFFIGURES2_CONTAINER = "pdffigures2"
PDFFIGURES2_IMAGE = "pdffigures2"
DEFAULT_JAR_CANDIDATES = [
    ROOT / "tools" / "pdffigures2.jar",
    Path("/private/tmp/pdffigures2.jar"),
    Path("/private/tmp/pdffigures2-hf.jar"),
]

METHOD_KEYWORDS = {
    "overview": 3.0,
    "framework": 3.0,
    "pipeline": 3.0,
    "architecture": 3.0,
    "method": 2.5,
    "approach": 2.0,
    "workflow": 2.0,
    "system": 1.6,
    "model": 1.4,
}

RESULT_KEYWORDS = {
    "main result": 2.4,
    "benchmark": 2.2,
    "comparison": 1.8,
    "performance": 1.8,
    "evaluation": 1.6,
    "accuracy": 1.2,
    "results": 1.2,
}

LOW_VALUE_KEYWORDS = {
    "ablation": -2.0,
    "sensitivity": -1.6,
    "hyperparameter": -1.8,
    "appendix": -2.5,
    "supplement": -2.2,
    "case study": -0.8,
}

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "our",
    "that",
    "the",
    "their",
    "this",
    "to",
    "we",
    "with",
}


def load_library() -> dict[str, Any]:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def save_library(library: dict[str, Any]) -> None:
    DATA_FILE.write_text(
        json.dumps(library, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def normalize_pdf_url(url: str) -> str:
    cleaned = url.strip()
    if not cleaned:
        raise ValueError("paper_url is empty")
    parsed = urlparse(cleaned)
    host = parsed.netloc.lower()
    path = parsed.path
    if host.endswith("arxiv.org") and path.startswith("/abs/"):
        arxiv_id = path.removeprefix("/abs/").strip("/")
        return f"https://arxiv.org/pdf/{arxiv_id}"
    if host.endswith("arxiv.org") and path.startswith("/pdf/"):
        return cleaned
    if cleaned.lower().endswith(".pdf"):
        return cleaned
    return cleaned


def http_request(
    url: str,
    *,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 90,
) -> bytes:
    request_headers = {"User-Agent": USER_AGENT}
    if headers:
        request_headers.update(headers)
    req = Request(url, method=method, data=data, headers=request_headers)
    with urlopen(req, timeout=timeout) as response:
        return response.read()


def endpoint_root(endpoint: str) -> str:
    parts = urlparse(endpoint)
    return f"{parts.scheme}://{parts.netloc}/" if parts.netloc else endpoint


def is_local_endpoint(endpoint: str) -> bool:
    host = urlparse(endpoint).hostname
    return host in {"localhost", "127.0.0.1", "::1"}


def service_ready(endpoint: str) -> bool:
    try:
        http_request(urljoin(endpoint_root(endpoint), "docs"), timeout=3)
        return True
    except Exception:
        return False


def wait_for_service(endpoint: str, timeout_seconds: int = 45) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if service_ready(endpoint):
            return True
        time.sleep(1)
    return service_ready(endpoint)


def run_docker_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def ensure_pdffigures2_service(endpoint: str, *, auto_start: bool) -> None:
    if service_ready(endpoint):
        return
    if not auto_start or not is_local_endpoint(endpoint):
        return

    if shutil.which("docker") is None:
        raise RuntimeError(
            "pdffigures2 service is not running and Docker is not available. "
            "Install/open Docker Desktop, then build the pdffigures2 image once."
        )

    started = run_docker_command(["start", PDFFIGURES2_CONTAINER])
    if started.returncode != 0:
        launched = run_docker_command(
            [
                "run",
                "-d",
                "--name",
                PDFFIGURES2_CONTAINER,
                "--restart",
                "unless-stopped",
                "-p",
                "5001:5001",
                PDFFIGURES2_IMAGE,
            ]
        )
        if launched.returncode != 0:
            raise RuntimeError(
                "pdffigures2 service is not running and the Docker container/image "
                f"could not be started. docker start stderr: {started.stderr.strip()} "
                f"docker run stderr: {launched.stderr.strip()} "
                "Build it once with: git clone https://github.com/vlln/pdffigures-mcp-server.git; "
                "cd pdffigures-mcp-server; docker build -t pdffigures2 ."
            )

    if not wait_for_service(endpoint):
        raise RuntimeError("pdffigures2 Docker container started, but the API did not become ready.")


def discover_candidates(endpoint: str, pdf_url: str, retries: int) -> list[dict[str, Any]]:
    payload = urlencode({"pdf_url": pdf_url}).encode("utf-8")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            raw = http_request(endpoint, method="POST", data=payload, headers=headers, timeout=180)
            data = json.loads(raw.decode("utf-8"))
            return normalize_candidate_payload(data)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.5)
                continue
            break
    raise RuntimeError(f"pdffigures2 extraction failed for {pdf_url}: {last_error}")


def normalize_candidate_payload(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        return []
    for key in ("figures", "items", "results", "data", "extracted", "output"):
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = normalize_candidate_payload(value)
            if nested:
                return nested
    if {"caption", "figType", "name"} & set(data):
        return [data]
    return []


def resolve_jar_path(value: str | None) -> Path | None:
    candidates = []
    if value:
        candidates.append(Path(value).expanduser())
    env_value = os_environ("PDFFIGURES2_JAR_PATH")
    if env_value:
        candidates.append(Path(env_value).expanduser())
    candidates.extend(DEFAULT_JAR_CANDIDATES)
    for path in candidates:
        if path.exists() and path.is_file():
            return path
    return None


def os_environ(name: str) -> str:
    import os

    return os.environ.get(name, "")


def discover_candidates_local_jar(
    *,
    pdf_path: Path,
    jar_path: Path,
    java_bin: str,
) -> tuple[list[dict[str, Any]], Path]:
    output_dir = Path(tempfile.mkdtemp(prefix="pdffigures2_out_"))
    output_prefix = str(output_dir) + "/"
    command = [
        java_bin,
        "-Djava.awt.headless=true",
        "-Dsun.java2d.cmm=sun.java2d.cmm.lcms.LcmsServiceProvider",
        "-jar",
        str(jar_path),
        str(pdf_path),
        "-m",
        output_prefix,
        "-d",
        output_prefix,
        "--dpi",
        "300",
    ]
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "local pdffigures2 JAR extraction failed. "
            f"stdout: {result.stdout[-1200:]} stderr: {result.stderr[-1200:]}"
        )

    metadata_path = output_dir / f"{pdf_path.stem}.json"
    if not metadata_path.exists():
        raise RuntimeError(f"local pdffigures2 JAR did not write metadata: {metadata_path}")

    candidates = normalize_candidate_payload(json.loads(metadata_path.read_text(encoding="utf-8")))
    for candidate in candidates:
        fig_type = candidate.get("figType")
        name = candidate.get("name")
        render_path = output_dir / f"{pdf_path.stem}-{fig_type}{name}-1.png"
        if render_path.exists():
            candidate["localRenderPath"] = str(render_path)
    return candidates, output_dir


def download_pdf(pdf_url: str) -> Path:
    suffix = ".pdf"
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    path = Path(handle.name)
    handle.close()
    path.write_bytes(http_request(pdf_url, timeout=180))
    return path


def enable_bundled_site_packages() -> None:
    bundled = (
        Path.home()
        / ".cache"
        / "codex-runtimes"
        / "codex-primary-runtime"
        / "dependencies"
        / "python"
        / "lib"
        / "python3.12"
        / "site-packages"
    )
    if bundled.exists():
        sys.path.append(str(bundled))


def extract_pdf_pages(pdf_path: Path) -> list[str]:
    try:
        from pypdf import PdfReader  # type: ignore
    except ModuleNotFoundError:
        enable_bundled_site_packages()
        try:
            from pypdf import PdfReader  # type: ignore
        except ModuleNotFoundError:
            return []

    try:
        reader = PdfReader(str(pdf_path))
    except Exception:
        return []

    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    return pages


def normalize_text(value: str) -> str:
    value = unescape(value or "")
    value = value.replace("\ufb01", "fi").replace("\ufb02", "fl")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def token_set(value: str) -> set[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", value.lower())
    return {word for word in words if word not in STOPWORDS}


def compact_ref_name(name: str) -> str:
    return re.sub(r"\s+", "", str(name or "")).strip().rstrip(".")


def build_reference_patterns(candidate: dict[str, Any]) -> list[re.Pattern[str]]:
    fig_type = str(candidate.get("figType") or "Figure").lower()
    name = compact_ref_name(str(candidate.get("name") or ""))
    if not name:
        return []
    escaped_name = re.escape(name)
    if fig_type.startswith("tab"):
        prefixes = r"(?:Table|Tab\.)"
    else:
        prefixes = r"(?:Figure|Figures|Fig\.|Figs\.)"
    return [
        re.compile(rf"\b{prefixes}\s*{escaped_name}\b", re.IGNORECASE),
        re.compile(rf"\b{prefixes}\s*\(?{escaped_name}\)?\b", re.IGNORECASE),
    ]


def context_window(text: str, start: int, end: int, chars: int = 420) -> str:
    left = max(0, start - chars)
    right = min(len(text), end + chars)
    window = text[left:right]
    sentence_start = max(window.rfind(". ", 0, start - left), window.rfind("\n", 0, start - left))
    sentence_end = window.find(". ", end - left)
    if sentence_start >= 0:
        window = window[sentence_start + 1 :]
    if sentence_end >= 0:
        window = window[: sentence_end + 1]
    return normalize_text(window)


def attach_contexts(candidates: list[dict[str, Any]], pages: list[str]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for candidate in candidates:
        item = dict(candidate)
        patterns = build_reference_patterns(item)
        contexts = []
        seen_contexts = set()
        for page_index, page_text in enumerate(pages, start=1):
            normalized = normalize_text(page_text)
            if not normalized:
                continue
            for pattern in patterns:
                for match in pattern.finditer(normalized):
                    key = (page_index, match.start(), match.end())
                    if key in seen_contexts:
                        continue
                    seen_contexts.add(key)
                    contexts.append(
                        {
                            "page": page_index,
                            "text": context_window(normalized, match.start(), match.end()),
                        }
                    )
                    if len(contexts) >= 3:
                        break
                if len(contexts) >= 3:
                    break
            if len(contexts) >= 3:
                break
        item["contexts"] = contexts
        enriched.append(item)
    return enriched


def paper_context_text(paper: dict[str, Any]) -> str:
    summary = paper.get("summary_cn") or {}
    parts = [
        paper.get("title", ""),
        paper.get("tldr", ""),
        paper.get("abstract", ""),
        " ".join(str(value) for value in summary.values()),
        " ".join(paper.get("keywords", [])),
        " ".join(paper.get("labels", [])),
    ]
    return normalize_text(" ".join(part for part in parts if part))


def candidate_text(candidate: dict[str, Any]) -> str:
    image_text = candidate.get("imageText") or []
    if isinstance(image_text, list):
        image_text_value = " ".join(str(item) for item in image_text)
    else:
        image_text_value = str(image_text)
    contexts = candidate.get("contexts") or []
    context_value = " ".join(str(item.get("text", "")) for item in contexts if isinstance(item, dict))
    return normalize_text(" ".join([str(candidate.get("caption") or ""), image_text_value, context_value]))


def candidate_score(candidate: dict[str, Any], paper_text: str) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    text = candidate_text(candidate)
    lower = text.lower()

    name = compact_ref_name(str(candidate.get("name") or ""))
    fig_type = str(candidate.get("figType") or "").lower()
    is_figure = fig_type.startswith("fig")
    is_table = fig_type.startswith("tab")
    if is_figure:
        if name == "1":
            score += 3.0
            reasons.append("Figure 1 prior")
        elif name == "2":
            score += 1.8
            reasons.append("early Figure 2 prior")
        else:
            score += 0.5
    elif is_table:
        score -= 4.0
        reasons.append("table default down-rank")

    for keyword, weight in METHOD_KEYWORDS.items():
        if keyword in lower:
            adjusted = weight
            if is_table:
                adjusted *= 0.35
            elif is_figure and keyword in {"overview", "framework", "pipeline", "architecture"}:
                adjusted *= 1.45
            score += adjusted
            reasons.append(f"method keyword: {keyword}")
    for keyword, weight in RESULT_KEYWORDS.items():
        if keyword in lower:
            adjusted = weight * (0.65 if is_table else 1.0)
            score += adjusted
            reasons.append(f"result keyword: {keyword}")
    for keyword, weight in LOW_VALUE_KEYWORDS.items():
        if keyword in lower:
            score += weight
            reasons.append(f"low-value keyword: {keyword}")

    paper_tokens = token_set(paper_text)
    candidate_tokens = token_set(text)
    if paper_tokens and candidate_tokens:
        overlap = paper_tokens & candidate_tokens
        similarity = len(overlap) / max(8, min(len(paper_tokens), len(candidate_tokens)))
        score += min(4.0, similarity * 8.0)
        if overlap:
            reasons.append(f"text overlap: {', '.join(sorted(overlap)[:8])}")

    contexts = candidate.get("contexts") or []
    if contexts:
        score += min(1.5, 0.5 * len(contexts))
        reasons.append(f"{len(contexts)} inline reference context(s)")

    page = candidate.get("page")
    try:
        page_number = int(page)
    except (TypeError, ValueError):
        page_number = 0
    if page_number and page_number <= 3:
        score += 0.8
        reasons.append("appears early in the paper")
    if is_table and page_number and page_number > 5:
        score -= 2.0
        reasons.append("late table down-rank")

    return score, reasons


def select_candidate(candidates: list[dict[str, Any]], paper: dict[str, Any]) -> dict[str, Any]:
    paper_text = paper_context_text(paper)
    ranked = []
    for index, candidate in enumerate(candidates):
        score, reasons = candidate_score(candidate, paper_text)
        ranked.append(
            {
                "index": index,
                "score": round(score, 3),
                "figType": candidate.get("figType", ""),
                "name": str(candidate.get("name", "")),
                "page": candidate.get("page"),
                "caption": candidate.get("caption", ""),
                "score_reason": "; ".join(reasons[:8]) or "no strong signal",
            }
        )
    ranked.sort(key=lambda item: item["score"], reverse=True)
    if not ranked:
        return {
            "selected": None,
            "confidence": 0.0,
            "needs_manual_review": True,
            "ranked_candidates": [],
        }

    top = ranked[0]
    second_score = ranked[1]["score"] if len(ranked) > 1 else 0.0
    margin = top["score"] - second_score
    confidence = max(0.2, min(0.95, 0.45 + top["score"] / 18.0 + margin / 8.0))
    needs_manual_review = confidence < 0.62 or margin < 0.8
    return {
        "selected": top,
        "confidence": round(confidence, 3),
        "needs_manual_review": needs_manual_review,
        "ranked_candidates": ranked[:8],
    }


def safe_asset_name(paper_id: str, selected: dict[str, Any]) -> str:
    fig_type = re.sub(r"[^A-Za-z0-9]+", "-", str(selected.get("figType") or "figure")).strip("-").lower()
    name = re.sub(r"[^A-Za-z0-9]+", "-", str(selected.get("name") or "selected")).strip("-").lower()
    return f"{paper_id}-{fig_type}-{name}.png"


def download_selected_render(candidate: dict[str, Any], out_path: Path, endpoint: str) -> bool:
    local_render_path = Path(str(candidate.get("localRenderPath") or ""))
    if local_render_path.exists():
        out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local_render_path, out_path)
        return True

    render_url = str(candidate.get("renderURL") or "").strip()
    if not render_url:
        return False
    render_url = urljoin(endpoint_root(endpoint), render_url)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(http_request(render_url, timeout=120))
    return True


def build_key_figure_metadata(
    paper: dict[str, Any],
    candidate: dict[str, Any],
    selected: dict[str, Any],
    asset_path: Path | None,
) -> dict[str, Any]:
    metadata = {
        "type": candidate.get("figType", selected.get("figType", "")),
        "name": str(candidate.get("name", selected.get("name", ""))),
        "page": candidate.get("page", selected.get("page")),
        "path": str(asset_path.relative_to(ROOT)) if asset_path else "",
        "caption": candidate.get("caption", ""),
        "caption_cn": candidate.get("caption_cn", ""),
        "bbox": candidate.get("regionBoundary", {}),
        "caption_bbox": candidate.get("captionBoundary", {}),
        "source": "pdffigures2",
        "confidence": selected.get("confidence"),
        "needs_manual_review": selected.get("needs_manual_review", True),
        "contexts": candidate.get("contexts", []),
    }
    return metadata


def find_paper(library: dict[str, Any], paper_id: str) -> dict[str, Any]:
    for paper in library.get("papers", []):
        if paper.get("id") == paper_id:
            return paper
    raise ValueError(f"paper id not found: {paper_id}")


def run(args: argparse.Namespace) -> int:
    library = load_library()
    paper = find_paper(library, args.paper_id)
    pdf_url = normalize_pdf_url(args.pdf_url or paper.get("pdf_url") or paper.get("paper_url") or "")

    pdf_path: Path | None = None
    local_output_dir: Path | None = None
    pages: list[str] = []
    candidates: list[dict[str, Any]]
    try:
        if args.force_local_jar:
            raise RuntimeError("forced local JAR extraction")
        ensure_pdffigures2_service(args.endpoint, auto_start=not args.no_auto_start_service)
        candidates = discover_candidates(args.endpoint, pdf_url, retries=args.retries)
    except RuntimeError:
        jar_path = resolve_jar_path(args.pdffigures_jar)
        if not jar_path:
            raise
        pdf_path = download_pdf(pdf_url)
        candidates, local_output_dir = discover_candidates_local_jar(
            pdf_path=pdf_path,
            jar_path=jar_path,
            java_bin=args.java_bin,
        )

    if not args.skip_context:
        try:
            if pdf_path is None:
                pdf_path = download_pdf(pdf_url)
            pages = extract_pdf_pages(pdf_path)
        finally:
            if pdf_path and pdf_path.exists() and local_output_dir is None:
                pdf_path.unlink(missing_ok=True)
    enriched = attach_contexts(candidates, pages) if pages else candidates
    selection = select_candidate(enriched, paper)

    selected_summary = selection.get("selected")
    selected_candidate = None
    asset_path: Path | None = None
    if isinstance(selected_summary, dict):
        selected_index = selected_summary.get("index")
        if isinstance(selected_index, int) and 0 <= selected_index < len(enriched):
            selected_candidate = enriched[selected_index]
            asset_path = ASSET_DIR / safe_asset_name(args.paper_id, selected_candidate)
            if not args.no_download:
                try:
                    saved = download_selected_render(selected_candidate, asset_path, args.endpoint)
                except (HTTPError, URLError, TimeoutError):
                    saved = False
                if not saved:
                    asset_path = None

    result = {
        "paper_id": args.paper_id,
        "pdf_url": pdf_url,
        "candidate_count": len(enriched),
        "selection": selection,
        "selected_candidate": selected_candidate,
        "asset_path": str(asset_path.relative_to(ROOT)) if asset_path else "",
    }

    if args.write_library and selected_candidate:
        key_figure = build_key_figure_metadata(paper, selected_candidate, selection, asset_path)
        paper["key_figure"] = key_figure
        save_library(library)
        result["written"] = True
    else:
        result["written"] = False

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if pdf_path and pdf_path.exists():
        pdf_path.unlink(missing_ok=True)
    if local_output_dir and local_output_dir.exists():
        shutil.rmtree(local_output_dir, ignore_errors=True)
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover and select a key figure/table for a paper.")
    parser.add_argument("--paper-id", required=True, help="Paper id in data/library.json.")
    parser.add_argument("--pdf-url", help="Override PDF URL. Defaults to paper_url normalized from library.")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="pdffigures2 API endpoint.")
    parser.add_argument("--retries", type=int, default=1, help="Retry count after the first extraction attempt.")
    parser.add_argument("--pdffigures-jar", help="Path to a local pdffigures2 JAR fallback.")
    parser.add_argument(
        "--java-bin",
        default="/opt/homebrew/opt/openjdk@21/bin/java",
        help="Java executable for local JAR fallback.",
    )
    parser.add_argument("--force-local-jar", action="store_true", help="Use the local JAR fallback instead of the API.")
    parser.add_argument("--skip-context", action="store_true", help="Skip inline reference context extraction.")
    parser.add_argument("--no-download", action="store_true", help="Do not download selected renderURL image.")
    parser.add_argument(
        "--no-auto-start-service",
        action="store_true",
        help="Do not try to start the local pdffigures2 Docker container when the API is unavailable.",
    )
    parser.add_argument("--write-library", action="store_true", help="Write selected key_figure into library.json.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
