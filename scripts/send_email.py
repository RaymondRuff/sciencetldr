"""Send mail from sciencetldrpod@gmail.com via Gmail SMTP + app password."""
from __future__ import annotations

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SENDER = "sciencetldrpod@gmail.com"


def send(
    subject: str,
    body_text: str,
    recipients: list[str],
    body_html: str | None = None,
    *,
    bcc: bool = False,
) -> None:
    """Send one message. With `bcc`, recipients cannot see each other.

    Delivery is decided by the envelope — sendmail's recipient list — not by
    the headers, so blind copying is simply a matter of not naming anyone in
    a header. Before this, the digest put every subscriber in `To`, which
    showed the whole list to everyone on it.
    """
    password = os.environ["GMAIL_APP_PASSWORD"]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SENDER
    msg["To"] = SENDER if bcc else ", ".join(recipients)
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", "utf-8"))
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as server:
        server.login(SENDER, password)
        server.sendmail(SENDER, recipients, msg.as_string())


def recipients_from_env() -> list[str]:
    """The DIGEST_RECIPIENTS secret, as a list.

    Superseded by mailing_list.recipients(), which folds this in and lets
    people subscribe and unsubscribe themselves. Kept because it is still the
    fallback when the papers repository cannot be read.
    """
    raw = os.environ.get("DIGEST_RECIPIENTS", "").strip()
    if not raw:
        raise RuntimeError("DIGEST_RECIPIENTS env var is empty")
    return [r.strip() for r in raw.split(",") if r.strip()]
