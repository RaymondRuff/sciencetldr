"""Tools for writing an episode script from a Claude Code routine.

A routine writes the script on the Claude subscription instead of the API, so
it has none of the API pipeline's guarantees: no enforced output schema, no
token accounting. These two commands supply the mechanical parts instead.

  context   Gather what the writer needs for one Issue into a scratch folder
            outside the repo: the paper's full text (never committed — it may
            be paywalled), the Issue metadata, and an index of past episodes.
  validate  Check a finished script against the rules that can be checked
            without judgment. Exits non-zero, listing every problem.
  render    Write a readable .script.md beside the JSON.

Needs no API key and no GitHub login: the repository is public, so Issues are
read over the unauthenticated REST API.

Usage:
  python scripts/routine_tools.py context --issue 41 --out /tmp/episode
  python scripts/routine_tools.py validate generated/routine/issue-41.script.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
CARDS_DIR = ROOT / "memory" / "cards"
REPO = "RaymondRuff/sciencetldr"

METADATA_RE = re.compile(
    r"<!-- METADATA -->\s*```json\s*(.*?)```\s*<!-- /METADATA -->", re.DOTALL
)

TARGET_MIN_CHARS = 10_200
TARGET_MAX_CHARS = 10_800
MAX_TURN_CHARS = 900
MAX_CALLBACKS = 3
SPEAKERS = ("Nadia", "Theo")

# The register rules of prompts/host_dialogue.md that a regex can enforce.
HYPE = [
    r"revolution(?:ary|i[sz]es?|i[sz]ing)", r"game[- ]chang", r"paradigm shift",
    r"breakthrough", r"landmark", r"holy grail", r"transformative", r"groundbreaking",
    r"changes everything", r"a new era", r"mind[- ]blowing", r"\bstunning\b",
]
SHOW_FRAMING = [
    r"our usual (?:beat|territory|lane)", r"usual beat", r"outside our (?:lane|field|wheelhouse)",
    r"not our (?:normal|usual)", r"(?:protein|immunology|antibody)[a-z ]* podcast",
    r"far from our",
]

_UNITS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}
_NUMBER_WORD = "|".join(list(_TENS) + list(_UNITS) + ["hundred", "and", "a"])
EPISODE_REF_RE = re.compile(
    rf"\bepisodes?\s+((?:\d+|{_NUMBER_WORD})(?:[\s-]+(?:\d+|{_NUMBER_WORD}))*)",
    re.IGNORECASE,
)


def spoken_number(phrase: str) -> int | None:
    """'seventy-four' -> 74, 'one hundred and two' -> 102, '74' -> 74."""
    phrase = phrase.strip().lower()
    if phrase.isdigit():
        return int(phrase)
    total = 0
    seen = False
    for word in re.split(r"[\s-]+", phrase):
        if word in ("and", "a"):
            continue
        if word == "hundred":
            total = (total or 1) * 100
        elif word in _TENS:
            total += _TENS[word]
        elif word in _UNITS:
            total += _UNITS[word]
        else:
            return None
        seen = True
    return total if seen else None


def load_cards() -> list[dict]:
    cards = []
    for path in sorted(CARDS_DIR.glob("*.json")):
        try:
            cards.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return sorted(cards, key=lambda c: c.get("episode_number", 0))


# --------------------------------------------------------------------------- #
# context
# --------------------------------------------------------------------------- #


def fetch_issue(number: int) -> dict:
    import requests

    resp = requests.get(
        f"https://api.github.com/repos/{REPO}/issues/{number}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "sciencetldr"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def cmd_context(issue_number: int, out_dir: Path) -> int:
    import paper_text

    out_dir.mkdir(parents=True, exist_ok=True)
    issue = fetch_issue(issue_number)
    match = METADATA_RE.search(issue.get("body") or "")
    metadata = json.loads(match.group(1)) if match else {}
    metadata.setdefault("title", issue.get("title", ""))
    (out_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    cards = load_cards()
    index = "\n".join(
        f"{c.get('episode_number')}: {c.get('title', '')} — {c.get('one_line', '')} "
        f"[tags: {', '.join(c.get('tags', []))}]"
        for c in cards
    )
    (out_dir / "episode_index.txt").write_text(index + "\n", encoding="utf-8")
    print(f"[context] metadata.json, episode_index.txt ({len(cards)} episodes) -> {out_dir}")

    try:
        resolved = paper_text.resolve(
            doi=metadata.get("doi") or "",
            pdf_url=metadata.get("pdf_url") or "",
            issue_number=issue_number,
        )
    except paper_text.TransientFetchError as exc:
        print(f"[context] PAPER NOT FETCHED (temporary failure): {exc}")
        return 2
    if not resolved:
        print("[context] PAPER NOT FETCHED: no open full text reachable from here")
        return 2
    text, source = resolved
    text = paper_text.prepare_paper_text(text)
    (out_dir / "paper.txt").write_text(text, encoding="utf-8")
    print(f"[context] paper.txt: {len(text):,} chars via {source}")
    return 0


# --------------------------------------------------------------------------- #
# validate
# --------------------------------------------------------------------------- #


def validate(script: dict) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for a script document."""
    errors: list[str] = []
    warnings: list[str] = []

    turns = script.get("turns")
    if not isinstance(turns, list) or not turns:
        return ["`turns` must be a non-empty list"], warnings
    for i, turn in enumerate(turns):
        if not isinstance(turn, dict) or set(turn) != {"speaker", "text"}:
            errors.append(f"turn {i}: must have exactly `speaker` and `text`")
            continue
        if turn["speaker"] not in SPEAKERS:
            errors.append(f"turn {i}: speaker {turn['speaker']!r} is not Nadia or Theo")
        if not isinstance(turn["text"], str) or not turn["text"].strip():
            errors.append(f"turn {i}: empty text")
        elif len(turn["text"]) > MAX_TURN_CHARS:
            errors.append(
                f"turn {i}: {len(turn['text'])} chars (max {MAX_TURN_CHARS}; split it)"
            )
    if errors:
        return errors, warnings

    total = sum(len(t["text"]) for t in turns)
    if not TARGET_MIN_CHARS <= total <= TARGET_MAX_CHARS:
        errors.append(
            f"spoken text is {total:,} chars; must be {TARGET_MIN_CHARS:,}-{TARGET_MAX_CHARS:,}"
        )

    opening = " ".join(t["text"] for t in turns[:3])
    if "Science TLDR" not in opening:
        errors.append('cold open: "Science TLDR" must appear in the first three turns')
    for name in SPEAKERS:
        if name not in opening:
            errors.append(f"cold open: {name} must be named in the first three turns")

    full = "\n".join(t["text"] for t in turns)
    for pattern in HYPE:
        for hit in re.finditer(pattern, full, re.IGNORECASE):
            errors.append(f"hype vocabulary: {hit.group(0)!r}")
    for pattern in SHOW_FRAMING:
        for hit in re.finditer(pattern, full, re.IGNORECASE):
            errors.append(f"frames the show by field: {hit.group(0)!r}")

    known = {c.get("episode_number") for c in load_cards()}
    declared = script.get("callbacks")
    if not isinstance(declared, list) or not all(isinstance(n, int) for n in declared):
        errors.append("`callbacks` must be a list of the episode numbers the hosts cite")
        declared = []
    spoken: set[int] = set()
    for hit in EPISODE_REF_RE.finditer(full):
        number = spoken_number(hit.group(1))
        if number is not None:
            spoken.add(number)
    for number in sorted(spoken - known):
        errors.append(f"hosts cite episode {number}, which is not in memory/cards")
    for number in sorted(set(declared) - known):
        errors.append(f"`callbacks` lists episode {number}, which is not in memory/cards")
    if spoken != set(declared):
        errors.append(
            f"episodes cited in the dialogue {sorted(spoken)} != `callbacks` {sorted(declared)}"
        )
    if len(spoken) > MAX_CALLBACKS:
        errors.append(f"{len(spoken)} episode callbacks; at most {MAX_CALLBACKS}")

    for i, turn in enumerate(turns):
        if 700 < len(turn["text"]) <= MAX_TURN_CHARS:
            warnings.append(f"turn {i}: {len(turn['text'])} chars (aim for under 700)")
    nadia = sum(len(t["text"]) for t in turns if t["speaker"] == "Nadia")
    if not 0.45 <= nadia / total <= 0.75:
        warnings.append(f"Nadia speaks {nadia / total:.0%} of the text (usual 60-65%)")
    return errors, warnings


def cmd_validate(path: Path) -> int:
    script = json.loads(path.read_text(encoding="utf-8-sig"))
    errors, warnings = validate(script)
    turns = script.get("turns") or []
    total = sum(len(t.get("text", "")) for t in turns if isinstance(t, dict))
    print(f"[validate] {path.name}: {len(turns)} turns, {total:,} chars (~{total / 1060:.1f} min)")
    for w in warnings:
        print(f"  warning: {w}")
    for e in errors:
        print(f"  ERROR: {e}")
    print("[validate] " + ("FAILED" if errors else "passed"))
    return 1 if errors else 0


def cmd_render(path: Path) -> int:
    """Write a readable .script.md next to the JSON, for reviewing in GitHub."""
    script = json.loads(path.read_text(encoding="utf-8-sig"))
    turns = script["turns"]
    total = sum(len(t["text"]) for t in turns)
    lines = [
        f"# Issue #{script.get('issue', '?')} — script ({script.get('writer', 'unknown')} writer)",
        "",
        f"**Length:** {total:,} chars (~{total / 1060:.1f} min)  ",
        f"**Episodes cited:** {script.get('callbacks') or 'none'}",
        "",
    ]
    changes = script.get("verification_changes") or []
    if changes:
        lines += ["## Corrections made by the fact-check pass", ""]
        lines += [f"- {c}" for c in changes] + [""]
    lines += ["---", ""]
    for turn in turns:
        lines += [f"**{turn['speaker']}:** {turn['text']}", ""]
    out = path.with_name(path.name.replace(".script.json", ".script.md"))
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[render] wrote {out.name}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    ctx = sub.add_parser("context")
    ctx.add_argument("--issue", type=int, required=True)
    ctx.add_argument("--out", type=Path, required=True)
    val = sub.add_parser("validate")
    val.add_argument("script", type=Path)
    ren = sub.add_parser("render")
    ren.add_argument("script", type=Path)
    args = parser.parse_args()
    if args.command == "context":
        sys.exit(cmd_context(args.issue, args.out))
    if args.command == "render":
        sys.exit(cmd_render(args.script))
    sys.exit(cmd_validate(args.script))


if __name__ == "__main__":
    main()
