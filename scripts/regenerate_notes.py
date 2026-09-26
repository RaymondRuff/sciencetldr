"""Rewrite the show notes of already-published episodes with the current prompt.

Uses the same generation as publishing (publish_episode.generate_show_notes,
prompts/show_notes.md, the series header), fed from each episode's stored
source metadata and transcript, then rebuilds feed.xml. The audio, GUID,
title and publication date are untouched, so podcast apps simply show the
new notes on their next refresh.

Usage:
  python scripts/regenerate_notes.py 82 83
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import feed_builder
import publish_episode

EPISODES_DIR = Path(__file__).resolve().parent.parent / "episodes"


def episode_json(number: int) -> Path:
    matches = sorted(EPISODES_DIR.glob(f"{number:03d}-*.json"))
    if len(matches) != 1:
        raise SystemExit(f"expected one episode {number:03d} JSON, found {len(matches)}")
    return matches[0]


def regenerate(number: int) -> None:
    path = episode_json(number)
    episode = json.loads(path.read_text(encoding="utf-8"))
    metadata = episode.get("source_metadata") or {}
    transcript_path = path.with_name(path.stem + ".transcript.txt")
    transcript = (
        transcript_path.read_text(encoding="utf-8") if transcript_path.exists() else None
    )

    notes = publish_episode.generate_show_notes(metadata, transcript=transcript)
    series = publish_episode.SERIES.get(metadata.get("source") or "")
    if series and series.get("description_header"):
        notes = f"{series['description_header']}\n\n{notes}"

    before = len(episode.get("description", "").split())
    episode["description"] = notes
    path.write_text(json.dumps(episode, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"[notes] episode {number}: {before} -> {len(notes.split())} words "
        f"({'with' if transcript else 'without'} transcript)"
    )


def main() -> None:
    numbers = [int(n) for n in " ".join(sys.argv[1:]).replace(",", " ").split()]
    if not numbers:
        raise SystemExit("usage: regenerate_notes.py EPISODE [EPISODE ...]")
    for number in numbers:
        regenerate(number)
    feed_builder.main()


if __name__ == "__main__":
    main()
