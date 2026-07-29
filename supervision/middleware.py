"""Per-request groundwork: the clock, and the language the page is drawn in."""

from supervision.catalog import DEFAULT_LOCALE, LOCALES
from supervision.clock import get_clock

LOCALE_COOKIE = "locale"


class ClockMiddleware:
    """§11 — resolve the instant once per request and pass it down.

    Views take `request.now` and hand it to the domain; nothing below this line
    reads a clock, which is what lets a test stand anywhere in time.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.now = get_clock().now()
        return self.get_response(request)


class LocaleMiddleware:
    """§10 — the language for this request.

    A signed-in person's choice lives on their account. Before sign-in there is
    no account to keep it on, so the toggle on the sign-in screen writes a
    cookie; §5's screens are reachable by someone who has no session at all.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.locale = self.resolve(request)
        return self.get_response(request)

    @staticmethod
    def resolve(request) -> str:
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            return user.locale
        chosen = request.COOKIES.get(LOCALE_COOKIE)
        return chosen if chosen in LOCALES else DEFAULT_LOCALE
