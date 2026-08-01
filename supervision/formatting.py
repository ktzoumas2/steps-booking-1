"""Rendering dates and times per locale — §10.

    de: Mo, 03.11.2025, 10:00 Uhr
    en: Mon, 3 Nov 2025, 10:00

24-hour clock in both: German convention, and unambiguous.

NOTE — this module is the one place this app knowingly holds user-facing copy
outside the catalog, and everything here is flagged rather than quietly settled.
Two gaps put it here, both belonging in a §14.11:

* **weekday and month names.** §10 specifies the date *formats* and gives an
  example of each, but no table of names, and dates cannot be rendered without
  them;
* **the two labels of a date-range picker.** §7.1 P3, §7.2 S5 and §7.3 A2 all
  need one; §14 has `Zeitraum` for the group but nothing for the from and to
  fields, and WCAG (§11) wants every control labelled, not just the fieldset.

Everything else on every screen still comes from `catalog.py`.
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

# Also awaiting a §14.11 — see the module note.
RANGE_LABELS = {
    "de": {"from": "Von", "to": "Bis"},
    "en": {"from": "From", "to": "To"},
}


def range_label(which: str, locale: str) -> str:
    return RANGE_LABELS.get(locale, RANGE_LABELS["de"])[which]


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
