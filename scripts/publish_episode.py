"""Pair audio files in inbox/ with metadata, publish episodes, update feed.

Triggered by .github/workflows/publish.yml on push to inbox/**.{mp3,m4a,mp4a,json}.
ffmpeg transcodes any accepted input format to a normalized mp3 episode file.

Metadata resolution order for each audio file:
  1. JSON sidecar with the same basename (e.g. foo.m4a + foo.json) — one-off flow.
  2. Oldest open Issue with the `podcast-pending` label — digest flow.
  3. Filename fallback: derive title from the filename; optionally look up the
     DOI via PubMed title search.
"""
from __future__ import annotations

import json
import os
import re
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
import requests
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

INBOX_AUDIO_EXTS = (".mp3", ".m4a", ".mp4a", ".wav")
DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-")
NCBI_KEY = os.environ.get("NCBI_API_KEY")


def list_inbox_audio() -> list[Path]:
    files = [p for p in INBOX.iterdir() if p.is_file() and p.suffix.lower() in INBOX_AUDIO_EXTS]
    return sorted(files, key=lambda p: p.stat().st_mtime)


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


def pubmed_doi_from_title(title: str) -> str | None:
    """Best-effort DOI lookup via PubMed title search. Returns None on any error."""
    try:
        params = {"db": "pubmed", "term": f'"{title}"[ti]', "retmode": "json", "retmax": 1}
        if NCBI_KEY:
            params["api_key"] = NCBI_KEY
        es = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params=params, timeout=15,
        )
        es.raise_for_status()
        ids = es.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return None
        sm_params = {"db": "pubmed", "id": ids[0], "retmode": "json"}
        if NCBI_KEY:
            sm_params["api_key"] = NCBI_KEY
        sm = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
            params=sm_params, timeout=15,
        )
        sm.raise_for_status()
        result = sm.json().get("result", {}).get(ids[0], {})
        for aid in result.get("articleids", []):
            if aid.get("idtype") == "doi":
                return aid.get("value")
    except Exception as exc:
        print(f"  [metadata] PubMed lookup failed: {exc}")
    return None


def metadata_from_filename(audio_path: Path) -> dict:
    stem = DATE_PREFIX_RE.sub("", audio_path.stem)
    title = stem.replace("_", " ").replace("-", " ").strip()
    title = (title[:1].upper() + title[1:]) if title else "Untitled"
    meta = {"title": title, "source": "filename-fallback"}
    doi = pubmed_doi_from_title(title)
    if doi:
        meta["doi"] = doi
        print(f"  [metadata] PubMed matched DOI: {doi}")
    return meta


def sidecar_for(audio_path: Path) -> Path | None:
    candidate = audio_path.with_suffix(".json")
    return candidate if candidate.exists() else None


def resolve_metadata(audio_path: Path, pending: list[dict]) -> tuple[dict, dict | None, Path | None]:
    """Return (metadata, paired_issue_or_none, sidecar_path_or_none)."""
    sidecar = sidecar_for(audio_path)
    if sidecar:
        print(f"  [metadata] sidecar {sidecar.name}")
        return json.loads(sidecar.read_text(encoding="utf-8")), None, sidecar

    if pending:
        issue = pending[0]
        meta = github_issue.parse_metadata(issue["body"])
        if meta:
            print(f"  [metadata] pairing with Issue #{issue['number']}")
            return meta, issue, None

    print("  [metadata] filename fallback")
    return metadata_from_filename(audio_path), None, None


def publish_one(src: Path, metadata: dict, issue: dict | None, sidecar: Path | None) -> dict:
    episode_number = next_episode_number()
    paper_title = metadata.get("title", "Untitled")
    slug = slugify(paper_title, max_length=60, word_boundary=True, save_order=True)
    base_name = f"{episode_number:03d}-{slug}"
    final_mp3 = EPISODES_DIR / f"{base_name}.mp3"
    json_path = EPISODES_DIR / f"{base_name}.json"

    print(f"[publish] Episode {episode_number}: {paper_title[:60]} (source: {src.suffix})")
    EPISODES_DIR.mkdir(parents=True, exist_ok=True)

    print("  • normalizing audio")
    normalize_audio(src, final_mp3)
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
        "source_issue": issue["number"] if issue else None,
    }
    json_path.write_text(
        json.dumps(episode_meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    src.unlink()
    if sidecar and sidecar.exists():
        sidecar.unlink()
    print(f"  ✓ wrote {final_mp3.name}")
    return episode_meta


def main() -> None:
    audio_files = list_inbox_audio()
    if not audio_files:
        print("No audio files in inbox/, nothing to publish.")
        return

    try:
        pending = github_issue.list_pending_issues()
    except subprocess.CalledProcessError as exc:
        print(f"[warn] could not list pending issues: {exc}")
        pending = []

    published: list[tuple[dict, dict | None]] = []
    for src in audio_files:
        metadata, issue, sidecar = resolve_metadata(src, pending)
        if issue is not None:
            pending.remove(issue)
        meta = publish_one(src, metadata, issue, sidecar)
        published.append((meta, issue))

    print("\n[feed] regenerating feed.xml")
    feed_builder.main()

    repo = os.environ.get("GITHUB_REPOSITORY", "RaymondRuff/sciencetldr")
    base_url = f"https://{repo.split('/')[0].lower()}.github.io/{repo.split('/')[1]}/"

    for meta, issue in published:
        if issue is None:
            continue
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
