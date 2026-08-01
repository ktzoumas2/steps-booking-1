"""Sending email — §8.1, §8.2.

One function sends every kind of mail in §8.1: the subject comes from §14.10,
the body from `templates/email/<kind>.txt`, and both are rendered in the
recipient's own `locale` (§10). Every send writes an `EmailLog` row (§4.6).

Session mails carry a calendar invite (§8.2), attached twice on purpose — as
`supervision.ics` **and** as an inline `text/calendar` part — because some
clients act only on one and some only on the other.

Locally the console backend prints the mail to the terminal, which is how you
sign in without a mail provider (§15). Choosing the production provider (§13,
question 7) changes the Django `EMAIL_BACKEND` setting and nothing in this file.
"""

from __future__ import annotations

import datetime as dt
from email.utils import make_msgid

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from supervision import calendar as ics
from supervision.catalog import t
from supervision.models import EmailKind, EmailLog, Settings, User
from supervision.pending_copy import calendar_link_label
from supervision.sending import sending_domain

# §8.1 — which mails carry an invite, and which METHOD it uses.
INVITE_METHOD = {
    EmailKind.REGISTRATION_CONFIRMED: ics.REQUEST,
    EmailKind.REGISTRATION_CANCELLED: ics.CANCEL,
    EmailKind.REMINDER: ics.REQUEST,
    EmailKind.SESSION_CANCELLED: ics.CANCEL,
    EmailKind.SESSION_CHANGED: ics.REQUEST,
    EmailKind.SESSION_CREATED: ics.REQUEST,
}


def _message_id() -> str:
    """A Message-ID stamped with our sending domain.

    Django otherwise builds one from `socket.getfqdn()`, which puts the sending
    machine's hostname into the header of every mail — and, on a laptop whose
    hostname does not resolve, blocks for the length of a DNS timeout the first
    time anything is sent. Our own address is both faster and the right domain.
    """
    return make_msgid(domain=sending_domain())


def was_sent_a_request(user: User, session) -> bool:
    """§8.3 — a CANCEL goes only to someone who was sent a REQUEST.

    `METHOD:CANCEL` for an event a calendar never had produces a confusing ghost
    entry in some clients, so this is a lookup `EmailLog` exists to answer.
    """
    return EmailLog.objects.filter(
        user=user,
        session=session,
        kind__in=[
            kind for kind, method in INVITE_METHOD.items() if method == ics.REQUEST
        ],
    ).exists()


def send(
    kind: str,
    *,
    user: User,
    now: dt.datetime,
    session=None,
    subject_params: dict | None = None,
    **context,
) -> EmailLog:
    """Send one mail to one person, in their language, and log that we did."""
    zoom_url = Settings.load().zoom_url if session is not None else ""
    method = INVITE_METHOD.get(kind) if session is not None else None

    # §8.3 — never a cancellation for an event this person's calendar never had.
    if method == ics.CANCEL and not was_sent_a_request(user, session):
        method = None

    subject = t(f"email.{kind}.subject", user.locale, **(subject_params or {}))
    body = render_to_string(
        f"email/{kind}.txt",
        {
            "locale": user.locale,
            "recipient": user,
            "session": session,
            # Read at send time, so changing the setting fixes every future mail
            # at once rather than only the ones sent afterwards (§4.2).
            "zoom_url": zoom_url,
            "calendar_links": (
                ics.add_to_calendar_links(session, user.locale)
                if session is not None
                else None
            ),
            "calendar_link_labels": {
                which: calendar_link_label(which, user.locale)
                for which in ("google", "outlook")
            },
            **context,
        },
    )

    message = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
        headers={"Message-ID": _message_id()},
    )

    if method is not None:
        invite = ics.build_ics(
            session, user, now=now, method=method, zoom_url=zoom_url
        )
        # Both forms, deliberately: some clients act only on the attachment and
        # some only on the inline part (§8.2).
        message.attach("supervision.ics", invite, "application/octet-stream")
        message.attach(
            "invite.ics",
            invite,
            f"text/calendar; method={method}; charset=UTF-8",
        )

    message.send()

    return EmailLog.objects.create(
        user=user, session=session, kind=kind, sent_at=now
    )
