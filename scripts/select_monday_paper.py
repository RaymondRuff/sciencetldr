"""Pick the top-DICE paper from this Monday's digest, open a podcast Issue.

Triggered after digest.yml completes. Parses the markdown the digest agent
wrote, finds the highest-DICE-scored paper, attempts to resolve an open-access
PDF, and creates a GitHub Issue with all the metadata the publish workflow
will need.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import paper_resolver
import github_issue

ROOT = Path(__file__).resolve().parent.parent
DIGEST_DIR = ROOT / "digest"
PROMPTS_DIR = ROOT / "prompts"

DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
DICE_RE = re.compile(r"DICE\s*(?:score)?\s*[:\-]?\s*\*{0,2}(\d)\*{0,2}", re.IGNORECASE)


def latest_digest() -> Path:
    files = sorted(DIGEST_DIR.glob("*.md"), reverse=True)
    if not files:
        sys.exit("No digest files found")
    return files[0]


def parse_papers(markdown: str) -> list[dict]:
    """Split a digest into per-paper blocks, then extract title + DOI + DICE.

    Heuristic: papers are separated by horizontal rules or 2+ blank lines, and
    the first non-empty line of each block contains the title. The user's
    prompt enforces blank lines between fields, so each paper is its own
    paragraph cluster.
    """
    chunks = re.split(r"\n(?:---+|\*\*\*+|===+)\n+|\n(?=## (?!#))", markdown)
    if len(chunks) < 3:
        chunks = re.split(r"\n{3,}", markdown)

    papers = []
    in_preprint_section = False
    position = 0
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        if re.search(r"^##\s+Notable\s+Preprints", chunk, re.MULTILINE | re.IGNORECASE):
            in_preprint_section = True
        elif re.search(r"^##\s+Top\s+(?:Peer-Reviewed\s+)?Papers", chunk, re.MULTILINE | re.IGNORECASE):
            in_preprint_section = False

        dice_match = DICE_RE.search(chunk)
        doi_match = DOI_RE.search(chunk)
        if not (dice_match and doi_match):
            continue

        first_lines = []
        for line in chunk.splitlines():
            raw = line.lstrip()
            if raw.startswith("## ") and not raw.startswith("### "):
                continue
            stripped = line.strip(" *#-•\t").strip()
            if stripped:
                first_lines.append(stripped)
        title = next(
            (l for l in first_lines if len(l) > 15 and not l.lower().startswith(("authors", "journal", "doi", "dice"))),
            first_lines[0] if first_lines else "",
        )
        if title.lower().startswith("title"):
            title = title.split(":", 1)[-1].strip()

        doi = doi_match.group(0).rstrip(".,);")
        is_preprint = (
            in_preprint_section
            or "(preprint)" in chunk.lower()
            or doi.startswith("10.1101/")
        )
        papers.append({
            "title": title[:300],
            "doi": doi,
            "dice": int(dice_match.group(1)),
            "raw": chunk[:2000],
            "is_preprint": is_preprint,
            "position": position,
        })
        position += 1

    papers.sort(key=lambda p: (-p["dice"], p["position"]))
    return papers


def render_issue_body(paper: dict, pdf_url: str | None, source: str) -> str:
    intro_prompt = (PROMPTS_DIR / "notebooklm_intro.md").read_text(encoding="utf-8").strip()

    pdf_section = (
        f"📎 **PDF (open-access):** {pdf_url}"
        if pdf_url
        else "⚠️ **No open-access PDF found.** Please drop the paper PDF into "
             "[`inbox/pdfs/`](https://github.com/RaymondRuff/sciencetldr/tree/main/inbox/pdfs) "
             "before generating the audio."
    )

    metadata = {
        "title": paper["title"],
        "doi": paper["doi"],
        "dice_score": paper.get("dice"),
        "pdf_url": pdf_url,
        "source": source,
        "digest_excerpt": paper.get("raw", ""),
    }

    return f"""# {paper['title']}

**Source:** {source}  •  **DICE:** {paper.get('dice', '?')}  •  **DOI:** [{paper['doi']}](https://doi.org/{paper['doi']})

{pdf_section}

---

## NotebookLM workflow

1. Open [NotebookLM](https://notebooklm.google.com/), create a new notebook
2. Upload the paper PDF (link above, or from `inbox/pdfs/` if closed-access)
3. Generate Audio Overview with this customization prompt:

```
{intro_prompt}
```

4. Download the MP3
5. Drop it into [`inbox/`](https://github.com/RaymondRuff/sciencetldr/tree/main/inbox) — the publish workflow will pick it up within ~2 minutes and close this issue automatically

---

## Digest excerpt

> {paper.get('raw', '').replace(chr(10), chr(10) + '> ')}

---

{github_issue.render_metadata_block(metadata)}
"""


def main() -> None:
    source_label = os.environ.get("SELECTION_SOURCE", "monday-digest")
    digest_path = latest_digest()
    print(f"[select-monday] using digest: {digest_path.name}")

    papers = parse_papers(digest_path.read_text(encoding="utf-8"))
    if not papers:
        sys.exit("Could not parse any papers from the digest")
    peer_reviewed = [p for p in papers if not p["is_preprint"]]
    print(f"[select-monday] parsed {len(papers)} candidates ({len(peer_reviewed)} peer-reviewed)")
    if not peer_reviewed:
        sys.exit("No peer-reviewed papers parsed from digest (only preprints found)")

    top = peer_reviewed[0]
    print(f"[select-monday] top pick (DICE {top['dice']}): {top['title'][:80]}")

    pdf_url = paper_resolver.resolve_pdf(doi=top["doi"])
    print(f"[select-monday] PDF: {pdf_url or 'none (closed-access fallback)'}")

    title = f"📄 {top['title'][:160]}"
    body = render_issue_body(top, pdf_url, source_label)
    issue_number = github_issue.open_issue(
        title=title,
        body=body,
        labels=[github_issue.PENDING_LABEL, source_label],
    )
    print(f"[select-monday] opened issue #{issue_number}")


if __name__ == "__main__":
    main()
