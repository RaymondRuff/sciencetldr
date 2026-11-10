"""Pick this Monday's paper from the digest, open a podcast Issue.

Triggered when the digest routine pushes a digest. Parses the markdown, ranks
the peer-reviewed papers by DICE score, and takes the best one whose full text
can actually be had — staging that text in the private papers repository on
the way, because the routine that writes the script cannot reach any paper
source itself and Actions can.

A paywalled top pick gives way silently only to another paper with the same
DICE score. Otherwise quality is Ray's call: the Issue opens for the top pick
and he is emailed once, with a deadline of 9 pm Pacific and the runner-up — the
best paper within one DICE point that can be fetched — named in the email. No
PDF by then, and the runner-up stands in; no runner-up, and the slot is
skipped. See pdf_window.py.
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import paper_resolver
import paper_text
import pdf_window
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
    pdf_url = paper.get("pdf_url") or None
    if not pdf_url:
        try:
            pdf_url = paper_resolver.resolve_pdf(doi=paper["doi"], pmid=paper.get("pmid", ""))
        except Exception as exc:  # noqa: BLE001 - Unpaywall being down is not fatal
            print(f"  [pick] open-access lookup failed for {paper['doi']}: {exc}")
    return pdf_url, paper_text.fetch_open_text(doi=paper["doi"], pdf_url=pdf_url or "")


@dataclass
class PickPlan:
    """What the picker will do this week."""

    chosen: dict  # the paper the Issue is for
    pdf_url: Optional[str]
    fetched: Optional["paper_text.Fetched"]  # its full text, when it could be had
    notes: list[str] = field(default_factory=list)  # other candidates tried, and why not
    window: bool = False  # ask Ray for the chosen paper's PDF, with a deadline
    runner_up: Optional[dict] = None  # stands in if no PDF arrives in time
    runner_up_url: Optional[str] = None
    # Candidates ranked above the runner-up (or, with none, within the floor)
    # whose sources were down at pick time. They are tried again at the
    # deadline: an outage is not a paywall.
    unchecked: list[dict] = field(default_factory=list)


def same_dice(a: dict, b: dict) -> bool:
    return a.get("dice") is not None and a.get("dice") == b.get("dice")


# Before deciding the top paper is closed, give a source that is down two more
# chances: asking Ray for a PDF the world could have given us is the costlier
# mistake.
TOP_RETRY_DELAYS = (20, 60)


def plan_pick(
    candidates: list[dict],
    *,
    floor: Optional[int] = None,
    max_tries: int = MAX_FETCH_TRIES,
    fetch=None,
    same_standard: Callable[[dict, dict], bool] = lambda a, b: False,
    sleep: Callable[[float], None] = time.sleep,
) -> PickPlan:
    """Decide between the best paper and the best paper that can be had.

    The top candidate goes ahead when its full text is open. When it is not,
    the best open candidate (no lower than `floor`, within `max_tries`) is the
    runner-up. A runner-up of the same standard simply takes the slot: no
    quality is lost, so there is nothing to ask. Otherwise the top candidate
    keeps the slot and a PDF window opens, with the runner-up — if there is
    one — standing by.
    """
    fetch = fetch or obtain
    top = candidates[0]
    notes: list[str] = []
    top_url = top_text = None
    for delay in (0, *TOP_RETRY_DELAYS):
        if delay:
            sleep(delay)
        try:
            top_url, top_text = fetch(top)
            break
        except paper_text.TransientFetchError as exc:
            print(f"  [pick] {top['title'][:60]}: a source was down ({str(exc)[:120]})")
    else:
        print("  [pick] still down after retries; treating the top pick as closed")
    if top_text is not None:
        return PickPlan(top, top_url, top_text)

    runner = runner_url = runner_text = None
    unchecked: list[dict] = []
    for paper in candidates[1:max_tries]:
        if floor is not None and (paper.get("dice") or 0) < floor:
            break
        try:
            url, text = fetch(paper)
        except paper_text.TransientFetchError:
            notes.append(f"{paper['title'][:90]}: its source was down; tried again at the deadline")
            unchecked.append(paper)
            continue
        if text is not None:
            runner, runner_url, runner_text = paper, url, text
            break
        notes.append(f"{paper['title'][:90]}: no open full text")

    if runner is not None and same_standard(runner, top):
        passed = [f"{top['title'][:90]}: no open full text", *notes]
        return PickPlan(runner, runner_url, runner_text, passed)
    return PickPlan(
        top, top_url, None, notes,
        window=True, runner_up=runner, runner_up_url=runner_url, unchecked=unchecked,
    )


def availability_section(
    fetched,
    notes: list[str],
    *,
    deadline=None,
    runner_up: Optional[dict] = None,
    unchecked: bool = False,
    supplied: bool = False,
) -> str:
    if supplied and fetched is None:
        lines = [
            "📄 **The PDF came with the request** and is being staged for the "
            "writer. It is never committed to this public repository."
        ]
    elif fetched is not None:
        lines = [f"📚 **Full text:** staged for the writer from `{fetched.provenance}`."]
    elif deadline is not None:
        lines = [
            f"⏳ **No open full text — waiting for a PDF until {pdf_window.describe(deadline)}.** "
            "Reply to the request email with the PDF attached, or upload it to the "
            "private papers repository as `papers/issue-<this Issue's number>.pdf`. "
            "Never commit it to this public repository.",
            "",
            (
                f"If none arrives by then, **{runner_up['title'][:200]}**"
                + (f" (DICE {runner_up['dice']})" if runner_up.get("dice") else "")
                + " stands in: its full text is open."
                if runner_up
                else "If none arrives by then, the candidates whose sources were down "
                "are tried again, and if none of them is open the slot is skipped "
                "rather than filled with a weaker paper."
                if unchecked
                else "If none arrives by then, this slot is skipped: no paper of the "
                "same standard is open, and a weaker one is not used instead."
            ),
            "",
            "Either way this Issue stays open, and a PDF that arrives later still "
            "becomes an episode.",
        ]
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
    deadline=None,
    runner_up: Optional[dict] = None,
    stand_ins: Optional[list[dict]] = None,
    supplied: bool = False,
) -> str:
    intro_prompt = (PROMPTS_DIR / "notebooklm_intro.md").read_text(encoding="utf-8").strip()

    pdf_section = availability_section(
        fetched, notes or [], deadline=deadline, runner_up=runner_up,
        unchecked=bool(stand_ins) and not runner_up, supplied=supplied,
    )
    if pdf_url:
        pdf_section = f"📎 **PDF (open-access):** {pdf_url}\n\n{pdf_section}"

    # A white paper has no DOI, so its source URL is what identifies it. The
    # show notes and the hosts' sign-off both fall back to that URL, and
    # publish_episode pairs the audio by Issue number rather than by DOI.
    doi = (paper.get("doi") or "").strip()
    source_url = (paper.get("source_url") or "").strip()
    metadata = {
        "title": paper["title"],
        "doi": doi or None,
        "dice_score": paper.get("dice"),
        "pdf_url": pdf_url,
        "source": source,
        "digest_excerpt": paper.get("raw", ""),
    }
    if source_url:
        metadata["source_url"] = source_url
    if paper.get("journal"):
        metadata["journal"] = paper["journal"]
    if deadline is not None:
        metadata["pdf_deadline"] = pdf_window.iso(deadline)
        metadata["runner_up"] = runner_up
        metadata["stand_ins"] = stand_ins or []

    if doi:
        citation = f"**DOI:** [{doi}](https://doi.org/{doi})"
    elif source_url:
        citation = f"**Paper:** [{source_url}]({source_url})"
    else:
        citation = "**No DOI recorded**"
    header = "  •  ".join(
        [f"**Source:** {source}"]
        + ([f"**DICE:** {paper['dice']}"] if paper.get("dice") is not None else [])
        + [citation]
    )

    return f"""# {paper['title']}

{header}

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


def as_paper(candidate: dict) -> dict:
    return {
        "title": candidate["title"],
        "doi": candidate["doi"],
        "dice": candidate.get("dice"),
        "raw": candidate.get("raw", ""),
    }


def render_pick(plan: PickPlan, source: str, *, picked_at=None):
    """(paper, Issue body, deadline or None, runner-up record or None) for a plan."""
    paper = as_paper(plan.chosen)
    deadline = runner = None
    stand_ins: list[dict] = []
    if plan.window:
        deadline = pdf_window.deadline_for(picked_at or pdf_window.now_utc())
        runner = pdf_window.runner_up_record(plan.runner_up, plan.runner_up_url)
        # Tried in this order at the deadline: anything that could not be
        # checked and ranks above the runner-up, then the runner-up itself.
        stand_ins = [pdf_window.runner_up_record(p, None) for p in plan.unchecked]
        if runner:
            stand_ins.append(runner)
    body = render_issue_body(
        paper, plan.pdf_url, source,
        fetched=plan.fetched, notes=plan.notes, deadline=deadline, runner_up=runner,
        stand_ins=stand_ins,
    )
    return paper, body, deadline, runner


def open_staged(*, title: str, body: str, labels: list[str], stage=None) -> int:
    """Open an Issue, put its paper in place, and only then make it eligible.

    `podcast-pending` is both what the sweep looks for and what the workflow's
    `issues: labeled` trigger fires on, so adding it last is what stops a
    sweep seeing the Issue before its paper is staged. Issue #113 was opened
    with the label, a sweep started three seconds later, found no bundle —
    staging the paper took eighty — and emailed a request for a PDF that was
    already arriving.

    The label is added even when staging fails, so a half-finished paper is
    visible to the pipeline rather than lost; the sweep then asks for its PDF
    for the right reason.
    """
    deferred = [label for label in labels if label != github_issue.PENDING_LABEL]
    number = github_issue.open_issue(
        title=title, body=body, labels=deferred or [github_issue.PENDING_LABEL]
    )
    print(f"[pick] opened issue #{number}")
    try:
        if stage is not None:
            stage(number)
    finally:
        if deferred:
            github_issue.add_labels(number, [github_issue.PENDING_LABEL])
    return number


def open_pick(plan: PickPlan, *, source: str, title: str, labels: list[str], journal: str = "") -> int:
    """Open the week's Issue, stage its paper, or ask for it once with a deadline."""
    import pdf_mailbox

    paper, body, deadline, runner = render_pick(plan, source)
    if plan.window:
        # awaiting-pdf tells the sweep this request is the picker's, so it
        # never sends a second one; needs-pdf keeps the writer away from it.
        labels = [*labels, "needs-pdf", pdf_window.LABEL_AWAITING]

    def finish(number: int) -> None:
        if plan.fetched is not None:
            stage_for_writer(number, paper, plan.fetched, journal=journal)
        if not plan.window:
            return
        try:
            sent = pdf_mailbox.request(
                number,
                title=paper["title"],
                doi=paper["doi"],
                journal=journal,
                deadline=pdf_window.describe(deadline),
                runner_up=(runner or {}).get("title", ""),
            )
        except Exception as exc:  # noqa: BLE001 - the Issue says it all; email is a courtesy
            print(f"[pick] could not email the PDF request for #{number}: {exc}")
            sent = False
        if sent:
            github_issue.add_labels(number, ["pdf-requested"])

    return open_staged(title=title, body=body, labels=labels, stage=finish)


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
    plan = plan_pick(peer_reviewed, floor=top_dice - 1, same_standard=same_dice)
    print(f"[select-monday] pick (DICE {plan.chosen['dice']}): {plan.chosen['title'][:80]}")
    for note in plan.notes:
        print(f"[select-monday]  {'also tried' if plan.window else 'passed over'}: {note}")
    if plan.fetched is not None:
        print(f"[select-monday] full text: {plan.fetched.provenance}")
    elif plan.runner_up:
        print(f"[select-monday] no open full text; runner-up (DICE {plan.runner_up['dice']}): "
              f"{plan.runner_up['title'][:80]}")
    else:
        print("[select-monday] no open full text and no runner-up within one DICE point")

    open_pick(
        plan,
        source=source_label,
        title=f"📄 {plan.chosen['title'][:160]}",
        labels=[github_issue.PENDING_LABEL, source_label],
    )


if __name__ == "__main__":
    main()
