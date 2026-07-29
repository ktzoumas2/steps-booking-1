"""Template access to the §14 catalog.

    {% load copy %}
    {% t "p1.action_signup" %}
    {% t "p1.seats" taken=3 capacity=5 %}

The locale comes from `locale` in the template context, which the view supplies
from the signed-in user (§10). An unknown key raises — see `catalog.t`.
"""

from django import template

from supervision.catalog import DEFAULT_LOCALE, t as translate

register = template.Library()


@register.simple_tag(takes_context=True)
def t(context, key, **params):
    locale = context.get("locale", DEFAULT_LOCALE)
    return translate(key, locale, **params)
