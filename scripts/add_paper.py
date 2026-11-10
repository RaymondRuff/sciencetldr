"""Queue one paper for an episode, by DOI.

For a paper you came across yourself, outside the Monday digest and the Friday
r/science crawl. It does what the pickers do for their own strands: look the
paper up, fetch its full text if anything open has it, stage that text in the
private papers repository where the writer routine can read it, and open the
`podcast-pending` Issue the pipeline runs on.

The writer takes it at the next 08:00 UTC, the checker at 11:00, and it
publishes about 11:25 — so a paper queued today is an episode tomorrow
morning. One script a day, oldest Issue first: if a Monday or Friday strand
pick is already waiting, that one goes first and this follows a day later.
Queue a one-off on a Monday, Tuesday or Wednesday and nothing competes.

A paper with no open full text gets the same single email request the strands
get. Reply to it with the PDF attached, or upload the PDF to the papers
repository as `papers/issue-NN.pdf`, and the next sweep stages it. There is no
runner-up and no deadline: a one-off is a specific paper or nothing.

Run it from Actions ("add-paper" → Run workflow) so it has the network and the
credentials, or locally with GH_TOKEN set:

  uv run python scripts/add_paper.py --doi 10.1016/j.chembiol.2026.09.022
  uv run python scripts/add_paper.py --doi 10.1/x --note "the spacer claim"
"""
from __future__ import annotations

import argparse
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import crossref_lookup
import github_issue
import paper_text
import pdf_mailbox
import select_friday_paper
import select_monday_paper

SOURCE = "one-off"
LABEL_NEEDS_PDF = "needs-pdf"
LABEL_REQUESTED = "pdf-requested"


def describe(doi: str, title: str) -> dict:
    """The paper's record from Crossref, with `title` as an override or fallback."""
    meta = {}
    try:
        meta = crossref_lookup.crossref_metadata(doi) or {}
    except Exception as exc:  # noqa: BLE001 - Crossref being down is not fatal
        print(f"[add] Crossref lookup failed ({exc})")
    resolved = title or meta.get("title") or ""
    if not resolved:
        sys.exit(
            f"No title for {doi}: Crossref has no record and --title was not given. "
            "Check the DOI, or pass --title."
        )
    pmid = ""
    try:
        pmid = crossref_lookup.pmid_for_doi(doi) or ""
    except Exception as exc:  # noqa: BLE001
        print(f"[add] PubMed id lookup failed ({exc})")
    return {
        "title": resolved,
        "doi": doi,
        "dice": None,
        "pmid": pmid,
        "journal": meta.get("journal", ""),
        "is_preprint": bool(meta.get("is_preprint")),
    }


def excerpt(paper: dict, note: str) -> str:
    lines = ["Queued by hand, outside the Monday digest and the Friday crawl."]
    if note:
        lines.append(f"Reason given: {note}")
    if paper.get("journal"):
        lines.append(f"Journal: {paper['journal']}")
    if paper.get("is_preprint"):
        lines.append("This is a preprint: it has not been peer reviewed.")
    return "\n".join(lines)


def add(doi: str, *, title: str = "", note: str = "", force: bool = False) -> int:
    doi = doi.strip().removeprefix("https://doi.org/").removeprefix("doi:").strip()
    if not doi.startswith("10."):
        sys.exit(f"{doi!r} does not look like a DOI (they start with '10.').")

    github_issue.ensure_auth()
    paper = describe(doi, title)
    print(f"[add] {paper['title'][:80]}")

    if not force:
        try:
            seen = select_friday_paper.already_seen_dois()
        except Exception as exc:  # noqa: BLE001 - the guard is a courtesy
            print(f"[add] could not check for duplicates ({exc})")
            seen = set()
        if doi.lower() in seen:
            sys.exit(
                f"{doi} is already published or already queued in an open Issue. "
                "Pass --force to queue it again anyway."
            )

    try:
        pdf_url, fetched = select_monday_paper.obtain(paper)
    except paper_text.TransientFetchError as exc:
        print(f"[add] a source was down, so no full text this time ({exc})")
        pdf_url, fetched = None, None
    print(
        "[add] full text: "
        + (fetched.provenance if fetched else "none open; a PDF will be asked for")
    )

    body = select_monday_paper.render_issue_body(
        {"title": paper["title"], "doi": doi, "dice": None, "raw": excerpt(paper, note)},
        pdf_url,
        SOURCE,
        fetched=fetched,
    )
    number = github_issue.open_issue(
        title=f"🎧 {paper['title'][:160]}",
        body=body,
        labels=[github_issue.PENDING_LABEL, SOURCE],
    )
    print(f"[add] opened issue #{number}")

    if fetched is not None:
        select_monday_paper.stage_for_writer(
            number, paper, fetched, journal=paper.get("journal", "")
        )
        print("[add] the writer will take it at the next 08:00 UTC run")
        return number

    labels = [LABEL_NEEDS_PDF]
    try:
        if pdf_mailbox.request(
            number, title=paper["title"], doi=doi, journal=paper.get("journal", "")
        ):
            labels.append(LABEL_REQUESTED)
    except Exception as exc:  # noqa: BLE001 - the Issue says what is needed anyway
        print(f"[add] could not email the PDF request ({exc})")
    github_issue.add_labels(number, labels)
    print(f"[add] labelled {', '.join(labels)}; the episode waits for the PDF")
    return number


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doi", required=True, help="the paper's DOI")
    parser.add_argument("--title", default="", help="override the Crossref title")
    parser.add_argument("--note", default="", help="why you want this paper (context for the writer)")
    parser.add_argument(
        "--force", action="store_true", help="queue it even if the DOI is already published or pending"
    )
    args = parser.parse_args()
    add(args.doi, title=args.title, note=args.note, force=args.force)


if __name__ == "__main__":
    main()
