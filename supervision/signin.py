"""Magic-link sign-in — §5.

The rules this file carries, all from §5:

* a link is a single-use token, valid 15 minutes (§5.3);
* requesting one for an unknown or deactivated address sends nothing, and the
  screen says the same thing either way — never reveal whether an address is
  registered (§5.2, §5.6);
* requesting a link is rate-limited, 5 per email per hour (§5.5).

Everything here takes `now` as an argument (§11). Nothing reads the clock.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import secrets
from dataclasses import dataclass

from supervision.models import EmailKind, EmailLog, LoginToken, User

# §5.5 — 5 per email per hour. The per-IP half of that rule waits for hosting
# (§13, question 8): behind an unknown proxy, REMOTE_ADDR is either the proxy's
# address or whatever a client claims, so a limit built on it now would be
# either useless or wrong, and it would mean storing addresses §4 does not name.
REQUESTS_PER_EMAIL_PER_HOUR = 5
RATE_LIMIT_WINDOW = dt.timedelta(hours=1)


def hash_token(raw_token: str) -> str:
    """§4.5 — store a hash, never the raw token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IssuedToken:
    """A token that has just been created. The raw value exists only here."""

    token: LoginToken
    raw_token: str


def issue_token(user: User, now: dt.datetime) -> IssuedToken:
    raw_token = secrets.token_urlsafe(32)
    token = LoginToken.objects.create(
        user=user,
        token_hash=hash_token(raw_token),
        expires_at=now + LoginToken.VALIDITY,
    )
    return IssuedToken(token=token, raw_token=raw_token)


def is_rate_limited(user: User, now: dt.datetime) -> bool:
    """Whether this address has had its allowance of links this hour (§5.5).

    Counted from the sent mails rather than from a separate counter: a request
    that was refused sent nothing, and it is deliveries that the rule is there
    to limit.
    """
    since = now - RATE_LIMIT_WINDOW
    recent = EmailLog.objects.filter(
        user=user, kind=EmailKind.LOGIN, sent_at__gte=since
    ).count()
    return recent >= REQUESTS_PER_EMAIL_PER_HOUR


def find_recipient(email: str) -> User | None:
    """The active user this address belongs to, if any.

    Returns None for an unknown *or* a deactivated address — §5.6 treats them
    identically, and so must every caller.
    """
    return User.objects.filter(email__iexact=email.strip(), is_active=True).first()


class RedemptionError(Exception):
    """A link that cannot sign anyone in, with the §14 key that explains why."""

    def __init__(self, copy_key: str):
        super().__init__(copy_key)
        self.copy_key = copy_key


def redeem_token(raw_token: str, now: dt.datetime) -> User:
    """Spend a magic link and return the user it signs in.

    Raises RedemptionError carrying `err.link_used` or `err.link_expired` (§7.4),
    which are different messages because they lead to different assumptions: one
    means "you already clicked this", the other "you waited too long".
    """
    token = LoginToken.objects.filter(token_hash=hash_token(raw_token)).first()

    if token is None:
        # An unknown token is indistinguishable from a very old one — tokens are
        # not kept forever — and "expired, request a new one" is the useful
        # thing to say about both.
        raise RedemptionError("err.link_expired")
    if token.is_used:
        raise RedemptionError("err.link_used")
    if token.is_expired(now):
        raise RedemptionError("err.link_expired")

    # Single use, and single use under a double click: whoever's UPDATE matches
    # the row while `used_at` is still null has spent the token, and a second
    # attempt matches nothing.
    spent = LoginToken.objects.filter(pk=token.pk, used_at__isnull=True).update(
        used_at=now
    )
    if not spent:
        raise RedemptionError("err.link_used")

    # Deactivation between issuing a link and clicking it is rare but must not
    # be a way in (§4.1 — inactive users cannot sign in).
    token.user.refresh_from_db()
    if not token.user.is_active:
        raise RedemptionError("err.link_expired")

    return token.user
