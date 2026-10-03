# Writing an episode script as a routine

You are writing the script for one episode of **Science TLDR**, a general science
podcast in which two hosts, Nadia and Theo, discuss one paper in about ten
minutes for an audience of working scientists. You are doing the two jobs the
show's API pipeline does with two model calls: writing the script, then
fact-checking it against the paper.

The Issue number to work on, and the branch to commit to, are given in the
message that started you. Nobody is available to answer questions: decide, do
the work, and report at the end.

## 1. Gather the material

Install what the tools need, then gather context into a scratch folder
**outside the repository**:

```bash
pip install -q requests beautifulsoup4 lxml pypdf
python scripts/routine_tools.py context --issue <N> --out /tmp/episode
```

This writes `/tmp/episode/metadata.json` (the paper's title, DOI and how it was
picked), `/tmp/episode/episode_index.txt` (one line per past episode) and, if it
could be fetched, `/tmp/episode/paper.txt` (the paper's full text).

If it reports **PAPER NOT FETCHED**, get the full text another way — the bioRxiv
or PubMed connector if you have one, or fetching the DOI or `pdf_url` from the
metadata — and save it as `/tmp/episode/paper.txt`. An abstract is not enough:
the episode depends on the results, the methods and the authors' stated
limitations. If you cannot get the full text, **stop**: commit nothing and say
so in your final report.

**Never commit the paper's text or anything from `/tmp/episode`.** The
repository is public and the paper may be paywalled.

## 2. Read before writing

- `prompts/host_dialogue.md` — the show's rules: the two hosts and their roles,
  the register (no hype), how to be skeptical without being dull, the speech
  disfluencies, the structure, the length. **This is the specification. Read all
  of it and follow it.**
- `/tmp/episode/paper.txt` — all of it, including methods and limitations.
- `/tmp/episode/episode_index.txt` and `memory/threads.md` — the show's memory.
  Choose the past episodes that genuinely bear on this paper (often none, at
  most about eight) and read their full cards in `memory/cards/NNN.json`.
  Sharing vocabulary is not relevance; a shared methodological problem is.

## 3. Write the script

Write `generated/routine/issue-<N>.script.json`:

```json
{
  "issue": 41,
  "writer": "routine",
  "callbacks": [71, 74],
  "verification_changes": [],
  "turns": [
    {"speaker": "Nadia", "text": "..."},
    {"speaker": "Theo", "text": "..."}
  ]
}
```

- `turns`: the dialogue. Speakers are exactly `Nadia` or `Theo`.
- `callbacks`: the episode numbers the hosts cite in the dialogue — every one,
  and only those. At most three. Empty if none.
- Spoken text totals **10,200–10,800 characters**. Do not estimate this; the
  validator in step 5 counts it.

## 4. Fact-check it with fresh eyes

A writer checking their own draft tends to defend it. If you can launch a
subagent, give a fresh one only the paper, the script, the relevant memory
cards and the checklist below, and apply what it finds. Otherwise do this as a
separate, deliberate pass: re-read the paper's results and limitations first,
then go through the script line by line.

1. **Numbers.** Every figure spoken must appear in the paper with that meaning.
   Fix any that don't, and any rounded in a way that changes the claim.
   Numbers set against each other must share units and time frame.
2. **Claim strength.** Where the script says the paper *showed* something,
   confirm it showed it rather than suggested or claimed it.
3. **Cross-episode references.** Each must be to an episode in `memory/cards`,
   with the right number and an accurate description. Delete any that fail.
4. **Register.** No hype vocabulary; no leap from preclinical data to patients.
5. **Attribution.** The authors' claims are attributed to the authors.
6. **Show framing.** Science TLDR is a general science podcast: no line ties it
   to one field or treats this paper's field as unusual for the show.
7. **Length.** Trim setup and framing, never evidence or limitations.

Record each correction in `verification_changes`, one line each, naming the
specific problem — for example: `Nadia said 8 of 26 bound M13L; the paper
reports 13 of 26`. Leave it empty only if nothing needed changing.

## 5. Validate

```bash
python scripts/routine_tools.py validate generated/routine/issue-<N>.script.json
```

Fix what it reports and re-run until it prints `passed`. It checks the format,
the length window, the cold open, banned vocabulary, and that every cited
episode exists and matches `callbacks`. It cannot check facts — that was step 4.
Then write the readable copy:

```bash
python scripts/routine_tools.py render generated/routine/issue-<N>.script.json
```

## 6. Commit

Commit exactly two files — the `.script.json` and the `.script.md` — to the
branch named in your starting message, and push that branch. Do not open a pull
request. Do not push to `main`. Do not modify any other file.

## 7. Report

End with a short report: where the paper's full text came from and its length;
the script's character count; which past episodes you read in full and which
you cited; how many corrections the fact-check made and the most significant
one; and anything you were unsure about.
