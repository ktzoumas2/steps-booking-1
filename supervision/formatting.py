"""Rendering dates and times per locale — §10.

    de: Mo, 03.11.2025, 10:00 Uhr
    en: Mon, 3 Nov 2025, 10:00

24-hour clock in both: German convention, and unambiguous.

The weekday and month names this needs are not in §14; they live in
`supervision/pending_copy.py` with every other string awaiting a §14.11.
"""

from __future__ import annotations

import datetime as dt

from supervision.pending_copy import MONTHS_EN, WEEKDAYS, range_label  # noqa: F401


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
