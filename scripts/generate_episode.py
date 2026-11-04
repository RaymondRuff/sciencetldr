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

Most scripts are now written by Claude Code routines on the subscription, in
a sandbox that cannot reach any paper source. So the sweep's other job is to
put each paper where a routine *can* read it: it fetches what is open, takes
what was emailed or uploaded, and stages either as a bundle in the private
papers repository (see paper_bundle.py). A checked routine script on main is
then synthesised here without the paper at all.

MAX_EPISODES_PER_RUN caps *attempts* — every Issue that reaches the paid model
calls counts, whether it succeeds or fails — so one run can never spend more
than that many episodes' worth. Nothing gets past it: not an emailed PDF,
which is now staged for the routine instead, and not a routine script that
fails validation. At 0 the sweep makes no paid model calls at all.

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
from typing import NamedTuple

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
import routine_tools
import tts_dialogue

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "inbox"
GENERATED = ROOT / "generated"
# The audio extensions publish.yml triggers on; a draft PR has to carry one.
AUDIO_SUFFIXES = (".mp3", ".m4a", ".mp4a", ".wav")

# Where the Claude Code routines leave a script they have already written.
ROUTINE_DIR = GENERATED / "routine"

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
DRAFTED_UNPAID = "drafted-unpaid"  # a routine wrote it; nothing was billed
NEEDS_PDF = "needs-pdf"
DEFERRED = "deferred"  # a source was rate-limited or down; try again next run
WAITING = "waiting"  # no checked script yet and the paid path is capped out

NEEDS_PDF_COMMENT = """No open-access full text could be reached for this paper \
automatically{reason}.

{how}

Publishers often refuse scripted downloads even for open-access articles, so \
this step can be needed even when the Issue lists a PDF link."""

HOW_EMAIL = """A request has been emailed. Either **reply to that email with \
the PDF attached** or [upload it to the private papers repository]({upload}) \
— both stop at 25 MB, and the email says how to shrink a paper past that. The \
next sweep stages it for the writer routine, and the episode follows within a \
day or so. The PDF is never committed to this public repository."""

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


class PapersState:
    """What this run learned about the papers repository."""

    reached: bool = False  # the staging pass got through the repository
    denied: str = ""  # why GH_PAT could not reach it, if it could not
    transient: set[int] = set()  # Issues whose sources failed only temporarily


def _paper_items(issues: list[dict]) -> list[dict]:
    items = []
    for issue in issues:
        if LABEL_IN_REVIEW in issue_labels(issue):
            continue
        meta = github_issue.parse_metadata(issue["body"]) or {}
        items.append(
            {
                "issue": issue["number"],
                "doi": meta.get("doi") or "",
                "title": meta.get("title") or issue["title"],
                "journal": meta.get("journal") or "",
                "pdf_url": meta.get("pdf_url") or "",
            }
        )
    return items


def fetch_open_papers(items: list[dict]) -> list[dict]:
    """Fetch every open paper among `items`, ready to stage. HTTP only."""
    fetched = []
    for item in items:
        number = item["issue"]
        print(f"[stage] #{number}: looking for open full text")
        try:
            found = paper_text.fetch_open_text(doi=item["doi"], pdf_url=item["pdf_url"])
        except paper_text.TransientFetchError as exc:
            print(f"[stage] #{number}: a source failed temporarily; trying again next run ({exc})")
            PapersState.transient.add(number)
            continue
        if found is None:
            print(f"[stage] #{number}: no open full text")
            continue
        print(f"[stage] #{number}: {len(found.text):,} chars via {found.provenance}")
        fetched.append(item | {"fetched": found})
    return fetched


def bundle_waiting_papers(issues: list[dict]) -> dict[int, dict]:
    """Put every waiting paper that can be had into the papers repository.

    Two sources, in order. First anything supplied — an emailed PDF or a
    browser upload — which is normalised into a bundle. Then, for each Issue
    still without one, whatever full text the open sources give, fetched
    here because Actions can reach them and the routines cannot. Either way
    the routine that writes the script reads the same bundle.

    An Issue that has a checked script already needs no paper, and is left
    alone. Never fatal: if the repository cannot be reached the reason is
    kept in PapersState.denied and the run reports it at the end.
    """
    PapersState.reached = False
    PapersState.denied = ""
    PapersState.transient = set()
    items = [i for i in _paper_items(issues) if routine_script(i["issue"]) is None]
    try:
        import paper_bundle
    except Exception as exc:  # noqa: BLE001 - pillow or pypdf missing
        print(f"[bundle] no bundles this run ({exc})")
        return {}

    bundled: dict[int, dict] = {}
    try:
        bundled.update(paper_bundle.sync_all(items))
        unbundled = [i for i in items if i["issue"] not in bundled]
        bundled.update(paper_bundle.stage_many(fetch_open_papers(unbundled)))
        PapersState.reached = True
    except paper_bundle.PapersRepoDenied as exc:
        PapersState.denied = str(exc)
        print(f"[bundle] the papers repository refused GH_PAT: {exc}")
    except Exception as exc:  # noqa: BLE001 - the papers repo is an optimisation
        print(f"[bundle] no bundles this run ({exc})")

    for issue in issues:
        if issue["number"] in bundled:
            clear_pdf_request(issue, bundled[issue["number"]])
    return bundled


def clear_pdf_request(issue: dict, meta: dict) -> None:
    """A waiting Issue's paper has arrived: say so once, and drop the labels."""
    labels = issue_labels(issue)
    if not labels & {LABEL_NEEDS_PDF, LABEL_PDF_REQUESTED}:
        return
    for stale in (LABEL_NEEDS_PDF, LABEL_PDF_REQUESTED):
        remove_label(issue["number"], stale)
    source = meta.get("provenance") or "a supplied PDF"
    try:
        github_issue.comment(
            issue["number"],
            f"The paper is in: staged for the writer routine (`{source}`). "
            "No PDF is needed any more.",
        )
    except Exception as exc:  # noqa: BLE001 - a missing comment costs nothing
        print(f"[bundle] could not comment on #{issue['number']}: {exc}")


def eligible_issues(
    issues: list[dict],
    explicit: int | None,
    emailed: set[int],
    bundled: set[int] = frozenset(),
) -> list[dict]:
    """Issues worth attempting: those with a supplied paper first, then oldest.

    Not capped here: the cap in main() counts paid attempts, so an Issue that
    turns out to need a PDF doesn't use up the run.
    """
    if explicit is not None:
        chosen = [i for i in issues if i["number"] == explicit]
        if not chosen:
            raise SystemExit(f"Issue #{explicit} is not an open {LABEL_PENDING} issue")
        return chosen

    scripted, with_pdf, uploaded, rest = [], [], [], []
    for issue in issues:
        labels = issue_labels(issue)
        number = issue["number"]
        if LABEL_IN_REVIEW in labels:
            continue
        if number in emailed:
            # A PDF reply is an explicit request to generate — including a
            # retry after a failure, so it overrides generation-failed.
            with_pdf.append(issue)
            continue
        if labels & SKIP_LABELS:
            continue
        if routine_script(number) is not None:
            # A checked script is the finished product: it needs no paper
            # text here and bills nothing, so it goes first — whatever the
            # paper's labels say about how hard its text was to reach.
            scripted.append(issue)
            continue
        meta = github_issue.parse_metadata(issue["body"]) or {}
        if number in bundled:
            # Someone supplied this paper deliberately, so it goes near the
            # front — but inside the run's cap, because an upload is not
            # consumed the way an email reply is and must not be able to
            # re-bill on every sweep.
            uploaded.append(issue)
            continue
        if LABEL_NEEDS_PDF in labels and not paper_text.from_local_pdf(
            meta.get("doi", ""), number
        ):
            continue  # still waiting on the human
        rest.append(issue)
    return scripted + with_pdf + uploaded + rest


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
        papers_repo = os.environ.get("PAPERS_REPO", "RaymondRuff/sciencetldr-papers")
        how = (
            HOW_EMAIL.format(
                upload=f"https://github.com/{papers_repo}/upload/main/papers"
            )
            if emailed
            else HOW_COMMIT.format(
                number=number,
                pdf_dir="https://github.com/RaymondRuff/sciencetldr/tree/main/inbox/pdfs",
            )
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


def request_missing_pdfs(issues: list[dict], bundled: dict[int, dict]) -> None:
    """Ask once for each paper that no open source has and nobody supplied.

    The staging pass has already tried every open source, so an Issue left
    without a bundle needs a PDF — unless its sources only failed for now, or
    the staging pass never reached the papers repository, in which case a
    supplied PDF could not reach the routine either and asking would only be
    noise. The pdf-requested label is the memory: each paper is asked for once.
    """
    if not PapersState.reached:
        print("[episode] not requesting PDFs: the papers repository was not reached")
        return
    for issue in issues:
        number = issue["number"]
        labels = issue_labels(issue)
        if labels & {LABEL_IN_REVIEW, LABEL_PDF_REQUESTED}:
            continue
        if number in bundled or number in PapersState.transient:
            continue
        if routine_script(number) is not None:
            continue
        print(f"[episode] #{number}: no full text anywhere open; requesting a PDF")
        request_pdf(issue, github_issue.parse_metadata(issue["body"]) or {})


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


def routine_script_path(number: int) -> Path:
    return ROUTINE_DIR / f"issue-{number}.script.json"


class RoutineScript(NamedTuple):
    turns: list[dict]
    changes: list[str]
    source: str
    show_notes: str


def routine_script(number: int) -> RoutineScript | None:
    """A script a Claude Code routine already wrote, if one is waiting.

    The routines run on the subscription, so a script that already exists is
    free to use, and the two Opus passes it replaces are the most expensive
    part of a run. Only a *checked* script the validator accepts is used: the
    checker's push to main is what puts an episode into production, so a
    draft that reached main some other way waits for it. A malformed script
    is treated as no script; whether the paid path may then run is the cap's
    decision, not this function's.
    """
    path = routine_script_path(number)
    if not path.is_file():
        return None
    try:
        script = json.loads(path.read_text(encoding="utf-8-sig"))
        if not script.get("checked"):
            print(f"  [episode] {path.name} has not been through the checker yet")
            return None
        errors, _ = routine_tools.validate(script, "checked")
        if errors:
            print(f"  [episode] {path.name} does not validate: {errors[0]}")
            return None
        return RoutineScript(
            script["turns"],
            script.get("verification_changes") or [],
            script.get("paper_source") or "routine",
            (script.get("show_notes") or "").strip(),
        )
    except Exception as exc:  # noqa: BLE001 - never let a bad file stop a sweep
        print(f"  [episode] could not read {path.name}: {exc}")
        return None


def process(
    issue: dict,
    client: anthropic.Anthropic,
    *,
    dry_run: bool,
    allow_paid: bool = True,
) -> str:
    """Attempt one Issue.

    A checked routine script is used as it stands: the paper was read when the
    script was written and checked, so nothing here needs its text — which
    matters, because the text often lives only in the private papers
    repository. Without one, the paid path runs only if `allow_paid`.

    Returns NEEDS_PDF when no full text was reachable (nothing was spent),
    WAITING when the paid path was not allowed (nothing was spent), or a
    DRAFTED outcome once a draft (or dry-run script) exists. Anything else
    raises.
    """
    subprocess.run(["git", "checkout", "-q", BASE_BRANCH], check=True)
    number = issue["number"]
    metadata = github_issue.parse_metadata(issue["body"]) or {}
    title = metadata.get("title") or issue["title"]
    doi = metadata.get("doi") or ""
    print(f"\n[episode] Issue #{number}: {title[:70]}")

    show_notes = ""
    written = routine_script(number)
    if written:
        turns, changes, provenance, show_notes = written
        outcome = DRAFTED_UNPAID
        print("  [episode] using the routine's checked script — no paid passes, "
              "no paper text needed")
    elif not allow_paid:
        print("  [episode] no checked routine script and no paid attempts left; waiting")
        return WAITING
    else:
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
        if client is None:
            raise RuntimeError(
                "no Anthropic client and no routine script at "
                f"{routine_script_path(number).relative_to(ROOT)}; nothing to write with"
            )
        outcome = DRAFTED
        context = memory.memory_context(
            " ".join(
                [
                    title,
                    metadata.get("digest_excerpt") or "",
                    full_text[:4000],
                ]
            ),
            client=client,
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
        return outcome

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
    sidecars = [transcript_path]
    if show_notes:
        # The routine wrote the show notes with the paper in front of it, and
        # the checker checked them, so publishing needs no model call at all.
        notes_path = INBOX / f"{stem}.notes.md"
        notes_path.write_text(show_notes + "\n", encoding="utf-8")
        sidecars.append(notes_path)

    url = open_review_pr(
        issue=issue,
        metadata=metadata,
        files=[mp3_path, *sidecars, script_json, script_md],
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
    return outcome


def carries_audio(number: int) -> bool:
    """Whether this PR actually adds an episode's audio to inbox/.

    A branch name is not evidence. The routines commit a written script on a
    branch of their own, and a PR carrying only a script publishes nothing if
    it is merged in the publish slot — it consumes the slot and leaves the real
    draft waiting another day. So the audio is what makes a draft a draft.

    A confident "nothing matches" skips the PR. A lookup that *fails* falls
    back to trusting the branch name, because silently never publishing again
    is worse than merging one PR too eagerly.
    """
    try:
        files = json.loads(gh(["pr", "view", str(number), "--json", "files"]))["files"]
    except Exception as exc:  # noqa: BLE001 - an older gh, or a transient API error
        print(
            f"[publish] could not list the files on #{number} ({exc}); "
            "falling back to the branch name"
        )
        return True
    return any(
        f["path"].startswith("inbox/") and f["path"].lower().endswith(AUDIO_SUFFIXES)
        for f in files
    )


def publish_next_draft() -> None:
    """Merge the oldest waiting episode draft, which publishes it.

    One per call, oldest first, so a backlog of drafts reaches the feed one a
    day rather than all at once. The merge is made with GH_TOKEN (the PAT), and
    a push made with a PAT — unlike one made with GITHUB_TOKEN — fires the
    publish workflow that watches inbox/.
    """
    prs = json.loads(
        gh(
            [
                "pr", "list", "--state", "open", "--limit", "100",
                "--json", "number,title,headRefName,createdAt",
            ]
        )
    )
    candidates = sorted(
        (p for p in prs if p["headRefName"].startswith("episode/")),
        key=lambda p: p["createdAt"],
    )
    drafts = []
    for pr in candidates:
        if carries_audio(pr["number"]):
            drafts.append(pr)
        else:
            print(f"[publish] #{pr['number']} carries no audio, so it is not a draft")
    if not drafts:
        print("[publish] no episode drafts waiting")
        return
    pr = drafts[0]
    gh(["pr", "merge", str(pr["number"]), "--merge", "--delete-branch"])
    print(
        f"[publish] merged draft PR #{pr['number']} ({pr['title'][:60]}); "
        f"{len(drafts) - 1} still waiting"
    )


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
    parser.add_argument(
        "--publish-next",
        action="store_true",
        help="after the sweep, merge the oldest waiting draft PR (auto-publish)",
    )
    args = parser.parse_args()

    github_issue.ensure_auth()
    emailed = pdf_mailbox.received()
    all_pending = github_issue.list_pending_issues()
    bundled = bundle_waiting_papers(all_pending)
    issues = eligible_issues(all_pending, args.issue, set(emailed), set(bundled))
    eligible_numbers = {i["number"] for i in issues}
    if args.mailbox_only:
        issues = [i for i in issues if i["number"] in emailed]

    print(
        f"{len(issues)} eligible issue(s), {len(emailed)} with an emailed PDF, "
        f"{len(bundled)} with a bundled paper; "
        f"at most {MAX_PER_RUN} paid attempt(s) this run"
    )

    if issues and not args.dry_run and not can_open_prs():
        sys.exit(
            "GH_TOKEN cannot create pull requests, so no draft could be delivered. "
            "Stopping before any paid calls. Give the GH_PAT token "
            "'Pull requests: Read and write' on this repository."
        )

    client = None
    if issues:
        try:
            client = anthropic.Anthropic()
        except Exception as exc:  # noqa: BLE001 - routine scripts need no client
            print(f"[episode] no Anthropic client ({exc}); only issues with a "
                  "routine-written script can be drafted this run")
    attempts = drafts = failures = 0
    for issue in issues:
        number = issue["number"]
        # A checked routine script bills nothing, so it sits outside the cap.
        # Nothing else does: an emailed PDF has been staged for the routine
        # above, not drafted on the API here. And "free" means a script that
        # will actually be used — one that fails validation must not carry its
        # Issue past the cap into the paid path.
        free = routine_script(number) is not None
        allow_paid = attempts < MAX_PER_RUN
        if not free and not allow_paid:
            continue
        try:
            outcome = process(
                issue, client, dry_run=args.dry_run, allow_paid=allow_paid
            )
            if outcome == DRAFTED:
                attempts += 1
            if outcome in (DRAFTED, DRAFTED_UNPAID):
                drafts += 1
        except Exception as exc:  # noqa: BLE001 - one bad paper shouldn't stop the sweep
            failures += 1
            if not free:
                attempts += 1  # a failure on the paid path still spent money
            fatal = is_run_fatal(exc)
            print(f"  [episode] FAILED on #{number}: {exc}")
            if not args.dry_run and not fatal:
                add_label(number, LABEL_FAILED)
                github_issue.comment(
                    number,
                    f"Episode generation failed:\n\n```\n{exc}\n```\n\n"
                    "Remove the `generation-failed` label to retry.",
                )
            if fatal:
                print("\n[episode] stopping: this error will affect every remaining issue")
                break

    if not args.dry_run:
        consume_replies(emailed, eligible_numbers, bundled)

    if not args.mailbox_only and args.issue is None and not args.dry_run:
        request_missing_pdfs(github_issue.list_pending_issues(), bundled)

    print(f"\n{drafts} draft(s) produced, {attempts} paid attempt(s), {failures} failure(s)")
    # After generation, so a draft made in this run can publish in this run
    # when nothing older is waiting.
    if args.publish_next and not args.dry_run:
        publish_next_draft()
    problems = []
    if failures:
        problems.append(f"{failures} issue(s) failed")
    if PapersState.denied:
        problems.append(PAPERS_DENIED_MESSAGE)
    if problems:
        sys.exit("; ".join(problems))


PAPERS_DENIED_MESSAGE = (
    "GH_PAT cannot open the private papers repository, so no emailed, uploaded "
    "or open-access paper can reach the writer routine. Edit the token at "
    "https://github.com/settings/personal-access-tokens, add the "
    "sciencetldr-papers repository, and give it Contents: Read and write"
)


def consume_replies(
    emailed: dict[int, dict], eligible_numbers: set[int], bundled: dict[int, dict]
) -> None:
    """Mark emailed PDFs used once they can no longer be lost.

    The mailbox is the only copy of an emailed paywalled PDF until it is
    staged, so a reply is consumed when its bundle exists, when the PDF
    reached a working papers repository and still would not bundle (it
    never will), or when its Issue is no longer waiting. If the repository
    was out of reach the reply is kept, and the next run tries again.
    """
    for number in emailed:
        if number in bundled:
            pdf_mailbox.mark_processed(number)
        elif number not in eligible_numbers:
            print(f"[mailbox] #{number}: PDF received but Issue isn't waiting; consuming reply")
            pdf_mailbox.mark_processed(number)
        elif PapersState.reached:
            print(f"[mailbox] #{number}: the emailed PDF would not bundle; consuming reply")
            pdf_mailbox.mark_processed(number)
            try:
                github_issue.comment(
                    number,
                    "The emailed PDF arrived but could not be read. Reply again "
                    "with a different copy, or upload one to the papers repository.",
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[mailbox] could not comment on #{number}: {exc}")
        else:
            print(f"[mailbox] #{number}: papers repository unreachable; keeping the reply")


if __name__ == "__main__":
    main()
