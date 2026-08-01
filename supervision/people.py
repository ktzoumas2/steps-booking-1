"""Adding and deactivating people — §4.1, §7.3 A3.

Deactivation is where this file earns its keep. Preserving history is not enough
(§4.1), and the two roles need opposite treatment:

* **a participant** has their upcoming registrations cancelled — seats free
  immediately, and they get the usual mail and cancellation invite;
* **a supervisor is blocked** while they hold upcoming offered sessions, and the
  message names those sessions so the admin can cancel or reassign them first.

D25 explains why those are the only two options that surprise nobody: leaving a
supervisor's sessions offered strands participants with someone who cannot sign
in, and auto-cancelling them fires mail the admin never chose to send. Making
them choose is the honest third path.

**Reactivating restores nothing.** Cancelled registrations and sessions stay
cancelled; the person signs up again like anyone else.
"""

from __future__ import annotations

import datetime as dt

from supervision import mail, registrations, sessions as session_service
from supervision.formatting import format_datetime
from supervision.models import EmailKind, Role, Session, SessionStatus, User


class DeactivationBlocked(Exception):
    """Carries the §14 key and the sessions that have to be dealt with first."""

    def __init__(self, copy_key: str, sessions: list[Session]):
        super().__init__(copy_key)
        self.copy_key = copy_key
        self.sessions = sessions


def upcoming_sessions_of(supervisor: User, now: dt.datetime) -> list[Session]:
    return [
        session
        for session in Session.objects.filter(
            supervisor=supervisor, status=SessionStatus.OFFERED
        )
        if session.is_upcoming(now)
    ]


def add_person(
    *,
    first_name: str,
    last_name: str,
    email: str,
    role: str,
    now: dt.datetime,
    send_invitation: bool = False,
    link: str = "",
) -> User:
    """§7.3 A3 — every account originates here, bar the install-time admin.

    Adding someone sends no email **by default** (D10): the admin usually tells
    them in person, and there is no welcome flow to get lost in. The optional
    invitation exists because without it the app cannot reach its own users —
    every other mail in §8.1 is a reply to something the user did, and `login`
    requires already knowing the URL, so on launch day twelve people would have
    no message and no link.
    """
    person = User.objects.create_user(
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        email=email.strip(),
        role=role,
        now=now,
    )
    if send_invitation:
        mail.send(EmailKind.INVITATION, user=person, now=now, link=link)
    return person


def deactivate(person: User, *, now: dt.datetime) -> None:
    """§4.1 — deactivate, never delete. Raises DeactivationBlocked for §7.4."""
    if person.is_supervisor:
        holding = upcoming_sessions_of(person, now)
        if holding:
            raise DeactivationBlocked("err.supervisor_has_sessions", holding)

    if person.is_participant:
        # Their upcoming seats go back into circulation straight away, and each
        # cancellation carries the usual mail and invite (§4.1, §8).
        for registration in person.registrations.filter(
            cancelled_at__isnull=True
        ).select_related("session"):
            if registration.session.is_upcoming(now):
                registrations.cancel_place(registration.session, person, now)

    person.is_active = False
    person.save(update_fields=["is_active"])


def reactivate(person: User) -> None:
    person.is_active = True
    person.save(update_fields=["is_active"])


def describe_blocking_sessions(sessions, locale: str) -> str:
    return session_service.describe_sessions(sessions, locale)


def everyone():
    return User.objects.all().order_by("role", "last_name", "first_name")


def role_choices() -> list[tuple[str, str]]:
    """§14.7 carries the labels; the values are §4.1's enum."""
    return [
        (Role.PARTICIPANT, "a3.role_participant"),
        (Role.SUPERVISOR, "a3.role_supervisor"),
        (Role.ADMIN, "a3.role_admin"),
    ]
