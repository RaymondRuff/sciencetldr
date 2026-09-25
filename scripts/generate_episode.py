"""Turn open `podcast-pending` Issues into review-ready episode drafts.

For each eligible Issue: fetch the paper's full text, have Claude write and then
verify a two-host script, synthesize it with Gemini multi-speaker TTS, and open
a pull request carrying the audio. Merging that PR lands the mp3 in `inbox/`,
which is what the existing publish workflow watches — so review is the merge
button and nothing reaches the feed unreviewed.

Issue label states:
  podcast-pending        eligible (set by the Monday/Friday selection scripts)
  needs-pdf              no full text reachable; waiting on a PDF
  pdf-requested          a PDF request has been emailed (see pdf_mailbox.py)
  episode-in-review      a draft PR is open
  generation-failed      the run errored; needs a look before retrying

MAX_EPISODES_PER_RUN caps *attempts* — every Issue that reaches the paid model
calls counts, whether it succeeds or fails — so one run can never spend more
than that many episodes' worth. Issues that only need a PDF cost nothing and
don't count. A PDF emailed back in reply to a request is generated straight
away outside the cap — replying is an explicit request.

The run stops outright on errors that will affect every Issue (the Anthropic
spend limit, bad credentials), and refuses to start if the GitHub token can't
open the review PR, rather than discovering that after paying for a script.

Usage:
  python scripts/generate_episode.py                 # sweep eligible issues
  python scripts/generate_episode.py --issue 45      # one specific issue
  python scripts/generate_episode.py --mailbox-only  # only emailed-PDF issues
  python scripts/generate_episode.py --dry-run       # script only, no audio, no PR
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import anthropic
from slugify import slugify

import generate_script
import github_issue
import memory
import paper_text
import pdf_mailbox
import tts_dialogue

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "inbox"
GENERATED = ROOT / "generated"

LABEL_PENDING = "podcast-pending"
LABEL_NEEDS_PDF = "needs-pdf"
LABEL_PDF_REQUESTED = "pdf-requested"
LABEL_IN_REVIEW = "episode-in-review"
LABEL_FAILED = "generation-failed"

SKIP_LABELS = {LABEL_IN_REVIEW, LABEL_FAILED}
MAX_PER_RUN = int(os.environ.get("MAX_EPISODES_PER_RUN", "3"))
BASE_BRANCH = "main"

# Outcomes of process(); failures raise instead.
DRAFTED = "drafted"
NEEDS_PDF = "needs-pdf"
DEFERRED = "deferred"  # a source was rate-limited or down; try again next run

NEEDS_PDF_COMMENT = """No open-access full text could be reached for this paper \
automatically{reason}.

{how}

Publishers often refuse scripted downloads even for open-access articles, so \
this step can be needed even when the Issue lists a PDF link."""

HOW_EMAIL = """A request has been emailed. **Reply to that email with the PDF \
attached** and the episode generates within about half an hour. The PDF stays \
in the mailbox and is never committed to this public repository."""

HOW_COMMIT = """To unblock it, reply to a PDF-request email if one arrives, or — \
only for openly licensed papers, since this repository is public — commit the \
PDF as [`inbox/pdfs/issue-{number}.pdf`]({pdf_dir})."""


def gh(args: list[str]) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def add_label(number: int, label: str) -> None:
    github_issue.ensure_label(label)
    gh(["issue", "edit", str(number), "--add-label", label])


def remove_label(number: int, label: str) -> None:
    subprocess.run(
        ["gh", "issue", "edit", str(number), "--remove-label", label],
        capture_output=True,
        text=True,
    )


def issue_labels(issue: dict) -> set[str]:
    return {
        label["name"] if isinstance(label, dict) else label
        for label in issue.get("labels", [])
    }


def eligible_issues(
    issues: list[dict], explicit: int | None, emailed: set[int]
) -> list[dict]:
    """Issues worth attempting: those with an emailed PDF first, then oldest first.

    Not capped here: the cap in main() counts paid attempts, so an Issue that
    turns out to need a PDF doesn't use up the run.
    """
    if explicit is not None:
        chosen = [i for i in issues if i["number"] == explicit]
        if not chosen:
            raise SystemExit(f"Issue #{explicit} is not an open {LABEL_PENDING} issue")
        return chosen

    with_pdf, rest = [], []
    for issue in issues:
        labels = issue_labels(issue)
        if LABEL_IN_REVIEW in labels:
            continue
        if issue["number"] in emailed:
            # A PDF reply is an explicit request to generate — including a
            # retry after a failure, so it overrides generation-failed.
            with_pdf.append(issue)
            continue
        if labels & SKIP_LABELS:
            continue
        meta = github_issue.parse_metadata(issue["body"]) or {}
        if LABEL_NEEDS_PDF in labels and not paper_text.from_local_pdf(
            meta.get("doi", ""), issue["number"]
        ):
            continue  # still waiting on the human
        rest.append(issue)
    return with_pdf + rest


def request_pdf(issue: dict, metadata: dict) -> None:
    """Mark an Issue as waiting on a PDF and ask for one — each step only once."""
    number = issue["number"]
    labels = issue_labels(issue)
    title = metadata.get("title") or issue["title"]

    emailed = LABEL_PDF_REQUESTED in labels
    if not emailed:
        emailed = pdf_mailbox.request(
            number,
            title=title,
            doi=metadata.get("doi") or "",
            journal=metadata.get("journal") or "",
        )
        if emailed:
            add_label(number, LABEL_PDF_REQUESTED)

    if LABEL_NEEDS_PDF not in labels:
        add_label(number, LABEL_NEEDS_PDF)
        how = HOW_EMAIL if emailed else HOW_COMMIT.format(
            number=number,
            pdf_dir="https://github.com/RaymondRuff/sciencetldr/tree/main/inbox/pdfs",
        )
        github_issue.comment(
            number,
            NEEDS_PDF_COMMENT.format(
                reason=" (the publisher refused the download)"
                if metadata.get("pdf_url")
                else "",
                how=how,
            ),
        )


def request_missing_pdfs(issues: list[dict]) -> None:
    """Ask for PDFs up front, so replies can arrive before an Issue's turn.

    Checks full-text availability only (HTTP, no model calls). Covers Issues the
    sweep didn't reach this run, and Issues marked needs-pdf before emailing
    existed.
    """
    for issue in issues:
        labels = issue_labels(issue)
        if labels & {LABEL_IN_REVIEW, LABEL_PDF_REQUESTED}:
            continue
        meta = github_issue.parse_metadata(issue["body"]) or {}
        if LABEL_NEEDS_PDF not in labels:
            try:
                if paper_text.resolve(
                    doi=meta.get("doi") or "",
                    pdf_url=meta.get("pdf_url") or "",
                    issue_number=issue["number"],
                ):
                    continue
            except paper_text.TransientFetchError:
                continue  # can't tell yet whether it's open; ask next run
        print(f"[episode] #{issue['number']}: no full text; requesting a PDF")
        request_pdf(issue, meta)


def can_open_prs() -> bool:
    """Check, before spending anything, that GH_TOKEN may create pull requests.

    Posts a PR with a head branch that cannot exist: a token with the
    permission gets 422 (validation failed), one without gets 403. Nothing is
    created either way.
    """
    repo = os.environ.get("GITHUB_REPOSITORY", "RaymondRuff/sciencetldr")
    result = subprocess.run(
        [
            "gh", "api", "-X", "POST", f"repos/{repo}/pulls",
            "-f", "title=permission probe",
            "-f", f"base={BASE_BRANCH}",
            "-f", "head=sciencetldr-permission-probe-does-not-exist",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    output = (result.stdout + result.stderr).lower()
    return "http 422" in output or "validation failed" in output


def open_review_pr(
    *,
    issue: dict,
    metadata: dict,
    files: list[Path],
    turns: list[dict],
    changes: list[str],
    duration_s: float,
    provenance: str,
) -> str:
    number = issue["number"]
    slug = slugify(metadata.get("title", "episode"), max_length=50, word_boundary=True)
    branch = f"episode/issue-{number}-{slug}"

    subprocess.run(["git", "checkout", "-b", branch], check=True)
    try:
        return _commit_push_and_open(
            branch=branch,
            number=number,
            metadata=metadata,
            files=files,
            turns=turns,
            changes=changes,
            duration_s=duration_s,
            provenance=provenance,
        )
    finally:
        # Always return to the base branch — otherwise a failure here leaves
        # the next episode's branch stacked on top of this one.
        subprocess.run(["git", "checkout", BASE_BRANCH], check=True)


def _commit_push_and_open(
    *,
    branch: str,
    number: int,
    metadata: dict,
    files: list[Path],
    turns: list[dict],
    changes: list[str],
    duration_s: float,
    provenance: str,
) -> str:
    subprocess.run(["git", "add", *[str(f) for f in files]], check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=github-actions[bot]",
            "-c",
            "user.email=github-actions[bot]@users.noreply.github.com",
            "commit",
            "-m",
            f"episode draft: {metadata.get('title', 'untitled')[:60]} (#{number})",
        ],
        check=True,
    )
    subprocess.run(["git", "push", "-u", "origin", branch], check=True)

    chars = generate_script.total_chars(turns)
    # Never put a GitHub closing keyword ("closes #N", "fixes #N", ...) in this
    # body. Merging would close the Issue before the publish run, which only
    # pairs audio with *open* Issues — the episode would lose its series
    # branding and the Issue would never get its "Published as" comment.
    body = f"""Draft episode for #{number} — **review by listening, then merge to publish**.

| | |
|---|---|
| Paper | {metadata.get('title', 'n/a')} |
| DOI | {metadata.get('doi', 'n/a')} |
| Full text via | `{provenance}` |
| Length | {duration_s / 60:.1f} min ({chars} chars) |
| Voices | Nadia = Kore, Theo = Achird ({tts_dialogue.MODEL}) |

Merging this PR puts the mp3 in `inbox/`, which triggers the publish workflow:
it normalizes the audio, writes show notes, updates `feed.xml`, and then marks the
Issue done.
Closing this PR without merging discards the draft.

### Verification pass
"""
    if changes:
        body += "\n".join(f"- {c}" for c in changes)
    else:
        body += "No corrections needed — no unsupported numbers, invalid callbacks or hype vocabulary found."
    body += f"""

### Script
The full script is in `{files[-1].relative_to(ROOT).as_posix()}` in this PR.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
"""

    url = gh(
        [
            "pr",
            "create",
            "--base",
            BASE_BRANCH,
            "--head",
            branch,
            "--title",
            f"Episode draft: {metadata.get('title', 'untitled')[:60]} (#{number})",
            "--body",
            body,
        ]
    ).strip().splitlines()[-1]
    return url


def process(issue: dict, client: anthropic.Anthropic, *, dry_run: bool) -> str:
    """Attempt one Issue.

    Returns NEEDS_PDF when no full text was reachable (nothing was spent), or
    DRAFTED once a draft (or dry-run script) exists. Anything else raises.
    """
    subprocess.run(["git", "checkout", "-q", BASE_BRANCH], check=True)
    number = issue["number"]
    metadata = github_issue.parse_metadata(issue["body"]) or {}
    title = metadata.get("title") or issue["title"]
    doi = metadata.get("doi") or ""
    print(f"\n[episode] Issue #{number}: {title[:70]}")

    try:
        resolved = paper_text.resolve(
            doi=doi, pdf_url=metadata.get("pdf_url") or "", issue_number=number
        )
    except paper_text.TransientFetchError as exc:
        print(f"  [episode] full text temporarily unreachable; retrying next run ({exc})")
        return DEFERRED
    if not resolved:
        print("  [episode] no full text reachable; requesting a PDF")
        if not dry_run:
            request_pdf(issue, metadata)
        return NEEDS_PDF
    full_text, provenance = resolved
    full_text = generate_script.prepare_paper_text(full_text)

    context = memory.memory_context(
        " ".join(
            [
                title,
                metadata.get("digest_excerpt") or "",
                full_text[:4000],
            ]
        )
    )
    turns = generate_script.draft(
        client, paper_text=full_text, metadata=metadata, memory=context
    )
    turns, changes = generate_script.verify(
        client, turns=turns, paper_text=full_text, metadata=metadata, memory=context
    )

    GENERATED.mkdir(parents=True, exist_ok=True)
    slug = slugify(title, max_length=60, word_boundary=True, save_order=True)
    stem = f"issue-{number}-{slug}"
    script_json = GENERATED / f"{stem}.script.json"
    script_md = GENERATED / f"{stem}.script.md"
    script_json.write_text(
        json.dumps(
            {
                "issue": number,
                "generated_at": datetime.now(tz=timezone.utc).isoformat(),
                "metadata": metadata,
                "paper_text_source": provenance,
                "verification_changes": changes,
                "turns": turns,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    script_md.write_text(
        generate_script.to_markdown(turns, metadata, changes), encoding="utf-8"
    )

    if dry_run:
        print(f"  [episode] dry run — wrote {script_md.relative_to(ROOT)}")
        return DRAFTED

    INBOX.mkdir(parents=True, exist_ok=True)
    wav_path = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / f"{stem}.wav"
    duration = tts_dialogue.synthesize(turns, wav_path)
    mp3_path = INBOX / f"{stem}.mp3"
    tts_dialogue.to_mp3(wav_path, mp3_path, doi=doi, title=title)

    # The script doubles as an exact transcript, so publish_episode.py can skip
    # Whisper and use text that has already been fact-checked.
    transcript_path = INBOX / f"{stem}.transcript.txt"
    transcript_path.write_text(
        "\n\n".join(f"{t['speaker']}: {t['text']}" for t in turns), encoding="utf-8"
    )

    url = open_review_pr(
        issue=issue,
        metadata=metadata,
        files=[mp3_path, transcript_path, script_json, script_md],
        turns=turns,
        changes=changes,
        duration_s=duration,
        provenance=provenance,
    )
    for stale in (LABEL_NEEDS_PDF, LABEL_PDF_REQUESTED, LABEL_FAILED):
        remove_label(number, stale)
    add_label(number, LABEL_IN_REVIEW)
    github_issue.comment(
        number,
        f"Episode draft ready for review: {url}\n\n"
        f"- Length: {duration / 60:.1f} min\n"
        f"- Full text source: `{provenance}`\n"
        f"- Verification corrections: {len(changes)}\n\n"
        "Listen to the audio in the PR, then merge to publish or close to discard.",
    )
    print(f"  [episode] review PR: {url}")
    return DRAFTED


def is_run_fatal(exc: Exception) -> bool:
    """Errors that will hit every remaining Issue too, so the run should stop."""
    if isinstance(exc, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        return True
    if isinstance(exc, anthropic.BadRequestError) and "usage limit" in str(exc).lower():
        return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issue", type=int, help="process one specific Issue number")
    parser.add_argument(
        "--mailbox-only",
        action="store_true",
        help="only generate Issues whose PDF arrived by email (the frequent poll)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="write the script but skip synthesis, commits and the PR",
    )
    args = parser.parse_args()

    github_issue.ensure_auth()
    emailed = pdf_mailbox.received()
    all_pending = github_issue.list_pending_issues()
    issues = eligible_issues(all_pending, args.issue, set(emailed))
    if args.mailbox_only:
        issues = [i for i in issues if i["number"] in emailed]

    print(
        f"{len(issues)} eligible issue(s), {len(emailed)} with an emailed PDF; "
        f"at most {MAX_PER_RUN} other paid attempt(s) this run"
    )

    if issues and not args.dry_run and not can_open_prs():
        sys.exit(
            "GH_TOKEN cannot create pull requests, so no draft could be delivered. "
            "Stopping before any paid calls. Give the GH_PAT token "
            "'Pull requests: Read and write' on this repository."
        )

    client = anthropic.Anthropic() if issues else None
    attempts = drafts = failures = 0
    for issue in issues:
        number = issue["number"]
        from_email = number in emailed
        # Emailed PDFs are deliberate requests and sit outside the cap.
        if not from_email and attempts >= MAX_PER_RUN:
            continue
        fatal = False
        try:
            outcome = process(issue, client, dry_run=args.dry_run)
            if outcome == DRAFTED and not from_email:
                attempts += 1
            if outcome == DRAFTED:
                drafts += 1
        except Exception as exc:  # noqa: BLE001 - one bad paper shouldn't stop the sweep
            failures += 1
            if not from_email:
                attempts += 1  # a failure still spent money; it counts
            fatal = is_run_fatal(exc)
            print(f"  [episode] FAILED on #{number}: {exc}")
            if not args.dry_run and not fatal:
                add_label(number, LABEL_FAILED)
                retry = (
                    "Reply to the PDF-request email again to retry."
                    if from_email
                    else "Remove the `generation-failed` label to retry."
                )
                github_issue.comment(
                    number,
                    f"Episode generation failed:\n\n```\n{exc}\n```\n\n{retry}",
                )
        finally:
            # Consume the reply whether or not the episode succeeded, so a
            # failing PDF can't re-trigger (and re-bill) every poll — except on
            # a run-wide failure, which says nothing about this PDF.
            if from_email and not args.dry_run and not fatal:
                pdf_mailbox.mark_processed(number)
        if fatal:
            print("\n[episode] stopping: this error will affect every remaining issue")
            break

    unprocessed = set(emailed) - {i["number"] for i in issues}
    for number in unprocessed:
        print(f"[mailbox] #{number}: PDF received but Issue isn't eligible; consuming reply")
        if not args.dry_run:
            pdf_mailbox.mark_processed(number)

    if not args.mailbox_only and args.issue is None and not args.dry_run:
        request_missing_pdfs(github_issue.list_pending_issues())

    print(f"\n{drafts} draft(s) produced, {attempts} paid attempt(s), {failures} failure(s)")
    if failures:
        sys.exit(f"{failures} issue(s) failed")


if __name__ == "__main__":
    main()
