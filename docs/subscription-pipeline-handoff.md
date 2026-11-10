# Handoff: move episode generation onto the Claude subscription

Written 2026-10-31 for a fresh session. Self-contained: assume no memory of
earlier conversations. The goal is approved and the direction is settled; what
follows is the work.

## Update, 2026-11-04 evening: paper supply

The writer's first unattended run (08:11 UTC) showed that the routine sandbox
cannot reach any paper source — doi.org, Europe PMC, Unpaywall, OpenAlex,
Crossref, Semantic Scholar and the publishers are all refused or unresolvable.
Only the PubMed and bioRxiv connectors, web search and `gh` REST get out, and
`gh` GraphQL is refused too. It also pushed one notification per stalled
paper, though Actions had already emailed a request for every one of them.

**Actions fetches, routines read.** The fix puts every fetch where the network
is:

- **The pickers stage at pick time.** When the week's top paper is open, its
  text goes into `sciencetldr-papers` as a bundle as the Issue opens (from a
  PDF, with figures, when one is open; from Europe PMC XML or the publisher
  page otherwise). A landing page that is only an abstract and references is
  refused: a staged paper needs 12,000 characters of body before its last
  references heading. When the top paper is *not* open, a PDF window decides
  — see the 2026-11-06 update below. (As first built, the pickers silently
  took the best open paper instead; the owner preferred to be asked.)
- **The daily sweep stages the rest.** `bundle_waiting_papers()` bundles any
  emailed or uploaded PDF, then fetches open text for every waiting Issue that
  has neither a bundle nor a checked script — including `needs-pdf` ones, since
  papers do become open later. When one turns up its PDF request is cleared.
- **One request per paper, by email.** `request_missing_pdfs()` now runs after
  staging and asks only for Issues still without a bundle, skipping any whose
  sources merely failed for now. The `pdf-requested` label is the memory. If
  the papers repository could not be reached it asks for nothing, because a
  supplied PDF could not reach the routine either.
- **The writer picks mechanically and never pushes about a paper.**
  `routine_tools.py queue` ranks the Issues over REST — staged papers first,
  then Issues nobody has asked a PDF for — and skips anything already asked
  for. A paper the writer cannot get is parked `needs-pdf` with
  `routine_tools.py park`, silently; the sweep's one email is the only ask.
  The only push either routine sends is for an Issue it parks
  `generation-failed` (the checker holding a script back, or a staged paper
  that is wrong or unreadable), and a parked Issue is never touched again.
- The daily prompts now live in the repo: `prompts/routine_writer_daily.md`
  and `prompts/routine_checker_daily.md`. The triggers just point at them, so
  a prompt change is a reviewed PR.

**What needs the owner, once:** `GH_PAT` has no access to
`sciencetldr-papers` (the sweep's clone gets `403 Write access to repository
not granted`; SETUP.md told you to select only the public repo). Every bundle
so far was pushed from a desktop. Until the token lists the papers repository
with Contents read and write, nothing staged by Actions can reach the routines,
and every sweep that has papers to stage fails with that message — which the
new failure alert turns into one Issue.

**Options considered and not taken:**

- *A Gmail connector in a routine instead of IMAP in Actions.* The IMAP path
  already works — every stalled Issue carries `pdf-requested`, so the emails
  went out — and the broken link was the token, not the mailbox. The connector
  returns an attachment only as a raw MIME message through the model's own
  context, which costs plan usage on every poll, and the reply lands in the
  podcast account's inbox, not the account the connector is signed into.
- *Allowlisting paper hosts for the routine environment.* It buys nothing once
  Actions stages the open papers, and the stalled six are closed: none of #40,
  #43, #48 or #85 has a PubMed Central copy (checked through the PubMed
  connector), #44 is a paywalled SAGE paper, and #58 is open on Wiley but Wiley
  refuses scripted downloads from Actions too.

**Also changed:** a checked script on `main` now makes its episode without the
paper text (#98, which is what let episode 95 publish), and landing one starts
a sweep at once instead of waiting for the 14:00 cron, which GitHub has been
starting up to six hours late. Nothing gets past `MAX_EPISODES_PER_RUN` any
more — not an emailed PDF, not an invalid routine script. Show notes come from
the routine (`show_notes` in the script, checked by the checker, validated),
so publishing makes no Anthropic call and `publish.yml` no longer has the key.
A failing workflow opens one `pipeline-alert` Issue assigned to the owner,
which repeat failures edit silently and the next success closes.

## Update, 2026-11-06: the PDF window

Quality is the owner's call, not the picker's. When the week's top paper has
no open full text, `scripts/pdf_window.py` takes over:

1. **Same standard, no question.** Monday only: if another paper with the same
   DICE score is open, it takes the slot silently. r/science rank is
   popularity, not a score two papers can tie on, so Friday always asks.
2. **Otherwise one email, at pick time.** The Issue opens for the top paper,
   labelled `awaiting-pdf` and `needs-pdf`, and the picker emails at once. The
   email gives the deadline, 9 pm Pacific that day, and names the runner-up:
   the best open paper within one DICE point (Monday) or among the first eight
   (Friday). Answering "the runner-up is fine" takes no action at all. The
   deadline and the runner-up are kept in the Issue's METADATA
   (`pdf_deadline`, `runner_up`).
3. **A PDF in time** is staged by the next sweep or mailbox poll, which also
   clears `awaiting-pdf`; the writer takes the top paper next morning.
4. **At the deadline** a sweep opens the runner-up as its own Issue, stages
   it, and comments on the original. The `17 5 * * *` sweep exists for this:
   the deadline is 04:00 or 05:00 UTC and the writer starts at 08:00, so a
   missed deadline costs no time. If GitHub starts that sweep late, the
   worst case is a one-day delay.
5. **No runner-up** (nothing open within the floor): the slot is skipped
   rather than filled with a weaker paper.
6. **The original stays open** with `needs-pdf`. A PDF sent later still
   becomes an episode; the sweep never asks a second time.

The writer's queue skips an Issue in its window ("Actions decides at the
deadline") unless its PDF has already been staged. Evidence behind the
frequency: in the ten Mondays to 2026-11-02, four top picks had no open full
text (#43, #48, #85, #90); on Fridays three (#40, #44, #58). Expect roughly one
ask a week. The one PDF the owner did supply (#90) arrived about 27 hours
after its request, which is why the window covers a whole working day.

## Update, 2026-11-06: the hosts stopped reciting numbers

Episode 95 spoke about nine figures a minute — forty-four of them, twenty-two
decimals, eight stacked in a single turn — because the show's rules asked for
it: "every number in the paper still belongs in the episode", "cut from the
setup, never from the numbers". Measured against episode 81, the NotebookLM
episode whose register the owner prefers (about one and a half figures a
minute, five decimals in twenty-three minutes, no statistical apparatus at
all), that is the main thing making the dialogue feel dry.

`prompts/host_dialogue.md` now has a **Numbers — few, and chosen** section.
What changed, in order of effect:

- **The paper holds the numbers; the episode holds what they mean.** A figure
  is spoken only where the other host can react to it. Fifteen to twenty-five
  an episode, at most two in a turn.
- **Quantities become comparisons, scales and movements** — "about twice as
  fast", "low picomolar", "barely moved" — except for the headline result,
  sample sizes and counts, and values whose precision is the point. Each
  precise figure comes with a plain reading of what it means.
- **No statistical apparatus aloud.** No confidence intervals, p-values,
  standard deviations or "plus or minus"; the hosts say what these imply.
  Talking about spread and overlap in words is encouraged.
- **A rounding is a claim.** "About twice" for a ratio of one point four is a
  defect, and the checker treats it as one.
- **One spine per episode.** Nadia states the paper's central claim early and
  the results are evidence for or against it, rather than a walk through the
  panels. Limitations attach to the spine.
- **Plain intensity words are allowed** ("almost all of them failed", "every
  single submission passed"); the hype ban is about claiming significance, not
  about describing size.
- **The checker's job flipped.** It used to add figures for completeness — two
  of its eight corrections on episode 95 did exactly that. Now over-precision
  and recital are defects it fixes by cutting, and an omission means a missing
  caveat, never a missing number.
- **The show notes keep the precision**, in digits, restored from the paper
  where the dialogue rounded.

`routine_tools.py check_number_register()` is the backstop: it warns past the
budget (25 figures, 2 per turn, 6 decimals) and rejects past a ceiling (40, 5,
12), and refuses apparatus read aloud. Episode 95's script fails all three
ceilings, which is the regression test. The counting is mechanical; whether a
figure earns its reaction stays with the checker.

## Update, 2026-11-10: timing, strand call-outs, one-offs

**The register change worked.** Episodes 96 and 97, the first two written under
the Numbers section, speak 1.0 and 0.9 figures a minute against episode 95's
4.3 — eleven and ten figures each, nought and one decimal, no validator
warnings. The owner's verdict: "a considerable improvement, much more
enjoyable to listen to."

Three things changed on the back of it.

**1. The picks moved a day earlier, because the pipeline takes a day.** A pick
on day D is written at 08:00 UTC on D+1, checked at 11:00, and published about
11:25 (03:25 Pacific). Episode 96 was picked on a Friday and published on
Saturday; episode 97's digest ran Monday and published Tuesday. So:

| Strand | Pick | Episode |
|---|---|---|
| digest | **Sunday** 06:00 Pacific (the `WeeklyDigestGenerator` routine) | Monday morning |
| r/science | **Thursday** 11:00 UTC (`friday-podcast.yml`) | Friday morning |

The morning of the pick day matters when the top paper is paywalled: a PDF
window closes at 9 pm Pacific *that day*, which is 05:00 UTC the next, and the
runner-up has to be staged before the writer runs at 08:00. Sweeps now run at
05:17 **and 07:28** UTC to give that two chances, because GitHub starts
schedules hours late often enough to matter. A pick made in the evening
Pacific rolls its deadline to the following night and so slips the episode a
day — another reason the digest belongs in the Sunday morning slot.

**2. The hosts say which strand they are on.** `prompts/host_dialogue.md` has a
**The strands** section: the cold open names the Monday digest pairing or the
Friday r/science crawl, in the hosts' own words, varied each episode. The
distinction that keeps this from colliding with the show's field-neutrality
rule is **provenance, not field**: where the paper came from is required, while
characterising the show by discipline is still banned. `routine_tools.py
context` now prints the strand so the writer cannot miss it, and
`describe_strand()` is the single source for what each `source` means.

**3. One-off papers have a path.** There was none: queueing a paper by hand
meant writing an Issue METADATA block by hand. `scripts/add_paper.py`, run from
the **add-paper** workflow with a DOI, does what the pickers do — Crossref
lookup, fetch and stage the open full text, open the `podcast-pending` Issue
labelled `one-off` — and asks once for a PDF when nothing open has the paper.
No window and no runner-up: a one-off is that paper or nothing. It carries no
series branding, and the hosts give it no strand framing. The writer takes the
oldest eligible Issue, so a one-off queued Monday to Wednesday has no
competition; queued on a pick day it waits a day behind the strand.

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
- ~~**Seven Issues are stalled on PDFs.**~~ See the update at the top: papers
  are now chosen for being readable and staged by Actions. Six stalled Issues
  remain (#40, #43, #44, #48, #58, #85), each asked for once by email; the
  writer skips them silently until a PDF arrives. A supplied PDF is normalised
  into a bundle — text with collected captions plus downsampled figures —
  before anything reads it; see [paper-bundles.md](paper-bundles.md).
- **Memory has no schedule.** `prompts/routine_memory.md` exists but no
  routine runs it, and `memory.yml` is manual. Cards 094 and 095 are missing,
  and the writer draws its callbacks from these files.
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
