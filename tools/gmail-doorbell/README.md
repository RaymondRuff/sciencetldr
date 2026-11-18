# The mailbox doorbell

An Apps Script on the podcast's Gmail account that asks `generate-episode` to
run as soon as mail arrives, instead of waiting for GitHub's scheduler.

## Why

`scripts/schedule_health.py` measures what GitHub actually delivers. Since the
crons were split on 2026-11-14 the answer is three runs a day, at times of
GitHub's choosing, and **none of them before 08:00 UTC** — which is when the
writer routine picks its paper. So a one-off emailed at any hour was collected
by an afternoon sweep and written the *following* morning. Two days from
sending a paper to hearing it.

The doorbell makes that minutes. It also covers subscribe and unsubscribe mail
and replies carrying a PDF, which were waiting on the same schedules.

It is a **doorbell, not a gatekeeper**. It parses nothing and labels nothing;
the Python in `scripts/pdf_mailbox.py` decides what every message means. A
false ring costs one workflow run that finds nothing. A missed ring costs
nothing at all, because the daily sweeps still collect the mail. Keep that
asymmetry if you change the patterns.

## Setup, once

1. Sign in to Gmail **as the podcast account** (`sciencetldrpod@gmail.com`),
   not your personal one. The script reads that mailbox.
2. Go to <https://script.new>. Name the project something like
   `Science TLDR doorbell`.
3. Replace the contents of `Code.gs` with the `Code.gs` beside this file.
4. **Project Settings → Script Properties → Add script property**, twice:

   | Property | Value |
   |---|---|
   | `GITHUB_REPO` | `RaymondRuff/sciencetldr` |
   | `GITHUB_TOKEN` | a GitHub token — see below |

   The token lives here, never in the code.
5. Back in the editor, choose `installTrigger` from the function dropdown and
   press **Run**. Google asks you to authorise Gmail access and external
   requests; approve both. This creates the five-minute timer.
6. Choose `ringNow` and press **Run** to check the wiring. A run should appear
   in the repository's Actions tab within seconds.

## The token

A fine-grained personal access token, scoped to `RaymondRuff/sciencetldr`
alone, with **Contents: Read and write** — that is the permission GitHub
requires to create a repository dispatch event. If `ringNow` logs
`dispatch refused: 403`, that permission is what to check first.

Do not reuse a token with wider access than this. The script can do exactly
one thing with it: ask a workflow to run.

## Watching it

- **Apps Script → Executions** lists every tick, with the log lines.
- A ring shows up in GitHub as a `repository_dispatch` run of
  `generate-episode`.
- Nothing it does publishes an episode: `PUBLISH_SLOT` is false for this
  event, so a doorbell run collects, queues and stages, and the day's publish
  slot stays where it belongs.

## Quotas

A consumer Google account allows about ninety minutes of trigger runtime a
day. A tick that finds nothing takes a second or two, so 288 ticks come to
well under ten minutes. The `UrlFetch` call only happens when mail is actually
waiting.

## If it stops

Google disables a trigger that fails repeatedly and emails the account. The
pipeline is unaffected — it falls back to exactly what it does today, the
daily sweeps — so a broken doorbell costs latency, never an episode.
