# Key Figure Extraction Design

## Goal

Add a `key_figure` field to each paper in the local paper database. The field should point to one extracted figure or table image that best represents the paper's core idea, method, result, benchmark, or contribution.

The intended pipeline is:

```text
paper_url
  -> online PDF URL
  -> pdffigures2 MCP discovers Figure/Table candidates
  -> local selection logic chooses one key item
  -> only the selected item is rendered/cropped and saved
  -> data/library.json stores the key_figure metadata
```

Online PDF URLs are the default input. If extraction fails, retry once. If the second attempt fails, skip automatic key figure extraction for that paper.

## Proposed Field

```json
"key_figure": {
  "type": "Figure",
  "name": "1",
  "page": 2,
  "path": "assets/paper_images/paper-id-figure-1.png",
  "caption": "Figure 1: Overview of the proposed method...",
  "bbox": [45.8, 49.6, 549.1, 276.0],
  "source": "pdffigures2",
  "confidence": 0.82,
  "needs_manual_review": false
}
```

The `path` should point to a committed static asset so the generated site does not depend on a running extraction service.

## Discovery Stage

Use `pdffigures2-mcp-server` as the primary discovery component. Its role is to identify candidate figures and tables in a paper PDF and return structured metadata.

The useful candidate fields are:

- `caption`: figure/table caption. This is the most important selection signal.
- `figType`: usually `Figure` or `Table`.
- `name`: figure/table marker, such as `1`, `2`, or `3a`.
- `page`: page index reported by the extractor.
- `regionBoundary`: bounding box for the figure/table region.
- `captionBoundary`: bounding box for the caption.
- `imageText`: text found inside the figure/table region when available.
- `renderDpi` and `renderURL`: useful if the server already rendered extracted images.

The current product direction is not to blindly keep all rendered outputs. The discovery stage should provide a candidate list first. The later selection stage chooses one item, and the final extraction stage saves only that item into the paper database.

## Selection Stage

The selection stage should be content-based. It should compare each candidate figure/table against the paper's own title, TL;DR, abstract, and Chinese summary.

The central lesson from Yang et al. 2019, *Identifying the Central Figure of a Scientific Paper*, is that text context is more predictive than raw visual appearance. Their feature design used caption, inline mentions, abstract similarity, figure order, layout, section information, and visual embeddings. The strongest signals came from caption/reference text and abstract similarity, while image content was comparatively weak. The task is also subjective: their reported exact match was about 33.6%, while top-3 accuracy was about 77.9%.

Yamamoto et al. 2021, *Visual Summary Identification From Scientific Publications via Self-Supervised Learning*, also supports an abstract-caption matching formulation. However, in their CS paper setting, the learned method did not reliably beat a simple first-figure baseline. This matters for this project because AI/ML papers often put an overview, pipeline, or architecture diagram early in the paper. Position is useful, but should remain a prior rather than a hard rule.

## Prompt Requirements

The selection prompt should encode the following rules.

1. Choose the figure/table that best represents the paper's core method, contribution, result, benchmark, or conceptual framing.
2. Prioritize textual evidence: candidate `caption`, `imageText`, paper title, TL;DR, abstract, and `summary_cn`.
3. Strongly reward candidates whose captions overlap semantically with the paper's core contribution, method name, task setting, or main result.
4. Give Figure 1 and Figure 2 a prior advantage, but do not mechanically select them.
5. Prefer overview/framework/pipeline/architecture/method diagrams for method papers.
6. Prefer benchmark design, task taxonomy, dataset construction overview, or evaluation protocol diagrams for benchmark and dataset papers.
7. Prefer main trend or key comparison plots for empirical analysis papers.
8. Prefer taxonomy or landscape figures for survey-style papers.
9. Down-rank tables by default unless the table is clearly the main benchmark, leaderboard, or result summary.
10. Down-rank ablation, hyperparameter, sensitivity, implementation-detail, appendix-style, and narrow module figures.
11. If the evidence is weak or candidates are too similar, mark the result for manual review instead of forcing a confident choice.

The prompt should require auditable JSON output:

```json
{
  "selected": {
    "figType": "Figure",
    "name": "1",
    "page": 2,
    "reason": "The caption describes the full method pipeline and matches the paper's TL;DR and method summary."
  },
  "confidence": 0.82,
  "needs_manual_review": false,
  "ranked_candidates": [
    {
      "figType": "Figure",
      "name": "1",
      "score_reason": "Best overview of the proposed method."
    },
    {
      "figType": "Table",
      "name": "2",
      "score_reason": "Important result table, but less explanatory than the method overview."
    }
  ]
}
```

## Figure/Table Context Extraction

Extracting the text around where a paper references a figure or table is feasible and useful. It should be treated as a separate enrichment layer because pdffigures2 primarily discovers figure/table regions and captions; it does not reliably provide all inline reference contexts from the body text.

### Lightweight Version

The first implementation can use PDF text extraction plus reference matching:

1. Extract page text from the online PDF.
2. Normalize whitespace, ligatures, and common figure/table spellings.
3. For each candidate, build reference patterns:
   - `Figure 1`, `Fig. 1`, `Fig. 1a`, `Figures 1 and 2`
   - `Table 1`, `Tab. 1`, `Tables 1 and 2`
4. Search the extracted text for these references.
5. Return a sentence or paragraph window around each match.
6. Attach the contexts to the candidate before selection.

Example candidate extension:

```json
{
  "figType": "Figure",
  "name": "1",
  "caption": "Figure 1: Overview of the method.",
  "contexts": [
    {
      "page": 2,
      "section": "Method",
      "text": "As shown in Figure 1, our framework first retrieves..."
    }
  ]
}
```

This version is easy to implement and likely sufficient for many arXiv-style AI papers. Its main weakness is PDF text order: multi-column layouts can scramble paragraph order, and references can be split across lines.

### Structured Version

For higher quality, use GROBID as a second-stage parser. GROBID converts scientific PDFs into TEI XML and marks structured elements such as paragraphs, section titles, figures, tables, and references. Its fulltext model includes `<ref type="figure">` pointers, and its coordinate support can include figures, references, formulas, and other elements.

This makes it possible to extract cleaner inline mention contexts:

```text
PDF -> GROBID TEI
  -> find <ref type="figure">Fig. 1</ref>
  -> collect containing paragraph and section title
  -> map "Fig. 1" to pdffigures2 candidate Figure 1
```

This is more accurate than regex over raw PDF text, especially for multi-column papers, but it adds a Java service and more integration complexity.

### Recommended Context Strategy

Start with the lightweight version:

```text
pdffigures2 candidates
  + extracted abstract/title/summary
  + regex-based inline contexts
  -> LLM selector
```

Add GROBID only if the lightweight extractor produces too many bad contexts or if inline mention context proves decisive for selection quality.

## Recommended Implementation Plan

1. Add a standalone discovery script that calls pdffigures2 MCP with the online PDF URL and returns candidate metadata.
2. Add a lightweight context extractor that finds figure/table references in extracted PDF text.
3. Add a selector prompt using title, TL;DR, abstract, summary, captions, image text, and inline contexts.
4. Add a final crop/render step that saves only the selected figure/table asset.
5. Add `key_figure` rendering to `scripts/build_site.py`.
6. Evaluate on 20-30 existing papers and revise the prompt based on failures.

## First Implementation

The first implementation lives in `scripts/key_figure_pipeline.py`.

Example usage:

```bash
python3 scripts/key_figure_pipeline.py \
  --paper-id too-correct-to-learn-2604-18493 \
  --endpoint http://localhost:5001/api/extract \
  --write-library
```

Behavior:

1. Reads the paper from `data/library.json`.
2. Converts arXiv `/abs/` URLs to `/pdf/` URLs.
3. Calls the pdffigures2 HTTP API with `pdf_url`.
4. If the local API is unavailable, tries to start a Docker container named `pdffigures2`.
5. Retries extraction once by default.
6. Downloads the PDF for lightweight inline reference context extraction.
7. Selects a candidate using a transparent heuristic scorer based on caption, paper text, early-figure prior, figure/table type, method/result keywords, low-value keywords, and inline contexts.
8. Downloads only the selected candidate's `renderURL` if one is returned.
9. Optionally writes `key_figure` back to `data/library.json`.

The prompt specification for a later LLM selector is stored in `prompts/key_figure_selector.txt`. The current script uses a deterministic scorer first so the pipeline can be tested without an LLM key.

### Local Service Lifecycle

The script does not start a new pdffigures2 service for each paper. It expects one reusable local service:

```text
one local pdffigures2 server
  -> many paper extraction requests
```

First-time setup:

```bash
git clone https://github.com/vlln/pdffigures-mcp-server.git
cd pdffigures-mcp-server
docker build -t pdffigures2 .
docker run -d --name pdffigures2 --restart unless-stopped -p 5001:5001 pdffigures2
```

After the image/container exists, `scripts/key_figure_pipeline.py` checks `http://localhost:5001/docs`. If it is not available, it tries:

```bash
docker start pdffigures2
```

If the container does not exist but the image exists, it tries:

```bash
docker run -d --name pdffigures2 --restart unless-stopped -p 5001:5001 pdffigures2
```

If Docker is not installed/open or the image has never been built, the script fails with setup instructions instead of silently skipping extraction.

## References

- AllenAI PDFFigures2: https://github.com/allenai/pdffigures2
- pdffigures2 MCP server: https://github.com/vlln/pdffigures-mcp-server
- Yang et al. 2019, *Identifying the Central Figure of a Scientific Paper*: https://par.nsf.gov/servlets/purl/10188257
- viziometrics central figure data: https://github.com/viziometrics/centraul_figure
- Yamamoto et al. 2021, *Visual Summary Identification From Scientific Publications via Self-Supervised Learning*: https://www.frontiersin.org/journals/research-metrics-and-analytics/articles/10.3389/frma.2021.719004/full
- Visual-Summary code: https://github.com/yamashin42/Visual-Summary
- GROBID fulltext model documentation: https://grobid.readthedocs.io/en/latest/training/fulltext/
- GROBID PDF coordinates documentation: https://grobid.readthedocs.io/en/latest/Coordinates-in-PDF/
