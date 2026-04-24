"""Pair audio files in inbox/ with metadata, publish episodes, update feed.

Triggered by .github/workflows/publish.yml on push to inbox/**.{mp3,m4a,mp4a,wav}.
ffmpeg transcodes any accepted input format to a normalized mp3 episode file
and stamps it with canonical ID3 tags.

Metadata resolution order for each audio file:
  1. DOI embedded in the audio file's Comment tag → CrossRef canonical metadata.
  2. Oldest open Issue with the `podcast-pending` label → digest flow.
  3. Filename fallback: derive title from filename; optional PubMed DOI lookup.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import anthropic
import requests
from mutagen import File as MutagenFile
from mutagen.id3 import ID3, ID3NoHeaderError
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
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
DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-")
NCBI_KEY = os.environ.get("NCBI_API_KEY")
CROSSREF_UA = "sciencetldr/1.0 (mailto:sciencetldrpod@gmail.com)"

WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "small")
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")

# Recurring-series branding. Keyed by the `source` field set by the
# select_*_paper.py scripts in the issue's METADATA block.
SERIES = {
    "friday-trending": {
        "title_prefix": "Trending — ",
        "description_header": (
            "**Top Trending Friday** — our weekly pick of the "
            "most-discussed paper on PubMed this week."
        ),
    },
    "monday-digest": {
        "title_prefix": "",
        "description_header": (
            "**Monday Immune Engager** — our weekly pick from the "
            "latest immune-engager digest."
        ),
    },
}


def list_inbox_audio() -> list[Path]:
    files = [p for p in INBOX.iterdir() if p.is_file() and p.suffix.lower() in INBOX_AUDIO_EXTS]
    return sorted(files, key=lambda p: p.stat().st_mtime)


def next_episode_number() -> int:
    existing = [
        json.loads(p.read_text(encoding="utf-8"))["episode_number"]
        for p in EPISODES_DIR.glob("*.json")
    ]
    return (max(existing) + 1) if existing else 1


def extract_comment(audio_path: Path) -> str | None:
    """Return the Comment field from the audio file's tags, if present."""
    suffix = audio_path.suffix.lower()
    try:
        if suffix == ".mp3":
            try:
                tags = ID3(audio_path)
            except ID3NoHeaderError:
                return None
            for key in list(tags.keys()):
                if key.startswith("COMM"):
                    text = tags[key].text
                    if text:
                        return str(text[0])
        elif suffix in (".m4a", ".mp4a"):
            mp4 = MP4(audio_path)
            if not mp4.tags:
                return None
            comments = mp4.tags.get("\xa9cmt")
            if comments:
                return str(comments[0])
        else:
            f = MutagenFile(audio_path)
            if f and getattr(f, "tags", None):
                for key in ("comment", "COMM", "\xa9cmt"):
                    if key in f.tags:
                        v = f.tags[key]
                        return str(v[0] if isinstance(v, list) else v)
    except Exception as exc:
        print(f"  [metadata] tag read failed: {exc}")
    return None


def extract_doi(text: str) -> str | None:
    match = DOI_RE.search(text)
    if not match:
        return None
    return match.group(0).rstrip(".,);")


def crossref_metadata(doi: str) -> dict:
    """Fetch canonical paper metadata from CrossRef for a given DOI."""
    resp = requests.get(
        f"https://api.crossref.org/works/{doi}",
        headers={"User-Agent": CROSSREF_UA},
        timeout=15,
    )
    resp.raise_for_status()
    msg = resp.json().get("message", {})
    title = (msg.get("title") or [""])[0].strip()
    authors = [
        f"{a.get('given', '')} {a.get('family', '')}".strip()
        for a in msg.get("author", [])
        if a.get("family")
    ]
    journal = (msg.get("container-title") or [""])[0]
    raw_abstract = msg.get("abstract", "") or ""
    abstract = re.sub(r"<[^>]+>", "", raw_abstract).strip()
    return {
        "title": title,
        "doi": doi,
        "authors": authors,
        "journal": journal,
        "abstract": abstract,
        "source": "crossref",
    }


def pubmed_abstract_for_doi(doi: str) -> str | None:
    """Fetch the abstract from PubMed for a given DOI.

    CrossRef frequently returns no abstract (many publishers don't deposit one),
    so we fall back to PubMed's efetch to fill the gap before the LLM sees the
    metadata. Returns None on any failure.
    """
    try:
        es_params = {"db": "pubmed", "term": f"{doi}[aid]", "retmode": "json", "retmax": 1}
        if NCBI_KEY:
            es_params["api_key"] = NCBI_KEY
        es = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params=es_params, timeout=15,
        )
        es.raise_for_status()
        ids = es.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return None
        ef_params = {"db": "pubmed", "id": ids[0], "rettype": "abstract", "retmode": "xml"}
        if NCBI_KEY:
            ef_params["api_key"] = NCBI_KEY
        ef = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            params=ef_params, timeout=15,
        )
        ef.raise_for_status()
        root = ET.fromstring(ef.content)
        parts: list[str] = []
        for el in root.iter("AbstractText"):
            text = "".join(el.itertext()).strip()
            if not text:
                continue
            label = el.get("Label")
            parts.append(f"{label}: {text}" if label else text)
        return "\n\n".join(parts) or None
    except Exception as exc:
        print(f"  [metadata] PubMed abstract lookup failed: {exc}")
        return None


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
        try:
            cr = crossref_metadata(doi)
            if cr.get("title"):
                meta.update(cr)
                print(f"  [metadata] CrossRef title: {cr['title'][:60]}")
        except Exception as exc:
            print(f"  [metadata] CrossRef lookup failed: {exc}")
    return meta


def resolve_metadata(audio_path: Path, pending: list[dict]) -> tuple[dict, dict | None]:
    """Return (metadata, paired_issue_or_none)."""
    comment = extract_comment(audio_path)
    if comment:
        doi = extract_doi(comment)
        if doi:
            print(f"  [metadata] DOI from tag: {doi}")
            try:
                meta = crossref_metadata(doi)
                if meta.get("title"):
                    print(f"  [metadata] CrossRef title: {meta['title'][:60]}")
                    if not meta.get("abstract"):
                        pm_abstract = pubmed_abstract_for_doi(doi)
                        if pm_abstract:
                            meta["abstract"] = pm_abstract
                            print(f"  [metadata] abstract from PubMed ({len(pm_abstract)} chars)")
                        else:
                            print("  [metadata] no abstract available from CrossRef or PubMed")
                    matched_issue = None
                    doi_key = doi.lower().rstrip(".,;)")
                    for candidate in pending:
                        cm = github_issue.parse_metadata(candidate["body"]) or {}
                        cdoi = (cm.get("doi") or "").lower().rstrip(".,;)")
                        if cdoi and cdoi == doi_key:
                            matched_issue = candidate
                            if cm.get("source"):
                                meta["source"] = cm["source"]
                            print(f"  [metadata] paired with Issue #{matched_issue['number']} (source={meta.get('source')})")
                            break
                    return meta, matched_issue
                print("  [metadata] CrossRef returned no title; falling through")
            except Exception as exc:
                print(f"  [metadata] CrossRef lookup failed: {exc}; falling through")

    if pending:
        issue = pending[0]
        meta = github_issue.parse_metadata(issue["body"])
        if meta:
            print(f"  [metadata] pairing with Issue #{issue['number']}")
            return meta, issue

    print("  [metadata] filename fallback")
    return metadata_from_filename(audio_path), None


def normalize_audio(src: Path, dest: Path, metadata: dict, episode_number: int) -> None:
    """EBU R128 loudness normalization to -16 LUFS + canonical ID3 tags."""
    title = metadata.get("title", "Untitled")
    authors = metadata.get("authors") or []
    author_str = ", ".join(authors) if isinstance(authors, list) else str(authors)
    doi = metadata.get("doi", "")
    journal = metadata.get("journal", "")
    cmd = [
        "ffmpeg", "-y",
        "-i", str(src),
        "-af", "loudnorm=I=-16:LRA=11:TP=-1.5",
        "-b:a", "96k",
        "-ac", "1",
        "-metadata", f"title={title}",
        "-metadata", "artist=Science TLDR",
        "-metadata", f"album=Episode {episode_number:03d}",
        "-metadata", "genre=Science",
    ]
    if author_str:
        cmd.extend(["-metadata", f"composer={author_str}"])
    comment_bits = [f"DOI: {doi}"] if doi else []
    if journal:
        comment_bits.append(f"Journal: {journal}")
    if comment_bits:
        cmd.extend(["-metadata", f"comment={' | '.join(comment_bits)}"])
    cmd.append(str(dest))
    subprocess.run(cmd, check=True, capture_output=True)


def mp3_duration_seconds(path: Path) -> int:
    return int(MP3(path).info.length)


def transcribe_audio(audio_path: Path) -> str | None:
    """Transcribe an audio file with faster-whisper. Returns None on failure.

    Uses the `small` int8 CPU model by default (~240 MB, ~2-4x realtime).
    Override via WHISPER_MODEL / WHISPER_COMPUTE_TYPE env vars if needed.
    A transcription failure is non-fatal — we fall back to abstract-only notes.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        print(f"  [transcribe] faster-whisper unavailable, skipping: {exc}")
        return None
    try:
        print(f"  [transcribe] loading whisper {WHISPER_MODEL} ({WHISPER_COMPUTE_TYPE})")
        model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type=WHISPER_COMPUTE_TYPE)
        segments, info = model.transcribe(str(audio_path), vad_filter=True)
        parts = [seg.text.strip() for seg in segments]
        transcript = " ".join(p for p in parts if p).strip()
        print(f"  [transcribe] {len(transcript)} chars, language={info.language}")
        return transcript or None
    except Exception as exc:
        print(f"  [transcribe] failed: {exc}")
        return None


def generate_show_notes(metadata: dict, transcript: str | None = None) -> str:
    template = (PROMPTS_DIR / "show_notes.md").read_text(encoding="utf-8")
    client = anthropic.Anthropic()
    parts = [f"Paper metadata (JSON):\n{json.dumps(metadata, indent=2, ensure_ascii=False)}"]
    if transcript:
        parts.append(
            "Episode transcript (Whisper ASR — may contain minor errors in "
            "specialized terminology; reconcile against the paper metadata):\n"
            f"{transcript}"
        )
    parts.append("Write the show notes following the template in the system prompt.")
    resp = client.messages.create(
        model=SHOW_NOTES_MODEL,
        max_tokens=SHOW_NOTES_MAX_TOKENS,
        system=template,
        messages=[{"role": "user", "content": "\n\n".join(parts)}],
    )
    return resp.content[0].text.strip()


def publish_one(src: Path, metadata: dict, issue: dict | None) -> dict:
    episode_number = next_episode_number()
    paper_title = metadata.get("title", "Untitled")
    series = SERIES.get(metadata.get("source") or "")
    display_title = f"{series['title_prefix']}{paper_title}" if series else paper_title
    slug = slugify(paper_title, max_length=60, word_boundary=True, save_order=True)
    base_name = f"{episode_number:03d}-{slug}"
    final_mp3 = EPISODES_DIR / f"{base_name}.mp3"
    json_path = EPISODES_DIR / f"{base_name}.json"

    print(f"[publish] Episode {episode_number}: {paper_title[:60]} (source: {src.suffix})")
    EPISODES_DIR.mkdir(parents=True, exist_ok=True)

    print("  • normalizing audio + stamping tags")
    normalize_audio(src, final_mp3, metadata, episode_number)
    duration = mp3_duration_seconds(final_mp3)
    length_bytes = final_mp3.stat().st_size

    print("  • transcribing episode")
    transcript = transcribe_audio(src)
    if transcript:
        (EPISODES_DIR / f"{base_name}.transcript.txt").write_text(
            transcript, encoding="utf-8"
        )

    print("  • generating show notes (Sonnet)")
    show_notes = generate_show_notes(metadata, transcript=transcript)
    if series and series.get("description_header"):
        show_notes = f"{series['description_header']}\n\n{show_notes}"

    pub_date = format_datetime(datetime.now(tz=timezone.utc))
    episode_meta = {
        "guid": str(uuid.uuid4()),
        "title": f"Episode {episode_number}: {display_title}",
        "itunes_title": display_title,
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
        metadata, issue = resolve_metadata(src, pending)
        if issue is not None:
            pending.remove(issue)
        meta = publish_one(src, metadata, issue)
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
