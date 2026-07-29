"""Rendering dates and times per locale — §10.

    de: Mo, 03.11.2025, 10:00 Uhr
    en: Mon, 3 Nov 2025, 10:00

24-hour clock in both: German convention, and unambiguous.

NOTE — the weekday and month names below are user-facing strings that §14 does
not contain, which is the one place this app knowingly holds copy outside the
catalog. §10 specifies the *formats* and gives an example of each, but no table
of names, and dates cannot be rendered without them. They belong in a §14.11;
flagged rather than quietly settled. Everything else on every screen still comes
from `catalog.py`.
"""

from __future__ import annotations

import datetime as dt

WEEKDAYS = {
    "de": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
}

MONTHS_EN = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def weekday(date: dt.date, locale: str) -> str:
    return WEEKDAYS.get(locale, WEEKDAYS["de"])[date.weekday()]


def format_date(date: dt.date, locale: str) -> str:
    """`Mo, 03.11.2025` / `Mon, 3 Nov 2025`."""
    if locale == "en":
        return f"{weekday(date, locale)}, {date.day} {MONTHS_EN[date.month - 1]} {date.year}"
    return f"{weekday(date, locale)}, {date:%d.%m.%Y}"


def format_day_and_month(date: dt.date, locale: str) -> str:
    """`Mo 03.11.` / `Mon 3 Nov` — the short form the week headings use (§7.1)."""
    if locale == "en":
        return f"{weekday(date, locale)} {date.day} {MONTHS_EN[date.month - 1]}"
    return f"{weekday(date, locale)} {date:%d.%m.}"


def format_time(time: dt.time, locale: str) -> str:
    """`10:00 Uhr` / `10:00`."""
    rendered = f"{time:%H:%M}"
    return rendered if locale == "en" else f"{rendered} Uhr"


def format_datetime(date: dt.date, time: dt.time, locale: str) -> str:
    return f"{format_date(date, locale)}, {format_time(time, locale)}"


def format_timestamp(instant: dt.datetime, locale: str) -> str:
    """A recorded UTC instant, read on a Berlin wall clock (§11)."""
    from supervision.clock import to_berlin

    local = to_berlin(instant)
    return format_datetime(local.date(), local.time(), locale)
