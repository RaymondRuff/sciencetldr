# Science TLDR

Automation pipeline for the [Science TLDR](https://raymondruff.github.io/sciencetldr/) podcast — a 10-minute paper-summary podcast for scientists, hosted by Raymond Ruff.

## What this repo does

- **Mondays:** an episode paired with the weekly literature digest. The digest runs across PubMed, bioRxiv and the web on **Sunday**, is emailed to a coworker list, and its top-DICE-scored paper becomes Monday morning's episode.
- **Fridays:** an episode on the week's most interesting paper from r/science (with PubMed trending as a fallback). The crawl runs **Thursday**.
- **Any day:** one paper you came across yourself, two ways in — **email** the podcast address with `one-off` starting the subject and either the DOI in the body or the PDF attached, or Actions → **add-paper** and paste the DOI ([`scripts/add_paper.py`](scripts/add_paper.py)). A paper with no DOI, such as an industry white paper, is identified by its link instead: give the link and a `Title:` line, and the hosts name the publisher rather than reading a DOI. Either is an episode the next morning. Emailed requests are answered: you get one reply with the Issue number, or the reason it was not queued. Only the owner's own address may commission an episode, and at most four may be waiting at once.

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

## The weekly digest list

The Sunday digest goes to a list that manages itself. **To join**, mail the podcast address with `subscribe` starting the subject; **to leave**, the same with `unsubscribe` — which the footer of every digest spells out as a link. One reply comes back either way, usually within the half hour, since the mailbox is polled that often.

The list is two files in the private `sciencetldr-papers` repository, `list/subscribers.txt` and `list/unsubscribed.txt`, and recipients are **(the file plus the `DIGEST_RECIPIENTS` secret) minus the unsubscribed** ([`scripts/mailing_list.py`](scripts/mailing_list.py)). So the people already on the secret stay subscribed with no action from them — the secret is still read, both as the seed the first send folds into the file and as the fallback if the private repository cannot be reached — and unsubscribing beats both sources, so an address that arrived on the secret can still leave. Once `list/subscribers.txt` holds everyone, the secret can be deleted.

Only the address Gmail's own DKIM or DMARC verdict vouches for is ever added or removed, never one written in a body, so no one can subscribe or unsubscribe anybody else; automated mail is ignored rather than answered. Digests are blind-copied, so no subscriber sees another's address.

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
