"""The PDF window: ask once for a paywalled top pick, then fall back on time.

When the week's best paper cannot be fetched, the picker does not quietly
take a weaker one. It opens the Issue for the best paper, emails Ray once with
a deadline of 9 pm Pacific that day, and names the runner-up — the best paper
that *can* be fetched — so he can tell at a glance whether the PDF is worth
the trouble. Then:

  * a PDF arrives in time   → it is staged, and the writer takes the top pick;
  * the deadline passes     → the runner-up gets its own Issue and is staged,
                              before the writer's 08:00 UTC run (a candidate
                              that was merely unreachable at pick time and
                              ranks higher is tried first);
  * there is no runner-up   → the slot is skipped rather than filled with a
                              weaker paper.

Either way the original Issue stays open. A PDF that arrives late still
becomes an episode; it was the better paper.

The deadline sits a few hours before the writer runs, so a missed deadline
costs no time. The fallback runs in the sweep, including one scheduled for the
small hours. If GitHub starts that sweep late, the worst case is a one-day
delay, never a weaker paper.

Issue state, all in the Issue itself:
  label `awaiting-pdf`          the window is open
  METADATA.pdf_deadline         when it closes (UTC, ISO 8601)
  METADATA.runner_up            the paper named in the email, or null
  METADATA.stand_ins            what is tried at the deadline, in order: any
                                candidate that could not be checked at pick
                                time and ranks above the runner-up, then the
                                runner-up
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import github_issue

LABEL_AWAITING = "awaiting-pdf"
PACIFIC = ZoneInfo("America/Los_Angeles")
DEADLINE_HOUR = 21  # 9 pm Pacific: the end of Ray's day, three or four hours before the writer
MIN_WINDOW = timedelta(hours=6)  # a pick made late in the day gets until 9 pm tomorrow

EMOJI = {"monday-digest": "📄", "friday-reddit": "🔥", "friday-trending": "📈"}
RUNNER_UP_KEYS = ("title", "doi", "dice", "raw", "pmid", "journal_citation", "rank", "pdf_url")


def now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def deadline_for(picked_at: datetime) -> datetime:
    """9 pm Pacific on the day of the pick, or the next day if that is too soon."""
    local = picked_at.astimezone(PACIFIC)
    deadline = local.replace(hour=DEADLINE_HOUR, minute=0, second=0, microsecond=0)
    if deadline - local < MIN_WINDOW:
        deadline += timedelta(days=1)  # wall-clock arithmetic: still 9 pm across DST
    return deadline.astimezone(timezone.utc)


def describe(deadline: datetime) -> str:
    """'9:00 pm Pacific on Mon 9 Nov (05:00 UTC)' — portable, no %-d."""
    local = deadline.astimezone(PACIFIC)
    hour = local.hour % 12 or 12
    meridiem = "am" if local.hour < 12 else "pm"
    return (
        f"{hour}:{local.minute:02d} {meridiem} Pacific on "
        f"{local.strftime('%a')} {local.day} {local.strftime('%b')} "
        f"({deadline.astimezone(timezone.utc):%H:%M} UTC)"
    )


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(text: str) -> Optional[datetime]:
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def runner_up_record(paper: Optional[dict], pdf_url: Optional[str]) -> Optional[dict]:
    """What the Issue keeps about the runner-up, so the fallback can open it later."""
    if not paper:
        return None
    record = {k: paper[k] for k in RUNNER_UP_KEYS if paper.get(k) not in (None, "")}
    if pdf_url:
        record["pdf_url"] = pdf_url
    return record


def _labels(issue: dict) -> set[str]:
    return {l["name"] if isinstance(l, dict) else l for l in issue.get("labels", [])}


def resolve(issues: list[dict], bundled: dict, *, now: Optional[datetime] = None) -> list[str]:
    """Close every window whose deadline has passed. Returns errors, if any.

    An Issue whose PDF arrived is left alone here: staging it already cleared
    its labels. One whose source failed only for now is retried next run.
    """
    now = now or now_utc()
    errors: list[str] = []
    for issue in issues:
        number = issue["number"]
        if LABEL_AWAITING not in _labels(issue) or number in bundled:
            continue
        meta = github_issue.parse_metadata(issue.get("body") or "") or {}
        deadline = parse_iso(meta.get("pdf_deadline") or "")
        if deadline is None:
            print(f"[window] #{number}: no readable deadline; closing its window now")
        elif now < deadline:
            print(f"[window] #{number}: waiting for its PDF until {describe(deadline)}")
            continue
        try:
            fall_back(issue, meta, deadline)
        except Exception as exc:  # noqa: BLE001 - one Issue must not stop the sweep
            errors.append(f"#{number}: the PDF window could not close ({exc})")
            print(f"[window] #{number}: FAILED to close the window: {exc}")
    return errors


def fall_back(issue: dict, meta: dict, deadline: Optional[datetime]) -> Optional[int]:
    """The deadline passed with no PDF: open a stand-in, or skip the slot.

    The stand-ins are tried in rank order: any candidate whose source was down
    at pick time and ranks above the runner-up, then the runner-up named in
    the email. A source that is down again is passed over; if every stand-in
    was down the window stays open for the next sweep, because an outage is
    not a paywall. Only when every stand-in is known to be closed, or there
    were none, is the slot skipped.
    """
    import paper_text
    import select_friday_paper
    import select_monday_paper

    number = issue["number"]
    when = describe(deadline) if deadline else "the deadline"
    source = meta.get("source") or ""
    stand_ins = meta.get("stand_ins")
    if stand_ins is None:  # an Issue opened before stand-ins were recorded
        stand_ins = [meta["runner_up"]] if meta.get("runner_up") else []

    def close_window(message: str) -> None:
        github_issue.comment(number, message)
        github_issue.remove_label(number, LABEL_AWAITING)

    later = (
        "This Issue stays open: if the PDF still arrives, by reply or upload, it "
        "becomes an episode too."
    )
    seen = select_friday_paper.already_seen_dois() if stand_ins else set()
    chosen = pdf_url = fetched = None
    down = queued = 0
    for candidate in stand_ins:
        if (candidate.get("doi") or "").lower() in seen:
            queued += 1
            continue
        try:
            url, text = select_monday_paper.obtain(candidate)
        except paper_text.TransientFetchError as exc:
            print(f"[window] #{number}: {candidate.get('title', '')[:60]}: source down ({exc})")
            down += 1
            continue
        if text is not None:
            chosen, pdf_url, fetched = candidate, url, text
            break

    if chosen is None:
        if down:
            print(f"[window] #{number}: every stand-in still to try was down; retrying next run")
            return None
        reason = (
            "no paper of the same standard was open"
            if not stand_ins
            else "the stand-in is already published or queued"
            if queued == len(stand_ins)
            else "no stand-in's full text could be fetched any more"
        )
        print(f"[window] #{number}: deadline passed and {reason}; skipping the slot")
        close_window(
            f"No PDF arrived by {when}, and {reason}, so this slot is skipped rather "
            f"than filled with a weaker paper. {later}"
        )
        return None

    paper = {
        "title": chosen["title"],
        "doi": chosen["doi"],
        "dice": chosen.get("dice"),
        "raw": chosen.get("raw", ""),
    }
    body = select_monday_paper.render_issue_body(
        paper,
        pdf_url or chosen.get("pdf_url"),
        source,
        fetched=fetched,
        notes=[f"Stands in for #{number}, whose PDF did not arrive by {when}."],
    )
    emoji = EMOJI.get(source, "📄")
    labels = [github_issue.PENDING_LABEL, source] if source else [github_issue.PENDING_LABEL]
    new = github_issue.open_issue(title=f"{emoji} {paper['title'][:160]}", body=body, labels=labels)
    print(f"[window] #{number}: deadline passed; stand-in opened as #{new}")
    select_monday_paper.stage_for_writer(new, paper, fetched, journal=chosen.get("journal_citation", ""))
    close_window(f"No PDF arrived by {when}, so #{new} stands in: {paper['title'][:160]}. {later}")
    return new
