"""Rendering a session in words — §10's date formats over §14's strings.

    {% load display %}
    {% when session %}      Mo, 03.11.2025, 10:00 Uhr
    {% duration session %}  90 Min.
    {% where session %}     Online  /  Raum 2.14

The locale comes from the context, as it does for `{% t %}`.
"""

from django import template

from supervision.catalog import DEFAULT_LOCALE, t
from supervision.formatting import format_date, format_datetime, format_time
from supervision.models import Mode

register = template.Library()


def _locale(context):
    return context.get("locale", DEFAULT_LOCALE)


@register.simple_tag(takes_context=True)
def when(context, session):
    return format_datetime(session.date, session.start_time, _locale(context))


@register.simple_tag(takes_context=True)
def on_date(context, session):
    return format_date(session.date, _locale(context))


@register.simple_tag(takes_context=True)
def at_time(context, session):
    return format_time(session.start_time, _locale(context))


@register.simple_tag(takes_context=True)
def duration(context, session):
    return t("session.duration", _locale(context), minutes=session.duration_minutes)


@register.simple_tag(takes_context=True)
def where(context, session):
    """§4.2 — online sessions carry no per-session link, so this is just the mode."""
    locale = _locale(context)
    if session.mode == Mode.IN_PERSON:
        return t("mode.room", locale, room=session.room)
    return t("mode.online", locale)


@register.simple_tag(takes_context=True)
def timestamp(context, instant):
    from supervision.formatting import format_timestamp

    return format_timestamp(instant, _locale(context))
