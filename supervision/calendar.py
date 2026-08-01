"""Calendar invites — §8.2.

Apple Calendar, Google Calendar, Outlook and Thunderbird all consume iCalendar,
so attaching a file is the entire mechanism: **no per-provider integration, no
API, no OAuth, and no calendar accounts** (D18).

Three properties carry the reasoning worth keeping:

* **`UID` stable, `SEQUENCE` rising** is the only thing that makes a client
  *replace* an event rather than add a second one. The UID is identical for
  every recipient and every mail about that session, forever; the sequence is
  bumped once per outgoing change (§6.5), not per recipient.
* **One recipient per file.** Listing every participant as an `ATTENDEE` would
  disclose their names and addresses to each other (D19). The session detail
  screen is where you see who else is coming.
* **`RSVP=FALSE`, `ORGANIZER` = the app.** The app is the source of truth for
  who is registered, so declining in Outlook must not change a booking, and the
  sending address is unmonitored. Sending as the supervisor from another domain
  would trip DMARC.

The embedded `VTIMEZONE` is there because Outlook mistrusts a `TZID` it was
given no definition for. There is deliberately no `VALARM` (D20): the app sends
its own reminder, and a calendar alarm on top is a second notification on a
schedule the admin cannot see or change.
"""

from __future__ import annotations

import datetime as dt
from urllib.parse import urlencode

from django.conf import settings

from supervision.catalog import t
from supervision.models import Mode, Session, User

# Europe/Berlin, written out rather than referenced. The RRULEs are the EU rule:
# forward on the last Sunday in March, back on the last Sunday in October.
VTIMEZONE = """BEGIN:VTIMEZONE
TZID:Europe/Berlin
BEGIN:DAYLIGHT
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
TZNAME:CEST
DTSTART:19700329T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
TZNAME:CET
DTSTART:19701025T030000
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU
END:STANDARD
END:VTIMEZONE""".split("\n")

REQUEST = "REQUEST"
CANCEL = "CANCEL"


def _escape(value: str) -> str:
    """RFC 5545 text escaping. A comma or semicolon left raw ends the value."""
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> list[str]:
    """Fold to 75 octets, continuing with a leading space (RFC 5545).

    Counted in octets, not characters: `ö` is two bytes, and a fold that splits
    it produces a file some clients reject outright.
    """
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return [line]

    folded, chunk, size = [], [], 0
    limit = 75
    for character in line:
        width = len(character.encode("utf-8"))
        if size + width > limit:
            folded.append("".join(chunk))
            chunk, size = [character], width + 1  # +1 for the leading space
            limit = 75
        else:
            chunk.append(character)
            size += width
    folded.append("".join(chunk))
    return [folded[0]] + [f" {part}" for part in folded[1:]]


def unfold(body: str) -> str:
    """The inverse of `_fold` — what a calendar client actually reads.

    Folding may fall anywhere in a content line, including the middle of an
    email address, so any check on the *content* of an invite has to unfold
    first. Kept next to the folding it undoes, because a reader who does not
    know that will write an assertion that fails for the wrong reason.
    """
    return body.replace("\r\n ", "").replace("\n ", "")


def _stamp(instant: dt.datetime) -> str:
    return instant.astimezone(dt.UTC).strftime("%Y%m%dT%H%M%SZ")


def _local(date: dt.date, time: dt.time) -> str:
    return f"{date:%Y%m%d}T{time:%H%M%S}"


def summary(session: Session, locale: str) -> str:
    return f"Supervision · {session.supervisor.last_name}"


def location(session: Session, locale: str) -> str:
    if session.mode == Mode.IN_PERSON:
        return session.room
    return f"{t('mode.online', locale)} (Zoom)"


def description(session: Session, locale: str, zoom_url: str = "") -> str:
    """§8.2 — supervisor and Schwerpunkt, duration, the Zoom link, a link to the app."""
    lines = [session.supervisor.full_name]
    if session.supervisor.focus_area:
        lines.append(f"{t('label.focus_area', locale)}: {session.supervisor.focus_area}")
    lines.append(t("session.duration", locale, minutes=session.duration_minutes))
    if session.mode == Mode.ONLINE and zoom_url:
        lines.append(f"{t('p2.zoom_link', locale)}: {zoom_url}")
    return "\n".join(lines)


def build_ics(
    session: Session,
    recipient: User,
    *,
    now: dt.datetime,
    method: str = REQUEST,
    zoom_url: str = "",
) -> str:
    """One `.ics` for one recipient — and only that recipient (D19)."""
    locale = recipient.locale
    cancelled = method == CANCEL
    end = (
        dt.datetime.combine(session.date, session.start_time)
        + dt.timedelta(minutes=session.duration_minutes)
    )

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//STEPS//Supervision//DE",
        "CALSCALE:GREGORIAN",
        f"METHOD:{method}",
        *VTIMEZONE,
        "BEGIN:VEVENT",
        f"UID:{session.calendar_uid}",
        f"SEQUENCE:{session.calendar_sequence}",
        f"DTSTAMP:{_stamp(now)}",
        f"DTSTART;TZID=Europe/Berlin:{_local(session.date, session.start_time)}",
        f"DTEND;TZID=Europe/Berlin:{_local(end.date(), end.time())}",
        f"SUMMARY:{_escape(summary(session, locale))}",
        f"LOCATION:{_escape(location(session, locale))}",
        f"DESCRIPTION:{_escape(description(session, locale, zoom_url))}",
        f"STATUS:{'CANCELLED' if cancelled else 'CONFIRMED'}",
        f"ORGANIZER;CN={_escape(t('app.name', locale))}:mailto:{_sender()}",
        f"ATTENDEE;CN={_escape(recipient.full_name)};PARTSTAT=ACCEPTED;RSVP=FALSE:"
        f"mailto:{recipient.email}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]

    folded = []
    for line in lines:
        folded.extend(_fold(line))
    return "\r\n".join(folded) + "\r\n"


def _sender() -> str:
    from email.utils import parseaddr

    _, address = parseaddr(settings.DEFAULT_FROM_EMAIL)
    return address


def add_to_calendar_links(session: Session, locale: str) -> dict[str, str]:
    """§8.2 — for clients that ignore attachments.

    Built from the session's date, time, title and location and **never a
    participant's name or address**: a URL is handed to a third party the moment
    it is clicked.
    """
    starts = session.starts_at
    ends = session.ends_at

    google = "https://calendar.google.com/calendar/render?" + urlencode(
        {
            "action": "TEMPLATE",
            "text": summary(session, locale),
            "dates": f"{_stamp(starts)}/{_stamp(ends)}",
            "location": location(session, locale),
        }
    )
    outlook = (
        "https://outlook.office.com/calendar/0/deeplink/compose?"
        + urlencode(
            {
                "path": "/calendar/action/compose",
                "rru": "addevent",
                "subject": summary(session, locale),
                "startdt": starts.astimezone(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "enddt": ends.astimezone(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "location": location(session, locale),
            }
        )
    )
    return {"google": google, "outlook": outlook}
