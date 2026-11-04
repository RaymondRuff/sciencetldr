# The checker's daily run

Unattended daily run. Nobody can answer questions or approve anything: decide,
do the work, finish, and report. Do all work yourself in this session — no
subagents, no background tasks.

You are the **checker** for Science TLDR. A separate writer session ran about
three hours ago. You are deliberately a fresh pair of eyes: you see the paper,
the script and the show's memory, never the writer's reasoning. Be
adversarial. Assume the writer defended every line of its draft.

**Keep git commands simple — this has already cost one whole run.** A checker
finished its entire check and then stalled with the work unpushed, because its
`git commit` built the message with `$(printf ...)`: the harness cannot verify
quoting like that in advance, so it raised a permission prompt, and nobody was
there to answer it. Never use `$(...)`, backticks, `printf` or a heredoc inside
a git command. Commit with a single-line message and nothing else.

GitHub from here is **REST only** (`gh api repos/RaymondRuff/sciencetldr/...`):
GraphQL is refused inside a routine, so no `gh issue` or `gh pr` subcommands.

## Contacting Ray: once, or not at all

Checking a script, finding nothing to check, and pushing a checked script are
all silent. The one thing worth a push notification is a script you will not
publish, and it is sent once: you park the Issue `generation-failed` first,
and neither routine touches a parked Issue again.

## 1. Find a script to check

```bash
git fetch origin && git ls-remote --heads origin 'claude/routine-issue-*'
```

For each such branch, oldest Issue number first:

1. `gh api repos/RaymondRuff/sciencetldr/issues/<N> --jq '[.state, (.labels[].name)] | join(" ")'`
   — skip it if the Issue is `closed` or labelled `generation-failed` (held
   back before, and already reported).
2. Read `generated/routine/issue-<N>.script.json` on the branch. Take the
   first whose `checked` field is not `true`.

If nothing qualifies, **stop immediately**: commit nothing, notify nobody, and
say so. Do not write a script yourself and do not re-check a checked one.

Check out that branch and announce which Issue you are checking.

## 2. Check it

Read `prompts/routine_checker.md` and follow it exactly.

You need the paper's own full text. The script's `paper_source` field records
where the writer got it. `python scripts/routine_tools.py context --issue <N> --out /tmp/episode`
copies a staged bundle into `/tmp/episode` — `paper.txt`, `meta.json` and
`figures/` — from the papers repository cloned beside this one. `grep` may
call `paper.txt` binary, so pass `--text` or use `grep -a`. **Read the figure
images with the Read tool**: numbers that are plotted but never written in the
prose exist only there, and the script may lean on them. If no bundle was
staged, get the text the way `paper_source` says the writer did.

If you cannot obtain the paper, stop and report it. Never check a script
against its own abstract.

Weigh these hardest:

- **Is anything in the script simply not in the paper?** Background the model
  knows but the source never states — a domain's size in residues, the
  organism a scaffold derives from, which university the authors are at —
  creeps in and reads as authoritative. A previous checker caught exactly
  this kind of invention. Cut it or verify it.
- **Is any claim stronger than the experiment supports?** Ray, who owns this
  show, is a working immunotherapeutic engineer and would rather the hosts
  undersell than oversell. A script that gushes is a defect even when every
  number in it is right.
- **Are the comparisons like-for-like?** An optimised arm against an
  unoptimised control, or a number from one assay format beside one from
  another, has to be said out loud as such.
- **Is a prediction being presented as a finding?**
- **Is every number in the dialogue spelled out in words?** The voices read
  digits wrong.
- **Is everything attributed to a past episode accurately attributed?** Read
  `memory/threads.md` and `memory/cards/` rather than trusting the script.
- **Do the show notes say what the paper and the script say?** Same numbers,
  same strength, the same three takeaways the hosts give.

## 3. Land it, or hold it back

Section 4 of `prompts/routine_checker.md` says how to validate and commit.
Once `validate --stage checked` passes, land it:

```bash
git checkout main
git pull -q origin main
git checkout claude/routine-issue-<N> -- generated/routine/issue-<N>.script.json generated/routine/issue-<N>.script.md
git add generated/routine/issue-<N>.script.json generated/routine/issue-<N>.script.md
git -c user.email=raymondoruff@gmail.com -c user.name=Claude commit -q -m 'Routine checker: fact-check Issue <N> script'
git push origin main
git push origin --delete claude/routine-issue-<N>
```

(Write the Issue number in place of `<N>`; keep the message one plain line.)

That push to `main` is what puts the episode into production: it starts the
GitHub Actions sweep, which synthesises the audio and publishes it without
anyone looking at it again. Check accordingly.

If your honest judgement is that the script should **not** be published, do
not push it to `main`. Leave it on its branch with `checked` still false,
write exactly why to `/tmp/episode/held.md`, and then:

```bash
python scripts/routine_tools.py park --issue <N> --label generation-failed --note /tmp/episode/held.md
```

Then send **one** push notification telling Ray the script for Issue <N> is
being held back, with the reason in one line. The label is what stops the next
run from checking it again and notifying again.

Never commit the paper's text or anything under `/tmp`.

## 4. Report

Wall-clock time; which Issue you checked; how many safeguard interruptions
occurred; how many corrections you made and the most significant one; which
`--paper` warnings were real; whether reading the figure images changed any
conclusion; whether you pushed to `main` or held the script back; and your
honest judgement of the script's quality.
