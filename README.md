# Science TLDR

Automation pipeline for the [Science TLDR](https://raymondruff.github.io/sciencetldr/) podcast — a 10-minute paper-summary podcast for scientists, hosted by Raymond Ruff.

## What this repo does

- **Mondays:** runs a literature digest across PubMed, bioRxiv, and the web; emails it to a coworker list; picks the top-DICE-scored paper and opens a GitHub Issue with the PDF and prompt ready for [NotebookLM](https://notebooklm.google.com).
- **Fridays:** picks the top trending paper on PubMed (any field) and opens a similar Issue.
- **On MP3 upload:** when an MP3 is dropped into [`inbox/`](inbox/), the publish workflow normalizes the audio, generates show notes, updates [`feed.xml`](feed.xml), and GitHub Pages auto-deploys.

The only manual step each week is generating the audio in NotebookLM (~2 clicks, ~5 min total per week).

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
