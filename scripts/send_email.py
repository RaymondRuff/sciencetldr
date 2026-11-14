"""Send mail from sciencetldrpod@gmail.com via Gmail SMTP + app password."""
from __future__ import annotations

import os
import re
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SENDER = "sciencetldrpod@gmail.com"

# A Message-ID comes off a message somebody else wrote, so its shape is
# checked before it goes anywhere near a header: a newline in there would let
# the sender add headers of their own. A reply that does not thread is no loss.
MESSAGE_ID_RE = re.compile(r"^<[^\s<>]+@[^\s<>]+>$")


def send(
    subject: str,
    body_text: str,
    recipients: list[str],
    body_html: str | None = None,
    *,
    unsubscribe: str | None = None,
    in_reply_to: str | None = None,
) -> int:
    """Send one message, to everyone in `recipients`. Returns how many bounced.

    `unsubscribe` adds the `List-Unsubscribe` pair, so a mail client can offer
    leaving as a button; the body says how to leave as well, for the clients
    that do not. Both belong on anything list-shaped — the digest and the
    welcome — and on nothing else.

    smtplib answers with the recipients the server would not take, and that
    answer used to be dropped, so a dead address was never noticed. The count
    is printed, never the addresses: these Actions logs are public.
    """
    password = os.environ["GMAIL_APP_PASSWORD"]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SENDER
    msg["To"] = ", ".join(recipients)
    if unsubscribe:
        msg["List-Unsubscribe"] = f"<mailto:{unsubscribe}?subject=unsubscribe>"
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    if in_reply_to and MESSAGE_ID_RE.match(in_reply_to.strip()):
        msg["In-Reply-To"] = in_reply_to.strip()
        msg["References"] = in_reply_to.strip()
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", "utf-8"))
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as server:
        server.login(SENDER, password)
        refused = server.sendmail(SENDER, recipients, msg.as_string()) or {}
    if refused:
        print(f"[mail] {len(refused)} of {len(recipients)} recipient(s) refused by the server")
    return len(refused)


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
