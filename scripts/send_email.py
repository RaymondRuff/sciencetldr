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


def failure_reason(exc: BaseException) -> str:
    """Why a send failed, in a form safe for a public log.

    smtplib puts the addresses it could not deliver to in the exception's own
    string form — `{'someone@example.com': (550, b'...')}` — and this
    repository's Actions logs are world-readable. GitHub masks the whole
    DIGEST_RECIPIENTS secret, not one address out of it, so printing the
    exception was printing a subscriber. The class name and an SMTP code say
    as much as anyone needs to act; the counts say the rest.
    """
    name = type(exc).__name__
    refused = getattr(exc, "recipients", None)
    if isinstance(refused, dict):
        return f"{name} ({len(refused)} recipient(s) refused)"
    code = getattr(exc, "smtp_code", None)
    return f"{name} (SMTP {code})" if isinstance(code, int) else name
