# Science TLDR

Automation pipeline for the [Science TLDR](https://raymondruff.github.io/sciencetldr/) podcast — a 10-minute paper-summary podcast for scientists, hosted by Raymond Ruff.

## What this repo does

- **Mondays:** runs a literature digest across PubMed, bioRxiv, and the web; emails it to a coworker list; picks the top-DICE-scored paper and opens a GitHub Issue with the PDF and prompt ready for [NotebookLM](https://notebooklm.google.com).
- **Fridays:** picks the top trending paper on PubMed (any field) and opens a similar Issue.
- **On a new Issue:** the generate-episode workflow fetches the paper's full text, has Claude write and then fact-check a two-host script, synthesizes it with Gemini multi-speaker TTS, and opens a **review PR** carrying the finished audio.
- **On merging that PR:** the MP3 lands in [`inbox/`](inbox/) and the publish workflow normalizes the audio, generates show notes, updates [`feed.xml`](feed.xml), and GitHub Pages auto-deploys.
- **After publishing:** the memory workflow distils the episode into a card under [`memory/cards/`](memory/) and updates [`memory/threads.md`](memory/threads.md), so later episodes can draw accurate connections across the back catalogue.

The only weekly step is listening to the draft and merging the PR. Audio generation replaced the manual NotebookLM flow; see [the episode generation notes](#episode-generation) below.

## Episode generation

| Piece | Where |
|---|---|
| Host characters, register rules, structure | [`prompts/host_dialogue.md`](prompts/host_dialogue.md) |
| Full-text acquisition (local PDF → Europe PMC → OA PDF → publisher HTML) | [`scripts/paper_text.py`](scripts/paper_text.py) |
| Script writing + verification pass | [`scripts/generate_script.py`](scripts/generate_script.py) |
| Speech synthesis (Gemini multi-speaker) | [`scripts/tts_dialogue.py`](scripts/tts_dialogue.py) |
| Cross-episode memory | [`scripts/memory.py`](scripts/memory.py) |
| Orchestration + review PR | [`scripts/generate_episode.py`](scripts/generate_episode.py) |

**Issue labels drive the state machine:** `podcast-pending` (eligible) → `needs-pdf` + `pdf-requested` (no reachable full text; a request was emailed) → `episode-in-review` (draft PR open) → closed on publish. A failed run gets `generation-failed`; remove the label to retry.

**Papers are chosen for being readable.** The Monday and Friday pickers take the best paper whose full text can actually be had, and stage that text in the private `sciencetldr-papers` repository, where the script-writing routine reads it (the routine's own sandbox cannot reach any paper source). A paywalled top pick gives way to the next paper down. Only when nothing good is open does a paper go ahead without its text, and then the workflow emails **one** request from the podcast account: **reply with the PDF attached**, or upload it to the papers repository as `papers/issue-NN.pdf`, and the next sweep ([`scripts/pdf_mailbox.py`](scripts/pdf_mailbox.py), [`scripts/paper_bundle.py`](scripts/paper_bundle.py)) stages it. Only allow-listed senders whose mail passes Gmail's authentication checks are accepted, and a paywalled PDF never enters this public repository.

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
