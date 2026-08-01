"""The two date-range field labels §14 does not yet carry.

Kept in its own tag module so the gap is greppable rather than buried; see the
note at the top of `supervision/formatting.py`.
"""

from django import template

from supervision.catalog import DEFAULT_LOCALE
from supervision.formatting import range_label as label_for

register = template.Library()


@register.simple_tag(takes_context=True)
def range_label(context, which):
    return label_for(which, context.get("locale", DEFAULT_LOCALE))
