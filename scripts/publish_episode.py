"""Pair MP3s in inbox/ with pending podcast Issues, publish, update feed.

Triggered by .github/workflows/publish.yml on push to inbox/**.mp3.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import anthropic
from mutagen.mp3 import MP3
from slugify import slugify

import feed_builder
import github_issue

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "inbox"
EPISODES_DIR = ROOT / "episodes"
PROMPTS_DIR = ROOT / "prompts"

SHOW_NOTES_MODEL = "claude-sonnet-4-6"
SHOW_NOTES_MAX_TOKENS = 1500


def list_inbox_mp3s() -> list[Path]:
    return sorted(INBOX.glob("*.mp3"), key=lambda p: p.stat().st_mtime)


def next_episode_number() -> int:
    existing = [
        json.loads(p.read_text(encoding="utf-8"))["episode_number"]
        for p in EPISODES_DIR.glob("*.json")
    ]
    return (max(existing) + 1) if existing else 1


def normalize_audio(src: Path, dest: Path) -> None:
    """EBU R128 loudness normalization to -16 LUFS, podcast standard."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(src),
        "-af", "loudnorm=I=-16:LRA=11:TP=-1.5",
        "-b:a", "96k",
        "-ac", "1",
        str(dest),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def mp3_duration_seconds(path: Path) -> int:
    return int(MP3(path).info.length)


def generate_show_notes(metadata: dict) -> str:
    template = (PROMPTS_DIR / "show_notes.md").read_text(encoding="utf-8")
    client = anthropic.Anthropic()
    user_message = (
        "Paper metadata (JSON):\n"
        f"{json.dumps(metadata, indent=2, ensure_ascii=False)}\n\n"
        "Write the show notes following the template in the system prompt."
    )
    resp = client.messages.create(
        model=SHOW_NOTES_MODEL,
        max_tokens=SHOW_NOTES_MAX_TOKENS,
        system=template,
        messages=[{"role": "user", "content": user_message}],
    )
    return resp.content[0].text.strip()


def publish_one(mp3: Path, issue: dict) -> dict:
    metadata = github_issue.parse_metadata(issue["body"])
    if not metadata:
        sys.exit(f"Issue #{issue['number']} has no METADATA block")

    episode_number = next_episode_number()
    paper_title = metadata.get("title", "Untitled")
    slug = slugify(paper_title, max_length=60, word_boundary=True, save_order=True)
    base_name = f"{episode_number:03d}-{slug}"
    final_mp3 = EPISODES_DIR / f"{base_name}.mp3"
    json_path = EPISODES_DIR / f"{base_name}.json"

    print(f"[publish] Episode {episode_number}: {paper_title[:60]}")
    EPISODES_DIR.mkdir(parents=True, exist_ok=True)

    print("  • normalizing audio")
    normalize_audio(mp3, final_mp3)
    duration = mp3_duration_seconds(final_mp3)
    length_bytes = final_mp3.stat().st_size

    print("  • generating show notes (Sonnet)")
    show_notes = generate_show_notes(metadata)

    pub_date = format_datetime(datetime.now(tz=timezone.utc))
    episode_meta = {
        "guid": str(uuid.uuid4()),
        "title": f"Episode {episode_number}: {paper_title}",
        "itunes_title": paper_title,
        "description": show_notes,
        "pub_date": pub_date,
        "duration_seconds": duration,
        "episode_number": episode_number,
        "episode_type": "full",
        "explicit": "false",
        "enclosure_filename": final_mp3.name,
        "enclosure_length_bytes": length_bytes,
        "source_metadata": metadata,
        "source_issue": issue["number"],
    }
    json_path.write_text(
        json.dumps(episode_meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    mp3.unlink()
    print(f"  ✓ wrote {final_mp3.name}")
    return episode_meta


def main() -> None:
    mp3s = list_inbox_mp3s()
    if not mp3s:
        print("No MP3s in inbox/, nothing to publish.")
        return

    pending = github_issue.list_pending_issues()
    if not pending:
        sys.exit(
            "Found MP3s in inbox/ but no open issues with the "
            f"'{github_issue.PENDING_LABEL}' label. Aborting."
        )

    pairs = list(zip(mp3s, pending))
    if len(mp3s) != len(pending):
        print(
            f"WARNING: {len(mp3s)} MP3s vs {len(pending)} pending issues — "
            f"pairing oldest {len(pairs)} only."
        )

    published = []
    for mp3, issue in pairs:
        meta = publish_one(mp3, issue)
        published.append((meta, issue))

    print("\n[feed] regenerating feed.xml")
    feed_builder.main()

    repo = os.environ.get("GITHUB_REPOSITORY", "RaymondRuff/sciencetldr")
    base_url = f"https://{repo.split('/')[0].lower()}.github.io/{repo.split('/')[1]}/"

    for meta, issue in published:
        permalink = f"{base_url}#episode-{meta['episode_number']:03d}"
        github_issue.comment(
            issue["number"],
            f"Published as **Episode {meta['episode_number']}** — feed will update within ~2 minutes.\n\n"
            f"- Permalink: {permalink}\n"
            f"- Direct MP3: {base_url}episodes/{meta['enclosure_filename']}\n"
            f"- GUID: `{meta['guid']}`",
        )
        github_issue.close(issue["number"])
        print(f"  ✓ closed issue #{issue['number']}")


if __name__ == "__main__":
    main()
