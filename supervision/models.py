"""The data model of §4.

Timestamps are never written by `auto_now_add`. §11 requires the current instant
to be supplied rather than read from the system clock, and a field that quietly
calls `timezone.now()` is exactly the thing that makes a time-dependent rule
untestable. Every record-keeping timestamp is passed in.
"""

from __future__ import annotations

import datetime as dt
import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower

from supervision.clock import wall_clock_to_instant
from supervision.sending import sending_domain


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


class Settings(models.Model):
    """§4.4 — a single row of programme-wide settings, edited at A4 (§7.3).

    The defaults for duration and capacity are placeholders confirmed with
    nobody yet (D9, §13 question 1); they are settings precisely so that being
    wrong about them costs nothing.
    """

    SINGLETON_PK = 1

    # §4.2 — online sessions carry no per-session link. The URL lives here once
    # and is read at display and send time, so changing it fixes every future
    # session at once.
    zoom_url = models.URLField(max_length=500, blank=True, default="")
    default_duration_minutes = models.PositiveIntegerField(default=90)
    default_capacity = models.PositiveIntegerField(default=5)
    weekly_session_cap = models.PositiveIntegerField(default=2)
    enforce_weekly_cap = models.BooleanField(default=True)
    reminder_lead_hours = models.PositiveIntegerField(default=24)

    class Meta:
        verbose_name_plural = "settings"

    def __str__(self) -> str:
        return "settings"

    def save(self, *args, **kwargs):
        self.pk = self.SINGLETON_PK
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "Settings":
        """The settings row, created with §4.4's defaults if it is not there yet."""
        instance, _ = cls.objects.get_or_create(pk=cls.SINGLETON_PK)
        return instance


class Mode(models.TextChoices):
    """§4.2. The labels users see are `s2.mode_online` / `s2.mode_in_person`."""

    ONLINE = "online", "Online"
    IN_PERSON = "in_person", "In person"


class SessionStatus(models.TextChoices):
    """§4.2. Everything else about a session's state is derived, not stored."""

    OFFERED = "offered", "Offered"
    CANCELLED = "cancelled", "Cancelled"


def generate_calendar_uid() -> str:
    """§4.2, §8.2 — generated once at creation, never reused or changed.

    A stable UID is the only thing that makes a calendar client *replace* an
    event rather than add a second one, so it must survive every edit.
    """
    return f"{uuid.uuid4()}@{sending_domain()}"


class Session(models.Model):
    """§4.2 — one scheduled supervision meeting.

    `date` and `start_time` are separate fields on purpose (§15.1): they are a
    wall-clock intention in Europe/Berlin, and a 10:00 session stays at 10:00
    across a DST change. The actual instant is derived, never stored.
    """

    supervisor = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="sessions_held"
    )
    date = models.DateField()
    start_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField()
    mode = models.CharField(max_length=20, choices=Mode)
    room = models.CharField(max_length=100, blank=True, default="")
    capacity = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20, choices=SessionStatus, default=SessionStatus.OFFERED
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessions_cancelled",
    )
    # null = nobody has reviewed it, which still counts as held once the end
    # time has passed (§6.4, D29). Never write this to mean "it happened".
    took_place = models.BooleanField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessions_reviewed",
    )
    calendar_uid = models.CharField(
        max_length=200, unique=True, default=generate_calendar_uid
    )
    calendar_sequence = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        ordering = ["date", "start_time"]
        indexes = [models.Index(fields=["date", "status"])]

    def __str__(self) -> str:
        return f"{self.date} {self.start_time:%H:%M} · {self.supervisor.last_name}"

    def clean(self):
        if self.supervisor_id and self.supervisor.role != Role.SUPERVISOR:
            raise ValidationError({"supervisor": "Sessions are held by supervisors."})

    # --- Derived state (§4.2). None of this is stored; all of it is computed. ---

    @property
    def starts_at(self) -> dt.datetime:
        return wall_clock_to_instant(self.date, self.start_time)

    @property
    def ends_at(self) -> dt.datetime:
        return self.starts_at + dt.timedelta(minutes=self.duration_minutes)

    @property
    def is_cancelled(self) -> bool:
        return self.status == SessionStatus.CANCELLED

    def has_ended(self, now: dt.datetime) -> bool:
        return now >= self.ends_at

    def is_upcoming(self, now: dt.datetime) -> bool:
        return not self.is_cancelled and now < self.starts_at

    def is_in_progress(self, now: dt.datetime) -> bool:
        return not self.is_cancelled and self.starts_at <= now < self.ends_at

    def is_held(self, now: dt.datetime) -> bool:
        """§6.4 — ended and nobody said otherwise. Written `is not False`, never
        `is True`: `null` means "no claim either way", and that counts.
        """
        return (
            not self.is_cancelled
            and self.has_ended(now)
            and self.took_place is not False
        )

    @property
    def is_not_held(self) -> bool:
        return self.took_place is False

    @property
    def is_reviewed(self) -> bool:
        """§2 — whether a human has opened it and saved it. Never affects a count."""
        return self.confirmed_at is not None

    # --- Seats (§6.2) ---------------------------------------------------------
    #
    # `seats_taken` is a query, so list screens annotate the count instead of
    # asking once per row. These are for a single session in hand.

    def active_registrations(self):
        return self.registrations.filter(cancelled_at__isnull=True)

    @property
    def seats_taken(self) -> int:
        return self.active_registrations().count()

    @property
    def is_full(self) -> bool:
        return self.seats_taken >= self.capacity

    def is_open_for_signup(self, now: dt.datetime) -> bool:
        """§6.2 — offered, still to come, and not yet full."""
        return self.is_upcoming(now) and not self.is_full

    def can_be_cancelled(self, now: dt.datetime) -> bool:
        """§6.3 — any time until the end time, including while in progress.

        Deliberately open past the start: the commonest cancellation, supervisor
        ill, is acted on around the start time, and closing the door there would
        leave participants waiting with a live calendar entry and nobody able to
        do anything about it.
        """
        return not self.is_cancelled and now < self.ends_at


class RegistrationSource(models.TextChoices):
    """§4.3 — how the row came to exist.

    The distinction matters exactly once, in `sessions_registered` (§9.1, D27):
    counting supervisor-added rows would inflate the figure with the very
    population it exists to measure against.
    """

    SELF_SIGNUP = "self_signup", "Signed up themselves"
    ADDED_AT_CONFIRMATION = "added_at_confirmation", "Added when the session was reviewed"


class Registration(models.Model):
    """§4.3 — one participant's place in one session.

    A cancelled row is kept rather than deleted: it explains why a seat freed
    up. `attended = null` means nobody said otherwise, which counts as present
    at a session that counts as held (§6.4) — never write it to mean "was here".
    """

    session = models.ForeignKey(
        Session, on_delete=models.CASCADE, related_name="registrations"
    )
    user = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="registrations"
    )
    source = models.CharField(
        max_length=32, choices=RegistrationSource, default=RegistrationSource.SELF_SIGNUP
    )
    created_at = models.DateTimeField()
    cancelled_at = models.DateTimeField(null=True, blank=True)
    attended = models.BooleanField(null=True, blank=True)
    attendance_recorded_at = models.DateTimeField(null=True, blank=True)
    attendance_recorded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_recorded",
    )
    # §8.3 — the provider's handle for this person's scheduled reminder, so it
    # can be cancelled or rescheduled. Nothing writes it until the mail slice.
    reminder_message_id = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["created_at"]
        constraints = [
            # §4.3 — at most one *active* registration per (session, user). The
            # condition is what allows the history: cancelling and signing up
            # again must not be blocked by the row that explains the free seat.
            models.UniqueConstraint(
                fields=["session", "user"],
                condition=models.Q(cancelled_at__isnull=True),
                name="one_active_registration_per_person_per_session",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user.email} → {self.session_id}"

    def clean(self):
        if self.user_id and self.user.role != Role.PARTICIPANT:
            raise ValidationError({"user": "Only participants hold registrations."})

    @property
    def is_active(self) -> bool:
        return self.cancelled_at is None

    @property
    def counts_as_attended(self) -> bool:
        """§9.1 — written `is not False`, never `is True`.

        Getting this backwards is the easiest way to break billing: it would
        silently exclude every session nobody reviewed, which is most of them.
        """
        return self.is_active and self.attended is not False


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
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="emails")
    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="emails",
    )
    kind = models.CharField(max_length=32, choices=EmailKind)
    sent_at = models.DateTimeField()

    class Meta:
        ordering = ["-sent_at"]
        indexes = [models.Index(fields=["user", "kind", "sent_at"])]

    def __str__(self) -> str:
        return f"{self.kind} to {self.user.email}"
