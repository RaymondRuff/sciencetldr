"""Send mail from sciencetldrpod@gmail.com via Gmail SMTP + app password."""
from __future__ import annotations

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SENDER = "sciencetldrpod@gmail.com"


def send(subject: str, body_text: str, recipients: list[str], body_html: str | None = None) -> None:
    password = os.environ["GMAIL_APP_PASSWORD"]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SENDER
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", "utf-8"))
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as server:
        server.login(SENDER, password)
        server.sendmail(SENDER, recipients, msg.as_string())


def recipients_from_env() -> list[str]:
    raw = os.environ.get("DIGEST_RECIPIENTS", "").strip()
    if not raw:
        raise RuntimeError("DIGEST_RECIPIENTS env var is empty")
    return [r.strip() for r in raw.split(",") if r.strip()]
