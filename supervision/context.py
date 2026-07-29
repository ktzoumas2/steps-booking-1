"""Template context every screen needs: the language, and the header's nav."""

from supervision.catalog import DEFAULT_LOCALE, LOCALES
from supervision.navigation import nav_for


def app(request):
    locale = getattr(request, "locale", DEFAULT_LOCALE)
    return {
        "locale": locale,
        # The language the toggle switches *to*. `lang.switch` reads "English"
        # in German and "Deutsch" in English, so the label and this value always
        # describe the same move (§14.1).
        "other_locale": next(other for other in LOCALES if other != locale),
        "nav_items": nav_for(getattr(request, "user", None)),
    }
