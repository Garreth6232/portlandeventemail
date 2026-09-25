"""Sends the digest from a Gmail account over SMTP.

Gmail needs an app password for this (a 16-character password made for
one app, separate from the normal one); see the README. Each recipient gets
their own copy, so nobody sees the others' addresses and replies come back
only to the sender. Header and footer images travel inside the email as
inline attachments (see mailer/banners.py).
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from typing import Iterable

from mailer.banners import Banner

TIMEOUT = 30

log = logging.getLogger(__name__)


def build_message(
    sender: str,
    from_name: str,
    to: str,
    subject: str,
    html: str,
    text: str,
    banners: Iterable[Banner] = (),
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = formataddr((from_name, sender))
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=sender.split("@")[-1])

    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    html_part = msg.get_payload()[1]
    for banner in banners:
        html_part.add_related(
            banner.path.read_bytes(),
            maintype="image",
            subtype="png",
            cid=f"<{banner.content_id}>",
            filename=banner.path.name,
        )
    return msg


def send(host: str, port: int, user: str, password: str, messages: list[EmailMessage]) -> int:
    """Send each message and return how many went out. One address Gmail
    turns away is logged and skipped, so it doesn't fail the run (a failed
    run gets retried, and everyone else would get the email twice). Login
    and connection errors still raise."""
    context = ssl.create_default_context()
    delivered = 0
    with smtplib.SMTP_SSL(host, port, context=context, timeout=TIMEOUT) as server:
        # Google shows app passwords in groups of four; the spaces aren't part of it.
        server.login(user, password.replace(" ", ""))
        for msg in messages:
            try:
                server.send_message(msg)
            except (smtplib.SMTPRecipientsRefused, smtplib.SMTPDataError) as exc:
                log.warning("Couldn't send to %s: %s", msg["To"], exc)
                continue
            delivered += 1
    log.info("Sent to %d of %d recipients", delivered, len(messages))
    if messages and not delivered:
        raise RuntimeError("Gmail refused every recipient; nothing was sent.")
    return delivered
