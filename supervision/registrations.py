"""Signing up and giving up a place — §6.2, §6.3.

The whole difficulty here is one sentence of §6.2: *the last-seat check must be
atomic.* Two participants clicking simultaneously on the final seat is a
realistic race with twelve people watching the same list, and the loser must be
told the session just filled up rather than shown a generic failure — which
reads as a bug — or, worse, than both being let in.

Three things together make that true:

* the seat count and the insert happen inside one `transaction.atomic()`;
* `select_for_update()` locks the session row, which serialises the readers on
  Postgres;
* SQLite begins that transaction in IMMEDIATE mode (see `config/settings.py`),
  which takes the write lock at BEGIN rather than at the first write.

Without the third, SQLite's default deferred transaction would let both readers
see "one seat left" before either wrote.
"""

from __future__ import annotations

import datetime as dt
import time

from django.db import OperationalError, transaction

from supervision import mail
from supervision.formatting import format_datetime
from supervision.models import (
    EmailKind,
    Registration,
    RegistrationSource,
    Session,
    User,
)


class SignUpRefused(Exception):
    """Carries the §14 key that explains why, so the screen can say it."""

    def __init__(self, copy_key: str):
        super().__init__(copy_key)
        self.copy_key = copy_key


class SessionFull(SignUpRefused):
    def __init__(self):
        super().__init__("err.session_just_filled")


# How many times to re-attempt a seat change the database refused because
# someone else was mid-write. Contention here is by definition two people going
# for the same seat, so the retry re-reads and usually finds the session full —
# which is a sentence we can show (§7.4) rather than a lock error, which is not.
LOCK_ATTEMPTS = 4
LOCK_BACKOFF_SECONDS = 0.05


def _with_retry_on_lock(critical_section):
    """Run a seat change, retrying while the database says it is busy.

    Postgres blocks on `select_for_update()` and needs this never; file-backed
    SQLite waits for its busy timeout and rarely needs it. Shared-cache SQLite —
    what Django's test runner uses — refuses immediately, and so might a future
    deployment we have not chosen yet (§13 question 8). Each attempt re-reads the
    seat count, so a retry can only ever conclude *more* correctly, never
    over-book.
    """
    for attempt in range(LOCK_ATTEMPTS):
        try:
            return critical_section()
        except OperationalError:
            if attempt == LOCK_ATTEMPTS - 1:
                raise
            time.sleep(LOCK_BACKOFF_SECONDS * (attempt + 1))


def sign_up(session: Session, participant: User, now: dt.datetime) -> Registration:
    """Take a seat, or refuse with the reason (§6.2)."""
    registration = _with_retry_on_lock(
        lambda: _take_a_seat(session, participant, now)
    )

    # Sent after the transaction commits: a mail cannot be unsent if the insert
    # is rolled back, and §8.3's reminder scheduling will hang off the same point.
    mail.send(
        EmailKind.REGISTRATION_CONFIRMED,
        user=participant,
        now=now,
        session=session,
        subject_params={
            "date": format_datetime(session.date, session.start_time, participant.locale)
        },
    )
    return registration


def _take_a_seat(
    session: Session, participant: User, now: dt.datetime
) -> Registration:
    with transaction.atomic():
        # Re-read under the lock: whatever the list said a moment ago, the
        # decision has to be made against the row as it is now.
        locked = Session.objects.select_for_update().get(pk=session.pk)

        if not locked.is_upcoming(now):
            raise SignUpRefused("err.date_in_past")

        active = Registration.objects.filter(
            session=locked, cancelled_at__isnull=True
        )
        if active.filter(user=participant).exists():
            # §6.2 — a participant cannot hold two active registrations for one
            # session. Nothing to do, and nothing to complain about.
            return active.get(user=participant)
        if active.count() >= locked.capacity:
            raise SessionFull()

        # §4.3 — a participant who cancels and signs up again reuses the row
        # rather than accumulating duplicates.
        registration = (
            Registration.objects.filter(session=locked, user=participant)
            .order_by("-created_at")
            .first()
        )
        if registration is None:
            registration = Registration(session=locked, user=participant)
        registration.source = RegistrationSource.SELF_SIGNUP
        registration.created_at = now
        registration.cancelled_at = None
        registration.attended = None
        registration.attendance_recorded_at = None
        registration.attendance_recorded_by = None
        registration.full_clean()
        registration.save()
        return registration


def cancel_place(
    session: Session, participant: User, now: dt.datetime
) -> Registration | None:
    """§6.3 — allowed any time before the session starts (D8: no cutoff).

    The seat frees immediately. Nobody else is notified — with these numbers the
    supervisor sees the list when they open the session — but the participant
    gets a short mail carrying a cancellation invite, so the session leaves
    their own calendar. Without it they keep a live entry for a session they are
    no longer registered for (D22).
    """
    registration = _with_retry_on_lock(
        lambda: _release_a_seat(session, participant, now)
    )
    if registration is None:
        return None

    mail.send(
        EmailKind.REGISTRATION_CANCELLED,
        user=participant,
        now=now,
        session=session,
        subject_params={
            "date": format_datetime(session.date, session.start_time, participant.locale)
        },
    )
    return registration


def _release_a_seat(
    session: Session, participant: User, now: dt.datetime
) -> Registration | None:
    with transaction.atomic():
        registration = (
            Registration.objects.select_for_update()
            .filter(session=session, user=participant, cancelled_at__isnull=True)
            .first()
        )
        if registration is None:
            return None
        if now >= session.starts_at:
            raise SignUpRefused("err.date_in_past")

        registration.cancelled_at = now
        registration.save(update_fields=["cancelled_at"])
        return registration


def registered_session_ids(participant: User) -> set[int]:
    """Which sessions this person currently holds a place in — one query, so a
    list screen does not ask once per row."""
    return set(
        Registration.objects.filter(
            user=participant, cancelled_at__isnull=True
        ).values_list("session_id", flat=True)
    )


def registrations_for(participant: User):
    """Active registrations with their sessions, for P1's My sessions tab."""
    return (
        Registration.objects.filter(user=participant, cancelled_at__isnull=True)
        .select_related("session", "session__supervisor")
        .order_by("session__date", "session__start_time")
    )
