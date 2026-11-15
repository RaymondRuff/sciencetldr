"""Email a digest markdown file to the subscriber list via Gmail SMTP.

Reads DIGEST_FILE from env (path to the markdown file). If unset, picks the
newest file in digest/.

Who it goes to comes from mailing_list.recipients(): the list in the private
papers repository, plus anyone still on the DIGEST_RECIPIENTS secret, minus
anyone who has unsubscribed.

One message per subscriber, addressed to them. It was one blind-copied message
to everyone, which hid the list from the people on it but is also the shape a
spam filter scores hardest against — and the filtered message that matters
most is a new subscriber's welcome. Every message carries the footer saying
how to leave, and the List-Unsubscribe headers that let a client offer it as a
button.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import markdown as md

import mailing_list
import send_email

ROOT = Path(__file__).resolve().parent.parent
DIGEST_DIR = ROOT / "digest"


def main() -> None:
    digest_file = os.environ.get("DIGEST_FILE", "").strip()
    if digest_file:
        path = Path(digest_file)
        if not path.is_absolute():
            path = ROOT / path
    else:
        files = sorted(DIGEST_DIR.glob("*.md"))
        if not files:
            sys.exit("No digest files found in digest/")
        path = files[-1]

    if not path.exists():
        sys.exit(f"Digest file not found: {path}")

    # Has this one already gone out? The workflow fires on any push touching
    # digest/*.md, so an edit to a digest already sent would otherwise send it
    # again — which is exactly what happened on 2026-11-15, two minutes apart.
    stamp = path.stem
    force = os.environ.get("DIGEST_FORCE", "").strip().lower() == "true"
    if stamp in mailing_list.sent_digests():
        if not force:
            print(
                f"[email] {stamp} has already been emailed; not sending it again. "
                "Dispatch with force to override."
            )
            return
        print(f"[email] {stamp} has already been emailed; sending again because force is set")

    body_md = path.read_text(encoding="utf-8")
    body_html = md.markdown(body_md, extensions=["extra", "sane_lists"])
    today = datetime.now(tz=timezone.utc).date().isoformat()

    recipients = mailing_list.recipients()
    if not recipients:
        sys.exit("[email] nobody is subscribed; not sending")
    text_footer, html_footer = mailing_list.footer(send_email.SENDER)
    html = mailing_list.wrap_html(body_html + html_footer)
    print(f"[email] sending {path.name} to {len(recipients)} subscriber(s), one message each")
    # A connection per message. At five subscribers the handshakes cost less
    # than the plumbing to reuse one session would; past a few hundred this
    # wants rewriting to log in once.
    failed = 0
    for address in recipients:
        try:
            send_email.send(
                subject=f"Science TLDR Weekly Digest — {today}",
                body_text=body_md + text_footer,
                recipients=[address],
                body_html=html,
                unsubscribe=send_email.SENDER,
            )
        except Exception as exc:  # noqa: BLE001 - one bad address is not the send
            # The reason, never the exception itself: smtplib puts the refused
            # addresses in its string form and these logs are public.
            failed += 1
            print(f"[email]   one message failed: {send_email.failure_reason(exc)}")
    if failed == len(recipients):
        sys.exit("[email] every message failed; nobody received the digest")
    print(f"[email] {len(recipients) - failed} of {len(recipients)} sent")
    # Recorded after the send, not before: a run that dies halfway is worth
    # retrying by hand, and a retry that doubles up on the first few addresses
    # is better than a digest nobody receives. Nothing retries on its own.
    if not mailing_list.record_sent(stamp):
        print(f"[email] WARNING: could not record {stamp} as sent; a later push may resend it")


if __name__ == "__main__":
    main()
