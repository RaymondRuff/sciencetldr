"""Turn open `podcast-pending` Issues into review-ready episode drafts.

For each eligible Issue: fetch the paper's full text, have Claude write and then
verify a two-host script, synthesize it with Gemini multi-speaker TTS, and open
a pull request carrying the audio. Merging that PR lands the mp3 in `inbox/`,
which is what the existing publish workflow watches — so review is the merge
button and nothing reaches the feed unreviewed.

Issue label states:
  podcast-pending        eligible (set by the Monday/Friday selection scripts)
  needs-pdf              no full text reachable; waiting on a manual PDF drop
  episode-in-review      a draft PR is open
  generation-failed      the run errored; needs a look before retrying

Usage:
  python scripts/generate_episode.py            # sweep eligible issues
  python scripts/generate_episode.py --issue 45 # one specific issue
  python scripts/generate_episode.py --dry-run  # script only, no audio, no PR
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
import tts_dialogue

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "inbox"
GENERATED = ROOT / "generated"

LABEL_PENDING = "podcast-pending"
LABEL_NEEDS_PDF = "needs-pdf"
LABEL_IN_REVIEW = "episode-in-review"
LABEL_FAILED = "generation-failed"

SKIP_LABELS = {LABEL_IN_REVIEW, LABEL_FAILED}
MAX_PER_RUN = int(os.environ.get("MAX_EPISODES_PER_RUN", "3"))

NEEDS_PDF_COMMENT = """No open-access full text could be reached for this paper \
automatically{reason}.

To unblock it, download the PDF and commit it as \
[`inbox/pdfs/issue-{number}.pdf`]({pdf_dir}). The generator picks it up within a \
few minutes and this label clears itself.

Publishers often refuse scripted downloads even for open-access articles, so \
this step can be needed even when the Issue lists a PDF link."""


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


def eligible_issues(explicit: int | None) -> list[dict]:
    """Issues worth attempting, oldest first.

    Not capped here: the cap in main() counts drafts actually produced, so an
    Issue that turns out to need a PDF doesn't use up the run.
    """
    issues = github_issue.list_pending_issues()
    if explicit is not None:
        chosen = [i for i in issues if i["number"] == explicit]
        if not chosen:
            raise SystemExit(f"Issue #{explicit} is not an open {LABEL_PENDING} issue")
        return chosen

    ready = []
    for issue in issues:
        labels = issue_labels(issue)
        if labels & SKIP_LABELS:
            continue
        meta = github_issue.parse_metadata(issue["body"]) or {}
        if LABEL_NEEDS_PDF in labels and not paper_text.from_local_pdf(
            meta.get("doi", ""), issue["number"]
        ):
            continue  # still waiting on the human
        ready.append(issue)
    return ready


def current_branch() -> str:
    return subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


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
    base = current_branch()

    subprocess.run(["git", "checkout", "-b", branch], check=True)
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
    body = f"""Draft episode for #{number} — **review by listening, then merge to publish**.

| | |
|---|---|
| Paper | {metadata.get('title', 'n/a')} |
| DOI | {metadata.get('doi', 'n/a')} |
| Full text via | `{provenance}` |
| Length | {duration_s / 60:.1f} min ({chars} chars) |
| Voices | Nadia = Kore, Theo = Achird ({tts_dialogue.MODEL}) |

Merging this PR puts the mp3 in `inbox/`, which triggers the publish workflow:
it normalizes the audio, writes show notes, updates `feed.xml` and closes #{number}.
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
            base,
            "--head",
            branch,
            "--title",
            f"Episode draft: {metadata.get('title', 'untitled')[:60]} (#{number})",
            "--body",
            body,
        ]
    ).strip().splitlines()[-1]

    subprocess.run(["git", "checkout", base], check=True)
    return url


def process(issue: dict, client: anthropic.Anthropic, *, dry_run: bool) -> bool:
    """Attempt one Issue. Returns True if a draft (or dry-run script) was produced."""
    number = issue["number"]
    metadata = github_issue.parse_metadata(issue["body"]) or {}
    title = metadata.get("title") or issue["title"]
    doi = metadata.get("doi") or ""
    print(f"\n[episode] Issue #{number}: {title[:70]}")

    resolved = paper_text.resolve(
        doi=doi, pdf_url=metadata.get("pdf_url") or "", issue_number=number
    )
    if not resolved:
        print("  [episode] no full text reachable; asking for a manual PDF")
        # Only ask once: a needs-pdf Issue is re-attempted only after a PDF
        # lands, and an unreadable PDF shouldn't earn a second identical comment.
        if not dry_run and LABEL_NEEDS_PDF not in issue_labels(issue):
            add_label(number, LABEL_NEEDS_PDF)
            github_issue.comment(
                number,
                NEEDS_PDF_COMMENT.format(
                    number=number,
                    reason=" (the publisher refused the download)" if metadata.get("pdf_url") else "",
                    pdf_dir="https://github.com/RaymondRuff/sciencetldr/tree/main/inbox/pdfs",
                ),
            )
        return False
    full_text, provenance = resolved

    context = memory.memory_context()
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
        return True

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
    remove_label(number, LABEL_NEEDS_PDF)
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
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issue", type=int, help="process one specific Issue number")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="write the script but skip synthesis, commits and the PR",
    )
    args = parser.parse_args()

    github_issue.ensure_auth()
    issues = eligible_issues(args.issue)
    if not issues:
        print("No eligible podcast-pending issues.")
        return
    print(f"{len(issues)} eligible issue(s); will produce at most {MAX_PER_RUN} draft(s)")

    client = anthropic.Anthropic()
    drafts = failures = 0
    for issue in issues:
        if drafts >= MAX_PER_RUN:
            break
        try:
            if process(issue, client, dry_run=args.dry_run):
                drafts += 1
        except Exception as exc:  # noqa: BLE001 - one bad paper shouldn't stop the sweep
            failures += 1
            print(f"  [episode] FAILED on #{issue['number']}: {exc}")
            if not args.dry_run:
                add_label(issue["number"], LABEL_FAILED)
                github_issue.comment(
                    issue["number"],
                    f"Episode generation failed:\n\n```\n{exc}\n```\n\n"
                    "Remove the `generation-failed` label to retry.",
                )
    print(f"\n{drafts} draft(s) produced, {failures} failure(s)")
    if failures:
        sys.exit(f"{failures} issue(s) failed")


if __name__ == "__main__":
    main()
