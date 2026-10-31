# Writing an episode script as a routine

You are writing the script for one episode of **Science TLDR**, a general science
podcast in which two hosts, Nadia and Theo, discuss one paper in about ten
minutes for an audience of working scientists.

You are the **writer**. A separate routine, the **checker**, runs later in a
fresh session and fact-checks your script against the paper. It never sees
your reasoning, only the paper, the script and the show's memory. So do not
fact-check your own draft with a subagent, and do not launch background tasks
of any kind: when this session ends, anything still running is lost.

The Issue number `<N>` and the branch to commit to are given in the message
that started you. Nobody is available to answer questions: decide, do the work,
and report at the end.

## 0. Start the clock and check this isn't a rerun

```bash
date -u +%Y-%m-%dT%H:%M:%SZ        # note it: this is your run's `started`
git fetch origin <branch> 2>/dev/null && git ls-tree -r --name-only FETCH_HEAD generated/routine/
```

If the branch already has `generated/routine/issue-<N>.script.json`, an earlier
run already wrote this draft: **stop**, commit nothing, and say so in your
report. Rerunning this routine must always be safe.

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

If it reports **PAPER NOT FETCHED**, get the full text another way: the PubMed
connector (convert the DOI to a PMC id, then fetch the full text), the bioRxiv
connector, or fetching the DOI, the `pdf_url` or a working-paper version
(NBER, SSRN, the authors' pages) directly. Save it as `/tmp/episode/paper.txt`.
An abstract is not enough: the episode depends on the results, the methods and
the authors' stated limitations. If you cannot get the full text, **stop**:
commit nothing and say what you tried in your report.

Note exactly where the text came from, for example `PubMed Central PMC13614707
via the PubMed connector` or `NBER working paper w31234 PDF,
https://www.nber.org/...`. This goes in the script as `paper_source` so the
checker can fetch the same text.

**Never commit the paper's text or anything from `/tmp/episode`.** The
repository is public and the paper may be paywalled.

## 2. Read before writing

- `prompts/host_dialogue.md`: the show's rules (the two hosts and their roles,
  the register with no hype, how to be skeptical without being dull, the speech
  disfluencies, the structure). **This is the specification. Read all of it and
  follow it**, with the two overrides in step 3.
- `/tmp/episode/paper.txt`: all of it, including methods and limitations.
- `/tmp/episode/episode_index.txt` and `memory/threads.md`: the show's memory.
  Choose the past episodes that genuinely bear on this paper (often none, at
  most about eight) and read their full cards in `memory/cards/NNN.json`.
  Sharing vocabulary is not relevance; a shared methodological problem is.

## 3. Write the script

Build it at `/tmp/episode/draft.script.json`, **not inside the repository**. A
hook commits untracked repository files when a session ends, so a half-written
draft there could be pushed if this session is cut short.

```json
{
  "issue": 86,
  "writer": "routine",
  "paper_source": "NBER working paper w31234 PDF, https://www.nber.org/...",
  "checked": false,
  "callbacks": [71, 74],
  "verification_changes": [],
  "runs": [
    {"role": "writer", "started": "2026-11-06T14:03:00Z",
     "finished": "2026-11-06T14:21:00Z", "safeguard_stops": 0}
  ],
  "turns": [
    {"speaker": "Nadia", "text": "..."},
    {"speaker": "Theo", "text": "..."}
  ]
}
```

- `turns`: the dialogue. Speakers are exactly `Nadia` or `Theo`.
- `callbacks`: the episode numbers the hosts cite in the dialogue, every one and
  only those. At most three. Empty if none.
- `checked` stays `false` and `verification_changes` stays empty: both belong to
  the checker.
- `runs`: your one run. `finished` is the time you validate for the last time.

Two rules here **override** `prompts/host_dialogue.md`:

1. **Write every word as it will be spoken.** The voices read the text
   literally, so the validator rejects digits, runs of capitals and symbols in
   the dialogue:
   - numbers in words: "twelve thousand seven hundred seventy-nine", or "nearly
     thirteen thousand" where rounding does not change the claim. Years too:
     "twenty twenty-four".
   - acronyms said as letters, hyphenated: "C-D-four", "H-L-A-A-two", "D-O-I".
   - acronyms said as words, in ordinary case: "Crispr", "Covid".
   - symbols and Greek letters spelled: "percent", "plus or minus", "alpha".
   - the DOI in the sign-off, spelled for the ear: "ten dot one two five seven
     slash pol dot two zero two four zero eight zero six".
   The one exception is the show's name, "Science TLDR".
2. **Length is measured as spoken text: 11,000 to 11,600 characters** of the
   text as read aloud, about 10.2 to 10.8 minutes. This replaces the
   specification's 10,200 to 10,800 written characters. Writing numbers as
   words costs exactly the characters it costs in airtime, so there is nothing
   to gain from any spelling. Do not estimate the length: run the validator in
   step 4 early and often.

## 4. Validate

```bash
python scripts/routine_tools.py validate --stage draft /tmp/episode/draft.script.json
```

Fix what it reports and re-run until it prints `passed`. It checks the format,
the spoken length, that the dialogue is written for the ear, the cold open,
banned vocabulary, that every cited episode exists and matches `callbacks`, and
the `runs` record. It cannot check facts. That is the checker's job, but the
specification's accuracy rules still bind you. When you trim, cut setup and
framing, never evidence or limitations.

## 5. Commit

```bash
mkdir -p generated/routine
cp /tmp/episode/draft.script.json generated/routine/issue-<N>.script.json
python scripts/routine_tools.py render generated/routine/issue-<N>.script.json
git checkout -b <branch>
git add generated/routine/issue-<N>.script.json generated/routine/issue-<N>.script.md
git commit -m "Routine writer: draft script for Issue #<N>"
git push -u origin <branch>
```

Commit exactly those two files. Keep the commit message to that one line: the
checker should meet the script without your commentary. Do not open a pull
request. Do not push to `main`. Do not modify any other file.

## If a safeguard stops you

Your session may be stopped by a safety classifier, which shows up as a message
saying your response was stopped. This happens on ordinary research papers and
is not a judgment of your work. Do not reproduce the stopped content. Continue
the task from where you were, and count each stop in `safeguard_stops`. If you
are stopped so often that you cannot finish, commit nothing and report it.
Because nothing is committed until the draft validates, a rerun will start
cleanly.

## 6. Report

End with a short report:

- where the paper's full text came from, and its length;
- the spoken length and the validator result;
- which past episodes you read in full and which you cited;
- `started`, `finished` and the number of safeguard stops;
- anything you were unsure about.
