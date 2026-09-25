"""Write a two-host episode script from a paper, then verify it against the paper.

Two passes:
  1. Draft — Claude writes the conversation following prompts/host_dialogue.md,
     with the show's memory (episode cards + running threads) in context.
  2. Verify — a second pass checks every number against the paper, every
     cross-episode reference against the memory cards, and the register rules
     (no hype vocabulary), and returns a corrected script plus the list of
     changes it made. That list goes in the review PR so a human can see what
     the check caught.

Both passes share one cached prefix — the show prompt as the system message,
then the paper, then the memory — so the verify pass reads it from cache rather
than paying to process it again. Only the final instruction block differs.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import anthropic

import claude

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT / "prompts"

TARGET_MIN_CHARS = 10_200
TARGET_MAX_CHARS = 10_800
# Measured across the existing back catalogue and confirmed on the Gemini 2.5
# multi-speaker voices: ~1,060 spoken characters per minute.
CHARS_PER_MINUTE = 1060
# Output includes adaptive thinking. The verify pass on a 205k-char paper hit a
# 32k ceiling and the whole attempt was lost; streaming makes 64k safe.
MAX_OUTPUT_TOKENS = 64_000

TURNS_SCHEMA = {
    "type": "object",
    "properties": {
        "turns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "speaker": {"type": "string", "enum": ["Nadia", "Theo"]},
                    "text": {"type": "string"},
                },
                "required": ["speaker", "text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["turns"],
    "additionalProperties": False,
}

VERIFIED_SCHEMA = {
    "type": "object",
    "properties": {
        "changes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "One line per correction made, naming what was wrong. Empty if nothing needed changing.",
        },
        "turns": TURNS_SCHEMA["properties"]["turns"],
    },
    "required": ["changes", "turns"],
    "additionalProperties": False,
}

VERIFY_INSTRUCTIONS = """This time you are not writing the episode: you are \
fact-checking a draft script, written to the show prompt above, against the \
paper it covers. The audience are working scientists, several of whom work on \
exactly these molecules, so an overstated or unsupported claim is the most \
costly error possible.

Check, in this order:

1. **Numbers.** Every figure spoken in the script must appear in the paper with \
that meaning. Correct any number that does not, and any that has been rounded \
in a way that changes the claim.
2. **Claim strength.** Where the script says the paper showed something, confirm \
the paper showed it rather than suggested or claimed it. Rewrite over-strong \
statements to match the evidence.
3. **Cross-episode references.** The hosts may only cite past episodes that \
appear in the memory cards provided, with the right episode number and an \
accurate description. Delete any reference that fails this.
4. **Register.** Remove hype vocabulary — revolutionary, breakthrough, \
game-changer, paradigm shift, transformative, "changes everything", and any \
leap from preclinical data to patient benefit. Enthusiasm may attach to a \
specific methodological choice, never to magnitude.
5. **Attribution.** Claims belonging to the authors must be attributed to them.
6. **Length.** Keep the total spoken characters inside the stated window, \
trimming setup and framing rather than evidence or limitations.

Preserve the hosts' voices, the disfluencies, and the structure. Change only \
what is wrong. Return the complete corrected script — every turn, not just the \
edited ones — plus a list of the changes you made, each naming the specific \
problem (for example: "Nadia said 8 of 26 bound M13L; the paper reports 13 of \
26"). If nothing needed changing, return the script unchanged and an empty \
changes list."""


def host_prompt() -> str:
    return (PROMPTS_DIR / "host_dialogue.md").read_text(encoding="utf-8")


def total_chars(turns: list[dict]) -> int:
    return sum(len(t["text"]) for t in turns)


def estimated_minutes(turns: list[dict]) -> float:
    return total_chars(turns) / CHARS_PER_MINUTE


# Papers arrive with reference lists, supplementary tables and publisher
# boilerplate; past this length the extra text costs money without improving
# the script. 120k chars is ~30k tokens — room for any main text we've seen.
MAX_PAPER_CHARS = 120_000
REFERENCES_RE = re.compile(
    r"\n\s*(References|REFERENCES|Bibliography|Literature Cited)\s*\n"
)


def prepare_paper_text(text: str) -> str:
    """Drop the reference list and cap the length, logging what was cut."""
    original = len(text)
    # Only treat a References heading as the tail if it's in the back half —
    # an early match is more likely a table of contents or a figure label.
    matches = [m for m in REFERENCES_RE.finditer(text) if m.start() > len(text) * 0.5]
    if matches:
        text = text[: matches[-1].start()]
    if len(text) > MAX_PAPER_CHARS:
        text = text[:MAX_PAPER_CHARS]
    if len(text) < original:
        print(f"  [script] paper text trimmed {original:,} -> {len(text):,} chars")
    return text


def _shared_prefix(paper_text: str, metadata: dict, memory: str) -> list[dict]:
    """The cached prefix both passes share: paper, then memory.

    Both passes also use the same system prompt, so the verify pass reads this
    whole prefix from cache instead of paying to process it a second time.
    Caching is a prefix match — keep anything that differs between the two
    passes after these blocks.
    """
    blocks = [
        {
            "type": "text",
            "text": (
                "Paper metadata (JSON):\n"
                + json.dumps(metadata, indent=2, ensure_ascii=False, sort_keys=True)
                + "\n\nFull text of the paper:\n"
                + paper_text
            ),
            "cache_control": {"type": "ephemeral"},
        }
    ]
    if memory:
        blocks.append(
            {"type": "text", "text": memory, "cache_control": {"type": "ephemeral"}}
        )
    return blocks


def draft(
    client: anthropic.Anthropic,
    *,
    paper_text: str,
    metadata: dict,
    memory: str,
) -> list[dict]:
    content = _shared_prefix(paper_text, metadata, memory)
    content.append(
        {
            "type": "text",
            "text": (
                "Write this episode's script, following the show prompt in the "
                f"system message. Total spoken text must land between "
                f"{TARGET_MIN_CHARS} and {TARGET_MAX_CHARS} characters."
            ),
        }
    )
    result = claude.structured(
        client,
        system=claude.cached_system(host_prompt()),
        user=content,
        schema=TURNS_SCHEMA,
        effort="high",
        max_tokens=MAX_OUTPUT_TOKENS,
    )
    turns = result["turns"]
    print(
        f"  [script] draft: {len(turns)} turns, {total_chars(turns)} chars "
        f"(~{estimated_minutes(turns):.1f} min)"
    )
    return turns


def verify(
    client: anthropic.Anthropic,
    *,
    turns: list[dict],
    paper_text: str,
    metadata: dict,
    memory: str,
) -> tuple[list[dict], list[str]]:
    content = _shared_prefix(paper_text, metadata, memory)
    content.append(
        {
            "type": "text",
            "text": (
                VERIFY_INSTRUCTIONS
                + "\n\nDraft script to check (JSON):\n"
                + json.dumps({"turns": turns}, indent=2, ensure_ascii=False)
                + f"\n\nThe draft is {total_chars(turns)} characters of spoken "
                f"text; the target window is {TARGET_MIN_CHARS}-{TARGET_MAX_CHARS}."
            ),
        }
    )
    result = claude.structured(
        client,
        system=claude.cached_system(host_prompt()),
        user=content,
        schema=VERIFIED_SCHEMA,
        effort="high",
        max_tokens=MAX_OUTPUT_TOKENS,
    )
    checked, changes = result["turns"], result["changes"]
    print(
        f"  [script] verified: {len(checked)} turns, {total_chars(checked)} chars "
        f"(~{estimated_minutes(checked):.1f} min), {len(changes)} correction(s)"
    )
    for change in changes:
        print(f"    - {change}")
    return checked, changes


def to_markdown(turns: list[dict], metadata: dict, changes: list[str]) -> str:
    """Human-readable script for the review PR."""
    lines = [
        f"# {metadata.get('title', 'Untitled')}",
        "",
        f"**DOI:** {metadata.get('doi', 'n/a')}  ",
        f"**Length:** {total_chars(turns)} chars (~{estimated_minutes(turns):.1f} min)",
        "",
    ]
    if changes:
        lines += ["## Corrections made by the verification pass", ""]
        lines += [f"- {c}" for c in changes]
        lines += [""]
    lines += ["---", ""]
    for turn in turns:
        lines += [f"**{turn['speaker']}:** {turn['text']}", ""]
    return "\n".join(lines)
