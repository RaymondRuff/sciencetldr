# Science TLDR

Automation pipeline for the [Science TLDR](https://raymondruff.github.io/sciencetldr/) podcast — a 10-minute paper-summary podcast for scientists, hosted by Raymond Ruff.

## What this repo does

- **Mondays:** an episode paired with the weekly literature digest. The digest runs across PubMed, bioRxiv and the web on **Sunday**, is emailed to a coworker list, and its top-DICE-scored paper becomes Monday morning's episode.
- **Fridays:** an episode on the week's most interesting paper from r/science (with PubMed trending as a fallback). The crawl runs **Thursday**.
- **Any day:** one paper you came across yourself, two ways in — **email** the podcast address with `one-off` starting the subject and either the DOI in the body or the PDF attached, or Actions → **add-paper** and paste the DOI ([`scripts/add_paper.py`](scripts/add_paper.py)). A paper with no DOI, such as an industry white paper, is identified by its link instead: give the link and a `Title:` line, and the hosts name the publisher rather than reading a DOI. Either is an episode the next morning. Emailed requests are answered: you get one reply with the Issue number, or the reason it was not queued. Only the owner's own address may commission an episode, and at most four may be waiting at once.

**Emailed papers are picked up within minutes**, not on GitHub's schedule. An Apps Script on the podcast mailbox rings the pipeline when mail arrives ([`tools/gmail-doorbell/`](tools/gmail-doorbell/)) — GitHub has not started a scheduled run before 08:00 UTC since 2026-11-14, so without it a one-off waited for an afternoon sweep and was written the *following* morning. Actions → **generate-episode** → Run workflow does the same thing by hand, and no longer publishes anything unless you tick the box.

The picks run a day ahead of the drop because the pipeline takes a day: a pick on day D is written by a Claude Code routine at 08:00 UTC on D+1, fact-checked by a second routine at 11:00, and published about 11:25.
- **On a new Issue:** the generate-episode workflow fetches the paper's full text, has Claude write and then fact-check a two-host script, synthesizes it with Gemini multi-speaker TTS, and opens a PR carrying the finished audio.
- **On that PR's publish slot:** it merges itself, the MP3 lands in [`inbox/`](inbox/), and the publish workflow normalizes the audio, generates show notes, updates [`feed.xml`](feed.xml), and GitHub Pages auto-deploys. One episode per slot, so a backlog reaches the feed a day at a time.
- **After publishing:** the memory workflow distils the episode into a card under [`memory/cards/`](memory/) and updates [`memory/threads.md`](memory/threads.md), so later episodes can draw accurate connections across the back catalogue.

Nothing waits on a person: an episode goes from pick to feed on its own, and the pipeline writes only when it genuinely cannot proceed. Audio generation replaced the manual NotebookLM flow; see [the episode generation notes](#episode-generation) below.

## Episode generation

| Piece | Where |
|---|---|
| Host characters, register rules, structure | [`prompts/host_dialogue.md`](prompts/host_dialogue.md) |
| Full-text acquisition (local PDF → Europe PMC → OA PDF → publisher HTML) | [`scripts/paper_text.py`](scripts/paper_text.py) |
| Script writing + verification pass | [`scripts/generate_script.py`](scripts/generate_script.py) |
| Speech synthesis (Gemini multi-speaker) | [`scripts/tts_dialogue.py`](scripts/tts_dialogue.py) |
| Cross-episode memory | [`scripts/memory.py`](scripts/memory.py) |
| Orchestration + publish PR | [`scripts/generate_episode.py`](scripts/generate_episode.py) |

**Issue labels drive the state machine:** `podcast-pending` (eligible) → `needs-pdf` + `pdf-requested` (no reachable full text; a request was emailed) → `episode-in-review` (built and queued to publish) → closed on publish. A failed run gets `generation-failed`; remove the label to retry.

**The best paper, or an honest stand-in.** When the week's top paper is open, the Monday or Friday picker stages its full text in the private `sciencetldr-papers` repository, where the script-writing routine reads it (the routine's own sandbox cannot reach any paper source). When it is paywalled, the picker emails **one** request from the podcast account, with a deadline of 9 pm Pacific that day and the name of the open runner-up that will stand in. **Reply with the PDF attached**, or upload it to the papers repository as `papers/issue-NN.pdf`, and the top paper is written next morning; otherwise the runner-up is, and with no runner-up the slot is skipped rather than filled with a weaker paper ([`scripts/pdf_window.py`](scripts/pdf_window.py)). A PDF sent later still becomes an episode. Only allow-listed senders whose mail passes Gmail's authentication checks are accepted, and a paywalled PDF never enters this public repository.

An emailed PDF is collected by the mailbox check at the top of every generate-episode run — the three daily sweeps, and every Issue or push event, which are immediate. It is not polled for more often than that, deliberately: see [the schedule note](#a-note-on-schedules).

## The weekly digest list

The Sunday digest goes to a list that manages itself. **To join**, mail the podcast address with `subscribe` starting the subject; **to leave**, the same with `unsubscribe` — which the footer of every digest spells out as a link, and which a mail client can offer as a button, from the `List-Unsubscribe` header. Leaving gets a short note; **joining gets the most recent digest**, so a new subscriber has something to read straight away rather than a fortnight's wait and a promise.

**How long that takes is GitHub's to decide.** The poll asks to run four times an hour; over the eighteen days to 14 November 2026 its scheduled runs were actually *delivered* four to seven times a **day**, with one gap of seven hours. So expect an answer in hours, not minutes — and if you are waiting on one, **Actions → mailing-list → Run workflow** answers immediately.

`subscribe` has to **start** the subject. "Fwd: can you subscribe me?" matches nothing and gets no answer at all, deliberately: anything wider means replying to mail that merely mentions subscribing. `unsubscribe` counts anywhere in the subject, because someone leaving is likely to hit reply and type it after our own subject line.

The list is two files in the private `sciencetldr-papers` repository, `list/subscribers.txt` and `list/unsubscribed.txt`, and recipients are **(the file plus the `DIGEST_RECIPIENTS` secret) minus the unsubscribed** ([`scripts/mailing_list.py`](scripts/mailing_list.py)). So the people already on the secret stay subscribed with no action from them — it is still read, as the seed the first send folds into the file — and unsubscribing beats both sources, so an address that arrived on the secret can still leave. Once `list/subscribers.txt` holds everyone, the secret can be deleted.

The secret is **not** a fallback. Only the private repository knows who has unsubscribed, so a send that cannot read it stops, non-zero, and `alert-on-failure` opens an Issue: a digest a day late beats one sent to somebody who opted out.

Only the address Gmail's own DKIM or DMARC verdict vouches for is ever added or removed, never one written in a body, so no one can subscribe or unsubscribe anybody else; automated mail is ignored rather than answered. The verdict has to be one Gmail stamped itself, for the sender's own domain — a header the sender wrote is not a verdict ([`_authenticated`](scripts/pdf_mailbox.py)). The digest goes out as one message per subscriber, addressed to them, so nobody sees anybody else's address.

Subscribe and unsubscribe mail is answered by the **mailing-list** workflow, on its own schedule — not the episode workflow's, so joining never waits on an episode sweep — and running it by hand from Actions is the only way to get an answer in minutes. A dispatch while a scheduled run is going queues behind it rather than racing it for the same two files.

**The scout runs Sunday; the email goes out Monday morning.** The digest routine is free to keep researching and to revise what it has already committed — on 2026-11-15 it did, two minutes later, and everyone received both versions. Nothing downstream now watches those pushes: the email is sent by a Monday-morning schedule (three chances between 11:50 and 13:50 UTC, so it is waiting before 6am Pacific, with the paired episode already in the feed), and whatever the digest settled on is what goes out. One email per digest, keyed by the digest's own date and recorded in the papers repository; Actions → **email-digest** with `force` resends deliberately. If every scheduled chance is dropped, the mailing-list poll opens an Issue rather than letting the week pass silently.

The Monday pick is recorded the same way — one episode per digest, so a revised digest cannot queue a second one. First pick wins: a revision that changed the *top* paper would leave the episode on the paper picked first.

**To read the list:** [`list/subscribers.txt`](https://github.com/RaymondRuff/sciencetldr-papers/blob/main/list/subscribers.txt) in the private papers repository. Actions → **mailing-list** writes the secret's addresses into it on demand, so the roster can be checked without waiting for a send; it emails nobody. No address is ever printed in an Actions log — this repository is public and so are its logs.

## A note on schedules

GitHub's `schedule` event is best-effort, and on this repository it is much worse than that. Measured over 14 days with [`scripts/schedule_health.py`](scripts/schedule_health.py): `generate-episode` was delivered about **5.6 runs a day whatever its crons asked for**, and of the 42 daily sweeps it should have run, **8 fired** — the 14:11 publish slot on 4 days of 14, the 05:17 PDF-window sweep on 2. A neighbouring workflow's single weekly cron, meanwhile, was delivered every time.

So as of 2026-11-14 the half-hourly mailbox poll no longer shares a workflow with the daily sweeps. The hypothesis under test is that a workflow gets roughly five scheduled runs a day however many it asks for, and that a half-hourly cron therefore spends the budget its own daily sweeps need. If that is right, a workflow asking for three ticks a day should get three, and the publish slot becomes a real time again.

What actually keeps the pipeline moving is events, not schedules: an Issue being labelled, and the checker's script landing on `main`, both fire within seconds. Treat the crons as a safety net.

Run `uv run python scripts/schedule_health.py --days 14 --times`, or Actions → **schedule-health**, for the current numbers.

## Feed

- **New feed:** https://raymondruff.github.io/sciencetldr/feed.xml
- **Legacy (rss.com, redirects via `<itunes:new-feed-url>`):** https://media.rss.com/sciencetldr/feed.xml

## Architecture

See [the implementation plan](https://github.com/RaymondRuff/sciencetldr/blob/main/README.md) for the full design. Workflows live under [.github/workflows/](.github/workflows/), Python in [scripts/](scripts/), prompts in [prompts/](prompts/).

## Local development

```bash
uv sync
uv run python scripts/feed_builder.py
```

## License

Episode audio and show notes © Raymond Ruff. Code in this repo is MIT-licensed.
