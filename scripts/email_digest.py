"""Email a digest markdown file to the subscriber list via Gmail SMTP.

Reads DIGEST_FILE from env (path to the markdown file). If unset, picks the
newest file in digest/.

Who it goes to comes from mailing_list.recipients(): the list in the private
papers repository, plus anyone still on the DIGEST_RECIPIENTS secret, minus
anyone who has unsubscribed. Every send is blind-copied — before this, each
subscriber could read the whole list in their own copy — and carries a footer
saying how to leave.
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

    body_md = path.read_text(encoding="utf-8")
    body_html = md.markdown(body_md, extensions=["extra", "sane_lists"])
    today = datetime.now(tz=timezone.utc).date().isoformat()

    recipients = mailing_list.recipients()
    if not recipients:
        sys.exit("[email] nobody is subscribed; not sending")
    text_footer, html_footer = mailing_list.footer(send_email.SENDER)
    batches = mailing_list.chunks(recipients)
    print(
        f"[email] sending {path.name} to {len(recipients)} subscriber(s) "
        f"in {len(batches)} blind-copied message(s)"
    )
    for number, batch in enumerate(batches, start=1):
        send_email.send(
            subject=f"Science TLDR Weekly Digest — {today}",
            body_text=body_md + text_footer,
            recipients=batch,
            body_html=(
                "<html><body style='font-family:system-ui,sans-serif;max-width:42rem'>"
                f"{body_html}{html_footer}</body></html>"
            ),
            bcc=True,
        )
        print(f"[email]   batch {number}/{len(batches)}: {len(batch)} address(es)")


if __name__ == "__main__":
    main()
