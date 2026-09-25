"""Cross-episode memory: one distilled card per episode, plus running threads.

Raw transcripts are a poor memory — they are long, they carry ASR errors, and
they let a past episode's mistakes propagate into future ones. Instead each
published episode gets a compact card (claims, numbers, limitations, open
questions, tags) and the show keeps a human-readable `memory/threads.md` of the
recurring debates. Both are committed to the repo, so every change to the show's
memory is reviewable as a diff.

Usage:
  python scripts/memory.py build          # cards for episodes that lack one
  python scripts/memory.py threads        # rewrite threads.md from all cards
  python scripts/memory.py update         # both, incrementally (post-publish)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import anthropic

import claude

ROOT = Path(__file__).resolve().parent.parent
EPISODES_DIR = ROOT / "episodes"
MEMORY_DIR = ROOT / "memory"
CARDS_DIR = MEMORY_DIR / "cards"
THREADS_PATH = MEMORY_DIR / "threads.md"

CARD_SCHEMA = {
    "type": "object",
    "properties": {
        "episode_number": {"type": "integer"},
        "title": {"type": "string"},
        "doi": {"type": "string"},
        "journal": {"type": "string"},
        "source": {"type": "string"},
        "one_line": {
            "type": "string",
            "description": "What this paper did, in one sentence a colleague would recognise.",
        },
        "key_claims": {
            "type": "array",
            "items": {"type": "string"},
            "description": "What the authors claim, with the numbers that support each claim.",
        },
        "limitations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "What was not shown, including limitations the authors stated themselves.",
        },
        "open_questions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "The experiment or evidence that would settle the paper's central claim.",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Lowercase topic tags, e.g. 'tcr-mimic', 'cd3-affinity', 'specificity-screening'.",
        },
    },
    "required": [
        "episode_number",
        "title",
        "doi",
        "journal",
        "source",
        "one_line",
        "key_claims",
        "limitations",
        "open_questions",
        "tags",
    ],
    "additionalProperties": False,
}

CARD_SYSTEM = """You distil published podcast episodes of "Science TLDR" into \
memory cards. Each card is read later by the show's hosts so they can make \
accurate connections across episodes.

Rules:
- Every claim and number must come from the material you are given. Never infer \
a number that is not present.
- Record what the authors showed, not how the show framed it.
- Limitations matter as much as findings; include the authors' own stated \
limitations when they appear.
- Keep each list to at most five entries, each one sentence.
- Tags should be reusable across episodes: prefer 'specificity-screening' over \
'X-scan'."""

THREADS_SYSTEM = """You maintain `memory/threads.md` for the science podcast \
"Science TLDR" — the running debates the show keeps returning to across \
episodes. This file is read by the hosts when they record, so it must be \
accurate and compact.

Write markdown with one `##` section per thread. Each section:
- One sentence stating the open question the thread is about.
- 2-5 bullets, each citing the episodes that bear on it by number and what they \
added. Cite only episode numbers present in the cards or index you are given.
- A closing line: what would resolve the thread, or what to watch for.

Six to ten threads total. Prefer threads spanning three or more episodes. Drop \
threads that no longer earn their place. Never invent an episode, a number, or \
a finding. No preamble, no closing commentary — just the markdown."""


def episode_files() -> list[Path]:
    return sorted(p for p in EPISODES_DIR.glob("*.json"))


def card_path(episode_number: int) -> Path:
    return CARDS_DIR / f"{episode_number:03d}.json"


def load_cards() -> list[dict]:
    if not CARDS_DIR.is_dir():
        return []
    cards = []
    for path in sorted(CARDS_DIR.glob("*.json")):
        try:
            cards.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            print(f"[memory] skipping malformed card {path.name}: {exc}")
    return sorted(cards, key=lambda c: c.get("episode_number", 0))


def load_threads() -> str:
    return THREADS_PATH.read_text(encoding="utf-8") if THREADS_PATH.exists() else ""


STOPWORDS = frozenset(
    """the and for with from that this into their than then have been were
    which while about after under over between within across using based
    study analysis effect effects role human cells cell patients""".split()
)
FULL_CARDS = 8


def _terms(text: str) -> set[str]:
    return {
        w
        for w in re.findall(r"[a-z0-9][a-z0-9\-]{3,}", text.lower())
        if w not in STOPWORDS
    }


def _relevance(card: dict, query: set[str]) -> int:
    tags = {t.lower() for t in card.get("tags", [])}
    tag_terms = set().union(*(_terms(t) for t in tags)) if tags else set()
    text_terms = _terms(f"{card.get('title', '')} {card.get('one_line', '')}")
    # Tags are curated to be reusable across episodes, so they count double.
    return 2 * len(tag_terms & query) + len(text_terms & query)


def memory_context(query_text: str = "", full_cards: int = FULL_CARDS) -> str:
    """Memory for a script-generation prompt, sized to what the paper needs.

    Sending every card in full costs ~54k input tokens per call and is almost
    all irrelevant to any one paper. Instead: a one-line index of every episode
    (so no callback target is lost), full cards only for the episodes that share
    the most terms with this paper, and the running threads.
    """
    cards = load_cards()
    parts = []
    if cards:
        query = _terms(query_text)
        ranked = sorted(cards, key=lambda c: _relevance(c, query), reverse=True)
        chosen = [c for c in ranked[:full_cards] if _relevance(c, query) > 0]
        chosen_numbers = {c.get("episode_number") for c in chosen}

        index = [
            f"{c.get('episode_number')}: {c.get('title', '')} — {c.get('one_line', '')}"
            for c in cards
            if c.get("episode_number") not in chosen_numbers
        ]
        parts.append(
            "Past episodes. You may only reference episodes listed here, by the "
            "number shown. The most relevant ones are given as full cards; the "
            "rest as a one-line index.\n\nFull cards:\n"
            + "\n".join(json.dumps(c, ensure_ascii=False) for c in chosen)
            + "\n\nIndex of the other episodes:\n"
            + "\n".join(index)
        )
    threads = load_threads()
    if threads.strip():
        parts.append("Running threads of the show:\n" + threads)
    return "\n\n".join(parts)


def build_card(client: anthropic.Anthropic, episode_path: Path) -> dict:
    episode = json.loads(episode_path.read_text(encoding="utf-8"))
    meta = episode.get("source_metadata") or {}
    transcript_path = episode_path.with_suffix("").with_suffix(".transcript.txt")
    if not transcript_path.exists():
        transcript_path = episode_path.parent / (
            episode_path.stem + ".transcript.txt"
        )

    parts = [
        "Episode metadata (JSON):\n"
        + json.dumps(
            {
                "episode_number": episode.get("episode_number"),
                "title": episode.get("itunes_title") or episode.get("title"),
                "pub_date": episode.get("pub_date"),
                "source_metadata": meta,
            },
            indent=2,
            ensure_ascii=False,
        ),
        "Show notes as published:\n" + (episode.get("description") or ""),
    ]
    if transcript_path.exists():
        parts.append(
            "Episode transcript (ASR — may contain errors in specialised terms; "
            "reconcile against the metadata):\n"
            + transcript_path.read_text(encoding="utf-8")
        )
    parts.append("Write the memory card for this episode.")

    card = claude.structured(
        client,
        system=CARD_SYSTEM,
        user="\n\n".join(parts),
        schema=CARD_SCHEMA,
        effort="low",
        max_tokens=8000,
    )
    card["episode_number"] = episode.get("episode_number", card.get("episode_number"))
    return card


def cmd_build() -> list[dict]:
    """Write cards for episodes that lack one; return the new cards."""
    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    client = anthropic.Anthropic()
    written: list[dict] = []
    for path in episode_files():
        try:
            number = json.loads(path.read_text(encoding="utf-8"))["episode_number"]
        except (json.JSONDecodeError, KeyError) as exc:
            print(f"[memory] skipping {path.name}: {exc}")
            continue
        target = card_path(number)
        if target.exists():
            continue
        print(f"[memory] card for episode {number}: {path.name}")
        card = build_card(client, path)
        target.write_text(
            json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        written.append(card)
    print(f"[memory] wrote {len(written)} new card(s)")
    return written


def cmd_threads(new_cards: list[dict] | None = None) -> None:
    """Rewrite threads.md.

    With new_cards and an existing threads.md, revise incrementally: send only
    the new cards, the current threads, and a one-line index of every episode
    (so bullets can still cite anything). Re-sending all ~80 full cards costs
    ~54k input tokens per publish for no benefit. Without new_cards, rebuild
    from every card — the one-time backfill and the manual full refresh.
    """
    cards = load_cards()
    if not cards:
        print("[memory] no cards yet; nothing to thread")
        return
    client = anthropic.Anthropic()
    existing = load_threads()
    incremental = bool(new_cards) and bool(existing.strip())
    if incremental:
        index = "\n".join(
            f"{c.get('episode_number')}: {c.get('title', '')} — {c.get('one_line', '')}"
            for c in cards
        )
        parts = [
            "Index of every episode (number: title — summary):\n" + index,
            "New episode card(s) to fold in (one JSON object per line):\n"
            + "\n".join(json.dumps(c, ensure_ascii=False) for c in new_cards),
            "The current threads.md. Revise it to incorporate the new "
            "episode(s): extend a thread they bear on, or add one if they open "
            "a genuinely recurring question. Leave the rest as it is unless the "
            "new evidence changes it:\n" + existing,
        ]
    else:
        parts = [
            "Episode cards (one JSON object per line):\n"
            + "\n".join(json.dumps(c, ensure_ascii=False) for c in cards)
        ]
        if existing.strip():
            parts.append(
                "The current threads.md, which you are revising rather than "
                "replacing wholesale:\n" + existing
            )
    parts.append("Write the updated threads.md.")
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    THREADS_PATH.write_text(
        claude.text(
            client,
            system=THREADS_SYSTEM,
            user="\n\n".join(parts),
            effort="medium",
            max_tokens=8000,
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    how = f"{len(new_cards)} new card(s), incremental" if incremental else f"all {len(cards)} cards"
    print(f"[memory] wrote {THREADS_PATH.name} ({how})")


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "update"
    if command == "build":
        cmd_build()
    elif command == "threads":
        cmd_threads()
    elif command == "update":
        new_cards = cmd_build()
        if new_cards:
            cmd_threads(new_cards)
        else:
            print("[memory] no new episodes; threads unchanged")
    else:
        sys.exit(f"unknown command: {command}")


if __name__ == "__main__":
    main()
