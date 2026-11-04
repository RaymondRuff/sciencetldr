"""Pick this Monday's paper from the digest, open a podcast Issue.

Triggered when the digest routine pushes a digest. Parses the markdown, ranks
the peer-reviewed papers by DICE score, and takes the best one whose full text
can actually be had — staging that text in the private papers repository on
the way, because the routine that writes the script cannot reach any paper
source itself and Actions can.

A paywalled top pick gives way to the next paper within one DICE point of it.
Only when nothing that good is open does the top pick go ahead without its
text, and then the sweep asks for its PDF, once.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import paper_resolver
import paper_text
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


# How far down the ranking to look for a paper that can be had. Each try is a
# handful of HTTP requests; the digest rarely has more than ten candidates.
MAX_FETCH_TRIES = 8


def obtain(paper: dict) -> tuple[Optional[str], Optional["paper_text.Fetched"]]:
    """(open-access PDF URL, full text) for a candidate; either may be None."""
    pdf_url = None
    try:
        pdf_url = paper_resolver.resolve_pdf(doi=paper["doi"], pmid=paper.get("pmid", ""))
    except Exception as exc:  # noqa: BLE001 - Unpaywall being down is not fatal
        print(f"  [pick] open-access lookup failed for {paper['doi']}: {exc}")
    return pdf_url, paper_text.fetch_open_text(doi=paper["doi"], pdf_url=pdf_url or "")


def choose_obtainable(
    candidates: list[dict],
    *,
    floor: Optional[int] = None,
    max_tries: int = MAX_FETCH_TRIES,
    fetch=obtain,
) -> tuple[dict, Optional[str], Optional["paper_text.Fetched"], list[str]]:
    """The best candidate whose full text can be had, best first.

    Returns (paper, pdf_url, fetched, notes). Stops looking below `floor` (a
    DICE score) and after `max_tries`. If nothing qualifies the first
    candidate is returned with fetched=None: it is still the right paper, and
    the sweep will ask for its PDF once.
    """
    notes: list[tuple[int, str]] = []
    first_url: Optional[str] = None
    for index, paper in enumerate(candidates[:max_tries]):
        if floor is not None and (paper.get("dice") or 0) < floor:
            break
        try:
            pdf_url, fetched = fetch(paper)
        except paper_text.TransientFetchError as exc:
            notes.append((index, f"{paper['title'][:90]}: a source was down ({str(exc)[:80]})"))
            continue
        if index == 0:
            first_url = pdf_url
        if fetched is not None:
            return paper, pdf_url, fetched, [text for _, text in notes]
        notes.append((index, f"{paper['title'][:90]}: no open full text"))
    # Nothing could be had: the first candidate stands, and the notes are the
    # others that were tried.
    return candidates[0], first_url, None, [text for i, text in notes if i != 0]


def availability_section(fetched, notes: list[str]) -> str:
    if fetched is not None:
        lines = [f"📚 **Full text:** staged for the writer from `{fetched.provenance}`."]
    else:
        lines = [
            "⚠️ **No open full text found.** The daily sweep emails one request for "
            "the PDF. Reply to it with the PDF attached, or upload the PDF to the "
            "private papers repository as `papers/issue-<this Issue's number>.pdf`. "
            "Never commit it to this public repository."
        ]
    if notes:
        lines.append(
            "\nPassed over because their full text could not be had:"
            if fetched is not None
            else "\nAlso tried, with no open full text either:"
        )
        lines += [f"- {note}" for note in notes]
    return "\n".join(lines)


def render_issue_body(
    paper: dict,
    pdf_url: str | None,
    source: str,
    *,
    fetched=None,
    notes: Optional[list[str]] = None,
) -> str:
    intro_prompt = (PROMPTS_DIR / "notebooklm_intro.md").read_text(encoding="utf-8").strip()

    pdf_section = availability_section(fetched, notes or [])
    if pdf_url:
        pdf_section = f"📎 **PDF (open-access):** {pdf_url}\n\n{pdf_section}"

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
2. Upload the paper PDF (link above, or from the private papers repository if closed-access)
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


def stage_for_writer(issue_number: int, paper: dict, fetched, journal: str = "") -> None:
    """Put the fetched text where the writer routine can read it. Never fatal."""
    if fetched is None:
        return
    try:
        import paper_bundle

        paper_bundle.stage(
            issue_number, fetched, doi=paper["doi"], title=paper["title"], journal=journal
        )
    except Exception as exc:  # noqa: BLE001 - the daily sweep stages it again
        print(f"[pick] could not stage the paper for #{issue_number} ({exc}); "
              "the daily sweep will try again")


def main() -> None:
    github_issue.ensure_auth()
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

    top_dice = peer_reviewed[0]["dice"]
    chosen, pdf_url, fetched, notes = choose_obtainable(
        peer_reviewed, floor=top_dice - 1
    )
    print(f"[select-monday] pick (DICE {chosen['dice']}): {chosen['title'][:80]}")
    for note in notes:
        print(f"[select-monday]  passed over: {note}")
    print(
        "[select-monday] full text: "
        + (fetched.provenance if fetched else "none open; the sweep will ask for the PDF")
    )

    title = f"📄 {chosen['title'][:160]}"
    body = render_issue_body(chosen, pdf_url, source_label, fetched=fetched, notes=notes)
    issue_number = github_issue.open_issue(
        title=title,
        body=body,
        labels=[github_issue.PENDING_LABEL, source_label],
    )
    print(f"[select-monday] opened issue #{issue_number}")
    stage_for_writer(issue_number, chosen, fetched)


if __name__ == "__main__":
    main()
