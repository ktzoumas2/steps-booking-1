"""User-facing strings that §14 does not yet contain.

**This is the only place in the app that holds copy outside the catalog**, and
everything in it is a flagged gap rather than a decision: each entry belongs in
a §14.11 once STEPS has settled the wording. Keeping them together makes the
list greppable, and makes it obvious when it grows.

The gaps, and why each is unavoidable rather than an oversight:

* **weekday and month names** — §10 specifies the date *formats* and gives one
  example of each, but no table of names, and dates cannot be rendered without
  them;
* **`Von` / `Bis`** — §14 has `Zeitraum` for a date range as a group, but P3, S5
  and A2 each need two labelled fields, and WCAG (§11) wants every control
  labelled, not just the fieldset;
* **the two *Add to calendar* link labels** — §8.2 requires a Google link and an
  Outlook link in the body of every session mail, for clients that ignore
  attachments. §14.4 has one generic `p2.add_to_calendar`, which cannot
  distinguish them.
"""

WEEKDAYS = {
    "de": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
}

MONTHS_EN = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

RANGE_LABELS = {
    "de": {"from": "Von", "to": "Bis"},
    "en": {"from": "From", "to": "To"},
}

CALENDAR_LINKS = {
    "de": {
        "google": "Zu Google Calendar hinzufügen",
        "outlook": "Zu Outlook hinzufügen",
    },
    "en": {
        "google": "Add to Google Calendar",
        "outlook": "Add to Outlook",
    },
}


def range_label(which: str, locale: str) -> str:
    return RANGE_LABELS.get(locale, RANGE_LABELS["de"])[which]


def calendar_link_label(which: str, locale: str) -> str:
    return CALENDAR_LINKS.get(locale, CALENDAR_LINKS["de"])[which]
