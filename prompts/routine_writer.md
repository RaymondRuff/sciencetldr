# Writing an episode script as a routine

You are writing the script for one episode of **Science TLDR**, a general science
podcast in which two hosts, Nadia and Theo, discuss one paper in about ten
minutes for an audience of working scientists.

You are the **writer**. A separate routine, the **checker**, runs later in a
fresh session and fact-checks your script against the paper. It never sees
your reasoning, only the paper, the script and the show's memory. So do not
fact-check your own draft with a subagent, and do not launch background tasks
of any kind: when this session ends, anything still running is lost.

The Issue number `<N>` is the one you took from the queue in
`prompts/routine_writer_daily.md` (or, for a one-off run, the one given in the
message that started you), and the branch is `claude/routine-issue-<N>`.
Nobody is available to answer questions: decide, do the work, and report at
the end.

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
pip install -q requests beautifulsoup4 lxml pypdf pillow
python scripts/routine_tools.py context --issue <N> --out /tmp/episode
```

This writes `/tmp/episode/metadata.json` (the paper's title, DOI and how it was
picked), `/tmp/episode/episode_index.txt` (one line per past episode) and, if it
could be fetched, `/tmp/episode/paper.txt` (the paper's full text).

When the paper was supplied as a PDF it arrives as a **bundle**, and the
context step says so. Then `paper.txt` ends in a `FIGURES AND TABLES` section
holding every caption as printed, and `/tmp/episode/figures/` holds the figure
images. This matters: **a value drawn inside a figure is not in the text at
all.** The hazard ratios on a forest plot, the points of a dot plot, the peak
of a Manhattan plot — extraction loses every one of them. A caption in that
section that names an image file is telling you the numbers are only in that
file, so open it with Read before citing anything from that figure. A caption
with no image file was drawn as vector graphics or is a table, and its numbers
are in the text above.

If it reports **PAPER NOT FETCHED**, the paper was not staged, and this
sandbox cannot reach doi.org, Europe PMC, Unpaywall or any publisher. Try the
PubMed connector (convert the DOI to a PMC id, then fetch the full text) and
the bioRxiv connector, and save what you get as `/tmp/episode/paper.txt`. An
abstract is not enough: the episode depends on the results, the methods and
the authors' stated limitations. If you cannot get the full text, **stop**:
commit nothing, park the Issue as `prompts/routine_writer_daily.md` step 2
says, and say what you tried in your report.

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
  "show_notes": "**[Full paper title](https://doi.org/...)**\n\n*Journal, 2026*\n\n...",
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
- `show_notes`: the episode page's notes, as Markdown — see below.
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

Beyond those two, the part of `prompts/host_dialogue.md` that most changes what
you write is **Numbers — few, and chosen**: fifteen to twenty-five spoken
figures in the whole episode, at most two in any turn, each one something the
other host actually reacts to, and no confidence intervals, p-values or
standard deviations read aloud. Everything else becomes a comparison, a rough
scale or a movement — "about twice as fast", "low picomolar", "barely moved".
Note what this does to length: a figure written as words is *long*, so reciting
values is the cheapest way to fill the window and the worst. The window is
there to be filled with explanation.

### Show notes

Write `show_notes` by following `prompts/show_notes.md` exactly, with your
finished script as the transcript: its three takeaways are the hosts' three
takeaways, tightened to a sentence each. The notes are read on a screen, so
here — and only here — numbers are digits and nomenclature is standard
("13 of 26", "CD4", "IL-10"). The paper is in front of you, so take the title,
journal and year from it rather than from memory. The validator checks the
structure and the 130-word budget; whether every number is right is the
checker's job, as it is for the dialogue.

## 4. Validate

```bash
python scripts/routine_tools.py validate --stage draft /tmp/episode/draft.script.json
```

Fix what it reports and re-run until it prints `passed`. It checks the format,
the spoken length, that the dialogue is written for the ear, the cold open,
banned vocabulary, that every cited episode exists and matches `callbacks`, the
show notes' structure and length, and the `runs` record. It cannot check facts. That is the checker's job, but the
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

Write that `git commit` exactly as shown, with a plain single-line `-m`
message. Never build a commit message with `$(...)`, backticks, `printf` or a
heredoc: the harness cannot verify quoting like that before the command runs,
so it raises a permission prompt, and in an unattended routine nobody is there
to answer it. A checker run on 2026-11-04 finished its whole fact-check and
then stalled with the work unpushed for exactly this reason.

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
