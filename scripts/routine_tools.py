"""Tools for writing an episode script from a Claude Code routine.

A routine writes the script on the Claude subscription instead of the API, so
it has none of the API pipeline's guarantees: no enforced output schema, no
token accounting. These commands supply the mechanical parts instead. Two
routines use them: a writer (prompts/routine_writer.md) and, in a separate
session, a checker (prompts/routine_checker.md).

  context   Gather what the writer needs for one Issue into a scratch folder
            outside the repo: the paper's full text (never committed — it may
            be paywalled), the Issue metadata, and an index of past episodes.
  validate  Check a finished script against the rules that can be checked
            without judgment, including its estimated *spoken* length and
            that it is written for the ear (no digits, bare acronyms or
            symbols). Exits non-zero, listing every problem.
  render    Write a readable .script.md beside the JSON.

Needs no API key and no GitHub login: the repository is public, so Issues are
read over the unauthenticated REST API.

Usage:
  python scripts/routine_tools.py context --issue 41 --out /tmp/episode
  python scripts/routine_tools.py validate --stage draft /tmp/episode/draft.script.json
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

# Length is measured in *spoken* characters (see spoken_form). Fitted on the
# twelve API-written episodes with audio (episodes 82-93): 1,075 spoken
# characters per minute of published audio, against which written characters
# correlated with runtime at r=0.31 and spoken ones at r=0.69. The window is
# the 10.2-10.8 minutes the old 10,200-10,800 written-character window
# actually produced.
SPOKEN_CHARS_PER_MINUTE = 1075
TARGET_MIN_CHARS = 11_000
TARGET_MAX_CHARS = 11_600
MAX_TURN_CHARS = 900  # written characters: the TTS chunker counts these
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


# --------------------------------------------------------------------------- #
# spoken form
#
# Runtime depends on what the voices say, not on what the text looks like:
# "12,779" is six characters but forty spoken ones. Counting written characters
# let the prototype hit the window by switching to digits. Length is therefore
# measured on the text as it would be read aloud.
# --------------------------------------------------------------------------- #

_ONES = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
]
_TENS_WORDS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_SCALES = [(10**12, "trillion"), (10**9, "billion"), (10**6, "million"), (1000, "thousand")]
LETTER_NAMES = {
    "A": "ay", "B": "bee", "C": "see", "D": "dee", "E": "ee", "F": "ef", "G": "gee",
    "H": "aitch", "I": "eye", "J": "jay", "K": "kay", "L": "el", "M": "em", "N": "en",
    "O": "oh", "P": "pee", "Q": "cue", "R": "ar", "S": "ess", "T": "tee", "U": "you",
    "V": "vee", "W": "double-you", "X": "ex", "Y": "why", "Z": "zee",
}
SYMBOL_WORDS = {
    "%": " percent", "&": " and ", "+": " plus ", "=": " equals ", "<": " less than ",
    ">": " greater than ", "±": " plus or minus ", "×": " times ", "~": " about ",
    "°": " degrees", "/": " slash ", "µ": "micro", "μ": "micro",
}
GREEK = {
    "α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "epsilon", "ζ": "zeta",
    "η": "eta", "θ": "theta", "κ": "kappa", "λ": "lambda", "ν": "nu", "ξ": "xi",
    "π": "pi", "ρ": "rho", "σ": "sigma", "τ": "tau", "φ": "phi", "χ": "chi",
    "ψ": "psi", "ω": "omega", "Δ": "delta", "Σ": "sigma", "Ω": "omega",
}
# Bracketed delivery directions such as [thoughtful] are performed, not spoken.
AUDIO_TAG_RE = re.compile(r"\[[a-z][a-z ,'-]*\]", re.IGNORECASE)
DOI_RE = re.compile(r"\b10\.\d{4,9}/\S+[^\s.,;:!?)\"'”’]")
NUMBER_RE = re.compile(r"\d+(?:,\d{3})+(?:\.\d+)?|\d*\.\d+|\d+")
# Two or more capitals together: CD4, HLA, CRISPR, mTORC1. Hyphenated spellings
# (C-D-four) and single capitals are fine.
ACRONYM_RE = re.compile(r"\b[A-Za-z]*[A-Z]{2,}[A-Za-z0-9]*\b")
SPELLED_LETTERS_RE = re.compile(r"\b[A-Z](?:-[A-Z])+\b")
ACRONYM_ALLOWED = {"TLDR"}  # the show's name, required verbatim in the cold open
SYMBOL_RE = re.compile("[" + re.escape("".join(SYMBOL_WORDS) + "".join(GREEK)) + "]")


def number_words(n: int) -> str:
    """12779 -> 'twelve thousand seven hundred seventy-nine'."""
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return _TENS_WORDS[tens] + (f"-{_ONES[ones]}" if ones else "")
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        return f"{_ONES[hundreds]} hundred" + (f" {number_words(rest)}" if rest else "")
    for value, name in _SCALES:
        if n >= value:
            head, rest = divmod(n, value)
            return f"{number_words(head)} {name}" + (f" {number_words(rest)}" if rest else "")
    raise ValueError(n)


def _speak_number(token: str) -> str:
    whole, _, frac = token.replace(",", "").partition(".")
    if not frac and "," not in token and len(whole) == 4 and 1100 <= int(whole) <= 2099:
        # A bare four-digit number in this range is almost always a year.
        head, tail = divmod(int(whole), 100)
        if tail == 0:
            return f"{number_words(head)} hundred"
        if head == 20 and tail < 10:
            return f"two thousand {number_words(tail)}"
        return f"{number_words(head)} {'oh ' if tail < 10 else ''}{number_words(tail)}"
    words = number_words(int(whole)) if whole else "zero"
    if frac:
        words += " point " + " ".join(_ONES[int(d)] for d in frac)
    return words


def _speak_doi(match: re.Match) -> str:
    out = []
    for ch in match.group(0):
        if ch.isdigit():
            out.append(_ONES[int(ch)])
        elif ch == ".":
            out.append("dot")
        elif ch == "/":
            out.append("slash")
        elif ch.isalpha():
            out.append(ch)
    return " ".join(out)


def _speak_letters(letters: str) -> str:
    return " ".join(LETTER_NAMES.get(c.upper(), c) for c in letters)


def _speak_acronym(match: re.Match) -> str:
    token = match.group(0)
    if token in ACRONYM_ALLOWED:
        return _speak_letters(token)
    # Capitals are read as letters, digits as numbers, lowercase as written.
    parts = re.findall(r"[A-Z]+|[a-z]+|\d+", token)
    return " ".join(
        _speak_letters(p) if p.isupper() else _speak_number(p) if p.isdigit() else p
        for p in parts
    )


def spoken_form(text: str) -> str:
    """The text roughly as the voices will say it."""
    text = AUDIO_TAG_RE.sub("", text)
    text = DOI_RE.sub(_speak_doi, text)
    text = SPELLED_LETTERS_RE.sub(lambda m: _speak_letters(m.group(0).replace("-", "")), text)
    text = ACRONYM_RE.sub(_speak_acronym, text)
    text = NUMBER_RE.sub(lambda m: f" {_speak_number(m.group(0))} ", text)
    text = SYMBOL_RE.sub(lambda m: f" {SYMBOL_WORDS.get(m.group(0)) or GREEK[m.group(0)]} ", text)
    return re.sub(r"\s+", " ", text).strip()


def spoken_chars(turns: list[dict]) -> int:
    return sum(len(spoken_form(t["text"])) for t in turns)


# --------------------------------------------------------------------------- #
# numbers against the paper
#
# Spelling numbers for the voices costs the one check a machine can do on a
# science script: whether a figure is in the paper at all. "13/26" could be
# grepped; "thirteen of twenty-six" cannot. So render the paper's numbers into
# the same spoken words and compare there. A miss is a warning, not an error —
# a spoken figure can be a legitimate rounding ("about two million" for
# 2,035,311) — but it tells the checker which numbers to look up rather than
# leaving it to read every one.
# --------------------------------------------------------------------------- #

_NUMBER_VOCAB = (
    set(_ONES)
    | {w for w in _TENS_WORDS if w}
    | {name for _, name in _SCALES}
    | {"hundred", "point", "oh", "negative", "minus"}
)
# Longest runs of number words: "zero point three six six", "twenty twenty-six".
SPOKEN_NUMBER_RE = re.compile(
    r"\b(?:" + "|".join(sorted(_NUMBER_VOCAB, key=len, reverse=True)) + r")"
    r"(?:[ -](?:" + "|".join(sorted(_NUMBER_VOCAB, key=len, reverse=True)) + r"))*\b",
    re.IGNORECASE,
)


SCALE_WORDS = {name for _, name in _SCALES}
# "22 million" in the paper is one figure written two ways; the digits alone
# speak as "twenty-two", so the scale word has to be carried across too.
PAPER_NUMBER_RE = re.compile(
    # NUMBER_RE is an alternation; group it before appending the suffix, or
    # the suffix binds to its last branch only. The lookahead keeps "5kb"
    # from reading as five thousand.
    r"(?:" + NUMBER_RE.pattern + r")\s*"
    r"(?:%|percent|million|billion|trillion|thousand|M|K|bn)?(?![A-Za-z])",
    re.IGNORECASE,
)
_SUFFIX_WORDS = {"m": "million", "k": "thousand", "bn": "billion", "%": "percent"}


YEAR_PHRASE_RE = re.compile(
    r"(?:nineteen|twenty)(?: (?:oh )?[a-z-]+)?|two thousand(?: [a-z-]+)?", re.IGNORECASE
)


def _normalise_spoken(phrase: str) -> str:
    phrase = re.sub(r"[\s-]+", " ", phrase.strip().lower())
    # The hosts drop the leading zero of a decimal: "point three nine".
    return re.sub(r"^zero point", "point", phrase)


def paper_spoken_numbers(paper_text: str) -> set[str]:
    """Every number in the paper, in the words the voices would say.

    Each figure is recorded with and without its scale word, since the script
    may say either "twenty-two million" or "twenty-two".
    """
    spoken = set()
    for match in PAPER_NUMBER_RE.finditer(paper_text):
        digits = NUMBER_RE.match(match.group(0))
        if not digits:
            continue
        words = _speak_number(digits.group(0))
        spoken.add(_normalise_spoken(words))
        suffix = match.group(0)[digits.end():].strip().lower()
        suffix = _SUFFIX_WORDS.get(suffix, suffix)
        if suffix in SCALE_WORDS:
            spoken.add(_normalise_spoken(f"{words} {suffix}"))
    return spoken


def numbers_not_in_paper(turns: list[dict], paper_text: str) -> list[str]:
    """Spoken figures with no matching number in the paper, in order, deduped.

    Single small words are skipped: "one line", "two guides" and "the third
    act" are prose, not findings, and flagging them would bury the real hits.
    """
    known = paper_spoken_numbers(paper_text)
    missing: list[str] = []
    for turn in turns:
        text = AUDIO_TAG_RE.sub("", str(turn.get("text", "")))
        # The sign-off reads the DOI aloud; its digits are not findings, and
        # episode callbacks are checked against memory/cards instead.
        if "D-O-I" in text:
            text = text.split("D-O-I")[0]
        # Episode callbacks are verified against memory/cards, not the paper.
        text = EPISODE_REF_RE.sub(" ", text)
        for match in SPOKEN_NUMBER_RE.finditer(text):
            phrase = _normalise_spoken(match.group(0))
            if phrase in known or phrase in missing:
                continue
            words = phrase.split()
            if len(words) == 1:
                value = spoken_number(phrase)
                if value is None or value < 20:
                    continue  # prose, not a figure
            if YEAR_PHRASE_RE.fullmatch(phrase):
                continue  # "twenty twenty-six" is a date, not a result
            missing.append(phrase)
    return missing


def unspoken_forms(text: str) -> list[str]:
    """Written forms the voices could read more than one way."""
    found = [m.group(0).rstrip(".,;:!?)\"'”’") for m in re.finditer(r"\S*\d\S*", text)]
    found += [
        m.group(0) for m in ACRONYM_RE.finditer(text) if m.group(0) not in ACRONYM_ALLOWED
        and not any(m.group(0) in f for f in found)
    ]
    found += [m.group(0) for m in SYMBOL_RE.finditer(AUDIO_TAG_RE.sub("", text))
              if not any(m.group(0) in f for f in found)]
    return found


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


TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def validate_provenance(script: dict, stage: str) -> list[str]:
    """The record each routine leaves: where the paper came from, and its runs.

    There is no token accounting on the subscription, so wall-clock time and
    safeguard stops per run are the only cost signals.
    """
    errors: list[str] = []
    if not str(script.get("paper_source") or "").strip():
        errors.append("`paper_source` must say where the full text came from")
    runs = script.get("runs")
    if not isinstance(runs, list) or not runs:
        return errors + ["`runs` must list each routine run that worked on this script"]
    for i, run in enumerate(runs):
        if not isinstance(run, dict):
            errors.append(f"runs[{i}]: must be an object")
            continue
        if run.get("role") not in ("writer", "checker"):
            errors.append(f"runs[{i}]: `role` must be writer or checker")
        for key in ("started", "finished"):
            if not TIMESTAMP_RE.match(str(run.get(key, ""))):
                errors.append(f"runs[{i}]: `{key}` must be a UTC time like 2026-11-06T14:03:00Z")
        if not isinstance(run.get("safeguard_stops"), int):
            errors.append(f"runs[{i}]: `safeguard_stops` must be a whole number")
    roles = [r.get("role") for r in runs if isinstance(r, dict)]
    checked = script.get("checked")
    if stage == "draft":
        if checked is not False:
            errors.append("a draft must have `checked: false`; only the checker sets it")
        if script.get("verification_changes"):
            errors.append("a draft must have empty `verification_changes`; the checker fills it")
        if roles != ["writer"]:
            errors.append(f"a draft's `runs` must be exactly one writer run, not {roles}")
    else:
        if checked is not True:
            errors.append("a checked script must have `checked: true`")
        if roles[:1] != ["writer"] or "checker" not in roles:
            errors.append(f"a checked script's `runs` must be the writer run then a checker run, not {roles}")
        if not isinstance(script.get("verification_changes"), list):
            errors.append("`verification_changes` must be a list (empty if nothing changed)")
    return errors


def validate(
    script: dict, stage: str | None = None, paper_text: str | None = None
) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for a script document.

    `stage` is "draft" (the writer's output) or "checked" (the checker's); None
    skips the provenance checks, for scripts the API pipeline wrote.
    """
    errors: list[str] = []
    warnings: list[str] = []
    if stage is not None:
        errors += validate_provenance(script, stage)

    turns = script.get("turns")
    if not isinstance(turns, list) or not turns:
        return errors + ["`turns` must be a non-empty list"], warnings
    malformed = False
    for i, turn in enumerate(turns):
        if not isinstance(turn, dict) or set(turn) != {"speaker", "text"}:
            errors.append(f"turn {i}: must have exactly `speaker` and `text`")
            malformed = True
            continue
        if turn["speaker"] not in SPEAKERS:
            errors.append(f"turn {i}: speaker {turn['speaker']!r} is not Nadia or Theo")
        if not isinstance(turn["text"], str) or not turn["text"].strip():
            errors.append(f"turn {i}: empty text")
            malformed = True
        elif len(turn["text"]) > MAX_TURN_CHARS:
            errors.append(
                f"turn {i}: {len(turn['text'])} chars (max {MAX_TURN_CHARS}; split it)"
            )
    if malformed:
        return errors, warnings

    for i, turn in enumerate(turns):
        forms = unspoken_forms(turn["text"])
        if forms:
            errors.append(
                f"turn {i}: write for the ear, not the page: {', '.join(repr(f) for f in forms)}"
            )
    if any(e.startswith("turn ") and "for the ear" in e for e in errors):
        errors.append(
            "numbers in words ('twelve thousand seven hundred seventy-nine', or 'nearly "
            "thirteen thousand' if rounding keeps the meaning); letters hyphenated "
            "('C-D-four', 'H-L-A-A-two'); acronyms said as words in ordinary case "
            "('Crispr', 'Covid'); symbols and Greek letters spelled ('percent', 'alpha')"
        )

    if paper_text:
        unmatched = numbers_not_in_paper(turns, paper_text)
        if unmatched:
            warnings.append(
                f"{len(unmatched)} spoken figure(s) with no matching number in the paper — "
                "check each against the source, or confirm it is a stated rounding: "
                + ", ".join(repr(p) for p in unmatched[:12])
                + (" …" if len(unmatched) > 12 else "")
            )

    total = spoken_chars(turns)
    if not TARGET_MIN_CHARS <= total <= TARGET_MAX_CHARS:
        errors.append(
            f"spoken length is {total:,} chars (~{total / SPOKEN_CHARS_PER_MINUTE:.1f} min); "
            f"must be {TARGET_MIN_CHARS:,}-{TARGET_MAX_CHARS:,}"
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
    nadia = spoken_chars([t for t in turns if t["speaker"] == "Nadia"])
    if not 0.45 <= nadia / total <= 0.75:
        warnings.append(f"Nadia speaks {nadia / total:.0%} of the text (usual 60-65%)")
    return errors, warnings


def cmd_validate(path: Path, stage: str, paper: Path | None = None) -> int:
    script = json.loads(path.read_text(encoding="utf-8-sig"))
    paper_text = paper.read_text(encoding="utf-8", errors="replace") if paper else None
    errors, warnings = validate(script, stage, paper_text)
    turns = [t for t in script.get("turns") or [] if isinstance(t, dict)]
    total = sum(len(spoken_form(str(t.get("text", "")))) for t in turns)
    print(
        f"[validate] {path.name}: {len(turns)} turns, {total:,} spoken chars "
        f"(~{total / SPOKEN_CHARS_PER_MINUTE:.1f} min)"
    )
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
    total = spoken_chars(turns)
    lines = [
        f"# Issue #{script.get('issue', '?')} — script ({script.get('writer', 'unknown')} writer)",
        "",
        f"**Length:** {total:,} spoken chars (~{total / SPOKEN_CHARS_PER_MINUTE:.1f} min)  ",
        f"**Episodes cited:** {script.get('callbacks') or 'none'}  ",
        f"**Paper text from:** {script.get('paper_source') or 'not recorded'}",
        "",
    ]
    runs = script.get("runs") or []
    if runs:
        lines += ["| Run | Started (UTC) | Finished (UTC) | Safeguard stops |", "|---|---|---|---|"]
        lines += [
            f"| {r.get('role', '?')} | {r.get('started', '')} | {r.get('finished', '')} "
            f"| {r.get('safeguard_stops', '')} |"
            for r in runs
        ]
        lines.append("")
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
    val.add_argument(
        "--stage", choices=("draft", "checked"), required=True,
        help="draft: the writer's output; checked: after the checker's pass",
    )
    val.add_argument(
        "--paper", type=Path, default=None,
        help="the paper's full text; warns about spoken figures not found in it",
    )
    ren = sub.add_parser("render")
    ren.add_argument("script", type=Path)
    args = parser.parse_args()
    if args.command == "context":
        sys.exit(cmd_context(args.issue, args.out))
    if args.command == "render":
        sys.exit(cmd_render(args.script))
    sys.exit(cmd_validate(args.script, args.stage, args.paper))


if __name__ == "__main__":
    main()
