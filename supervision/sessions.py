"""Offering, changing and calling off a session — §6.1, §6.3, §6.5.

Everything here takes `now` and returns what happened, so the views stay thin
and the rules stay testable at any point in time (§11).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from django.db import transaction

from supervision import mail
from supervision.clock import iso_week, week_bounds
from supervision.formatting import format_datetime
from supervision.models import (
    EmailKind,
    Session,
    SessionStatus,
    Settings,
    User,
)

# §6.5 — the changes that notify participants and ship an updated invite.
# Capacity is deliberately not among them: it changes nothing a calendar or a
# participant needs to know about.
NOTIFIABLE_FIELDS = ("date", "start_time", "duration_minutes", "mode", "room")


# --- The weekly distribution cap (§6.1) -----------------------------------


@dataclass(frozen=True)
class WeeklyCapCheck:
    """What the cap has to say about putting a session in a given week.

    The intent behind it is even distribution — roughly one session a week —
    so that participants have a steady supply rather than three in one week and
    nothing for a fortnight.
    """

    cap: int
    enforced: bool
    clashing: list[Session] = field(default_factory=list)

    @property
    def would_exceed(self) -> bool:
        return len(self.clashing) + 1 > self.cap


def sessions_in_week_of(date: dt.date, exclude: Session | None = None):
    """Every offered session sharing an ISO week with `date` (§6.1).

    Cancelled sessions are excluded — one frees its slot immediately — and so is
    `exclude`, because editing a session without moving it must not count the
    session against itself.
    """
    monday, sunday = week_bounds(*iso_week(date))
    queryset = Session.objects.filter(
        date__gte=monday, date__lte=sunday, status=SessionStatus.OFFERED
    ).select_related("supervisor")
    if exclude is not None and exclude.pk:
        queryset = queryset.exclude(pk=exclude.pk)
    return queryset


def check_weekly_cap(
    date: dt.date, settings: Settings, exclude: Session | None = None
) -> WeeklyCapCheck:
    return WeeklyCapCheck(
        cap=settings.weekly_session_cap,
        enforced=settings.enforce_weekly_cap,
        clashing=list(sessions_in_week_of(date, exclude=exclude)),
    )


def describe_sessions(sessions, locale: str) -> str:
    """The clashing sessions, named — date, time, supervisor (§7.4).

    This is the one error message in the app that does real work: the
    supervisor's next action is picking a different week, and they cannot do
    that without knowing what is already in this one.
    """
    return "; ".join(
        f"{format_datetime(session.date, session.start_time, locale)} "
        f"({session.supervisor.last_name})"
        for session in sessions
    )


# --- Creating, changing and cancelling ------------------------------------


def create_session(*, supervisor: User, now: dt.datetime, **fields) -> Session:
    session = Session(
        supervisor=supervisor, created_at=now, updated_at=now, **fields
    )
    session.full_clean()
    session.save()

    # §8.1 — the person who has to be there needs it in their calendar most (D21).
    mail.send(
        EmailKind.SESSION_CREATED,
        user=supervisor,
        now=now,
        session=session,
        subject_params={"date": format_datetime(
            session.date, session.start_time, supervisor.locale
        )},
    )
    return session


@dataclass(frozen=True)
class Change:
    """One field that moved, in the words the recipient reads (§14.10)."""

    before: str
    after: str


def update_session(
    session: Session, *, now: dt.datetime, **fields
) -> dict[str, Change]:
    """Apply an edit, and notify if it is one anybody needs to know about (§6.5).

    What changed is worked out against the *stored* row, not the instance in
    hand: a ModelForm has already written the new values onto its instance by
    the time it validates, so comparing against that would find every edit
    unchanged and quietly notify nobody.
    """
    locale = session.supervisor.locale
    stored = Session.objects.get(pk=session.pk)
    before = _describe(stored, locale)

    changed = [
        name
        for name in NOTIFIABLE_FIELDS
        if name in fields and fields[name] != getattr(stored, name)
    ]

    for name, value in fields.items():
        setattr(session, name, value)
    session.updated_at = now

    if changed:
        # §8.2 — same UID, higher SEQUENCE, so a calendar replaces the event
        # rather than leaving the participant with two entries for one session.
        session.calendar_sequence += 1

    session.full_clean()
    session.save()

    if not changed:
        return {}

    after = _describe(session, locale)
    mail.send(
        EmailKind.SESSION_CHANGED,
        user=session.supervisor,
        now=now,
        session=session,
        subject_params={"date": format_datetime(
            session.date, session.start_time, locale
        )},
        change=Change(before=before, after=after),
    )
    return {"summary": Change(before=before, after=after)}


def cancel_session(session: Session, *, by: User, now: dt.datetime) -> None:
    """§6.3 — allowed any time until the end time, including mid-session."""
    with transaction.atomic():
        session.status = SessionStatus.CANCELLED
        session.cancelled_at = now
        session.cancelled_by = by
        session.calendar_sequence += 1
        session.updated_at = now
        session.save()

    # §8.1 — every actively-registered participant, and the supervisor. There
    # are no registrations yet; the participant half arrives with them.
    mail.send(
        EmailKind.SESSION_CANCELLED,
        user=session.supervisor,
        now=now,
        session=session,
        subject_params={"date": format_datetime(
            session.date, session.start_time, session.supervisor.locale
        )},
    )


def _describe(session: Session, locale: str) -> str:
    """A session in one line, for the old → new of `email.session_changed.body`."""
    from supervision.catalog import t

    when = format_datetime(session.date, session.start_time, locale)
    where = (
        t("mode.online", locale)
        if session.mode == "online"
        else t("mode.room", locale, room=session.room)
    )
    duration = t("session.duration", locale, minutes=session.duration_minutes)
    return f"{when}, {duration}, {where}"
