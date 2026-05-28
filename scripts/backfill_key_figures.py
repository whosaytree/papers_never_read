from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from key_figure_pipeline import (
    ASSET_DIR,
    DATA_FILE,
    ROOT,
    attach_contexts,
    discover_candidates_local_jar,
    download_pdf,
    extract_pdf_pages,
    normalize_pdf_url,
    resolve_jar_path,
    safe_asset_name,
    select_candidate,
)


def load_library() -> dict[str, Any]:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def save_library(library: dict[str, Any]) -> None:
    DATA_FILE.write_text(json.dumps(library, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def has_key_figure(paper: dict[str, Any]) -> bool:
    return bool(((paper.get("key_figure") or {}).get("path") or "").strip())


def build_key_figure(paper_id: str, candidate: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any]:
    asset_path = ASSET_DIR / safe_asset_name(paper_id, candidate)
    return {
        "type": candidate.get("figType", ""),
        "name": str(candidate.get("name", "")),
        "page": candidate.get("page"),
        "path": str(asset_path.relative_to(ROOT)),
        "caption": candidate.get("caption", ""),
        "caption_cn": candidate.get("caption_cn", ""),
        "bbox": candidate.get("regionBoundary", {}),
        "caption_bbox": candidate.get("captionBoundary", {}),
        "source": "pdffigures2-local-jar",
        "confidence": selection.get("confidence"),
        "needs_manual_review": selection.get("needs_manual_review", True),
        "contexts": candidate.get("contexts", []),
    }


def process_paper(
    paper: dict[str, Any],
    *,
    jar_path: Path,
    java_bin: str,
    skip_context: bool,
) -> tuple[dict[str, Any], Path]:
    paper_id = paper["id"]
    pdf_url = normalize_pdf_url(paper.get("pdf_url") or paper.get("paper_url") or "")
    pdf_path = download_pdf(pdf_url)
    output_dir: Path | None = None
    try:
        candidates, output_dir = discover_candidates_local_jar(
            pdf_path=pdf_path,
            jar_path=jar_path,
            java_bin=java_bin,
        )
        pages = [] if skip_context else extract_pdf_pages(pdf_path)
        enriched = attach_contexts(candidates, pages) if pages else candidates
        selection = select_candidate(enriched, paper)
        selected = selection.get("selected")
        if not isinstance(selected, dict):
            raise RuntimeError("no selected candidate")
        selected_index = selected.get("index")
        if not isinstance(selected_index, int) or selected_index < 0 or selected_index >= len(enriched):
            raise RuntimeError("selected candidate index is invalid")
        candidate = enriched[selected_index]
        render_path = Path(str(candidate.get("localRenderPath") or ""))
        if not render_path.exists():
            raise RuntimeError("selected render image is missing")
        asset_path = ASSET_DIR / safe_asset_name(paper_id, candidate)
        asset_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(render_path, asset_path)
        return build_key_figure(paper_id, candidate, selection), asset_path
    finally:
        pdf_path.unlink(missing_ok=True)
        if output_dir and output_dir.exists():
            shutil.rmtree(output_dir, ignore_errors=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill key figures for approved papers.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of missing papers to process; 0 means all.")
    parser.add_argument("--start-after", default="", help="Skip missing papers until after this paper id.")
    parser.add_argument("--paper-id", action="append", default=[], help="Only process the given paper id; repeatable.")
    parser.add_argument("--pdffigures-jar", default="", help="Path to pdffigures2 JAR.")
    parser.add_argument("--java-bin", default="/opt/homebrew/opt/openjdk@21/bin/java", help="Java executable.")
    parser.add_argument("--skip-context", action="store_true", help="Skip inline reference context extraction.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write data/library.json.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    jar_path = resolve_jar_path(args.pdffigures_jar)
    if not jar_path:
        raise RuntimeError("pdffigures2 JAR not found. Put it at tools/pdffigures2.jar or pass --pdffigures-jar.")

    library = load_library()
    selected_ids = set(args.paper_id)
    papers = [
        paper for paper in library.get("papers", [])
        if (paper.get("status") or "approved") == "approved"
        and not has_key_figure(paper)
        and (not selected_ids or paper.get("id") in selected_ids)
    ]
    if args.start_after:
        seen = False
        filtered = []
        for paper in papers:
            if seen:
                filtered.append(paper)
            elif paper.get("id") == args.start_after:
                seen = True
        papers = filtered
    if args.limit > 0:
        papers = papers[: args.limit]

    results = []
    for index, paper in enumerate(papers, start=1):
        paper_id = paper["id"]
        print(f"[{index}/{len(papers)}] {paper_id}", flush=True)
        try:
            key_figure, asset_path = process_paper(
                paper,
                jar_path=jar_path,
                java_bin=args.java_bin,
                skip_context=args.skip_context,
            )
            if not args.dry_run:
                paper["key_figure"] = key_figure
                save_library(library)
            results.append({"id": paper_id, "status": "ok", "asset": str(asset_path.relative_to(ROOT))})
            print(f"  ok -> {asset_path.relative_to(ROOT)}", flush=True)
        except Exception as exc:
            results.append({"id": paper_id, "status": "failed", "error": str(exc)})
            print(f"  failed: {exc}", flush=True)

    print(json.dumps(results, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
