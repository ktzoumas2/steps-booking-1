"""The two counts — §9.1.

Both follow §6.4's default, so both are written **`is not False`, never
`is True`**. Getting that backwards is the easiest way to break billing: it
would silently exclude every session nobody reviewed, which is most of them.

Three exclusions do the work:

* `took_place = False` excludes the session for **everyone**, whatever the
  attendance rows say — a recorded no-show overrides every `attended` beneath it;
* a session that has not yet ended counts for nobody *yet* — the only "not yet"
  left, since unreviewed sessions count normally;
* a cancelled registration counts for nobody, even if the participant turned up
  anyway; the supervisor adds them back on review and *that* row is what counts.

The screens that show these numbers (A2, S5, P3) come with the counting slice;
this module is the arithmetic they will all share.
"""

from __future__ import annotations

import datetime as dt

from supervision.models import (
    Registration,
    RegistrationSource,
    Session,
    SessionStatus,
    User,
)


def _within(session: Session, start: dt.date | None, end: dt.date | None) -> bool:
    """§9.1 — the range filters on the session's local date, inclusive at both ends."""
    if start is not None and session.date < start:
        return False
    if end is not None and session.date > end:
        return False
    return True


def sessions_that_count(
    now: dt.datetime,
    *,
    supervisor: User | None = None,
    start: dt.date | None = None,
    end: dt.date | None = None,
) -> list[Session]:
    """Sessions that count as held: offered, ended, `took_place is not False`.

    Filtered in Python because "has ended" is a fact about a wall-clock date and
    time read against a supplied instant (§11), not a column to compare.
    """
    queryset = Session.objects.filter(status=SessionStatus.OFFERED).select_related(
        "supervisor"
    )
    if supervisor is not None:
        queryset = queryset.filter(supervisor=supervisor)

    return [
        session
        for session in queryset
        if session.is_held(now) and _within(session, start, end)
    ]


def sessions_held_by_supervisor(
    now: dt.datetime, *, start: dt.date | None = None, end: dt.date | None = None
) -> list[dict]:
    """The billing figure, grouped by supervisor (§9.1).

    Duration never enters it: a 60-minute and a 120-minute session each count as
    one. `total_minutes` rides along because A2 shows it, but §7.3 is explicit
    that **billing counts sessions, never minutes**.
    """
    tally: dict[int, dict] = {}
    for session in sessions_that_count(now, start=start, end=end):
        row = tally.setdefault(
            session.supervisor_id,
            {"supervisor": session.supervisor, "sessions_held": 0, "total_minutes": 0},
        )
        row["sessions_held"] += 1
        row["total_minutes"] += session.duration_minutes

    return sorted(
        tally.values(),
        key=lambda row: (row["supervisor"].last_name, row["supervisor"].first_name),
    )


def attended_registrations(
    now: dt.datetime,
    *,
    participant: User | None = None,
    start: dt.date | None = None,
    end: dt.date | None = None,
) -> list[Registration]:
    """Active registrations with `attended is not False` on a session that counts.

    The matching *list* is part of the figure, not an extra: it is what P3 and
    the A2 drill-down show.
    """
    counting = {session.pk: session for session in sessions_that_count(now, start=start, end=end)}
    if not counting:
        return []

    queryset = Registration.objects.filter(
        session_id__in=counting, cancelled_at__isnull=True
    ).select_related("session", "session__supervisor", "user")
    if participant is not None:
        queryset = queryset.filter(user=participant)

    # `source` never affects this: attending is attending, whether or not you
    # signed up first (§9.1).
    return [
        registration
        for registration in queryset.order_by(
            "session__date", "session__start_time"
        )
        if registration.attended is not False
    ]


def absent_registrations(
    now: dt.datetime,
    *,
    participant: User | None = None,
    start: dt.date | None = None,
    end: dt.date | None = None,
) -> list[Registration]:
    """Registered but marked absent — the one reason the two figures differ, so
    P3 shows it rather than silently omitting it (§7.1)."""
    counting = {session.pk: session for session in sessions_that_count(now, start=start, end=end)}
    if not counting:
        return []

    queryset = Registration.objects.filter(
        session_id__in=counting, cancelled_at__isnull=True, attended=False
    ).select_related("session", "session__supervisor", "user")
    if participant is not None:
        queryset = queryset.filter(user=participant)
    return list(queryset.order_by("session__date", "session__start_time"))


def sessions_registered_count(
    now: dt.datetime,
    participant: User,
    *,
    start: dt.date | None = None,
    end: dt.date | None = None,
) -> int:
    """§9.1, D27 — self-sign-ups only, whatever `attended` says.

    The number exists to show signed-up-but-did-not-come. Someone added at
    confirmation never signed up at all, so counting them would inflate it with
    the exact population it measures against — and, since they did attend,
    narrow the visible gap. Hence the asymmetry with `sessions_attended`, which
    ignores `source` entirely.
    """
    counting = {session.pk for session in sessions_that_count(now, start=start, end=end)}
    if not counting:
        return 0
    return Registration.objects.filter(
        session_id__in=counting,
        user=participant,
        cancelled_at__isnull=True,
        source=RegistrationSource.SELF_SIGNUP,
    ).count()


def participation_by_participant(
    now: dt.datetime, *, start: dt.date | None = None, end: dt.date | None = None
) -> list[dict]:
    """Per participant: attended and registered, for A2 (§7.3)."""
    attended = attended_registrations(now, start=start, end=end)

    people: dict[int, dict] = {}
    for registration in attended:
        row = people.setdefault(
            registration.user_id,
            {"participant": registration.user, "sessions_attended": 0},
        )
        row["sessions_attended"] += 1

    # Somebody who registered for everything and attended nothing still belongs
    # in this table — that gap is the whole point of showing both numbers.
    for registration in absent_registrations(now, start=start, end=end):
        people.setdefault(
            registration.user_id,
            {"participant": registration.user, "sessions_attended": 0},
        )

    for row in people.values():
        row["sessions_registered"] = sessions_registered_count(
            now, row["participant"], start=start, end=end
        )

    return sorted(
        people.values(),
        key=lambda row: (row["participant"].last_name, row["participant"].first_name),
    )


def unreviewed_in_range(
    now: dt.datetime, *, start: dt.date | None = None, end: dt.date | None = None
) -> list[Session]:
    """§7.3 A2 — the sessions nobody has opened, which are counted regardless.

    This is the one place the cost of §6.4's assumption is paid: a human is made
    to look before the numbers become an invoice.
    """
    return [
        session
        for session in sessions_that_count(now, start=start, end=end)
        if not session.is_reviewed
    ]
