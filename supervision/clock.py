"""Time: supplied to the application, never read from the system clock (§11).

Nearly every rule that matters here is time-dependent — a session counts *because*
its end time has passed (§6.4), weeks are ISO weeks in Europe/Berlin (§6.1),
reminders are scheduled relative to a start time (§8.3). None of that can be
tested against a clock that only moves forwards at one second per second, so the
current instant is passed in.

Two kinds of time live in this app and must not be confused (§11, §15.1):

* a session's `date` + `start_time` are a **wall-clock intention** in
  Europe/Berlin — a 10:00 session is still 10:00 after a DST change;
* `created_at`, `sent_at` and friends are **UTC instants**.

`wall_clock_to_instant` is the only bridge between them.
"""

from __future__ import annotations

import datetime as dt
from contextlib import contextmanager
from typing import Protocol
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")


class Clock(Protocol):
    """The application's only source of "now"."""

    def now(self) -> dt.datetime:
        """The current instant, timezone-aware and in UTC."""
        ...


class SystemClock:
    """The real clock. Used by the running app, never by a test."""

    def now(self) -> dt.datetime:
        return dt.datetime.now(dt.UTC)


class FixedClock:
    """A clock a test can stand anywhere on, and move at will."""

    def __init__(self, instant: dt.datetime):
        self.set(instant)

    def now(self) -> dt.datetime:
        return self._instant

    def set(self, instant: dt.datetime) -> None:
        if instant.tzinfo is None:
            raise ValueError("an instant must be timezone-aware")
        self._instant = instant.astimezone(dt.UTC)

    def advance(self, **timedelta_kwargs) -> None:
        self.set(self._instant + dt.timedelta(**timedelta_kwargs))


_clock: Clock = SystemClock()


def get_clock() -> Clock:
    """The clock for this process.

    The request layer resolves this once and passes it down; domain functions
    take the instant or the clock as an argument rather than calling this.
    """
    return _clock


@contextmanager
def using_clock(clock: Clock):
    """Run a block against a different clock. For tests and the seed fixture."""
    global _clock
    previous = _clock
    _clock = clock
    try:
        yield clock
    finally:
        _clock = previous


def wall_clock_to_instant(date: dt.date, time: dt.time) -> dt.datetime:
    """The actual moment a Europe/Berlin wall-clock date and time refers to.

    Where a wall-clock time is ambiguous (the hour repeated when the clocks go
    back) this takes the first of the two, and where it does not exist at all
    (the hour skipped when they go forward) Python maps it onto the offset
    before the change. Supervision sessions do not run at 02:00, so neither case
    is reachable in practice; both are resolved rather than raising, because a
    session that cannot be saved is worse than one that is an hour out.
    """
    return dt.datetime.combine(date, time, tzinfo=BERLIN)


def to_berlin(instant: dt.datetime) -> dt.datetime:
    """An instant as it reads on a Berlin wall clock."""
    return instant.astimezone(BERLIN)


def today_in_berlin(now: dt.datetime) -> dt.date:
    """The calendar date it is in Berlin at `now` — not the UTC date."""
    return to_berlin(now).date()


def iso_week(date: dt.date) -> tuple[int, int]:
    """The ISO year and week (Mon–Sun) a date falls in (§6.1, §2)."""
    iso = date.isocalendar()
    return iso.year, iso.week


def week_bounds(iso_year: int, iso_week_number: int) -> tuple[dt.date, dt.date]:
    """The Monday and Sunday of an ISO week, for the week headings of §7.1."""
    monday = dt.date.fromisocalendar(iso_year, iso_week_number, 1)
    return monday, monday + dt.timedelta(days=6)
