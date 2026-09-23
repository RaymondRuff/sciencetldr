"""Write a two-host episode script from a paper, then verify it against the paper.

Two passes:
  1. Draft — Claude writes the conversation following prompts/host_dialogue.md,
     with the show's memory (episode cards + running threads) in context.
  2. Verify — a second pass checks every number against the paper, every
     cross-episode reference against the memory cards, and the register rules
     (no hype vocabulary), and returns a corrected script plus the list of
     changes it made. That list goes in the review PR so a human can see what
     the check caught.

The paper text is the largest input and is identical across both passes, so it
sits behind a cache breakpoint.
"""
from __future__ import annotations

import json
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

VERIFY_SYSTEM = """You are fact-checking a draft episode script for the science \
podcast "Science TLDR" against the paper it covers. The audience are working \
scientists, several of whom work on exactly these molecules, so an overstated \
or unsupported claim is the most costly error possible.

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


def _paper_block(paper_text: str, metadata: dict) -> list[dict]:
    """Paper first and cached: it is the same across the draft and verify passes."""
    return [
        {
            "type": "text",
            "text": (
                "Paper metadata (JSON):\n"
                + json.dumps(metadata, indent=2, ensure_ascii=False)
                + "\n\nFull text of the paper:\n"
                + paper_text
            ),
            "cache_control": {"type": "ephemeral"},
        }
    ]


def draft(
    client: anthropic.Anthropic,
    *,
    paper_text: str,
    metadata: dict,
    memory: str,
) -> list[dict]:
    system = claude.cached_system(host_prompt())
    content = _paper_block(paper_text, metadata)
    if memory:
        content.append({"type": "text", "text": memory})
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
        client, system=system, user=content, schema=TURNS_SCHEMA, effort="high"
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
    content = _paper_block(paper_text, metadata)
    if memory:
        content.append({"type": "text", "text": memory})
    content.append(
        {
            "type": "text",
            "text": (
                "Draft script to check (JSON):\n"
                + json.dumps({"turns": turns}, indent=2, ensure_ascii=False)
                + f"\n\nThe draft is {total_chars(turns)} characters of spoken "
                f"text; the target window is {TARGET_MIN_CHARS}-{TARGET_MAX_CHARS}."
            ),
        }
    )
    result = claude.structured(
        client,
        system=claude.cached_system(VERIFY_SYSTEM),
        user=content,
        schema=VERIFIED_SCHEMA,
        effort="high",
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
