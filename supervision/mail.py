"""Sending email — §8.1.

One function sends every kind of mail in §8.1: the subject comes from §14.10, the
body from `templates/email/<kind>.txt`, and both are rendered in the recipient's
own `locale` (§10). Every send writes an `EmailLog` row (§4.6).

Locally the console backend prints the mail to the terminal, which is how you
sign in without a mail provider (§15). Choosing the production provider (§13,
question 7) changes the Django `EMAIL_BACKEND` setting and nothing in this file.

Calendar invites (§8.2) and the scheduled `reminder` (§8.3) attach to this in a
later slice; both need the Session model, and the reminder additionally needs the
scheduling port that stands in for the provider.
"""

from __future__ import annotations

import datetime as dt
from email.utils import make_msgid, parseaddr

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from supervision.catalog import t
from supervision.models import EmailLog, User


def _message_id() -> str:
    """A Message-ID stamped with our sending domain.

    Django otherwise builds one from `socket.getfqdn()`, which puts the sending
    machine's hostname into the header of every mail — and, on a laptop whose
    hostname does not resolve, blocks for the length of a DNS timeout the first
    time anything is sent. Our own address is both faster and the right domain.
    """
    _, address = parseaddr(settings.DEFAULT_FROM_EMAIL)
    _, _, domain = address.rpartition("@")
    return make_msgid(domain=domain or "localhost")


def send(
    kind: str,
    *,
    user: User,
    now: dt.datetime,
    subject_params: dict | None = None,
    **context,
) -> EmailLog:
    """Send one mail to one person, in their language, and log that we did."""
    subject = t(f"email.{kind}.subject", user.locale, **(subject_params or {}))
    body = render_to_string(
        f"email/{kind}.txt",
        {"locale": user.locale, "recipient": user, **context},
    )

    message = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
        headers={"Message-ID": _message_id()},
    )
    message.send()

    return EmailLog.objects.create(user=user, kind=kind, sent_at=now)
