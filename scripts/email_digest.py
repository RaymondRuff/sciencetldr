"""Email a digest markdown file to DIGEST_RECIPIENTS via Gmail SMTP.

Reads DIGEST_FILE from env (path to the markdown file). If unset, picks the
newest file in digest/.
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
    recipients = send_email.recipients_from_env()
    print(f"[email] sending {path.name} to {len(recipients)} recipient(s)")
    send_email.send(
        subject=f"Science TLDR Weekly Digest — {today}",
        body_text=body_md,
        recipients=recipients,
        body_html=f"<html><body style='font-family:system-ui,sans-serif;max-width:42rem'>{body_html}</body></html>",
    )


if __name__ == "__main__":
    main()
