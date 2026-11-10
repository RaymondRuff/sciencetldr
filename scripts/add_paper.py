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
  uv run python scripts/add_paper.py --url https://example.org/paper.pdf \\
      --title "A white paper" --publisher "Example Lab"

A paper with no DOI — an industry white paper — is identified by its URL
instead. Give the title too, or leave it out and the PDF's own front matter is
read for one, which is a guess worth checking on the Issue before the writer
runs in the morning.
"""
from __future__ import annotations

import argparse
import re
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
    if paper.get("source_url") and not paper.get("doi"):
        lines.append(
            f"No DOI: this is a white paper, published at {paper['source_url']}. "
            "The hosts name the organisation instead of reading a DOI."
        )
    if paper.get("is_preprint"):
        lines.append("This is a preprint: it has not been peer reviewed.")
    return "\n".join(lines)


def normalise(doi: str) -> str:
    doi = doi.strip().removeprefix("https://doi.org/").removeprefix("http://doi.org/")
    doi = doi.removeprefix("doi:").strip().rstrip(".,;")
    if not doi.startswith("10."):
        raise Refused(f"{doi!r} does not look like a DOI — they start with '10.'.")
    return doi


def check_url(url: str) -> str:
    url = url.strip()
    if not url.lower().startswith(("http://", "https://")):
        raise Refused(f"{url!r} does not look like a link — it needs to start with https.")
    return url


def _front_matter(data: bytes) -> tuple[str, str]:
    """(the PDF's own title, the text of its first pages). Blank on failure."""
    try:
        import io

        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        recorded = ""
        if reader.metadata is not None:
            recorded = str(reader.metadata.title or "").strip()
        text = "\n".join(
            page.extract_text() or "" for page in reader.pages[:DOI_SEARCH_PAGES]
        )
        return recorded, text
    except Exception as exc:  # noqa: BLE001 - an unreadable PDF just yields nothing
        print(f"[add] could not read the PDF ({exc})")
        return "", ""


def doi_from_pdf(path: Path) -> str | None:
    """The DOI printed on a paper's first pages, if it is there."""
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        print(f"[add] could not open the PDF ({exc})")
        return None
    found = pdf_mailbox.dois_in(_front_matter(data)[1])
    if len(found) == 1:
        return found[0]
    if found:
        print(f"[add] the PDF's first pages carry {len(found)} DOIs; not guessing")
    return None


def plausible_title(line: str) -> bool:
    """Whether a line off a PDF's front page could be the paper's title."""
    line = line.strip()
    if not 15 <= len(line) <= 300:
        return False
    if "@" in line or line.count(" ") < 2:
        return False  # an email address, or too few words to be a title
    if not any(c.isalpha() for c in line):
        return False
    lowered = line.lower()
    return not lowered.startswith(
        ("http", "www.", "doi:", "arxiv", "abstract", "preprint", "copyright", "©")
    )


def looks_like_authors(line: str) -> bool:
    """Whether a line is the author list that ends a title.

    Affiliation markers give it away: a dagger, or a name carrying a
    superscript number next to a comma ("Corley1,2,3"). A title that merely
    contains a number — "12,000 designs" — has no letter against a digit, so
    it is not mistaken for one.
    """
    if "†" in line or "‡" in line:
        return True
    return "," in line and bool(re.search(r"[A-Za-z]\d", line))


def title_from_pdf(data: bytes) -> str | None:
    """The paper's title, from the PDF's own metadata or its first lines.

    A white paper has no Crossref record to ask, so this is the only source
    besides the requester. A title usually wraps, so the lines after the
    first are taken too, as far as the author list — "Biomolecular design
    through latent reasoning with" alone is not a title. It is still a guess:
    it is printed in the log and lands in an Issue that can be corrected
    before the writer runs.
    """
    def tidy(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    recorded, text = _front_matter(data)
    if plausible_title(recorded):
        return tidy(recorded)

    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not plausible_title(line):
            continue
        title = [line.strip()]
        for following in lines[index + 1 :]:
            following = following.strip()
            if not following or looks_like_authors(following):
                break
            if following.lower().startswith(("abstract", "introduction", "summary")):
                break
            if title[-1].endswith((".", "?", "!")):
                break
            if len(" ".join(title)) + len(following) > 300:
                break
            title.append(following)
        return tidy(" ".join(title))
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


def white_paper(url: str, title: str, publisher: str) -> dict:
    """The record for a paper with no DOI, identified by where it was published."""
    return {
        "title": title,
        "doi": "",
        "dice": None,
        "pmid": "",
        "source_url": url,
        "pdf_url": url,
        "journal": f"White paper — {publisher}" if publisher else "White paper",
        "is_preprint": False,
    }


def check_duplicate(paper: dict, force: bool) -> None:
    if force:
        return
    doi, url = paper.get("doi", ""), paper.get("source_url", "")
    try:
        seen = (
            select_friday_paper.already_seen_dois() if doi
            else select_friday_paper.already_seen_urls()
        )
    except Exception as exc:  # noqa: BLE001 - the guard is a courtesy
        print(f"[add] could not check for duplicates ({exc})")
        return
    if (doi or url).lower() in seen:
        raise Refused(
            f"{doi or url} is already published, or already queued in an open Issue."
        )


def add(
    doi: str = "",
    *,
    url: str = "",
    title: str = "",
    publisher: str = "",
    note: str = "",
    force: bool = False,
    pdf: Path | None = None,
    email_request: bool = True,
) -> Queued:
    """Open the Issue for one paper, found by DOI or, failing that, by URL.

    With `pdf` the caller already holds the paper, so no source is fetched and
    no PDF is asked for; the caller stages it. The file is still read for the
    paper's title when nothing else can supply one.
    """
    supplied = pdf is not None
    github_issue.ensure_auth()
    if doi:
        doi = normalise(doi)
        paper = describe(doi, title)
    elif url:
        paper = white_paper(check_url(url), title, publisher)
    else:
        raise Refused("I need either a DOI or a link to the paper.")

    check_duplicate(paper, force)
    check_room(force)

    pdf_url, fetched = None, None
    if supplied:
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

    if not paper["title"]:
        # No DOI means no Crossref record, so the PDF itself is the only place
        # left to look. It is a guess: say so loudly.
        data = fetched.pdf if fetched and fetched.pdf else None
        if data is None and pdf is not None:
            try:
                data = Path(pdf).read_bytes()
            except OSError as exc:
                print(f"[add] could not read the supplied PDF ({exc})")
        guess = title_from_pdf(data) if data else None
        if not guess:
            raise Refused(
                "I could not work out the paper's title — there is no DOI to look "
                "up and no readable PDF to take it from. Send the title with the link."
            )
        paper["title"] = guess
        print(f"[add] title taken from the PDF (check it): {guess!r}")
    print(f"[add] {paper['title'][:80]}")

    body = select_monday_paper.render_issue_body(
        {
            "title": paper["title"],
            "doi": paper.get("doi", ""),
            "dice": None,
            "raw": excerpt(paper, note),
            "source_url": paper.get("source_url", ""),
            "journal": paper.get("journal", ""),
        },
        pdf_url,
        SOURCE,
        fetched=fetched,
        supplied=supplied,
    )
    identifier = paper.get("doi") or paper.get("source_url", "")
    outcome = {"staged": fetched is not None or supplied}

    def finish(number: int) -> None:
        if fetched is not None:
            select_monday_paper.stage_for_writer(
                number, paper, fetched, journal=paper.get("journal", "")
            )
            print("[add] the writer will take it at its next run")
            return
        if supplied:
            return
        labels = [LABEL_NEEDS_PDF]
        if email_request:
            try:
                if pdf_mailbox.request(
                    number, title=paper["title"], doi=paper.get("doi", ""),
                    journal=paper.get("journal", ""),
                ):
                    labels.append(LABEL_REQUESTED)
            except Exception as exc:  # noqa: BLE001 - the Issue says what is needed
                print(f"[add] could not email the PDF request ({exc})")
        else:
            # The caller writes to the owner itself; a second email is noise.
            labels.append(LABEL_REQUESTED)
        github_issue.add_labels(number, labels)
        print(f"[add] labelled {', '.join(labels)}; the episode waits for the PDF")

    number = select_monday_paper.open_staged(
        title=f"🎧 {paper['title'][:160]}",
        body=body,
        labels=[github_issue.PENDING_LABEL, SOURCE],
        stage=finish,
    )
    return Queued(number, paper["title"], identifier, outcome["staged"])


def from_email(request: dict) -> Queued:
    """Queue the paper an emailed one-off request names. Raises Refused.

    A DOI is preferred: it brings a Crossref record with it. Failing that, a
    single link identifies the paper — that is the white-paper case, where the
    title comes from a "Title:" line or from the PDF itself. Several DOIs or
    several links are refused rather than guessed at: the wrong paper is worse
    than a question.
    """
    dois = request.get("dois") or []
    urls = request.get("urls") or []
    fields = {k.lower(): v for k, v in (request.get("fields") or {}).items()}
    pdf = Path(request["pdf"]) if request.get("pdf") else None
    note = request.get("note", "")

    if len(dois) > 1:
        raise Refused(
            "the email names several DOIs (" + ", ".join(dois[:4])
            + "), so I could not tell which paper you meant. Send just the one."
        )
    doi = dois[0] if dois else (doi_from_pdf(pdf) if pdf else None)
    if doi:
        return add(doi, note=note, pdf=pdf, email_request=False)

    url = fields.get("url") or fields.get("link") or ""
    if not url and len(urls) == 1:
        url = urls[0]
    elif not url and urls:
        raise Refused(
            f"the email has {len(urls)} links in it, so I could not tell which is "
            "the paper. Put it on a line of its own starting 'URL:'."
        )
    if not url:
        where = " or on the first pages of the attached PDF" if pdf else ""
        raise Refused(
            f"I could not find a DOI in the email{where}. Send the DOI — or, for a "
            "paper that has none, a link to it and a line starting 'Title:'."
        )
    return add(
        url=url,
        title=fields.get("title", ""),
        publisher=(
            fields.get("publisher")
            or fields.get("organisation")
            or fields.get("organization")
            or fields.get("org")
            or ""
        ),
        note=note,
        pdf=pdf,
        email_request=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doi", default="", help="the paper's DOI")
    parser.add_argument(
        "--url",
        default="",
        help="where the paper is published, for one with no DOI (a white paper)",
    )
    parser.add_argument(
        "--publisher", default="", help="the organisation behind a white paper"
    )
    parser.add_argument("--title", default="", help="override the Crossref title")
    parser.add_argument("--note", default="", help="why you want this paper (context for the writer)")
    parser.add_argument(
        "--force", action="store_true", help="queue it even if the DOI is already published or pending"
    )
    args = parser.parse_args()
    try:
        add(
            args.doi,
            url=args.url,
            title=args.title,
            publisher=args.publisher,
            note=args.note,
            force=args.force,
        )
    except Refused as exc:
        sys.exit(f"Not queued: {exc}")


if __name__ == "__main__":
    main()
