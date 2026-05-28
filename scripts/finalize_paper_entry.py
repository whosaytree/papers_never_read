from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from backfill_key_figures import has_key_figure, process_paper
from key_figure_pipeline import DATA_FILE, ROOT, resolve_jar_path


def load_library() -> dict[str, Any]:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def save_library(library: dict[str, Any]) -> None:
    DATA_FILE.write_text(json.dumps(library, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def find_paper(library: dict[str, Any], paper_id: str) -> dict[str, Any]:
    for paper in library.get("papers", []):
        if paper.get("id") == paper_id:
            return paper
    raise RuntimeError(f"paper id not found in data/library.json: {paper_id}")


def run_checked(command: list[str]) -> None:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed: {' '.join(command)}\n"
            f"stdout:\n{result.stdout[-2000:]}\n"
            f"stderr:\n{result.stderr[-2000:]}"
        )


def validate_json() -> None:
    run_checked([sys.executable, "-m", "json.tool", str(DATA_FILE)])


def build_site() -> None:
    run_checked([sys.executable, "scripts/build_site.py"])


def verify_built_page(paper: dict[str, Any]) -> None:
    output_file = ROOT / "dist" / "index.html"
    if not output_file.exists():
        raise RuntimeError("dist/index.html was not built")
    html = output_file.read_text(encoding="utf-8")
    title = str(paper.get("title") or "").strip()
    if title and title not in html:
        raise RuntimeError(f"built page does not contain paper title: {title}")
    key_figure = paper.get("key_figure") or {}
    image_path = str(key_figure.get("path") or "").strip()
    if image_path and image_path not in html:
        raise RuntimeError(f"built page does not reference key figure: {image_path}")
    caption_cn = str(key_figure.get("caption_cn") or "").strip()
    if key_figure.get("caption") and caption_cn and caption_cn not in html:
        raise RuntimeError("built page does not contain Chinese key figure caption")


def maybe_extract_key_figure(args: argparse.Namespace, paper: dict[str, Any]) -> tuple[bool, Path | None]:
    if has_key_figure(paper):
        return False, None

    jar_path = resolve_jar_path(args.pdffigures_jar)
    if not jar_path:
        if args.allow_missing_key_figure:
            return False, None
        raise RuntimeError("pdffigures2 JAR not found. Put it at tools/pdffigures2.jar or pass --pdffigures-jar.")

    try:
        key_figure, asset_path = process_paper(
            paper,
            jar_path=jar_path,
            java_bin=args.java_bin,
            skip_context=args.skip_context,
        )
    except Exception:
        if args.allow_missing_key_figure:
            return False, None
        raise
    paper["key_figure"] = key_figure
    return True, asset_path


def maybe_apply_caption_cn(args: argparse.Namespace, paper: dict[str, Any], new_asset_path: Path | None) -> bool:
    key_figure = paper.get("key_figure") or {}
    caption = str(key_figure.get("caption") or "").strip()
    current_caption_cn = str(key_figure.get("caption_cn") or "").strip()
    requested_caption_cn = args.caption_cn.strip()

    if not caption:
        return False
    if current_caption_cn and not args.overwrite_caption_cn:
        return False
    if requested_caption_cn:
        key_figure["caption_cn"] = requested_caption_cn
        paper["key_figure"] = key_figure
        return True
    if args.allow_missing_caption_cn:
        return False

    if new_asset_path and new_asset_path.exists():
        new_asset_path.unlink()
    raise RuntimeError(
        "key figure has an English caption but no Chinese caption. "
        "Run again with --caption-cn. English caption:\n"
        f"{caption}"
    )


def finalize(args: argparse.Namespace) -> dict[str, Any]:
    library = load_library()
    paper = find_paper(library, args.paper_id)

    changed = False
    new_asset_path: Path | None = None
    try:
        extracted, new_asset_path = maybe_extract_key_figure(args, paper)
        changed = changed or extracted
        caption_changed = maybe_apply_caption_cn(args, paper, new_asset_path)
        changed = changed or caption_changed
    except Exception:
        if new_asset_path and new_asset_path.exists():
            new_asset_path.unlink()
        raise

    if changed and args.dry_run and new_asset_path and new_asset_path.exists():
        new_asset_path.unlink()

    if changed and not args.dry_run:
        save_library(library)

    if not args.dry_run:
        validate_json()
        if not args.no_build:
            build_site()
            verify_built_page(paper)

    key_figure = paper.get("key_figure") or {}
    return {
        "paper_id": args.paper_id,
        "changed": changed,
        "dry_run": args.dry_run,
        "has_key_figure": has_key_figure(paper),
        "key_figure_path": key_figure.get("path", ""),
        "has_caption_cn": bool(str(key_figure.get("caption_cn") or "").strip()),
        "built": not args.dry_run and not args.no_build,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Finalize a newly added paper entry: extract a key figure if missing, "
            "require/write its Chinese caption, validate JSON, and build the site."
        )
    )
    parser.add_argument("--paper-id", required=True, help="Paper id in data/library.json.")
    parser.add_argument("--caption-cn", default="", help="Chinese translation for the selected key figure caption.")
    parser.add_argument(
        "--overwrite-caption-cn",
        action="store_true",
        help="Replace an existing Chinese key figure caption with --caption-cn.",
    )
    parser.add_argument("--pdffigures-jar", default="", help="Path to pdffigures2 JAR.")
    parser.add_argument("--java-bin", default="/opt/homebrew/opt/openjdk@21/bin/java", help="Java executable.")
    parser.add_argument("--skip-context", action="store_true", help="Skip inline reference context extraction.")
    parser.add_argument(
        "--allow-missing-key-figure",
        action="store_true",
        help="Do not fail if key figure extraction is unavailable or fails.",
    )
    parser.add_argument(
        "--allow-missing-caption-cn",
        action="store_true",
        help="Do not fail when the key figure has an English caption but no Chinese caption.",
    )
    parser.add_argument("--no-build", action="store_true", help="Skip site build and built-page verification.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write data/library.json.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = finalize(args)
    except Exception as exc:
        print(f"failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
