# Science TLDR

Automation pipeline for the [Science TLDR](https://raymondruff.github.io/sciencetldr/) podcast — a 10-minute paper-summary podcast for scientists, hosted by Raymond Ruff.

## What this repo does

- **Mondays:** an episode paired with the weekly literature digest. The digest runs across PubMed, bioRxiv and the web on **Sunday**, is emailed to a coworker list, and its top-DICE-scored paper becomes Monday morning's episode.
- **Fridays:** an episode on the week's most interesting paper from r/science (with PubMed trending as a fallback). The crawl runs **Thursday**.
- **Any day:** one paper you came across yourself — Actions → **add-paper**, paste the DOI ([`scripts/add_paper.py`](scripts/add_paper.py)). It is an episode the next morning.

The picks run a day ahead of the drop because the pipeline takes a day: a pick on day D is written by a Claude Code routine at 08:00 UTC on D+1, fact-checked by a second routine at 11:00, and published about 11:25.
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

**The best paper, or an honest stand-in.** When the week's top paper is open, the Monday or Friday picker stages its full text in the private `sciencetldr-papers` repository, where the script-writing routine reads it (the routine's own sandbox cannot reach any paper source). When it is paywalled, the picker emails **one** request from the podcast account, with a deadline of 9 pm Pacific that day and the name of the open runner-up that will stand in. **Reply with the PDF attached**, or upload it to the papers repository as `papers/issue-NN.pdf`, and the top paper is written next morning; otherwise the runner-up is, and with no runner-up the slot is skipped rather than filled with a weaker paper ([`scripts/pdf_window.py`](scripts/pdf_window.py)). A PDF sent later still becomes an episode. Only allow-listed senders whose mail passes Gmail's authentication checks are accepted, and a paywalled PDF never enters this public repository.

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
