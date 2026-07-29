"""The domain this installation sends as.

Two things need it and neither should invent its own: the `Message-ID` of every
mail, and the iCalendar `UID` of every session (§4.2, §8.2). Both are identifiers
that must be globally unique and stable, and both conventionally end in the
sending domain — which is our address, not the hostname of whichever machine
happens to be running the app.
"""

from email.utils import parseaddr

from django.conf import settings


def sending_domain() -> str:
    _, address = parseaddr(settings.DEFAULT_FROM_EMAIL)
    _, _, domain = address.rpartition("@")
    return domain or "localhost"
