"""The data model of §4.

Timestamps are never written by `auto_now_add`. §11 requires the current instant
to be supplied rather than read from the system clock, and a field that quietly
calls `timezone.now()` is exactly the thing that makes a time-dependent rule
untestable. Every record-keeping timestamp is passed in.
"""

from __future__ import annotations

import datetime as dt

from django.db import models
from django.db.models.functions import Lower


class Role(models.TextChoices):
    """§4.1. One role per person (D5); the user-facing labels are in §14.7."""

    PARTICIPANT = "participant", "Participant"
    SUPERVISOR = "supervisor", "Supervisor"
    ADMIN = "admin", "Administrator"


class Locale(models.TextChoices):
    """§10. German is the default and the language content is authored in."""

    DE = "de", "Deutsch"
    EN = "en", "English"


class UserManager(models.Manager):
    def get_by_natural_key(self, email: str) -> "User":
        return self.get(email__iexact=email)

    def active(self) -> models.QuerySet["User"]:
        return self.filter(is_active=True)

    def create_user(
        self,
        *,
        first_name: str,
        last_name: str,
        email: str,
        role: str,
        now: dt.datetime,
        **extra,
    ) -> "User":
        """Create a person. `now` is supplied by the caller (§11).

        There is no `create_superuser`: this app has no Django admin site and no
        password. Every account is created by an administrator from A3 (§7.3),
        with the single exception of the install-time admin (§5.1).
        """
        user = self.model(
            first_name=first_name,
            last_name=last_name,
            email=email,
            role=role,
            created_at=now,
            **extra,
        )
        user.full_clean()
        user.save()
        return user


class User(models.Model):
    """§4.1 — the login identity, with no password field (§15.1).

    Authentication is a magic link (§5), so nothing here is ever hashed or
    checked. The attributes Django's session machinery expects
    (`USERNAME_FIELD`, `is_authenticated`, `is_anonymous`) are provided; the
    permission and group machinery of `django.contrib.auth` is not used —
    §3's table is the whole permission model, and it keys on `role`.
    """

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(max_length=254, unique=True)
    role = models.CharField(max_length=20, choices=Role)
    focus_area = models.TextField(blank=True, default="")
    profile_url = models.URLField(max_length=500, blank=True, default="")
    locale = models.CharField(max_length=2, choices=Locale, default=Locale.DE)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField()

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        constraints = [
            # §4.1 — email is unique, compared case-insensitively. The plain
            # `unique=True` above is not enough: "Anna@phb.de" and "anna@phb.de"
            # are one login identity, and a functional index is how both SQLite
            # and Postgres enforce that.
            models.UniqueConstraint(
                Lower("email"), name="user_email_case_insensitive_unique"
            ),
        ]
        ordering = ["last_name", "first_name"]

    def __str__(self) -> str:
        return self.full_name

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_participant(self) -> bool:
        return self.role == Role.PARTICIPANT

    @property
    def is_supervisor(self) -> bool:
        return self.role == Role.SUPERVISOR

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN

    # What django.contrib.auth's session handling asks of a user model. There is
    # no password, so there is no `get_session_auth_hash`; sessions end when they
    # expire (§5.4) or the user signs out.
    is_authenticated = True
    is_anonymous = False

    def get_username(self) -> str:
        return self.email


class LoginToken(models.Model):
    """§4.5 — a single-use magic link, valid 15 minutes (§5.3, D6).

    The raw token is never stored: it exists only in the email that carries it
    and in the URL the user clicks. What is kept is a SHA-256 hash, which is
    enough to recognise a token presented back to us and useless to anyone who
    reads the table.
    """

    VALIDITY = dt.timedelta(minutes=15)

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="login_tokens")
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-expires_at"]

    def __str__(self) -> str:
        return f"login token for {self.user.email}"

    def is_expired(self, now: dt.datetime) -> bool:
        return now >= self.expires_at

    @property
    def is_used(self) -> bool:
        return self.used_at is not None


class EmailKind(models.TextChoices):
    """§8.1. Every one of these is a synchronous reply to something a person did,
    the sole exception being `reminder`, which the provider holds until it is due
    (§8.3). The app itself runs nothing on a timer.
    """

    LOGIN = "login", "Sign-in link"
    INVITATION = "invitation", "Invitation"
    REGISTRATION_CONFIRMED = "registration_confirmed", "Registration confirmed"
    REGISTRATION_CANCELLED = "registration_cancelled", "Registration cancelled"
    REMINDER = "reminder", "Reminder"
    SESSION_CANCELLED = "session_cancelled", "Session cancelled"
    SESSION_CHANGED = "session_changed", "Session changed"
    SESSION_CREATED = "session_created", "Session created"


class EmailLog(models.Model):
    """§4.6 — a plain audit log, with no idempotency machinery.

    Nothing here enforces send-once, because nothing needs to. Its jobs are
    answering "was this person ever sent a REQUEST for this session?" (§8.3,
    which decides whether they may be sent a CANCEL) and, for `login`, carrying
    the rate limit of §5.5 without storing anything §4 does not already name.

    The `session` foreign key of §4.6 arrives with the Session model itself.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="emails")
    kind = models.CharField(max_length=32, choices=EmailKind)
    sent_at = models.DateTimeField()

    class Meta:
        ordering = ["-sent_at"]
        indexes = [models.Index(fields=["user", "kind", "sent_at"])]

    def __str__(self) -> str:
        return f"{self.kind} to {self.user.email}"
