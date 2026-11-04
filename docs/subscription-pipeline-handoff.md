# Handoff: move episode generation onto the Claude subscription

Written 2026-10-31 for a fresh session. Self-contained: assume no memory of
earlier conversations. The goal is approved and the direction is settled; what
follows is the work.

## The decision

Script generation currently runs on the **Anthropic API** from GitHub Actions
and costs **$1.35–$1.91 per episode**. In October the account hit its API spend
limit, which broke the memory workflow nine times in a row. The owner has a
Claude Pro subscription whose weekly cap is never reached.

**Move all model work to Claude Code routines billed to that subscription.
GitHub Actions keeps the mechanical work.**

Owner's constraints, stated explicitly:

- **No API fallback.** "I'd rather learn to operate within the subscription
  confines than spend my way out." If a routine fails, the episode waits.
  Keep the API code in the repo but unused.
- **Cadence stays twice a week** (Monday digest pick, Friday r/science pick).
  Don't design for more; plan capacity is the binding constraint.
- Gemini TTS (~$0.19/episode) stays as it is — it is not Anthropic spend.

## What the pipeline does today

| Stage | Where | Model cost |
|---|---|---|
| Monday digest | routine `WeeklyDigestGenerator` (already on subscription) | plan |
| Monday/Friday paper pick → opens an Issue | Actions (`monday-podcast`, `friday-podcast`) | none |
| Paper full text | `scripts/paper_text.py`: emailed PDF → Europe PMC → OA PDF → publisher HTML | none |
| Relevant past episodes | Haiku call in `scripts/memory.py` | ~$0.01 |
| Script draft + fact-check | `scripts/generate_script.py` (Opus 5, two passes) | ~$1.20–1.70 |
| Audio | `scripts/tts_dialogue.py` (Gemini 2.5 multi-speaker) | $0.19 |
| Draft PR → auto-merge | `scripts/generate_episode.py`, `AUTO_PUBLISH=true` variable | none |
| Show notes | `scripts/publish_episode.py` (Sonnet 5) | ~$0.02 |
| Memory card + threads | `scripts/memory.py` (Opus 5) | ~$0.30 |
| Feed + Pages | `scripts/feed_builder.py` | none |

Issue labels are the state machine: `podcast-pending` → `needs-pdf` /
`pdf-requested` → `episode-in-review` → closed on publish. `generation-failed`
parks a broken one.

## Target architecture

**Routines do judgment; Actions does mechanics. The repo is the queue.**

1. **Writer routine** — picks the oldest eligible Issue, gets the paper, writes
   the script, writes the show notes and the memory card, commits to a branch.
2. **Checker routine** — a *separate* session an hour or two later. Sees only
   the paper, the script and the memory cards, never the writer's reasoning.
   Applies corrections, records them, commits.
3. **Action** — validates, synthesizes audio, publishes, rebuilds the feed.
   Unchanged machinery; it just stops calling Claude.

Step 3 exists as of this change. `generate_episode.process()` looks for
`generated/routine/issue-<N>.script.json` before it writes anything, and uses
it when the validator accepts it, skipping both Opus passes. A script that
does not validate, or will not parse, falls through to the paid path rather
than taking the episode down, and the run says which. Because a routine script
bills nothing, those Issues sit outside `MAX_EPISODES_PER_RUN` and do not count
as attempts — and a run with no `ANTHROPIC_API_KEY` at all now starts, draft
whatever has a script waiting, and says so for the rest.

That leaves audio as the only unavoidable spend in an episode: roughly
nineteen cents of Gemini synthesis against the dollar thirty-five to dollar
ninety the two Opus passes cost.

One consequence worth knowing about. A routine now opens a pull request that
carries a script and no audio, and `publish_next_draft` used to pick the
oldest open `episode/*` branch — so such a PR could win the daily publish slot,
merge, publish nothing, and leave the real draft waiting another day. The
publish slot now requires the PR to actually add audio under `inbox/`, which is
what the publish workflow triggers on. Branch names are no longer evidence of
anything, but keep giving the routines `claude/routine-issue-<N>` anyway: it
reads correctly in the PR list.

Two routines rather than one is deliberate: it is genuinely two sets of eyes,
and it makes the prototype's worst failure (below) structurally impossible.

Reading the paper once per session instead of re-sending it to four API calls
is most of the saving. The Haiku relevance call disappears — the routine reads
`memory/cards` and the episode index itself.

## What the first prototype proved, and its four flaws

A one-time routine wrote a script for Issue #41 (perturb-seq, *Cell*) on
2026-10-04: 15 minutes, $0 API, quality at least equal to the API version, and
it found the published paper in PMC when `paper_text.py` had failed. Branch
`claude/routine-prototype-issue-41` still exists; the API version of the same
paper published as episode 85, so the two are directly comparable.

All four are fixed (2026-10-31). What the run log
(`RemoteTrigger get_run_log cse_01PaB4hcbZG8fAagnxJvWRqf`) showed, and the fix:

1. **The fact-check only landed by luck.** The routine launched it as a
   background subagent. A stop hook then made it commit the unchecked draft,
   and the run ended at 00:17:49 recorded as *succeeded*. The subagent's
   hand-back at 00:22 happened to revive the session, which applied 19
   corrections in a second commit at 00:26. **Fix:** the checker is its own
   routine, `prompts/routine_checker.md`. Both prompts forbid subagents and
   background tasks, and the writer builds its draft in `/tmp` so the stop hook
   cannot push half a script.
2. **It gamed the validator.** The validator counted written characters, so the
   writer swapped spelled-out numbers for digits ("12,779") to fit the window.
   **Fix:** `validate` measures *spoken* length (`spoken_form`) and rejects
   digits, runs of capitals and symbols in dialogue. Spoken length tracks real
   runtime better: r=0.69 against episodes 82–93's audio, versus r=0.31 for
   written characters, at 1,075 spoken chars/min. The window is now 11,000–11,600
   spoken characters, the 10.2–10.8 minutes the old window actually produced.
   Measured this way the prototype was 11,879, about a quarter-minute over.
   Note: the API scripts *also* use digits and bare acronyms throughout, and
   `host_dialogue.md`'s own examples do too ("13 of the 26"). So the ear rule is
   written as a routine-only override in `routine_writer.md`, and the API
   prompt is untouched.
3. **Safeguards stopped the session** when it read the episode index and
   threads. The harness then continued once and logged
   `model_refusal_fallback`; the later restart reports `model=claude-opus-5`,
   so the prototype was probably finished on the fallback model, not Opus 5.5.
   **Fix:** both routines count stops in the script's `runs[].safeguard_stops`.
   Both are safe to rerun: the writer stops if a draft exists, the checker
   stops if there is no draft or it is already `checked`. So the retry is just
   `RemoteTrigger run`. When measuring, also check the run log for
   `model_refusal_fallback`, which the session itself may not notice.
4. **No token accounting.** Accepted. Each run records `started`/`finished`
   UTC in `runs`, and `validate --stage draft|checked` enforces the record.
   Plan usage still has to be read before and after by hand.

Tests: `uv run python -m unittest discover tests`.

## Next step: prototype on Issue #86

This week's Friday pick: "The Effect of Deactivating Facebook and Instagram on
Users' Emotional State", *American Economic Journal: Economic Policy*,
DOI `10.1257/pol.20240806`. Labelled `needs-pdf` — no open-access PDF was
found, so it is blocked today. A working-paper version likely exists.

It tests three things at once: a non-biology paper, the writer/checker split,
and whether a routine can obtain a paper the Actions code cannot.

How to create a routine: load `RemoteTrigger` via
`ToolSearch select:RemoteTrigger`, then `action: "create"`. Copy the shape from
the existing `WeeklyDigestGenerator` (`action: "list"`). Known-good values:

- environment: `env_011CUJw7aTsHbmomzmRcsQzi`
- repo source: `https://github.com/RaymondRuff/sciencetldr`
- connectors available on the plan: PubMed
  (`320d4a41-2c05-4e2a-a5c0-d89db9696505`,
  `https://pubmed.mcp.claude.com/mcp`), bioRxiv
  (`b5ff6750-a1c4-4be6-bb8f-75a51c8844f6`,
  `https://hcls.mcp.claude.com/biorxiv/mcp`), Gmail
  (`https://gmailmcp.googleapis.com/mcp/v1`) and others — list the digest
  routine to see them all
- `run_once_at` for a one-shot; minimum cron interval is 1 hour
- routine instructions live in `prompts/routine_writer.md` and
  `prompts/routine_checker.md`; give each the Issue number and the branch
  `claude/routine-issue-<N>` in its starting message
- debug with `action: "list_runs"` then `action: "get_run_log"`

Measure: wall-clock, whether safeguards fire, whether the validator passes
first try, whether the checker finds anything real, and plan usage before and
after.

## The schedule, as it now runs

Three routines, all on the subscription, created 2026-11-04:

| Routine | Trigger | When |
|---|---|---|
| writer (daily) | `trig_01VBSoyKHPFYpDDMQnTuK7iX` | `0 8 * * *` UTC |
| checker (daily) | `trig_01WAWFF3Sqwd4GLnWquPKe6f` | `0 11 * * *` UTC |
| checker (issue 90, one-shot) | `trig_013iTMLgNkBh9YKhYmJPt152` | fired 2026-11-04 05:40 UTC |

The cadence is set by the Actions sweep at 14:00 UTC: writer, checker three
hours later, sweep three hours after that. The writer picks its own Issue —
oldest open `podcast-pending` first, skipping anything labelled
`episode-in-review`, anything with a script already on `main`, and anything
with `issue-<N>` in a remote branch or open PR head. Nothing hands it a number.

**The checker pushes the checked script straight to `main`**, as the digest
routine does, and that push is what puts an episode into production: the sweep
reads the script from `main`, synthesises it, and `AUTO_PUBLISH` merges the
audio PR in the same run. No human looks at it in between. That is deliberate
— the goal is a show that does not need reviewing — but it is worth saying out
loud, because four things are now carrying the quality on their own: the
writer, an independent checker that never sees the writer's reasoning,
`validate --stage checked`, and `generate_episode.routine_script()` revalidating
before it will use anything. The checker is told to hold a script back and
notify rather than push if it judges it unpublishable.

To put a human back in the loop, set the `AUTO_PUBLISH` variable to anything
but `true`: the audio PR is then left open for a listen. To stop the pipeline
spending on drafts at all, `MAX_EPISODES_PER_RUN` is `0` as of 2026-11-04,
which blocks every paid attempt while leaving routine-written scripts free to
run, since those bypass the cap. That is the stop-loss rule expressed as
config.

## What a routine can actually do (tested 2026-11-03)

A capability routine (`trig_0132enLut5dmfJrHikpQorWN`) ran four tests. All four
passed, and two of them change what is worth building:

1. **The private papers repository is cloned and readable.** List it as a
   second source and it appears at `/home/user/sciencetldr-papers`, on `main`.
2. **A routine can push to it.**
3. **A routine can read a PDF natively** with `Read` and its `pages` parameter,
   twenty pages at a time, and *see the plotted data* — it read hazard ratios
   off a dot plot and a forest plot that appear nowhere in the pypdf text.
   This is why both routine prompts tell the checker and writer to read
   `figures/` as images rather than trusting `paper.txt`.
4. **A PDF attached to a reply mid-session arrives as a file on disk** under
   `/root/.claude/uploads/<uuid>/`, with a `.saved-uploads.jsonl` beside it
   recording name, size and sha256. The routine read it and pushed it into the
   papers repository with a matching checksum.

Test 4 is the way out of the PDF bottleneck, and it is better than email: a
routine that cannot reach a paper now sends a push notification and waits, and
a PDF replied into that session goes straight into the papers repository. No
IMAP, no app password, no polling. `scripts/pdf_mailbox.py` can be retired once
that path has carried a few papers.

## Also outstanding

- ~~**Memory is 9 episodes stale.**~~ Done on 2026-11-01: the prototype routine
  wrote cards 85–93 and revised `memory/threads.md`, on the subscription. Only
  card 094 is missing, which `memory.yml` builds on the next publish. Worth
  rechecking after a few unattended episodes, because the writer draws its
  callbacks from these files and stale memory degrades them quietly.
- **`.github/workflows/memory.yml` discards its work on failure.** The commit
  step does not run when the script dies partway, so every failed run rebuilt
  and threw away the same cards. If that workflow survives the migration, give
  the commit step `if: always()`.
- **Seven Issues are stalled on PDFs**: #40, #43, #44, #48, #58, #85, #86. This
  is a bigger content bottleneck than cost. The digest routine already has a
  Gmail connector, so a routine could read the owner's emailed PDF replies
  directly and replace the IMAP code in `scripts/pdf_mailbox.py`. A supplied
  PDF is now normalised into a bundle — text with collected captions plus
  downsampled figures — before anything reads it; see
  [paper-bundles.md](paper-bundles.md).
- **Cache TTL is wrong in `scripts/claude.py`**: `CACHE` uses a 1-hour TTL
  (2× write premium), which for a single reuse costs slightly more than not
  caching at all. Every draft pass measured 155–282s, inside the 5-minute
  window. Moot if the API path is retired, but note it before reusing that code.

## Repo conventions

- Branch, PR, merge — nothing straight to `main` except docs.
- Lint every workflow change with `actionlint` before opening a PR.
- Test model-calling code with mocked clients; never spend to test plumbing.
- `uv run python ...` for anything in `scripts/`.
- End commits with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` and
  PR bodies with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
- `.claude/settings.json` is **committed** (`.gitignore` un-ignores just that
  file) and grants `Bash(gh pr merge:*)`. So any session in this repo, local or
  routine, can merge a pull request without being asked — deliberately, because
  an unmerged PR was the last thing in the pipeline that needed a human. The
  gate on publishing is the `AUTO_PUBLISH` variable, not a person. Put
  machine-specific grants in `.claude/settings.local.json`, which stays ignored.
