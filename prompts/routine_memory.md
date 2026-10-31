# Updating the show's memory as a routine

The show's memory is two things in the repository:

- `memory/cards/NNN.json` — one distilled card per published episode.
- `memory/threads.md` — the recurring debates the show returns to.

Both are read by whoever writes the next episode, so they are the mechanism by
which the hosts can refer back accurately. `scripts/memory.py` does this through
the Anthropic API; **you are doing it instead, so do not run that script.**
Write the files yourself.

## 1. Which episodes need a card

```bash
ls memory/cards/ | tail -3
ls episodes/*.json | tail -12
```

Every published episode needs `memory/cards/NNN.json`, zero-padded to three
digits. Work in ascending order and skip any that already exists.

## 2. What a card contains

Read, for each episode: `episodes/NNN-*.json` (the `description` field is the
published show notes; `source_metadata` holds the paper's title, DOI, journal
and which series picked it) and `episodes/NNN-*.transcript.txt` if present.

```json
{
  "episode_number": 85,
  "title": "the paper's title, not the episode title",
  "doi": "10.1016/j.cell.2026.08.002",
  "journal": "Cell",
  "source": "monday-digest",
  "one_line": "What this paper did, in one sentence a colleague would recognise.",
  "key_claims": ["What the authors claim, with the numbers that support it."],
  "limitations": ["What was not shown, including the authors' own stated limits."],
  "open_questions": ["The experiment that would settle the central claim."],
  "tags": ["perturb-seq", "cd4-t-cells", "context-specificity"]
}
```

Rules:

- Every claim and number must come from the episode's own notes or transcript.
  Never infer a number that is not there.
- Record what the authors showed, not how the hosts framed it.
- Limitations matter as much as findings.
- At most five entries per list, one sentence each.
- **Digits and standard nomenclature**, whatever the transcript does. The
  transcript spells figures out for the voices that read it aloud ("thirteen of
  twenty-six", "C-D-four"); a card is read later by a model, so write "13 of
  26" and "CD4".
- Tags are lowercase and meant to be reused across episodes: prefer
  `specificity-screening` over `X-scan`.

## 3. Then update the threads

Read the existing `memory/threads.md` and every card, then revise it. Do not
rewrite it from scratch: extend the threads the new episodes bear on, and add a
thread only if they open a genuinely recurring question.

Each `##` section: one sentence stating the open question; two to five bullets,
each citing the episodes that bear on it by number and what each added; a
closing line saying what would resolve it or what to watch for. Six to ten
threads total. Drop any that no longer earn their place.

Cite only episode numbers that have a card. Never invent an episode, a number
or a finding.

## 4. Commit

```bash
git add memory/
git commit -m "Routine memory: cards for episodes <first>-<last>, threads updated"
git push origin <branch>
```

Commit only files under `memory/`. Do not modify anything else, and do not open
a pull request.

## 5. Report

Say which cards you wrote, which threads you changed and why, and anything in
the back catalogue that looked wrong while you were reading it.
