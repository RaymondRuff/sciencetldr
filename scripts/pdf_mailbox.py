"""Collect paper PDFs by email, so paywalled PDFs never enter this public repo.

When no full text is reachable for a pending Issue, the generator emails a
request to PDF_REQUEST_TO with a subject tagged `[Science TLDR #NN]`. Replying
with the PDF attached is the whole hand-off: this module finds those replies in
the podcast's Gmail inbox over IMAP, saves the PDF to a scratch directory on the
runner, and labels the message once it has been used.

The mailbox doubles as the PDF store. A reply is labelled `tldr-processed` only
after its episode is attempted, so a run that dies midway leaves the reply to be
picked up again by the next poll.

Only PDFs from allow-listed senders are accepted, and only when Gmail's own
Authentication-Results show the sender was not spoofed — otherwise anyone who
knows the podcast address could have a document narrated and published.

Deliberately standard-library only: the workflow runs `check` before installing
dependencies, so a poll that finds nothing costs seconds.

It makes a second pass for **one-off requests**: an email from the owner whose
subject starts with "one-off", carrying a DOI in the body or a PDF attached, or
both. Those become their own `podcast-pending` Issue (see add_paper.py) and get
one reply saying so. Only the owner's own address may commission an episode —
replying to a request supplies a paper the show already chose, while a one-off
chooses the paper, so PDF_SENDER_ALLOWLIST does not grant it.

Usage:
  python scripts/pdf_mailbox.py check    # save waiting PDFs to $RUNNER_TEMP/tldr-pdfs
                                         # (or $PDF_DROP_DIR); writes found=true|false
                                         # to $GITHUB_OUTPUT
"""
from __future__ import annotations

import email
import email.policy
import imaplib
import json
import os
import re
import sys
from email.message import EmailMessage
from email.utils import parseaddr
from html import unescape
from pathlib import Path

import send_email

ACCOUNT = send_email.SENDER
IMAP_HOST = "imap.gmail.com"
SUBJECT_TAG = "Science TLDR #"
SUBJECT_RE = re.compile(r"\[Science TLDR #(\d+)\]")
LABEL_PROCESSED = "tldr-processed"
LABEL_REJECTED = "tldr-rejected"
MANIFEST = "manifest.json"
MAX_AGE_DAYS = 60

# A one-off request: a paper the owner wants an episode on, emailed in rather
# than picked by the Monday digest or the Friday crawl. The subject starts with
# "one-off"; everything after it is a note. A request older than this is stale.
ONEOFF_MANIFEST = "one-offs.json"
ONEOFF_MAX_AGE_DAYS = 14
ONEOFF_RE = re.compile(
    r"^(?:(?:re|fwd?|fw)\s*:\s*)*\s*one[-\s]?off\b[\s:.\-\u2013\u2014]*(?P<note>.*)",
    re.IGNORECASE | re.DOTALL,
)
DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)


def drop_dir() -> Path:
    base = os.environ.get("PDF_DROP_DIR") or os.path.join(
        os.environ.get("RUNNER_TEMP", "/tmp"), "tldr-pdfs"
    )
    return Path(base)


def owner_address() -> str:
    """The one address that may commission an episode.

    Deliberately narrower than `allowed_senders()`. Replying to a request only
    supplies a paper the show already chose; a one-off *chooses the paper*, so
    PDF_SENDER_ALLOWLIST does not grant it.
    """
    raw = os.environ.get("PDF_REQUEST_TO", "").split(",")[0]
    return parseaddr(raw)[1].strip().lower()


def one_off_note(subject: str) -> str | None:
    """The note after "one-off" in a subject, or None if it is not a request."""
    match = ONEOFF_RE.match(subject.strip())
    if match is None:
        return None
    return re.sub(r"\s+", " ", match.group("note")).strip()


def dois_in(text: str) -> list[str]:
    """Every distinct DOI in some text, in the order they appear."""
    seen: set[str] = set()
    found: list[str] = []
    for match in DOI_RE.finditer(text or ""):
        doi = match.group(0).rstrip(".,;:)>]}\"'")
        if doi.lower() not in seen:
            seen.add(doi.lower())
            found.append(doi)
    return found


URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
FIELD_RE = re.compile(
    r"^\s*(title|url|link|publisher|organisation|organization|org)\s*:\s*(\S.*?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def urls_in(text: str) -> list[str]:
    """Every distinct link in some text, in the order they appear."""
    seen: set[str] = set()
    found: list[str] = []
    for match in URL_RE.finditer(text or ""):
        url = match.group(0).rstrip(".,;:)>]}\"'")
        if url.lower() not in seen:
            seen.add(url.lower())
            found.append(url)
    return found


def fields_in(text: str) -> dict[str, str]:
    """"Title: ...", "URL: ...", "Publisher: ..." lines, for a paper with no DOI.

    The first of each wins, so a quoted reply underneath cannot override what
    the writer typed at the top.
    """
    fields: dict[str, str] = {}
    for match in FIELD_RE.finditer(text or ""):
        key = match.group(1).lower()
        fields.setdefault(key, match.group(2).strip())
    return fields


def allowed_senders() -> set[str]:
    raw = ",".join(
        filter(
            None,
            [
                os.environ.get("PDF_REQUEST_TO", ""),
                os.environ.get("PDF_SENDER_ALLOWLIST", ""),
                ACCOUNT,
            ],
        )
    )
    return {a.strip().lower() for a in raw.split(",") if a.strip()}


# --------------------------------------------------------------------------- #
# Sending the request
# --------------------------------------------------------------------------- #


def request(
    issue_number: int,
    *,
    title: str,
    doi: str,
    journal: str = "",
    deadline: str = "",
    runner_up: str = "",
) -> bool:
    """Email a request for the PDF. Returns False if no recipient is configured.

    With `deadline` this is a PDF window (see pdf_window.py): the email says
    when the window closes and what stands in if nothing arrives, so the
    answer can be "the runner-up is fine" without opening anything.

    Two routes, because a reply from a phone is the easiest thing in the world
    until the paper is bigger than Gmail's 25 MB attachment limit. The upload
    link is no larger a ceiling — GitHub's browser upload stops at 25 MiB too
    — but it suits a desktop, and the shrink note covers the rare paper that
    clears both.
    """
    to = os.environ.get("PDF_REQUEST_TO", "").strip()
    if not to or not os.environ.get("GMAIL_APP_PASSWORD"):
        print("  [mailbox] PDF_REQUEST_TO or GMAIL_APP_PASSWORD unset; not emailing")
        return False
    link = f"https://doi.org/{doi}" if doi else "(no DOI on the Issue)"
    repo = os.environ.get("GITHUB_REPOSITORY", "RaymondRuff/sciencetldr")
    papers_repo = os.environ.get("PAPERS_REPO", "RaymondRuff/sciencetldr-papers")
    upload = f"https://github.com/{papers_repo}/upload/main/papers"
    if deadline:
        fallback = (
            f"If it hasn't arrived by then, this runner-up takes the slot instead — its full\n"
            f"text is open, so if it is good enough there is nothing to do:\n\n  {runner_up}\n"
            if runner_up
            else "If it hasn't arrived by then, the slot is skipped: no paper of the same\n"
            "standard is open, and a weaker one is not used instead.\n"
        )
        opening = (
            f"This week's top pick has no open-access full text. It is wanted by\n"
            f"{deadline}.\n\n"
            f"  {title}\n  {journal}\n  {link}\n\n{fallback}\n"
            "Either way the Issue stays open, and a PDF sent later still becomes an episode.\n"
        )
    else:
        opening = (
            "No open-access full text could be found for this paper, so its episode is "
            f"waiting on a PDF.\n\n  {title}\n  {journal}\n  {link}\n"
        )
    body = f"""{opening}
Either route works — whichever is to hand:

  1. Reply to this email with the PDF attached.

  2. Drop it here, which opens straight into the right folder:
     {upload}
     Name it issue-{issue_number}.pdf if that's easy; a filename containing
     the DOI is recognised too.

The next sweep stages it for the writer, which writes the script the
following morning; once the checker has been through it, it publishes the same
day without needing anything more from you. This is the only email you will
get about this paper.

Over 25 MB? Both routes stop there. Shrink it first — this downsamples the
figures, which stay legible, and usually cuts a figure-heavy paper by most of
its size:

  python scripts/paper_bundle.py shrink --pdf big.pdf --out small.pdf

The PDF is never committed to the public repository. Whichever route it
arrives by, it is reduced to text plus downsampled figures in the private
papers repository, and the original is deleted.

Issue: https://github.com/{repo}/issues/{issue_number}
"""
    send_email.send(
        subject=(
            f"[{SUBJECT_TAG}{issue_number}] PDF wanted by "
            f"{deadline.split(' on ')[0] if deadline else ''}: {title[:80]}"
            if deadline
            else f"[{SUBJECT_TAG}{issue_number}] PDF needed: {title[:90]}"
        ),
        body_text=body,
        recipients=[to],
    )
    print(f"  [mailbox] emailed PDF request for #{issue_number}")
    return True


# --------------------------------------------------------------------------- #
# Collecting replies
# --------------------------------------------------------------------------- #


def _all_mail(imap: imaplib.IMAP4_SSL) -> str:
    """The All Mail folder, whatever this account's locale calls it."""
    status, boxes = imap.list()
    if status == "OK":
        for raw in boxes or []:
            line = raw.decode(errors="replace")
            if "\\All" in line:
                return line.rsplit(' "/" ', 1)[-1].strip()
    return "INBOX"


def _authenticated(msg: EmailMessage, sender: str) -> bool:
    """Trust Gmail's own verdict on whether the From address was spoofed."""
    domain = sender.rsplit("@", 1)[-1]
    results = [str(h).lower() for h in msg.get_all("Authentication-Results", [])]
    if not results:
        # Gmail stamps every message arriving from outside; a message with no
        # results header can only have originated inside the account itself.
        return sender == ACCOUNT
    for result in results:
        if "dmarc=pass" in result:
            return True
        if "dkim=pass" in result and (
            f"header.i=@{domain}" in result or f"header.d={domain}" in result
        ):
            return True
    return False


def _first_pdf(msg: EmailMessage) -> bytes | None:
    for part in msg.iter_attachments():
        name = (part.get_filename() or "").lower()
        if part.get_content_type() == "application/pdf" or name.endswith(".pdf"):
            data = part.get_content()
            if isinstance(data, bytes) and data[:5] == b"%PDF-":
                return data
    return None


def _label(imap: imaplib.IMAP4_SSL, uid: bytes, label: str) -> None:
    imap.uid("STORE", uid, "+X-GM-LABELS", f"({label})")


def _search(imap: imaplib.IMAP4_SSL, query: str) -> list[bytes]:
    """Gmail search syntax, sent as one IMAP quoted string — so no inner quotes."""
    status, data = imap.uid("SEARCH", "X-GM-RAW", f'"{query}"')
    return data[0].split() if status == "OK" and data and data[0] else []


def _fetch(imap: imaplib.IMAP4_SSL, uid: bytes, what: str) -> EmailMessage | None:
    status, fetched = imap.uid("FETCH", uid, what)
    if status != "OK" or not fetched or not isinstance(fetched[0], tuple):
        return None
    return email.message_from_bytes(fetched[0][1], policy=email.policy.default)


def _body_text(msg: EmailMessage) -> str:
    """The message body as plain text, for finding a DOI in it."""
    try:
        part = msg.get_body(preferencelist=("plain", "html"))
        if part is None:
            return ""
        text = part.get_content()
    except Exception:  # noqa: BLE001 - an odd body is not worth failing over
        return ""
    if not isinstance(text, str):
        return ""
    if part.get_content_type() == "text/html":
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
    return unescape(text)


def collect() -> tuple[dict[int, dict], list[dict]]:
    """Read the mailbox once. Returns (replies, one-off requests).

    Two passes, one session: PDFs replied to a numbered request, then one-off
    requests from the owner. Both write a manifest the sweep reads later, so
    this stays standard-library only and a quiet poll costs seconds.
    """
    password = os.environ.get("GMAIL_APP_PASSWORD")
    if not password:
        print("[mailbox] GMAIL_APP_PASSWORD unset; skipping mailbox")
        return {}
    allowed = allowed_senders()
    out_dir = drop_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    found: dict[int, dict] = {}
    one_offs: list[dict] = []
    imap = imaplib.IMAP4_SSL(IMAP_HOST)
    try:
        imap.login(ACCOUNT, password)
        folder = _all_mail(imap)
        imap.select(folder)
        # Gmail search syntax, sent as one IMAP quoted string — so no inner
        # quotes. It narrows candidates; SUBJECT_RE below does exact matching.
        query = (
            "subject:(Science TLDR) has:attachment filename:pdf "
            f"-label:{LABEL_PROCESSED} -label:{LABEL_REJECTED} "
            f"newer_than:{MAX_AGE_DAYS}d"
        )
        uids = _search(imap, query)
        print(f"[mailbox] {len(uids)} candidate repl(ies) in {folder}")

        for uid in uids:
            msg = _fetch(imap, uid, "(BODY.PEEK[])")
            if msg is None:
                continue
            subject = str(msg.get("Subject", ""))
            sender = parseaddr(str(msg.get("From", "")))[1].lower()
            match = SUBJECT_RE.search(subject)
            if not match:
                continue
            issue = int(match.group(1))

            if sender not in allowed:
                print(f"[mailbox] #{issue}: rejecting PDF from non-allow-listed sender")
                _label(imap, uid, LABEL_REJECTED)
                continue
            if not _authenticated(msg, sender):
                print(f"[mailbox] #{issue}: rejecting — sender failed authentication")
                _label(imap, uid, LABEL_REJECTED)
                continue
            pdf = _first_pdf(msg)
            if pdf is None:
                print(f"[mailbox] #{issue}: reply has no readable PDF attachment")
                _label(imap, uid, LABEL_REJECTED)
                continue

            # A later reply for the same Issue supersedes an earlier one.
            path = out_dir / f"issue-{issue}.pdf"
            path.write_bytes(pdf)
            found[issue] = {"uid": uid.decode(), "path": str(path)}
            print(f"[mailbox] #{issue}: PDF received ({len(pdf) / 1e6:.1f} MB)")

        one_offs = _collect_one_offs(imap, out_dir)
    finally:
        try:
            imap.logout()
        except Exception:  # noqa: BLE001 - logout failure is irrelevant
            pass

    (out_dir / MANIFEST).write_text(json.dumps(found), encoding="utf-8")
    (out_dir / ONEOFF_MANIFEST).write_text(json.dumps(one_offs), encoding="utf-8")
    return found, one_offs


def _collect_one_offs(imap: imaplib.IMAP4_SSL, out_dir: Path) -> list[dict]:
    """One-off requests from the owner: {uid, subject, note, dois, pdf}.

    The search is by sender and freshness only, because Gmail's query parser
    reads the hyphen in "one-off" as an exclusion. Subjects are matched here
    instead, on headers alone, so the body of an unrelated message is never
    fetched.
    """
    owner = owner_address()
    if not owner:
        print("[mailbox] PDF_REQUEST_TO unset; not accepting one-off requests")
        return []
    query = (
        f"from:{owner} -label:{LABEL_PROCESSED} -label:{LABEL_REJECTED} "
        f"newer_than:{ONEOFF_MAX_AGE_DAYS}d"
    )
    found: list[dict] = []
    for uid in _search(imap, query):
        header = _fetch(imap, uid, "(BODY.PEEK[HEADER])")
        if header is None:
            continue
        subject = str(header.get("Subject", ""))
        if SUBJECT_RE.search(subject):
            continue  # a reply to a numbered request; the first pass owns it
        note = one_off_note(subject)
        if note is None:
            continue
        msg = _fetch(imap, uid, "(BODY.PEEK[])")
        if msg is None:
            continue
        sender = parseaddr(str(msg.get("From", "")))[1].lower()
        # A From line can be forged; Gmail's own verdict on it cannot.
        if sender != owner or not _authenticated(msg, sender):
            print("[mailbox] one-off: rejecting — not the owner, or failed authentication")
            _label(imap, uid, LABEL_REJECTED)
            continue
        body = _body_text(msg)
        entry = {
            "uid": uid.decode(),
            "subject": subject,
            "note": note,
            "dois": dois_in(body),
            "urls": urls_in(body),
            "fields": fields_in(body),
            "pdf": None,
        }
        pdf = _first_pdf(msg)
        if pdf is not None:
            path = out_dir / f"one-off-{uid.decode()}.pdf"
            path.write_bytes(pdf)
            entry["pdf"] = str(path)
        found.append(entry)
        print(
            f"[mailbox] one-off request {subject[:60]!r}: "
            f"{len(entry['dois'])} DOI(s) in the body, "
            f"{'PDF attached' if pdf else 'no PDF'}"
        )
    return found


def record_reply(issue_number: int, uid: str, path: Path) -> None:
    """Treat a supplied PDF as a reply to this Issue.

    A one-off arrives before its Issue exists, so it cannot be saved under the
    Issue's name. Once the Issue is open, recording it here makes it
    indistinguishable from a PDF replied to a request: the sweep bundles it,
    and the email is consumed only when the PDF can no longer be lost.
    """
    manifest = drop_dir() / MANIFEST
    current = json.loads(manifest.read_text()) if manifest.exists() else {}
    current[str(issue_number)] = {"uid": uid, "path": str(path)}
    manifest.write_text(json.dumps(current), encoding="utf-8")


def one_offs_received() -> list[dict]:
    """The one-off manifest written by collect() earlier in this run."""
    manifest = drop_dir() / ONEOFF_MANIFEST
    if not manifest.exists():
        return []
    return json.loads(manifest.read_text())


def received() -> dict[int, dict]:
    """The manifest written by collect() earlier in this run, if any."""
    manifest = drop_dir() / MANIFEST
    if not manifest.exists():
        return {}
    return {int(k): v for k, v in json.loads(manifest.read_text()).items()}


def mark_uid(uid: str, label: str = LABEL_PROCESSED) -> bool:
    """Label one message so later polls ignore it."""
    password = os.environ.get("GMAIL_APP_PASSWORD")
    if not uid or not password:
        return False
    imap = imaplib.IMAP4_SSL(IMAP_HOST)
    try:
        imap.login(ACCOUNT, password)
        imap.select(_all_mail(imap))
        _label(imap, uid.encode(), label)
        return True
    finally:
        try:
            imap.logout()
        except Exception:  # noqa: BLE001
            pass


def mark_processed(issue_number: int) -> None:
    """Label a used reply so later polls ignore it."""
    entry = received().get(issue_number)
    if entry and mark_uid(entry["uid"]):
        print(f"  [mailbox] #{issue_number}: reply marked {LABEL_PROCESSED}")


def answer(subject: str, body: str) -> bool:
    """Write back to the owner about a one-off request.

    One message per request. When the request became an Issue the subject
    carries that Issue's tag, so replying to it with the PDF attached lands in
    the ordinary reply pass — the confirmation doubles as the PDF thread.
    """
    owner = owner_address()
    if not owner or not os.environ.get("GMAIL_APP_PASSWORD"):
        print("[one-off] no owner address or no mail password; not answering")
        return False
    try:
        send_email.send(subject=subject[:200], body_text=body, recipients=[owner])
    except Exception as exc:  # noqa: BLE001 - the Issue is the record; mail is a courtesy
        print(f"[one-off] could not answer the request: {exc}")
        return False
    print(f"[one-off] answered: {subject[:70]}")
    return True


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "check"
    if command != "check":
        sys.exit(f"unknown command: {command}")
    replies, one_offs = collect()
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as fh:
            fh.write(f"found={'true' if replies or one_offs else 'false'}\n")


if __name__ == "__main__":
    main()
