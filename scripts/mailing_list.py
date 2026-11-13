"""Who gets the weekly digest, and how they say so themselves.

The list used to be the `DIGEST_RECIPIENTS` secret: a secret cannot be read
back, so adding one person meant retyping everyone. It now lives in the
private papers repository, as two plain files:

    list/subscribers.txt    one address per line; `#` starts a comment
    list/unsubscribed.txt   addresses that must never be sent to again

Recipients are **(the file plus the old secret) minus the unsubscribed**.
Three properties fall out of that, and they are the point:

  * the people already on the secret keep receiving the digest without
    anyone doing anything, including if the papers repository cannot be
    reached — the secret alone is enough to send;
  * their first send folds them into the file, so the list becomes readable
    and the secret can be deleted whenever it suits;
  * unsubscribing sticks. The suppression file beats both sources, so
    someone who came in on the secret can still leave, which a list built
    only from a secret could never offer.

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

import os
import re
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIGEST_DIR = ROOT / "digest"

LIST_DIR = "list"
SUBSCRIBERS = "subscribers.txt"
UNSUBSCRIBED = "unsubscribed.txt"

# Gmail accepts far more than this, but a single message carrying every
# address is both a bigger blast radius and closer to the per-message cap.
CHUNK = 90

ADDRESS_RE = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$")


def valid(address: str) -> bool:
    """Whether this is an address we are willing to store and send to."""
    return bool(ADDRESS_RE.match((address or "").strip()))


def normalise(address: str) -> str:
    return (address or "").strip().lower()


def legacy() -> set[str]:
    """Addresses still coming from the DIGEST_RECIPIENTS secret."""
    raw = os.environ.get("DIGEST_RECIPIENTS", "")
    return {normalise(a) for a in raw.split(",") if valid(a)}


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


def _repo():
    import paper_bundle

    return paper_bundle.PapersRepo()


def recipients() -> list[str]:
    """Who to send the digest to, folding the old secret into the file as we go.

    Falls back to the secret alone when the papers repository cannot be
    reached, so an outage there delays nothing and drops nobody.
    """
    try:
        with _repo() as repo:
            roster = Roster(repo)
            moved = roster.fold_in_legacy()
            if moved:
                print(f"[list] folding {len(moved)} address(es) from the secret into the file")
                roster.save(f"Add {len(moved)} subscriber(s) carried over from DIGEST_RECIPIENTS")
            active = roster.active()
            print(
                f"[list] {len(active)} subscriber(s): {len(roster.subscribers)} on file, "
                f"{len(roster.unsubscribed)} unsubscribed"
            )
            return active
    except Exception as exc:  # noqa: BLE001 - the digest must still go out
        fallback = sorted(legacy())
        print(f"[list] could not read the list ({exc})")
        if not fallback:
            raise
        print(f"[list] falling back to the {len(fallback)} address(es) in DIGEST_RECIPIENTS")
        return fallback


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

    Each answer is {uid, address, outcome, subject, body}. A request whose
    change could not be stored is left out, so its mail stays unlabelled and
    the next poll tries again rather than promising something untrue.
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
                    }
                )
            if answers:
                today = datetime.now(tz=timezone.utc).date().isoformat()
                roster.save(f"Mailing list: {len(answers)} change(s) on {today}")
    except Exception as exc:  # noqa: BLE001 - leave the mail for the next poll
        print(f"[list] could not record the change ({exc}); it will be retried")
        return []
    return answers


# Outcomes whose answer is the digest itself rather than a short note. Both
# count: someone who writes in twice is asking to be sent something, and
# treating them the same way makes a failed welcome safe to retry — the retry
# reads as "already", and still arrives as the digest.
WELCOME_OUTCOMES = ("added", "already")

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


def chunks(addresses: list[str], size: int = CHUNK) -> list[list[str]]:
    return [addresses[i : i + size] for i in range(0, len(addresses), size)] or [[]]
