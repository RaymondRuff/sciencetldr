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

## Update, 2026-11-10: a one-off by email

The add-paper workflow wanted a browser and a DOI in hand. The lighter way in
is the mailbox that is already polled every thirty minutes: **email the podcast
address with "one-off" starting the subject**, and either name the DOI in the
body or attach the PDF. The whole exchange is one email out and one back.

How it is put together, in `pdf_mailbox.py` and `add_paper.py`:

- **A second pass over the same IMAP session.** The reply pass (PDFs replied to
  a numbered request) is untouched. The one-off pass searches by sender and
  freshness only — Gmail's query parser reads the hyphen in "one-off" as an
  exclusion — then matches subjects on *headers alone*, so an unrelated
  message's body is never fetched. The subject must *start* with the phrase,
  or an ordinary sentence would commission an episode.
- **Only the owner.** `owner_address()` is `PDF_REQUEST_TO` alone, deliberately
  narrower than `allowed_senders()`: replying to a request supplies a paper the
  show already chose, while a one-off chooses the paper, so
  `PDF_SENDER_ALLOWLIST` does not grant it. Gmail's own DKIM/DMARC verdict
  still decides whether the From line is real, and an unauthenticated message
  is labelled and **never answered** — a reply would make the show a
  backscatter source.
- **The DOI, or a question.** Exactly one DOI in the body wins; otherwise the
  first three pages of the attached PDF are read for one. Several DOIs, or
  none, are refused with a reply rather than guessed at — a forwarded
  table-of-contents alert would otherwise commission the wrong paper.
- **The confirmation is the PDF thread.** The reply's subject carries the new
  Issue's `[Science TLDR #N]` tag, so replying to it with the PDF attached
  lands in the ordinary reply pass. One email covers both jobs, and
  `add_paper.add(email_request=False)` suppresses the second.
- **An attached PDF rejoins the proven path.** It arrives before its Issue
  exists, so it cannot be saved under the Issue's name. Once the Issue is open
  the file is moved to `issue-N.pdf` and `record_reply()` adds it to the
  mailbox manifest — from there it is indistinguishable from a replied PDF, so
  the existing bundling stages it and `consume_replies()` only consumes the
  email once it can no longer be lost.
- **Capped at four waiting.** Each one-off costs a writer session, a checker
  session and about nineteen cents of audio, and the writer writes one script
  a day — so an easy way in is an easy way to spend the week's plan capacity.
  A fifth is refused, by name, until one publishes. `--force` overrides it.
  The owner's weekly usage has not passed eighty percent, which is the
  headroom this number is set against.

Failures are deliberately asymmetric: anything the owner should answer gets a
reply and the email is consumed, while an unexpected error leaves the email
unlabelled so the next sweep retries it.

## Update, 2026-11-10: papers with no DOI, and exact audio pairing

A white paper was the first thing queued by hand, and it exposed two gaps.

**A DOI was load-bearing.** `add_paper` keyed everything off it: Crossref for
the title, the DOI for duplicate detection, the DOI in the Issue header. An
industry white paper has none. The rest of the pipeline was already built for
the case — `prompts/show_notes.md` says to write `Source: [url]` when there is
no DOI, and `White paper — {organisation}` for the journal line — so only the
front door was too narrow. Now a paper can be identified by its **URL**
instead: `add_paper.add(url=..., title=..., publisher=...)`, or by email with
the link and a `Title:` line. The Issue's METADATA carries `doi: null` and
`source_url`, duplicate detection falls back to
`select_friday_paper.already_seen_urls()`, and the hosts name the organisation
instead of reading a DOI aloud — never the URL, which is miserable to listen
to. With no title given, the PDF's own front matter is read for one; that is a
guess, so it is printed in the log and lands in an Issue that can be corrected
before the writer runs in the morning.

**The audio would have been misfiled.** `tts_dialogue.to_mp3` stamped only the
DOI into the mp3's comment tag, and `publish_episode.resolve_metadata` used
that tag to find the episode's Issue. With no DOI the tag was empty and
publishing fell through to pairing with the **oldest open Issue** — which is
#40, stalled since August. The white paper would have published under the
Whitehall diet paper's title and closed its Issue. The comment in `to_mp3`
warned about exactly this; nothing had hit it because every episode so far had
a DOI.

So the audio now carries `Issue: 112; DOI: ...` and publishing pairs on the
number first. That is strictly better for every episode, not just DOI-less
ones: a generated episode always knows its own Issue, so the guess is gone.
Where the Issue does have a DOI, Crossref still supplies the canonical title
and authors — a digest title arrives as "1. Shared alpha-helix..." — while the
strand (`source`) and `source_url` stay as the Issue recorded them, because
Crossref would otherwise overwrite `source` with "crossref". The DOI branch
and the oldest-pending fallback both remain for audio dropped in by hand.

## Update, 2026-11-11: nothing waits on a review

Ray said he no longer wants to review drafts. He already wasn't: `AUTO_PUBLISH`
has been `true` throughout, and episodes 95 to 98 each reached the feed about a
minute after the checker landed the script. What made him think otherwise was
the wording. The pull request was titled "review by listening, then merge to
publish" and the Issue got a comment saying "Listen to the audio in the PR,
then merge to publish or close to discard" — an instruction for a decision that
auto-publish had already taken, and a second notification per episode for
nothing.

So the copy now says what happens, and that extra comment is gone: the episode
announces itself once, when it publishes, with the permalink. The labels carry
descriptions now too, because `episode-in-review` reads like it is waiting on a
person when it means "built and queued to publish".

**The pull request stays**, and not out of habit. It is the rate limiter:
`publish_next_draft` merges one per publish slot, so a backlog — three one-offs
queued in a week, say — reaches the feed one episode at a time instead of all
at once. It is also the only artefact that holds the audio, the script and the
checker's corrections together after the fact. Closing one before its slot is
still how a single episode is stopped; `AUTO_PUBLISH` set to anything but
`true` still holds all of them.

## Update, 2026-11-13: the digest list manages itself

Several people had asked Ray to add them to the weekly digest, and each one
meant editing the `DIGEST_RECIPIENTS` secret — which cannot be read back, so
adding one person meant retyping all of them from memory. The list now lives
in the private papers repository and people put themselves on it.

**Two plain files, in `sciencetldr-papers`:**

    list/subscribers.txt    one address per line; `#` starts a comment
    list/unsubscribed.txt   addresses that must never be sent to again

Recipients are **(the file plus the old secret) minus the unsubscribed**
([`scripts/mailing_list.py`](../scripts/mailing_list.py)). The arithmetic is
the point, because it answers the one thing Ray asked for — that nobody
currently subscribed falls off during the switch:

- the five on the secret keep receiving the digest with no action from anyone
  (the sync job's log settles the count: five entries, five distinct, five on
  file — an earlier draft of this document said six);
- the first send folds them into `list/subscribers.txt`, so the list becomes
  readable and `DIGEST_RECIPIENTS` can be deleted whenever it suits. Check the
  file has all five first; until then the secret is the seed. It is **not** a
  fallback — see the 2026-11-14 update below, which took that out. Actions →
  **mailing-list** does the fold on demand, so the roster can be read without
  waiting for a Sunday and without sending anything;
- `list/unsubscribed.txt` beats both sources, so someone who arrived on the
  secret can still leave — which a list held only in a secret could never
  offer.

**Joining:** mail the podcast address with `subscribe` starting the subject.
**Leaving:** the same with `unsubscribe`, which the digest's own footer spells
out as a `mailto:` link. The two subject rules are deliberately asymmetrical: `unsubscribe` counts anywhere in the
subject, because someone leaving is likely to hit reply and type it after our
own subject line, and failing to honour that is the one failure worth avoiding;
`subscribe` has to lead the subject, so a mail that merely mentions subscribing
never adds anyone.

Only the address **Gmail's own DKIM or DMARC verdict vouches for** is ever
added or removed — never one typed in a body — so nobody can sign up or cut off
somebody else, and mail carrying `Auto-Submitted`, `Precedence: bulk` or
`List-Id` is rejected unanswered rather than starting a loop between two
robots. The order of operations is: store the change, label the mail, then
reply. A change that could not be stored leaves the mail unlabelled for the
next poll, so nobody is ever told they are off a list they are still on.

**The confirmation for a new subscriber is the most recent digest**, with a
line of preamble on top, rather than a note saying "you're on the list". It
proves the subscription works, it is worth reading, and it means someone who
joins on a Tuesday is not left with a promise until Sunday. Rendering it needs
the markdown package, so the standard-library poll only records the request and
a later step — gated on that record, after `uv sync` — sends it.

Their mail is labelled **before** the welcome goes, which is the opposite of
how this was first built. An unlabelled request is found again by every poll
for a fortnight, and `imaplib` returns a refusal for a label Gmail declines
rather than raising, so sending first turned one unnoticed refusal into dozens
of copies of a 100 KB digest. Labelling first costs at worst one welcome to
somebody who is on the list either way and gets Sunday's digest. Writing in
twice gets the one-line note, not the digest a second time.

This is the third pass of the mailbox poll
([`scripts/pdf_mailbox.py`](../scripts/pdf_mailbox.py)), which runs on standard
library alone, before any dependency is installed, and now has a workflow of
its own — see the next update for why.

**Reading the secret generously, on purpose.** The first cut of `legacy()`
kept only bare addresses, which would have silently dropped an entry typed as
`Ray Ruff <ray@example.com>` — a form the old code delivered to perfectly well,
because smtplib strips the display name on the way out. Since nobody can read
the secret back to check which forms are in it, each entry is now parsed on its
own with `parseaddr`, commas and semicolons both separate, and anything still
unreadable is **counted and warned about** rather than passed over. One entry at
a time matters: `email.utils.getaddresses()` parses the whole string at once and,
since Python 3.13, answers a trailing comma with `[("", "")]` — a single stray
character would have discarded every subscriber.

No address is ever printed by any of this. The public repository's Actions logs
are world-readable, so the counts go in the log and the addresses stay in the
private repository.

**The digest no longer shows the list to the list.** Every send put all five
addresses in `To:`, so each subscriber could read the whole list in their own
copy; with the list open to anyone who asks, that gets worse with every person
added. This was first fixed by blind-copying one message to everybody, which
hid the addresses but kept the shape — and the shape was the next problem: see
the 2026-11-14 update, which sends one message per subscriber instead.

## Update, 2026-11-14: the schedule was the bottleneck, not the code

Ray sent a "Subscribe" mail and heard nothing for forty minutes. The code was
fine. The mailbox poll's cron was `*/30 * * * *`, so it fired at **:00 and
:30** — the two minutes GitHub's scheduler delays most, and drops outright
under load. It had run **six times on 13 November instead of forty-eight**,
with gaps of four and five hours; the last poll before his mail was nearly four
hours earlier. This had been true for days and nobody noticed, because a PDF
arriving six hours late looks like nothing at all.

Two changes:

- **Every cron moved off the congested minutes.** The mailbox poll is now
  `13,43`, the daily sweep and publish slot `11 14`, the Friday crawl `8 11`.
  `tests/test_schedules.py` fails if any schedule fires on the hour or the half
  hour, and separately if the `POLL` or `PUBLISH_SLOT` comparison stops naming
  a cron the workflow actually has — renaming a cron without its comparison
  would silently turn every poll into a full sweep.
- **The mailing list got its own workflow** (`mailing-list.yml`, four times an
  hour at `9,24,39,54`), because subscribing had no business depending on an
  episode workflow's scheduling luck. It also means the poll can be run by
  hand: dispatching generate-episode takes a publish slot with it, so it was
  never something to do casually. `alert-on-failure` now watches it, and
  `pdf_mailbox.py list` is the entry point — the same third pass, its own IMAP
  session, no PDF search.

The episode workflow still runs the list pass as before, so there are two
chances at every request. ~~They cannot collide: `13,43` and `9,24,39,54`
never fall in the same minute~~ — **that was wrong**, and the next update says
why: GitHub delivers backed-up schedules in a batch, so two runs whose crons
are eleven minutes apart were observed starting fifty-nine seconds apart. What
makes the overlap survivable is not the minutes but that whichever gets there
first labels the mail, and that git refuses a stale push rather than losing
the other writer's work.

## Update, 2026-11-14 evening: the congested-minute theory did not hold

An independent review of the subscription path, and then the GitHub API's own
record of this repository's runs, settled the question the previous update
guessed at.

**The numbers.** Scheduled runs here have been *delivered* **four to seven
times a day for eighteen days**, against roughly fifty-one asked for a day —
before *and* after last night's move off `:00` and `:30`. The minutes were
never the cause. They are harmless, so they stay (undoing them would be churn
for its own sake), but nothing should be built on the belief that they fixed
anything: a subscriber waits **hours**, not minutes, unless somebody dispatches
the workflow by hand. README now says that instead of "within the half hour".
`tests/test_schedules.py` no longer asserts the rule over every workflow,
where it would block a legitimate future cron in the name of a theory that did
not survive the data; it holds the two mailbox polls to it and says why.

An external scheduler is the obvious next move and is **not** taken here: that
is the owner's call and still open.

**The collision that was called impossible.** `13,43` and `9,24,39,54` do not
share a minute, but GitHub delivers a backlog in a batch: two runs were seen
starting fifty-nine seconds apart. On a `workflow_dispatch` it was worse —
`poll` and `sync` ran in parallel, both cloning, writing and pushing the same
two files. Nothing was ever lost, because `PapersRepo.commit()` pushes without
`--force` and git refuses the stale clone, but the result was a failed run and
an alert Issue caused by somebody clicking "Run workflow". So `sync` now
`needs: poll`, the workflow has `concurrency: {group: mailing-list,
cancel-in-progress: false}` so a dispatch queues instead of racing, and
`commit()` gets **one** retry: fetch, rebase onto `main`, push again, and fail
loudly if that is refused too.

**Four defects in the list code, found by review.** All four could affect real
mail, and all four now have tests that failed against the old code:

- `recipients()` wrapped the clone, the read *and* the push in one `try`, and
  the `except` returned the bare secret — which has no subtraction of
  `list/unsubscribed.txt`. A rejected push was enough to mail somebody who had
  left. The list is now computed before anything is written, the write has its
  own `try`, and a failed *read* exits non-zero. That is why the fallback
  promised above is gone.
- A welcome that failed sent the whole ~100 KB digest again, because
  `WELCOME_OUTCOMES` included `already` and because a Gmail label that Gmail
  *declined* read as one that stuck (`imaplib` returns `NO`; it raises only on
  `BAD`). Writing in twice gets the one-line note now, and the mail is
  labelled before the digest goes: one missed welcome beats seventy sent.
- `str(SMTPRecipientsRefused)` contains the refused address, and these Actions
  logs are public — GitHub masks the whole secret, not one address out of it.
  Failures log a class name and a count.
- `_authenticated()`, the only gate on subscribing, trusted any
  `Authentication-Results` header it found, including one the sender wrote;
  accepted `dmarc=pass` without checking whose domain passed; and matched the
  DKIM domain as a substring, so `header.i=@victim.com.attacker.net` vouched
  for `victim.com`. It now reads only the first header carrying Gmail's own
  authserv-id (`mx.google.com`), ties the verdict to `header.from=` or an
  anchored DKIM domain, and has the tests it should always have had.

**The mail shape.** For five people, one ~100 KB multipart message with
`To: sciencetldrpod@gmail.com` and five undisclosed envelope recipients is
both pointless and the shape spam filters score hardest against — and the
message most likely to be filtered is a new subscriber's welcome, which is
that same digest. The digest now goes out **one message per subscriber**, with
a real `To:`, plus `List-Unsubscribe` and `List-Unsubscribe-Post:
List-Unsubscribe=One-Click` on it and on the welcome, so a client can offer
leaving as a button. The visible footer stays. `chunks()`/`CHUNK` and the
`bcc` parameter are deleted rather than kept for a list that is not coming:
five subscribers do not need batching, and a hundred-fold list would want a
single SMTP session, which is a different piece of code. `sendmail()`'s return
value — the recipients the server refused — is no longer dropped; the count is
printed, never the addresses. Answers also thread now, under the `Message-ID`
of the request they answer.

## Update, 2026-11-14 night: the crons were starving each other

The forty-minute wait for a subscribe confirmation was blamed first on the
congested `:00`/`:30` minutes. Moving every cron off them changed nothing, so
`scripts/schedule_health.py` exists now and the guessing is over. Fourteen
days, `generate-episode`:

| date | 05:17 | 07:28 | 14:11 | runs that day |
|---|---|---|---|---|
| 11-01 | — | — | — | 6 |
| 11-04 | — | — | +54m | 5 |
| 11-08 | +71m | — | — | 7 |
| 11-12 | — | — | — | 7 |
| 11-13 | +38m | — | +81m | 6 |
| 11-14 | — | +6m | +11m | 6 |

**Eight of forty-two sweeps fired — nineteen per cent.** The publish slot on
four days of fourteen; the 05:17 sweep that closes PDF windows before the
writer starts, on two. Delivery was 5.6 runs a day, every day, whatever the
crons asked for, at times matching none of them. Meanwhile `friday-podcast`,
one weekly cron, was delivered three times out of three.

That contrast is the whole finding: **a workflow seems to get about five
scheduled runs a day however many ticks it asks for.** A cron every half hour
does not get its 48; it gets a share of five, and it spends the same budget the
daily sweeps in that workflow need. The sweeps were not merely late — most of
them never happened.

Why nobody noticed: episodes publish on the **push** trigger, when the checker
lands a checked script, and papers are queued by the **issues** trigger. Both
fire within seconds. The crons have been decoration, and the pipeline has been
running on events all along.

**The experiment, as of tonight:** the half-hourly poll is out of
`generate-episode`, which now asks for three daily ticks and nothing else. The
`POLL` flag and the `--mailbox-only` branch went with it — they existed only to
tell that cron from a sweep, and every run is a full sweep now. Emailed PDFs are
collected by the mailbox check at the top of each sweep and by every Issue and
push event; a PDF arriving during the day is used by the next morning's writer
either way, which is what the request email already promises. Subscribe and
unsubscribe mail is unaffected: `mailing-list.yml` owns it.

**Prediction:** three sweeps asked for, three delivered — against a baseline of
19%. First signal at 05:17 UTC on 15 November, three sweeps by that afternoon,
nine by 17 November. `tests/test_schedules.py::CrowdingTests` fails if anyone
puts a sub-daily cron back into the workflow that owns the publish slot.

**If it fails**, no cron arrangement will do, and the answer is an external
trigger. `pg_cron` on Supabase is capable but the free plan pauses projects
after seven days of low activity and both of this account's project slots hold
unrelated work, so the clock would be a lodger in somebody else's project. A
Gmail Apps Script timer is the better fit for the mailbox, because it can look
in the mailbox first and fire `repository_dispatch` only when something is
waiting; Cloudflare Workers is the better-behaved choice if the logic should
live in this repository under test, at the cost of being a blind ticker. That
decision is open.

Either way the measurement stays: `schedule_health.py --days 14 --times`
attributes a run to a daily cron only within ninety minutes, because at six
hours it called a 10:39 run a late 07:28 sweep and reported "all fired" on a
day when nothing fired on time.

## Update, 2026-11-15: the digest went out twice

Six people received the 2026-11-15 digest twice, two minutes apart, and the
two were not the same digest. The routine committed it at 14:14 and revised it
at 14:16 — "swap in the IgE disruptor preprint", six lines changed — and
`email-digest.yml` fires on **any** push touching `digest/*.md`, with its find
step matching `--diff-filter=AM`: added **or modified**. So the edit mailed the
whole thing again, and the first email carried a paper the digest no longer
recommends.

Nothing to do with the mailing-list work; that filter has been there for
months. It had simply never been true before that a digest was edited after it
was committed.

The fix is not a cleverer diff. Whether a digest has gone out is a fact about
the world, so it is recorded as one: `list/digests-sent.txt` in the private
papers repository, keyed by **the digest's own date**, not the day it was sent,
so a re-run tomorrow of today's digest is still a duplicate. The send checks it
first and writes it afterwards — afterwards, because a run that dies halfway is
worth retrying by hand, and a retry that doubles up on the first few addresses
beats a digest nobody receives. Nothing retries on its own.

A `force` input on the workflow sends anyway, for the case where a resend is
what you actually want.

`mailing_list.sync()` seeds the record from every digest file already in the
repository, since all of them have self-evidently gone out. Without that, a
typo fix in a digest from October would mail October's digest to everyone.

**A test wrote to production while fixing this.** Before the stubs were right,
two existing tests called `email_digest.main()` with `recipients()` stubbed but
not the new sent-record, and `_token()` falls back to `GH_TOKEN`, which a
developer shell has. So a unit test cloned the private papers repository and
pushed a commit to it. No mail was sent — those tests replace
`send_email.send` outright — and the commit happened to be true, but production
state changed from a test run, which this repo's conventions forbid.

`PapersRepo` now refuses a remote repository when `unittest` or `pytest` is in
`sys.modules`, unless `TLDR_ALLOW_REAL_PAPERS_REPO` says otherwise. The tests
that legitimately construct one with git stubbed waive it explicitly — and
without that waiver one of them passed without reaching the code it was about,
which is the second thing this guard caught.

**Superseded the same evening, in the better direction.** Ray's call: let the
model behave as it wants — if the scout decides to keep researching, let it —
and fix the coupling instead. So the digest's push no longer drives anything.
See the next update.

What this did **not** address: the routine revising a digest minutes after
committing it. That is reasonable editorial behaviour and the pipeline should
tolerate it — but anyone reading the first email got a recommendation that was
withdrawn. If that matters, the routine should settle its picks before it
commits, which is a change to its prompt, not to this repository.

## Update, 2026-11-15 evening: the digest's push drives nothing now

The double-send had a second victim nobody had looked for. `monday-podcast.yml`
fires on the same trigger as the email — any push touching `digest/*.md` — so
the picker also ran twice and opened **two** `podcast-pending` Issues for the
same paper, #130 and #131. Left alone, one paper would have published as two
episodes on consecutive days. #130 is closed as a duplicate; its staged bundle
in the papers repository is orphaned and nothing reads it.

Ray's instruction was to stop constraining the scout: *"I want the model to
behave as it wants and if it decides it wants to keep researching I say let
it."* That is the right call, and the earlier plan — a prompt rule telling the
routine to commit only once, when truly done — was fighting the model's
judgement to protect downstream consumers that should never have been watching
its commits. So:

**The email is now sent by a Monday-morning schedule**, not by the push. Three
crons, `50 11`, `50 12` and `50 13` UTC Monday: after the paired episode
publishes (~11:25 UTC) and before 6am Pacific, which is when Ray is up and
listening. Three chances is safe only because a digest is emailed once by date
— whichever run GitHub actually delivers sends it, the rest find it recorded
and stop. The scout can now take nine minutes or ninety, commit four times and
change its mind, and no subscriber sees a draft.

With no push to inspect, `email_digest.py` picks **the newest digest that has
not been sent** rather than simply the newest, so a scout run that slips past
the send window is still waiting next time instead of being skipped forever.
The find step and its `git diff-tree` are gone.

**The picker is idempotent per digest date**, recorded in
`list/digests-picked.txt` beside the sent record. It stays on Sunday, because
the PDF request for a paywalled top pick needs its 9pm Pacific deadline the
same day — moving the picker to Monday would collapse the PDF window. First
pick wins; if a revision ever changes the *top* paper the episode stays on the
one picked first. Ray: *"It seems unlikely that a model would completely change
its mind on what the top paper is and if it does we can reconsider."*

**The new failure mode is silence**, so there is a watchdog. A scheduled run
GitHub never delivers fails nothing, and `alert-on-failure` would see a
perfectly healthy pipeline that had quietly stopped sending. `mailing_list.py
pending` runs in the mailing-list poll — the workflow that runs most often —
and opens one Issue per digest that is unsent more than forty-eight hours after
its own date. It never fails the poll: a watchdog that breaks the thing it
watches is worse than none.

## Update, 2026-11-17: Theo gets room, and the hosts get a verdict

Monday's episode was good, and two things about it were not. Measured, rather
than felt:

| | turns | words | share | median turn |
|---|---|---|---|---|
| Nadia | 34 | 1,421 | 73% | 44 words |
| Theo | 34 | 516 | **27%** | **11 words** |

Equal turn counts means strict alternation: Nadia forty-four words, Theo eleven,
for ten minutes. A metronome. His shortest turns were "Which model?" and
"Nibbling. And it's functional?" — an interviewer working down a list.

The diagnosis was in the prompt, not the model. **Nadia had a described voice;
Theo had a described job.** She is "precise about the distinction between what
the authors showed and what they claim"; he got four numbered duties. So the
model gave him the shortest utterance that discharged each one. A checklist
produces interjections because a checklist is what it was handed.

He now has a manner, a share (a third to two fifths, about twenty turns at
thirty-five to forty words), a rhythm rule against strict alternation, and three
worked exchanges in the register Ray picked — the expansive one, which lays out
the competing readings and asks which the data supports. The counter-intuitive
part: a longer Theo is *cheaper* than it looks, because naming the competing
explanations is framing, and framing was Nadia's setup. Those words move rather
than being added.

The line that keeps it safe: **he never asserts what the paper found.** He may
pose alternatives, say what follows from each, and restate Nadia's claim more
precisely. "There are two readings that fit" is Theo; "they're tearing membrane
off the monocytes" is Nadia. Every checkable claim keeps coming out of one
mouth. `check_balance()` reports his share as a *warning* — a good episode must
not be blocked over a number nobody can dial precisely.

### The hype ban was too broad, and Ray was right about it

The register section banned the vocabulary (good: specific, unfalsifiable
marketing words, enforced mechanically) **and** the speech act — "what is banned
is claiming significance". That left the hosts no way to say the true thing when
the true thing is that a paper matters. And a sceptic who can never say "this
one holds up" has no credibility when they say "this one doesn't": the listener
learns only that the hosts always find a limitation, which is a mannerism, not
an assessment. The ban undermined the scepticism it existed to protect.

There was also an inconsistency inside the pipeline. The DICE score *is* a
significance ranking, and the digest prompt happily writes "the rate-limiting
input for new engager programmes rather than an incremental format tweak". The
upstream stage had a verdict; the hosts were the only ones muzzled.

So: **one verdict an episode, and it must name its comparison** — better than
what, stuck on what, impossible until when. The test is whether the checker
could verify it: "the first demonstration of X without Y" has a referent and can
be found wrong, which is the point; "groundbreaking" cannot. The slot may be
negative and usually is, which is what stops the slide — a positive verdict
means something only because the honest answer is normally "competent, moves
nothing". Surprise is allowed as a statement about the *speaker* ("I didn't
expect that to work"), never about the paper. The one bright line stays: no leap
to patients, no comparison earns it. `prompts/routine_checker_daily.md` now
tells the checker to test the comparison like a number.

### Two things found while in there

**"See you Friday" was a promise the pipeline had not made.** Nothing in the
prompt asked for a day; the model inferred it from the weekly rhythm in the cold
open, and a one-off can land on any day. `check_sign_off()` rejects a weekday in
the closing two turns — scoped there deliberately, because "as we do on Fridays"
is *required* framing in the cold open, and a paper that sampled on Tuesdays
must still be describable. Run against Monday's real script it produces exactly
one error, which is the line.

**The length target was wrong by seven hundred characters.** The prompt said
10,200–10,800 spoken characters; the validator demanded 11,000–11,600. Those
figures are the *minutes* — eleven thousand over one thousand and seventy-five
characters a minute is ten point two — written down as characters. Every script
was failing short and then being stretched to a target nobody had stated.
`PromptContractTests` now fails if the prompt's window and the validator's
constants ever drift apart again.

## Update, 2026-11-18: a doorbell, because the schedule never rings before eight

Ray emailed a one-off at 01:00 UTC and asked whether it would land the next
day. It would not have, and finding out why cost two bugs.

**The schedule.** `schedule_health.py --times` over seven days: since the
crons were split on the fourteenth, `generate-episode` gets exactly the three
runs a day it asks for — but **not one of them has started before 08:00 UTC**,
which is when the writer picks its paper. Before the split there were five or
six scattered runs a day, so one often landed early by luck. Tightening the
schedule removed the luck, which nobody predicted: an emailed paper was
collected by an afternoon sweep and written the *following* morning. Two days
from sending to hearing.

So `tools/gmail-doorbell/` — an Apps Script on the podcast's own Gmail
account, on a five-minute timer, that fires a `repository_dispatch` when mail
the pipeline cares about arrives. It is a **doorbell, not a gatekeeper**: it
parses nothing and labels nothing, the Python still decides what every message
means, and the asymmetry is deliberate. A false ring costs one workflow run
that finds nothing; a missed ring costs nothing at all, because the daily
sweeps still collect the mail. The token lives in Script Properties, scoped to
this repository with Contents: write, and the script can do exactly one thing
with it.

`tests/test_doorbell.py` pins the contract from the Python side: every subject
`pdf_mailbox` acts on must also ring. Writing it caught the first drift
immediately — the doorbell anchored "unsubscribe" to the start of a subject
while `pdf_mailbox` honours it anywhere, on purpose, so "Please unsubscribe
me" would have been acted on by the pipeline and never woken it.

**Running the sweep by hand no longer publishes.** `PUBLISH_SLOT` counted
`workflow_dispatch`, so collecting an emailed paper early also pushed a
finished episode out hours before its slot. It is now an opt-in checkbox, and
a doorbell run never takes the slot at all.

### The two bugs

**A one-off's PDF was thrown away and then asked for.** The first one-off ever
to arrive with a PDF attached opened Issue #138, and the sweep lost it. Two
fetches of the Issue list in one run disagreed: `queue_one_offs()` created the
Issue, `list_pending_issues()` called immediately after did not return it —
GitHub's list endpoints are eventually consistent — so the staging pass never
saw it, `consume_replies()` decided the Issue "isn't waiting" and marked the
email used, and `request_missing_pdfs()`, which re-fetches and by then *could*
see #138, emailed asking for the PDF that had come attached to the email that
opened it. The writer skips `needs-pdf` Issues silently, so the episode would
simply never have been written.

`github_issue.get_issue()` fetches one Issue directly, which is strongly
consistent; `ensure_listed()` fills in whatever the list has not caught up
with. And `request_missing_pdfs()` now takes what the staging pass actually
considered and never asks about anything outside it — *do not ask anyone for a
paper nobody tried to find* — which alone would have prevented the email.

**The hosts read the DOI aloud.** Forty seconds of digits in a synthesised
voice that nobody writes down, when the show notes already carry it as a link.
Matching it needed the *spoken* spelling: by the time a script exists the DOI
has been expanded for the ear, so `DOI_RE` never sees one.

## Update, 2026-11-19: adding somebody who asked you, not the mailbox

Self-service closed most of the original complaint, but not the part that
started it. Back on the 13th it was *"several people have asked to join the
email list"* — and a colleague who asks Ray in a meeting still needed him to
hand-edit `list/subscribers.txt`, because the list only ever subscribes the
verified sender.

So the owner may now name addresses in the subject: `subscribe
alice@example.com`, or several separated by commas, and `unsubscribe
alice@example.com` to remove one. Only his own verified address may do it —
`on_behalf_targets()` returns nothing for anybody else, who simply gets
subscribed themselves as before. Same rule as a one-off paper request: naming
what the show does is the owner's alone.

**Subject only, never the body.** Forwarding somebody's "can you add me?" is
the more natural gesture, but a forwarded body is full of addresses nobody
meant to subscribe — signatures, quoted headers, list footers.

**One note back, naming every address and its outcome.** Adding three
colleagues costs one message, and naming each one is what makes a typo
visible: a misspelling would otherwise sit on the list as a silent dead entry
forever.

### Two consent decisions, made deliberately

**An opt-out cannot be undone by a third party.** `Roster.subscribe` takes
`on_behalf`, and with it an address already on `list/unsubscribed.txt` comes
back `opted-out` and is left alone. They can rejoin by writing in themselves,
which is the only signal that actually means consent. Without this the owner
could silently re-add somebody who had left, which is the one thing a
suppression list exists to prevent.

**Somebody added is told they were added.** The welcome they receive opens
"You've been added to the Science TLDR weekly digest … If that was not at your
request, the link at the bottom takes you off the list immediately", rather
than the self-service "You're on the list". Telling someone they subscribed
when they did not is a small lie, and the remedy belongs in the first line.
This is notice-and-opt-out rather than confirmed opt-in; for a handful of
colleagues who have asked in person that is proportionate, and the feature
cannot tell the difference between those and anybody else, so that judgement
stays with Ray.

A bug worth recording: `welcome_message` derived its subject with `"Subscribed"
if outcome == "added" else "Already subscribed"`, so the new outcome went out
headed "Already subscribed" — the opposite of what had happened. It is a table
now, and a test walks every welcome outcome.

## Update, 2026-11-22: the Monday picker checks what we have already covered

Ray saw RFD4-Proteina in the 22 November digest and asked whether it had been
picked for an episode — we published it as episode 98 on the 11th, from the
white paper. It had not: the digest lists it under **Notable Preprints**, where
it happens to be numbered "### 1.", and the picker only ever considers
peer-reviewed entries. Two sections, two number ones, and the near miss was
decided by that boundary rather than by any check.

The broader fix — matching titles, to catch the same work under a different
identifier — he turned down, and convincingly: a preprint that later appears
in a journal usually carries revisions and new experiments, so a second
episode would be *worth* making rather than a duplicate. That argument changed
the design rather than overriding it.

What stayed worth fixing is narrower and has nothing to do with revisions:
**the same paper, same DOI, by two routes in one week.** A paper emailed in as
a one-off on the Tuesday can be the digest's top-scoring paper by the Sunday,
and nothing would have noticed — the Friday crawl checks
`already_seen_dois()`, but the Monday picker checked nothing, and a closed
Issue is not in the pending list so `rank_queue` cannot see it either.

`drop_covered()` now filters the candidates against published episodes and open
Issues, **before** the floor is computed — otherwise a paper we have already
covered could set the standard the rest are judged against, and a three would
qualify as "the same standard" where a four should have taken the slot. A paper
with no DOI is left alone, since there is nothing to compare and the
white-paper path has its own URL check. If the check cannot run at all, every
candidate stays: a Monday with no episode is worse than a small risk of a
repeat.

## Update, 2026-11-23: the watchdog asks instead of only complaining

The Monday episode dropped and the digest email did not. Nothing failed:
`email-digest` **did not run at all**, because GitHub delivered none of its
three Monday crons. The previous Monday it delivered all three — at 21:16,
22:32 and 23:03 UTC, seven to nine hours after their 11:50 to 13:50 windows,
so that week's digest went out at about one in the afternoon Pacific rather
than before Ray was up. The Monday-cron design has therefore never once hit
its target; on the 16th it was merely late enough to pass unnoticed.

The watchdog would have filed an Issue at midnight, forty-eight hours after
the digest's date. Ray noticed first.

The irony is that two schedules in this repository *are* delivered reliably —
the mailing-list poll, two or three runs a day without a gap, and the Apps
Script doorbell's five-minute timer — and the digest was using neither. So
`pending()` now **acts**: once Monday's send windows have closed (thirty-eight
hours from midnight of the digest's own date) it fires a `repository_dispatch`
at `email-digest` rather than waiting to complain. The sent record keeps that
safe, as it keeps the three crons safe: whichever route arrives first sends,
and the rest find it recorded and stop.

The Issue is still opened at forty-eight hours, but it now says something
different and more useful — by then the send has been asked for repeatedly and
has not happened, so the failure is in the send itself rather than in the
scheduling, and the body says to read the latest `email-digest` run.

It must be the PAT that fires the dispatch: a repository dispatch sent with the
default `GITHUB_TOKEN` deliberately triggers no workflow. The poll already
holds `GH_PAT`.

**Done the same evening.** Ray: *"Punctuality is a key aspect to a digest like
this."* The doorbell now rings a `digest` event at noon UTC on Mondays — after
the episode reaches the feed, before six in the morning Pacific in either half
of the year, once a Monday. It is called from inside `checkMailbox`, so
pasting the file is the whole update and the installed trigger never needs
recreating.

Three layers now, in order of punctuality: the Apps Script timer, which has
never missed; the poll's dispatch once Monday's windows close; and
`email-digest`'s own crons, which are the least reliable of the three and now
only a backstop. The sent record is what makes stacking them free.

## Update, 2026-11-26: r/science by OAuth, and a fallback that never worked

Friday's episode on 20 November opened as the PubMed trending pick, not the
r/science one, and Ray asked whether the crawl had failed. It had. Issue #144
carries `friday-reddit-failed`, and Thursday's run says why:

    [reddit] JSON endpoint failed (403 Client Error: Blocked); trying RSS
    [select-friday] reddit fetch failed: 404 Client Error: Not Found
    [select-friday] reddit yielded nothing — falling back to PubMed trending

Reddit 403s datacenter IPs on the public JSON endpoint whatever User-Agent it
is sent, which the code's own docstring already said. The strand has otherwise
held: **twenty-eight picks from Reddit against two failures**, the other in
May.

**The fallback had never worked.** It asked for `/r/science/top.rss?t=week`,
which answers Reddit's "Not Found" feed — Ray confirmed it in a browser, where
nothing is rate-limited or UA-blocked, and so did `/top/.rss`, which was the
first guess at a fix. Sorted RSS listings no longer exist. Every variant
tried from the sandbox:

| | |
|---|---|
| `/r/science/top.rss?t=week` | 404, the one the code requested |
| `/r/science/top/.rss?t=week` | 404 |
| `/r/science/.rss?sort=top&t=week` | 404 |
| `/r/science/.rss` | 429 — the path exists, the client is refused |
| `/r/science/top.json?t=week` | 403, as in production |

So the fallback burned a request to produce a guaranteed 404 while logging
"trying RSS" as though it might succeed. It is gone. There is no fallback now,
deliberately: a failure that announces itself is worth more than one that
cannot succeed, and `select_friday_paper` already handles the failure properly
by labelling the Issue and taking the PubMed strand, which the hosts then tell
the listener.

**The way in is application-only OAuth.** `_app_only_token()` exchanges the
app's id and secret for a bearer token at
`www.reddit.com/api/v1/access_token` with `grant_type=client_credentials`, and
`_fetch_top_week_oauth()` reads `oauth.reddit.com/r/science/top?t=week`. That
route is supported from a server and allows a hundred requests a minute per
client against the one a week this makes. Both routes share
`_posts_from_listing()`, because `oauth.reddit.com` returns the same shape as
the public endpoint — so a post dropped by one is dropped by the other.

Without credentials it still uses the public endpoint, which is what a laptop
has and works there. Ray registers the app at
`https://www.reddit.com/prefs/apps` (type: script) and adds
`REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` as repository secrets; the
workflow already passes them. Nothing here can be tested end to end from the
sandbox — Reddit refuses it with 403, 404 and 429 by turns even with
`www.reddit.com` allowed — so Thursday's run is the real test, and a wrong app
type or secret surfaces as an unswallowed `HTTPError` rather than as "reddit
had nothing".

### A test that only passed in the afternoon

`test_asking_comes_before_complaining`, written on the 23rd, derived its digest
date from `now - 40 hours`. The thresholds count from **midnight** of the
digest's date, so "due but not overdue" is the clock window 14:00 to 24:00
UTC: the test passed when it was written at about 17:40 and failed at 01:45
three days later. It now names the state it wants instead of inferring it from
the wall clock. Worth remembering that a date-stamped record compared against
hour-based thresholds has no stable relationship to "now minus N hours".

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
