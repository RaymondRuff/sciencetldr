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
from pathlib import Path
from typing import NamedTuple

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

# How many one-off papers may be waiting at once. Each one costs a writer
# session, a checker session and about nineteen cents of audio, and the writer
# writes one script a day — so an easy way in is also an easy way to spend the
# week's plan capacity. Past this the request is refused and says so.
OUTSTANDING_CAP = 4
# Only the first pages carry the DOI; reading a whole paper to find it is waste.
DOI_SEARCH_PAGES = 3


class Refused(Exception):
    """Why a paper was not queued, in words that can be emailed back."""


def describe(doi: str, title: str) -> dict:
    """The paper's record from Crossref, with `title` as an override or fallback."""
    meta = {}
    try:
        meta = crossref_lookup.crossref_metadata(doi) or {}
    except Exception as exc:  # noqa: BLE001 - Crossref being down is not fatal
        print(f"[add] Crossref lookup failed ({exc})")
    resolved = title or meta.get("title") or ""
    if not resolved:
        raise Refused(
            f"I could not find a title for {doi} — Crossref has no record of it. "
            "Check the DOI, or send the title with it."
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


def normalise(doi: str) -> str:
    doi = doi.strip().removeprefix("https://doi.org/").removeprefix("http://doi.org/")
    doi = doi.removeprefix("doi:").strip().rstrip(".,;")
    if not doi.startswith("10."):
        raise Refused(f"{doi!r} does not look like a DOI — they start with '10.'.")
    return doi


def doi_from_pdf(path: Path) -> str | None:
    """The DOI printed on a paper's first pages, if it is there."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        text = "\n".join(
            page.extract_text() or "" for page in reader.pages[:DOI_SEARCH_PAGES]
        )
    except Exception as exc:  # noqa: BLE001 - an unreadable PDF just yields nothing
        print(f"[add] could not read the PDF for a DOI ({exc})")
        return None
    found = pdf_mailbox.dois_in(text)
    if len(found) == 1:
        return found[0]
    if found:
        print(f"[add] the PDF's first pages carry {len(found)} DOIs; not guessing")
    return None


def check_room(force: bool) -> None:
    """Refuse when the one-off queue is already full."""
    try:
        waiting = github_issue.open_issues_with_label(SOURCE)
    except Exception as exc:  # noqa: BLE001 - never block on the count itself
        print(f"[add] could not count the one-off queue ({exc})")
        return
    if len(waiting) < OUTSTANDING_CAP or force:
        return
    listed = ", ".join(f"#{n}" for n in sorted(waiting))
    raise Refused(
        f"there are already {len(waiting)} one-off papers waiting ({listed}), which "
        f"is the limit of {OUTSTANDING_CAP}. Send this one again once one of them "
        "has published."
    )


class Queued(NamedTuple):
    number: int
    title: str
    doi: str
    staged: bool  # its full text is already in the papers repository


def add(
    doi: str,
    *,
    title: str = "",
    note: str = "",
    force: bool = False,
    supplied_pdf: bool = False,
    email_request: bool = True,
) -> Queued:
    """Open the Issue for one paper. Raises Refused with a reason if it will not.

    With `supplied_pdf` the caller already holds the paper, so no source is
    fetched and no PDF is asked for; the caller stages it.
    """
    doi = normalise(doi)
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
            raise Refused(
                f"{doi} is already published, or already queued in an open Issue."
            )
    check_room(force)

    pdf_url, fetched = None, None
    if supplied_pdf:
        print("[add] full text: the PDF came with the request")
    else:
        try:
            pdf_url, fetched = select_monday_paper.obtain(paper)
        except paper_text.TransientFetchError as exc:
            print(f"[add] a source was down, so no full text this time ({exc})")
        print(
            "[add] full text: "
            + (fetched.provenance if fetched else "none open; a PDF is needed")
        )

    body = select_monday_paper.render_issue_body(
        {"title": paper["title"], "doi": doi, "dice": None, "raw": excerpt(paper, note)},
        pdf_url,
        SOURCE,
        fetched=fetched,
        supplied=supplied_pdf,
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
        print("[add] the writer will take it at its next run")
        return Queued(number, paper["title"], doi, True)
    if supplied_pdf:
        return Queued(number, paper["title"], doi, True)

    labels = [LABEL_NEEDS_PDF]
    if email_request:
        try:
            if pdf_mailbox.request(
                number, title=paper["title"], doi=doi, journal=paper.get("journal", "")
            ):
                labels.append(LABEL_REQUESTED)
        except Exception as exc:  # noqa: BLE001 - the Issue says what is needed anyway
            print(f"[add] could not email the PDF request ({exc})")
    else:
        # The caller is writing to the owner itself; a second email would be noise.
        labels.append(LABEL_REQUESTED)
    github_issue.add_labels(number, labels)
    print(f"[add] labelled {', '.join(labels)}; the episode waits for the PDF")
    return Queued(number, paper["title"], doi, False)


def from_email(request: dict) -> Queued:
    """Queue the paper an emailed one-off request names. Raises Refused.

    The DOI comes from the body when it names exactly one, and otherwise from
    the first pages of an attached PDF. Several DOIs and no DOI are both
    refused rather than guessed at: the wrong paper is worse than a question.
    """
    dois = request.get("dois") or []
    pdf = Path(request["pdf"]) if request.get("pdf") else None
    if len(dois) > 1:
        raise Refused(
            "the email names several DOIs (" + ", ".join(dois[:4])
            + "), so I could not tell which paper you meant. Send just the one."
        )
    doi = dois[0] if dois else (doi_from_pdf(pdf) if pdf else None)
    if not doi:
        where = " or on the first pages of the attached PDF" if pdf else ""
        raise Refused(
            f"I could not find a DOI in the email{where}. Reply with the DOI and "
            "I will queue it."
        )
    return add(
        doi,
        note=request.get("note", ""),
        supplied_pdf=pdf is not None,
        email_request=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doi", required=True, help="the paper's DOI")
    parser.add_argument("--title", default="", help="override the Crossref title")
    parser.add_argument("--note", default="", help="why you want this paper (context for the writer)")
    parser.add_argument(
        "--force", action="store_true", help="queue it even if the DOI is already published or pending"
    )
    args = parser.parse_args()
    try:
        add(args.doi, title=args.title, note=args.note, force=args.force)
    except Refused as exc:
        sys.exit(f"Not queued: {exc}")


if __name__ == "__main__":
    main()
