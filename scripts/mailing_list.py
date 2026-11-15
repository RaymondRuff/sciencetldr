"""Who gets the weekly digest, and how they say so themselves.

The list used to be the `DIGEST_RECIPIENTS` secret: a secret cannot be read
back, so adding one person meant retyping everyone. It now lives in the
private papers repository, as two plain files:

    list/subscribers.txt    one address per line; `#` starts a comment
    list/unsubscribed.txt   addresses that must never be sent to again

Recipients are **(the file plus the old secret) minus the unsubscribed**.
Three properties fall out of that, and they are the point:

  * the people already on the secret keep receiving the digest without
    anyone doing anything;
  * their first send folds them into the file, so the list becomes readable
    and the secret can be deleted whenever it suits;
  * unsubscribing sticks. The suppression file beats both sources, so
    someone who came in on the secret can still leave, which a list built
    only from a secret could never offer.

That last one is why there is no fallback to the secret alone. Only the
papers repository knows who has left, so a send that cannot read it does not
know either, and `recipients()` stops instead: a digest a day late beats one
sent to somebody who opted out. A failed *write* is different — the list was
read correctly, so the send goes ahead and the next one repeats the fold.

Subscribing is a mail to the podcast address with "subscribe" starting the
subject, and leaving is the same with "unsubscribe". Only the **sender's own**
address is ever added, and only when Gmail's own DKIM or DMARC verdict says
the From line is genuine — otherwise anyone could sign up somebody else.

The confirmation for a new subscriber is **the most recent digest itself**,
with a line of preamble on top: it proves the subscription works, and it is
worth reading, which a note saying "you're on the list" is not.

Standard library only: this runs in the mailbox poll, before any dependency
is installed.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from email.utils import parseaddr
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIGEST_DIR = ROOT / "digest"

LIST_DIR = "list"
SUBSCRIBERS = "subscribers.txt"
UNSUBSCRIBED = "unsubscribed.txt"
SENT = "digests-sent.txt"
PICKED = "digests-picked.txt"

# A digest written on Sunday is emailed on Monday morning. Past this, counted
# from midnight of the digest's own date, something has gone wrong and nobody
# has been told — a scheduled run GitHub never delivers fails nothing, so
# alert-on-failure sees no problem at all.
OVERDUE_HOURS = 48
ALERT_LABEL = "pipeline-alert"

ADDRESS_RE = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$")


def valid(address: str) -> bool:
    """Whether this is an address we are willing to store and send to."""
    return bool(ADDRESS_RE.match((address or "").strip()))


def normalise(address: str) -> str:
    return (address or "").strip().lower()


def legacy_parts() -> tuple[set[str], int]:
    """(addresses, unreadable entries) from the DIGEST_RECIPIENTS secret.

    The secret was typed by hand over a year and nobody can read it back to
    check, so this parses generously: entries may be separated by commas or
    semicolons, and `Ray Ruff <ray@example.com>` counts as an address. The old
    code sent to whatever it found, because smtplib strips a display name on
    the way out; dropping such an entry now would silently unsubscribe
    somebody, which is the one thing this migration must not do.

    Each entry is parsed on its own, deliberately. email.utils.getaddresses()
    does the whole string at once and, since Python 3.13, answers a trailing
    comma with [("", "")] — one malformed character would discard the entire
    list. The count of what could not be read is returned so a send can say
    so out loud.
    """
    kept, dropped, _ = legacy_counted()
    return kept, dropped


def legacy_counted() -> tuple[set[str], int, int]:
    """As legacy_parts(), plus how many entries the secret actually holds.

    The entry count matters when the number of subscribers is not the number
    expected: six entries that yield five addresses means two of them are the
    same person (the same address twice, or in two letter cases), which is a
    different problem from an address having gone missing.
    """
    raw = os.environ.get("DIGEST_RECIPIENTS", "")
    kept: set[str] = set()
    dropped = 0
    entries = 0
    for token in re.split(r"[,;]", raw):
        if not token.strip():
            continue
        entries += 1
        address = parseaddr(token)[1] or token
        if valid(address):
            kept.add(normalise(address))
        else:
            dropped += 1
    return kept, dropped, entries


def legacy() -> set[str]:
    """Addresses still coming from the DIGEST_RECIPIENTS secret."""
    return legacy_parts()[0]


def _read(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    found = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if valid(line):
            found.add(normalise(line))
    return found


def _write(path: Path, addresses: set[str], heading: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {heading}", "# One address per line. Managed by scripts/mailing_list.py.", ""]
    lines += sorted(addresses)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class Roster:
    """The two files, read from a clone of the private papers repository."""

    def __init__(self, repo) -> None:
        self.repo = repo
        base = repo.dir / LIST_DIR
        self.subscribers_path = base / SUBSCRIBERS
        self.unsubscribed_path = base / UNSUBSCRIBED
        self.subscribers = _read(self.subscribers_path)
        self.unsubscribed = _read(self.unsubscribed_path)

    def active(self) -> list[str]:
        """Everyone the digest should go to, in a stable order."""
        return sorted((self.subscribers | legacy()) - self.unsubscribed)

    def save(self, message: str) -> bool:
        _write(self.subscribers_path, self.subscribers, "Science TLDR digest subscribers")
        _write(self.unsubscribed_path, self.unsubscribed, "Unsubscribed — never send to these")
        return self.repo.commit(message, paths=(LIST_DIR,))

    def subscribe(self, address: str) -> str:
        """Add an address. Returns what happened, for the reply."""
        address = normalise(address)
        if not valid(address):
            return "invalid"
        self.unsubscribed.discard(address)
        if address in self.subscribers or address in legacy():
            self.subscribers.add(address)
            return "already"
        self.subscribers.add(address)
        return "added"

    def unsubscribe(self, address: str) -> str:
        address = normalise(address)
        if not valid(address):
            return "invalid"
        known = address in self.subscribers or address in legacy()
        self.subscribers.discard(address)
        self.unsubscribed.add(address)
        return "removed" if known else "not-on-it"

    def fold_in_legacy(self) -> set[str]:
        """Move the secret's addresses into the file, once. Returns what moved."""
        moved = legacy() - self.subscribers - self.unsubscribed
        self.subscribers |= moved
        return moved


def _read_lines(path: Path) -> set[str]:
    """Non-comment lines of a plain record file."""
    if not path.is_file():
        return set()
    found = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            found.add(line)
    return found


def _write_lines(path: Path, lines: set[str], *headings: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join([*(f"# {h}" for h in headings), "", *sorted(lines)]) + "\n",
        encoding="utf-8",
    )


def _records(name: str) -> set[str]:
    with _repo() as repo:
        return _read_lines(repo.dir / LIST_DIR / name)


def _remember(name: str, stamp: str, message: str, *headings: str) -> bool:
    with _repo() as repo:
        path = repo.dir / LIST_DIR / name
        stamps = _read_lines(path)
        if stamp in stamps:
            return True
        _write_lines(path, stamps | {stamp}, *headings)
        return repo.commit(message, paths=(LIST_DIR,))


def picked_digests() -> set[str]:
    """Digest dates an episode has already been queued from.

    The Monday picker runs on every push touching digest/*.md, and on
    2026-11-15 the digest routine pushed twice — so it opened two Issues for
    the same paper, which would have published as two episodes on consecutive
    days. One episode per digest, recorded as a fact rather than inferred from
    a diff.
    """
    return _records(PICKED)


def record_picked(stamp: str) -> bool:
    """Note that an episode has been queued from this digest."""
    return _remember(
        PICKED,
        stamp,
        f"Digest {stamp} picked for an episode",
        "Digests an episode has been queued from, by the digest's own date.",
        "Managed by scripts/select_monday_paper.py; delete a line to re-pick.",
    )


def unsent_digests(sent: set[str] | None = None) -> list[Path]:
    """Digest files not yet emailed, oldest first."""
    if not DIGEST_DIR.is_dir():
        return []
    known = sent_digests() if sent is None else sent
    return sorted(
        (path for path in DIGEST_DIR.glob("*.md") if path.stem not in known),
        key=lambda path: path.stem,
    )


def overdue(stamp: str, *, now: datetime | None = None, hours: int = OVERDUE_HOURS) -> bool:
    """Whether a digest of this date should have gone out by now."""
    try:
        day = date.fromisoformat(stamp)
    except ValueError:
        return False
    now = now or datetime.now(tz=timezone.utc)
    due = datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(hours=hours)
    return now > due


def sent_digests() -> set[str]:
    """Digest dates already emailed, from the private papers repository.

    Keyed by the digest's own date — its filename — not the day it was sent,
    so a re-run tomorrow of today's digest is still a duplicate.

    On 2026-11-15 the digest routine committed the digest and then revised it
    two minutes later; the workflow fires on any push touching digest/*.md, so
    six people received two different digests. Whether a digest has gone out is
    a fact about the world, not something a diff can be trusted to infer.

    Raises if the record cannot be read: sending blind risks a duplicate, and
    the recipients come from the same repository anyway, so there is no case
    where this fails and the send could still have been correct.
    """
    return _records(SENT)


def record_sent(stamp: str) -> bool:
    """Note that this digest has gone out. Returns whether it was stored."""
    return _remember(
        SENT,
        stamp,
        f"Digest {stamp} emailed",
        "Digests already emailed, by the digest's own date.",
        "Managed by scripts/email_digest.py; delete a line to allow a resend.",
    )


def _repo():
    import paper_bundle

    return paper_bundle.PapersRepo()


def recipients() -> list[str]:
    """Who to send the digest to, folding the old secret into the file as we go.

    The list is worked out from what was read, before anything is written, and
    the write gets a `try` of its own. Those two used to share one, and its
    `except` answered any failure — a rejected push included — with the bare
    secret, which has no suppression list in it. A second writer pushing first
    was enough to mail somebody who had unsubscribed.

    A read that fails exits non-zero rather than guessing: see the module
    docstring.
    """
    active: list[str] = []
    try:
        with _repo() as repo:
            roster = Roster(repo)
            moved = roster.fold_in_legacy()
            # Everything the send needs, decided before anything is written.
            active = roster.active()
            print(
                f"[list] {len(active)} subscriber(s): {len(roster.subscribers)} on file, "
                f"{len(roster.unsubscribed)} unsubscribed"
            )
            if moved:
                print(f"[list] folding {len(moved)} address(es) from the secret into the file")
                try:
                    roster.save(
                        f"Add {len(moved)} subscriber(s) carried over from DIGEST_RECIPIENTS"
                    )
                except Exception as exc:  # noqa: BLE001 - the list read above is still right
                    print(
                        f"[list] the fold could not be written ({type(exc).__name__}); "
                        "sending to the list as read, and the next send will try again"
                    )
    except Exception as exc:  # noqa: BLE001 - reported, then exited on
        print(f"[list] could not read the list ({type(exc).__name__}: {exc})")
        sys.exit(
            "[list] could not read list/unsubscribed.txt, so who has left is unknown; "
            "not sending. Fix access to the papers repository and run the digest again."
        )

    unreadable = legacy_parts()[1]
    if unreadable:
        print(
            f"[list] WARNING: {unreadable} entr(ies) in DIGEST_RECIPIENTS are not "
            "readable as an address and nobody is being sent to them"
        )
    return active


REPLIES = {
    "added": (
        "You're on the list.\n\nThe Science TLDR weekly digest goes out once a week: "
        "the most relevant recent papers on T cell engagers and multispecific immune "
        "engagers, with a short read on each.\n\n"
        "To stop, reply to this message with 'unsubscribe' as the subject."
    ),
    "already": (
        "You were already on the list, so nothing changed — the weekly digest will "
        "keep arriving.\n\nTo stop, reply with 'unsubscribe' as the subject."
    ),
    "removed": (
        "You're off the list. No more digests will be sent to this address.\n\n"
        "If that was a mistake, reply with 'subscribe' as the subject."
    ),
    "not-on-it": (
        "That address wasn't on the list, but it is now recorded as unsubscribed, so "
        "nothing will be sent to it.\n\n"
        "If you meant to join, reply with 'subscribe' as the subject."
    ),
}

SUBJECTS = {
    "added": "Subscribed to the Science TLDR digest",
    "already": "Already subscribed to the Science TLDR digest",
    "removed": "Unsubscribed from the Science TLDR digest",
    "not-on-it": "Unsubscribed from the Science TLDR digest",
}


def apply_requests(requests: list[dict]) -> list[dict]:
    """Act on subscribe and unsubscribe mails. Returns one answer per request.

    Each answer is {uid, address, outcome, subject, body, message_id}. A
    request whose change could not be stored is left out — including a save
    that stored nothing — so its mail stays unlabelled and the next poll tries
    again rather than promising something untrue.
    """
    if not requests:
        return []
    answers: list[dict] = []
    try:
        with _repo() as repo:
            roster = Roster(repo)
            roster.fold_in_legacy()
            for request in requests:
                address = normalise(request.get("address", ""))
                wants = request.get("wants")
                outcome = (
                    roster.unsubscribe(address) if wants == "unsubscribe"
                    else roster.subscribe(address)
                )
                if outcome == "invalid":
                    print(f"[list] ignoring a {wants} from an address we cannot use")
                    continue
                print(f"[list] {wants}: {outcome}")
                answers.append(
                    {
                        "uid": request.get("uid", ""),
                        "address": address,
                        "outcome": outcome,
                        "subject": SUBJECTS[outcome],
                        "body": REPLIES[outcome] + "\n",
                        # So the answer threads under what they sent.
                        "message_id": request.get("message_id", ""),
                    }
                )
            if answers:
                today = datetime.now(tz=timezone.utc).date().isoformat()
                if not roster.save(f"Mailing list: {len(answers)} change(s) on {today}"):
                    # save() answers False when there was nothing staged to
                    # commit, which means the change is not on file anywhere.
                    # Same as the exception below: promise nothing, retry.
                    print("[list] the change did not store; it will be retried")
                    return []
    except Exception as exc:  # noqa: BLE001 - leave the mail for the next poll
        print(f"[list] could not record the change ({exc}); it will be retried")
        return []
    return answers


# Outcomes whose answer is the digest itself rather than a short note. Only a
# new subscriber: "already" used to be in here so that a failed welcome could
# be retried, but it also meant a lost race or a label that did not take sent
# the whole ~100 KB digest again, and again. Writing in twice now gets the
# one-line note from REPLIES["already"], which is all it needs to be.
# welcome_message() still renders "already" — the retry that reaches it is the
# one inside send_welcomes(), not another poll.
WELCOME_OUTCOMES = ("added",)

PREAMBLE = {
    "added": (
        "You're on the list. The Science TLDR weekly digest goes out once a week: "
        "the most relevant recent papers on T cell engagers and multispecific "
        "immune engagers, with a short read on each.\n\n"
        "Here is the most recent one, from {date}, so you can see what arrives."
    ),
    "already": (
        "You were already on the list, so nothing changed — the weekly digest will "
        "keep arriving.\n\n"
        "Here is the most recent one, from {date}, in case it went astray."
    ),
}


def latest_digest(directory: Path | None = None) -> tuple[str, str] | None:
    """(date, markdown) of the most recent digest, or None if there is none.

    Digest files are named by their date, so the last one in sort order is the
    newest — the same rule email_digest.py uses to pick what to send.
    """
    base = DIGEST_DIR if directory is None else directory
    if not base.is_dir():
        return None
    files = sorted(p for p in base.glob("*.md") if p.is_file())
    if not files:
        return None
    return files[-1].stem, files[-1].read_text(encoding="utf-8")


def spoken_date(stamp: str) -> str:
    """"2026-11-09" as "9 November 2026"; anything else unchanged."""
    try:
        when = date.fromisoformat(stamp)
    except ValueError:
        return stamp
    return f"{when.day} {when:%B %Y}"


def render_html(markdown_text: str) -> str | None:
    """The digest as HTML, or None where the markdown package is not installed.

    The mailbox poll runs before any dependency is installed, so this has to be
    allowed to fail: a welcome that arrives as plain text is much better than
    one that does not arrive. The workflow sends welcomes in a later step,
    after `uv sync`, so in practice this returns HTML.
    """
    try:
        import markdown
    except ImportError:  # pragma: no cover - the pre-install mailbox step
        return None
    return markdown.markdown(markdown_text, extensions=["extra", "sane_lists"])


def wrap_html(inner: str) -> str:
    return (
        "<html><body style='font-family:system-ui,sans-serif;max-width:42rem'>"
        f"{inner}</body></html>"
    )


def welcome_message(
    digest: tuple[str, str] | None, outcome: str, unsubscribe_to: str
) -> tuple[str, str, str | None]:
    """(subject, text, html) for a new subscriber: the latest digest, framed.

    With no digest to hand — a fresh checkout, or the very first week — this
    falls back to the short note, because an empty welcome is worse than a
    plain one.
    """
    text_footer, html_footer = footer(unsubscribe_to)
    if digest is None:
        return SUBJECTS[outcome], REPLIES[outcome] + text_footer, None
    stamp, body_md = digest
    preamble = PREAMBLE[outcome].format(date=spoken_date(stamp))
    lead = "Subscribed" if outcome == "added" else "Already subscribed"
    subject = f"{lead} — Science TLDR Weekly Digest, {stamp}"
    text = f"{preamble}\n\n---\n\n{body_md}{text_footer}"
    rendered = render_html(body_md)
    html = None
    if rendered is not None:
        paragraphs = "".join(
            f"<p>{line}</p>" for line in preamble.split("\n\n") if line.strip()
        )
        html = wrap_html(f"{paragraphs}<hr>{rendered}{html_footer}")
    return subject, text, html


def footer(unsubscribe_to: str) -> tuple[str, str]:
    """(plain, html) footer for the digest, so leaving never needs a person."""
    text = (
        "\n\n---\n"
        "You're receiving this because you subscribed to the Science TLDR weekly "
        f"digest. To stop, reply to {unsubscribe_to} with 'unsubscribe' as the "
        "subject.\n"
    )
    html = (
        "<hr><p style='color:#666;font-size:0.85em'>You're receiving this because "
        "you subscribed to the Science TLDR weekly digest. To stop, reply to "
        f"<a href='mailto:{unsubscribe_to}?subject=unsubscribe'>{unsubscribe_to}</a> "
        "with 'unsubscribe' as the subject.</p>"
    )
    return text, html


def sync() -> int:
    """Write the secret's addresses into the file and commit. Prints counts only.

    This exists so the list can be read without waiting for a send: afterwards
    list/subscribers.txt in the papers repository is the whole roster.

    **No address is ever printed.** This runs in a public repository's Actions
    logs, which anyone can read; the addresses belong in the private papers
    repository and nowhere else.
    """
    known, unreadable, entries = legacy_counted()
    with _repo() as repo:
        roster = Roster(repo)
        moved = roster.fold_in_legacy()
        if moved:
            roster.save(f"Add {len(moved)} subscriber(s) carried over from DIGEST_RECIPIENTS")
        active = roster.active()
        print(
            f"[list] {entries} entr(ies) in the DIGEST_RECIPIENTS secret, "
            f"{len(known)} distinct address(es)"
        )
        if entries > len(known) + unreadable:
            print(
                f"[list] note: {entries - len(known) - unreadable} entr(ies) repeat an "
                "address already counted, so the list is shorter than the secret"
            )
        print(f"[list] {len(moved)} of them newly written to list/subscribers.txt")
        print(f"[list] {len(roster.subscribers)} on file, {len(roster.unsubscribed)} unsubscribed")
        print(f"[list] {len(active)} will receive the next digest")
        if unreadable:
            print(
                f"[list] WARNING: {unreadable} entr(ies) in the secret are not readable as "
                "an address, so nobody is being sent to them — check the secret by hand"
            )
        # Every digest already in the repository has, self-evidently, gone
        # out. Recording them stops an edit to an old one mailing it again —
        # the workflow fires on any push touching digest/*.md. A digest that
        # was committed but never successfully emailed would be written off
        # here; none is known, and a resend is one dispatch away.
        record = repo.dir / LIST_DIR / SENT
        known = _read_lines(record)
        stamps = {path.stem for path in DIGEST_DIR.glob("*.md")} if DIGEST_DIR.is_dir() else set()
        if stamps - known:
            _write_lines(
                record,
                known | stamps,
                "Digests already emailed, by the digest's own date.",
                "Managed by scripts/email_digest.py; delete a line to allow a resend.",
            )
            repo.commit(f"Record {len(stamps - known)} digest(s) as already emailed", paths=(LIST_DIR,))
            print(f"[list] {len(stamps - known)} past digest(s) recorded as sent")
        print(f"[list] {len(known | stamps)} digest(s) on the sent record")

        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as fh:
                fh.write(
                    "### Digest list\n\n"
                    f"- **{len(active)}** subscribers for the next digest\n"
                    f"- {len(roster.subscribers)} on `list/subscribers.txt`, "
                    f"{len(roster.unsubscribed)} unsubscribed\n"
                    f"- {len(known)} readable in the `DIGEST_RECIPIENTS` secret"
                    f"{f', **{unreadable} unreadable**' if unreadable else ''}\n\n"
                    "Addresses are deliberately not printed here; read them in the "
                    "private papers repository.\n"
                )
        return len(active)


def _gh(*args: str) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:2])} failed: {result.stderr.strip()[:200]}")
    return result.stdout


def pending() -> int:
    """Open one Issue per digest that should have been emailed and was not.

    The send runs on a Monday-morning cron now, and a cron GitHub never
    delivers is not a failure: alert-on-failure sees nothing and the digest
    simply does not arrive. This is what notices. It is called from the
    mailing-list poll, which runs several times a day.
    """
    late = [path.stem for path in unsent_digests() if overdue(path.stem)]
    if not late:
        print("[list] no digest is overdue")
        return 0
    try:
        existing = {
            issue["title"]
            for issue in json.loads(
                _gh("issue", "list", "--label", ALERT_LABEL, "--state", "open",
                    "--json", "title", "--limit", "50")
            )
        }
    except (RuntimeError, ValueError) as exc:
        print(f"[list] could not read open alerts ({type(exc).__name__}); not opening one")
        return 0
    opened = 0
    for stamp in late:
        title = f"Digest {stamp} has not been emailed"
        if title in existing:
            print(f"[list] {stamp} is overdue; its Issue is already open")
            continue
        body = (
            f"`digest/{stamp}.md` is in the repository but is not on the sent record in "
            f"the papers repository, and it is more than {OVERDUE_HOURS} hours old.\n\n"
            "The send runs on a Monday-morning schedule, and a scheduled run GitHub "
            "never delivers fails nothing — so this Issue is the only thing that would "
            "tell you.\n\n"
            "To send it: Actions -> email-digest -> Run workflow. Closing this Issue "
            "changes nothing; the next check opens it again until the digest goes out."
        )
        args = ["issue", "create", "--title", title, "--body", body, "--label", ALERT_LABEL]
        owner = os.environ.get("OWNER", "")
        if owner:
            args += ["--assignee", owner]
        try:
            print(_gh(*args).strip())
            opened += 1
        except RuntimeError as exc:
            print(f"[list] could not open an Issue for {stamp}: {exc}")
    return opened


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "sync"
    if command == "pending":
        try:
            pending()
        except Exception as exc:  # noqa: BLE001 - a watchdog must not fail the poll
            print(f"[list] WARNING: could not check for an overdue digest ({exc})")
        return
    if command != "sync":
        sys.exit(f"unknown command: {command}")
    sync()


if __name__ == "__main__":
    main()
