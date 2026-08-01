"""The four CSV exports — §9.2.

Format, for all of them: **UTF-8 with a BOM**, comma-separated, `YYYY-MM-DD`
dates. The BOM is not decoration — this replaces an Excel workflow, and without
it Excel mangles `ö`, `ä` and `ü` on open (criterion 63).

Column names are ASCII and English on purpose: they are field names for whatever
reads the file next, not copy for a screen, so they are not in §14.
"""

from __future__ import annotations

import csv
import datetime as dt
import io

from supervision import counting
from supervision.models import Mode, Registration, Session

BOM = "﻿"


def _writer():
    buffer = io.StringIO()
    buffer.write(BOM)
    return buffer, csv.writer(buffer, lineterminator="\r\n")


def _flag(value: bool | None) -> str:
    """`true`, `false`, or empty for "no claim made" (§9.2).

    An empty `took_place` with `reviewed = false` is the ordinary case and still
    counts; the two columns together are what let anyone downstream tell an
    assumption from a statement.
    """
    if value is None:
        return ""
    return "true" if value else "false"


def _location(session: Session) -> str:
    return session.room if session.mode == Mode.IN_PERSON else "online"


def sessions_csv(
    now: dt.datetime, *, start: dt.date | None = None, end: dt.date | None = None
) -> str:
    """The session-level export the admin can rebuild anything from (§9.2).

    Every session in the range, whatever its state — `status` is a column, so a
    cancelled session belongs in the file rather than being quietly missing
    from it.
    """
    buffer, out = _writer()
    out.writerow(
        [
            "session_id", "date", "start_time", "duration_minutes", "mode",
            "location", "supervisor_last_name", "supervisor_first_name",
            "supervisor_email", "status", "took_place", "reviewed",
            "registered_count", "attended_count",
        ]
    )

    queryset = Session.objects.select_related("supervisor").order_by(
        "date", "start_time"
    )
    for session in queryset:
        if start is not None and session.date < start:
            continue
        if end is not None and session.date > end:
            continue

        active = list(session.active_registrations())
        out.writerow(
            [
                session.pk,
                session.date.isoformat(),
                session.start_time.strftime("%H:%M"),
                session.duration_minutes,
                session.mode,
                _location(session),
                session.supervisor.last_name,
                session.supervisor.first_name,
                session.supervisor.email,
                session.status,
                _flag(session.took_place),
                _flag(session.is_reviewed),
                len(active),
                # §9.1 — `is not False`, so an unreviewed session counts everyone.
                sum(1 for r in active if r.attended is not False),
            ]
        )
    return buffer.getvalue()


def per_supervisor_csv(
    now: dt.datetime, *, start: dt.date | None = None, end: dt.date | None = None
) -> str:
    buffer, out = _writer()
    out.writerow(["last_name", "first_name", "email", "sessions_held", "total_minutes"])
    for row in counting.sessions_held_by_supervisor(now, start=start, end=end):
        supervisor = row["supervisor"]
        out.writerow(
            [
                supervisor.last_name,
                supervisor.first_name,
                supervisor.email,
                row["sessions_held"],
                row["total_minutes"],
            ]
        )
    return buffer.getvalue()


def per_participant_csv(
    now: dt.datetime, *, start: dt.date | None = None, end: dt.date | None = None
) -> str:
    buffer, out = _writer()
    out.writerow(
        ["last_name", "first_name", "email", "sessions_attended", "sessions_registered"]
    )
    for row in counting.participation_by_participant(now, start=start, end=end):
        participant = row["participant"]
        out.writerow(
            [
                participant.last_name,
                participant.first_name,
                participant.email,
                row["sessions_attended"],
                row["sessions_registered"],
            ]
        )
    return buffer.getvalue()


def participation_detail_csv(
    now: dt.datetime, *, start: dt.date | None = None, end: dt.date | None = None
) -> str:
    """One row per registration on a session that took place (§9.2).

    This is the export that answers "which sessions did this person actually
    attend", which the summary row cannot. Absences are in the file — `attended`
    is `true` or `false`, never blank — rather than silently missing from it.
    """
    buffer, out = _writer()
    out.writerow(
        [
            "participant_last_name", "participant_first_name", "participant_email",
            "session_id", "date", "start_time", "duration_minutes", "mode",
            "supervisor_last_name", "supervisor_first_name", "attended",
        ]
    )

    counted = {s.pk for s in counting.sessions_that_count(now, start=start, end=end)}
    if not counted:
        return buffer.getvalue()

    registrations = (
        Registration.objects.filter(session_id__in=counted, cancelled_at__isnull=True)
        .select_related("session", "session__supervisor", "user")
        .order_by("user__last_name", "user__first_name", "session__date")
    )
    for registration in registrations:
        session = registration.session
        out.writerow(
            [
                registration.user.last_name,
                registration.user.first_name,
                registration.user.email,
                session.pk,
                session.date.isoformat(),
                session.start_time.strftime("%H:%M"),
                session.duration_minutes,
                session.mode,
                session.supervisor.last_name,
                session.supervisor.first_name,
                "true" if registration.attended is not False else "false",
            ]
        )
    return buffer.getvalue()


EXPORTS = {
    "sessions": (sessions_csv, "supervision-sessions"),
    "per_supervisor": (per_supervisor_csv, "supervision-per-supervisor"),
    "per_participant": (per_participant_csv, "supervision-per-participant"),
    "participation_detail": (participation_detail_csv, "supervision-participation"),
}
