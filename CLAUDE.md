# Science TLDR

A two-host science podcast built by a pipeline: Claude Code routines write and
fact-check the scripts on the subscription; GitHub Actions fetches papers,
synthesises audio and publishes. `docs/subscription-pipeline-handoff.md` is the
full picture.

## If you are a scheduled routine

The current instructions for the daily routines live in this repository:

- writer: `prompts/routine_writer_daily.md`
- checker: `prompts/routine_checker_daily.md`

They supersede the text a routine's trigger may still carry from before
2026-11-04. Where the two differ, follow the file. In particular:

- **Choose the Issue with `python scripts/routine_tools.py queue`**, not by
  listing Issues yourself.
- **Never send a push notification about a paper you cannot get.** Park it
  with `python scripts/routine_tools.py park --issue <N> --label needs-pdf`
  and move on; GitHub Actions emails the one request for its PDF. The only
  push either routine sends is for an Issue it parks `generation-failed`.
- **GitHub is REST only** (`gh api repos/...`). GraphQL is refused in the
  routine sandbox, so no `gh issue` or `gh pr` subcommands.
- The sandbox cannot reach doi.org, Europe PMC, Unpaywall or any publisher.
  Papers arrive staged in the private papers repository cloned beside this
  one; otherwise use the PubMed and bioRxiv connectors.

## Conventions

- Branch, PR, merge. `.claude/settings.json` grants `gh pr merge`; use it.
- `uv run python ...` for anything in `scripts/`. Tests:
  `uv run python -m unittest discover tests`. Lint workflows with `actionlint`.
- Mock model and network clients in tests; never spend money to test plumbing.
  `MAX_EPISODES_PER_RUN` is `0` and there is no API fallback for scripts.
- Never commit a paper's text, a PDF, or anything under `/tmp`. The papers
  repository is a private staging area for other people's copyrighted work,
  not an archive.
- In dialogue every number is spelled out in words; the validator enforces it.
  Show notes, read on a screen, use digits.
- The hosts are fair but sceptical — never credulous about a paper's claims.
