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


def drop_dir() -> Path:
    base = os.environ.get("PDF_DROP_DIR") or os.path.join(
        os.environ.get("RUNNER_TEMP", "/tmp"), "tldr-pdfs"
    )
    return Path(base)


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


def request(issue_number: int, *, title: str, doi: str, journal: str = "") -> bool:
    """Email a request for the PDF. Returns False if no recipient is configured."""
    to = os.environ.get("PDF_REQUEST_TO", "").strip()
    if not to or not os.environ.get("GMAIL_APP_PASSWORD"):
        print("  [mailbox] PDF_REQUEST_TO or GMAIL_APP_PASSWORD unset; not emailing")
        return False
    link = f"https://doi.org/{doi}" if doi else "(no DOI on the Issue)"
    repo = os.environ.get("GITHUB_REPOSITORY", "RaymondRuff/sciencetldr")
    body = f"""No open-access full text could be found for this paper, so its episode is waiting on a PDF.

  {title}
  {journal}
  {link}

Reply to this email with the PDF attached. That's all — the episode generates
automatically within about half an hour and a draft PR appears for review.

The PDF stays in this mailbox; it is never committed to the public repository.

Issue: https://github.com/{repo}/issues/{issue_number}
"""
    send_email.send(
        subject=f"[{SUBJECT_TAG}{issue_number}] PDF needed: {title[:90]}",
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


def collect() -> dict[int, dict]:
    """Save waiting PDFs to the drop directory; return {issue: {uid, path}}."""
    password = os.environ.get("GMAIL_APP_PASSWORD")
    if not password:
        print("[mailbox] GMAIL_APP_PASSWORD unset; skipping mailbox")
        return {}
    allowed = allowed_senders()
    out_dir = drop_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    found: dict[int, dict] = {}
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
        status, data = imap.uid("SEARCH", "X-GM-RAW", f'"{query}"')
        uids = data[0].split() if status == "OK" and data and data[0] else []
        print(f"[mailbox] {len(uids)} candidate repl(ies) in {folder}")

        for uid in uids:
            status, fetched = imap.uid("FETCH", uid, "(BODY.PEEK[])")
            if status != "OK" or not fetched or not isinstance(fetched[0], tuple):
                continue
            msg = email.message_from_bytes(fetched[0][1], policy=email.policy.default)
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
    finally:
        try:
            imap.logout()
        except Exception:  # noqa: BLE001 - logout failure is irrelevant
            pass

    (out_dir / MANIFEST).write_text(json.dumps(found), encoding="utf-8")
    return found


def received() -> dict[int, dict]:
    """The manifest written by collect() earlier in this run, if any."""
    manifest = drop_dir() / MANIFEST
    if not manifest.exists():
        return {}
    return {int(k): v for k, v in json.loads(manifest.read_text()).items()}


def mark_processed(issue_number: int) -> None:
    """Label a used reply so later polls ignore it."""
    entry = received().get(issue_number)
    password = os.environ.get("GMAIL_APP_PASSWORD")
    if not entry or not password:
        return
    imap = imaplib.IMAP4_SSL(IMAP_HOST)
    try:
        imap.login(ACCOUNT, password)
        imap.select(_all_mail(imap))
        _label(imap, entry["uid"].encode(), LABEL_PROCESSED)
        print(f"  [mailbox] #{issue_number}: reply marked {LABEL_PROCESSED}")
    finally:
        try:
            imap.logout()
        except Exception:  # noqa: BLE001
            pass


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "check"
    if command != "check":
        sys.exit(f"unknown command: {command}")
    found = collect()
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as fh:
            fh.write(f"found={'true' if found else 'false'}\n")


if __name__ == "__main__":
    main()
