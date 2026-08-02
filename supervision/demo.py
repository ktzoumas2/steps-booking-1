"""The §12.2 fixture — one set of data for the test suite and for demonstration.

D42: the same data proves the counts and fills the screens; two sets would
diverge. So this is a module rather than only a command, and the tests import it.

**Everything here is invented.** Names are made up and every address is
`@example.org` (§11 forbids committing real data or fixtures derived from it).
No client data appears, because the app holds none.

Sessions are placed **relative to a reference instant**, never on fixed calendar
dates (§12.2). Combined with the supplied clock (§11), that is what lets a test
stand at any point in a session's life, and stops the fixture rotting the moment
it is written.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from supervision import review as review_service
from supervision.clock import today_in_berlin
from supervision.models import (
    Mode,
    Registration,
    RegistrationSource,
    Role,
    Session,
    SessionStatus,
    Settings,
    User,
)

ADMIN = ("Kim", "Ackermann", "admin@example.org")

SUPERVISORS = [
    ("Johanna", "Böttcher", "boettcher@example.org", "Tiefenpsychologie, Schwerpunkt Trauma"),
    ("Miriam", "Krause", "krause@example.org", "Systemische Therapie"),
]

PARTICIPANTS = [
    ("Amir", "Haddad"), ("Nour", "Saleh"), ("Lena", "Vogt"),
    ("Tomas", "Nowak"), ("Sara", "Behrend"), ("Jonas", "Keller"),
    ("Rana", "Aziz"), ("Elif", "Yilmaz"), ("Paul", "Grimm"),
    ("Mira", "Lindqvist"), ("Ivan", "Petrov"), ("Chloé", "Marchand"),
]


@dataclass
class Fixture:
    admin: User = None
    supervisors: list[User] = field(default_factory=list)
    participants: list[User] = field(default_factory=list)
    sessions: dict[str, Session] = field(default_factory=dict)


def build(reference: dt.datetime) -> Fixture:
    """Create the whole §12.2 fixture against a reference instant."""
    fixture = Fixture()
    today = today_in_berlin(reference)

    def day(offset: int) -> dt.date:
        return today + dt.timedelta(days=offset)

    def monday_of(offset_weeks: int) -> dt.date:
        anchor = day(offset_weeks * 7)
        return anchor - dt.timedelta(days=anchor.isoweekday() - 1)

    fixture.admin = User.objects.create_user(
        first_name=ADMIN[0], last_name=ADMIN[1], email=ADMIN[2],
        role=Role.ADMIN, now=reference,
    )
    for first, last, email, focus in SUPERVISORS:
        fixture.supervisors.append(
            User.objects.create_user(
                first_name=first, last_name=last, email=email,
                role=Role.SUPERVISOR, now=reference, focus_area=focus,
            )
        )
    for first, last in PARTICIPANTS:
        fixture.participants.append(
            User.objects.create_user(
                first_name=first, last_name=last,
                email=f"{last.lower()}@example.org".replace("é", "e"),
                role=Role.PARTICIPANT, now=reference,
            )
        )

    settings = Settings.load()
    settings.zoom_url = "https://example.org/zoom/steps-supervision"
    settings.save()

    boettcher, krause = fixture.supervisors

    def make(key, supervisor, date, hour, **overrides):
        session = Session.objects.create(
            supervisor=supervisor,
            date=date,
            start_time=dt.time(hour, 0),
            duration_minutes=overrides.pop("minutes", 90),
            mode=overrides.pop("mode", Mode.ONLINE),
            room=overrides.pop("room", ""),
            capacity=overrides.pop("capacity", 5),
            created_at=reference,
            updated_at=reference,
            **overrides,
        )
        fixture.sessions[key] = session
        return session

    # --- The past, three ISO weeks of it -----------------------------------
    #
    # `reviewed_past` and `unreviewed_past` differ only in whether a human
    # opened them, which drives the export sign-off (§7.3 A2) and must never
    # drive a count (§9.1).
    reviewed = make("reviewed_past", boettcher, monday_of(-3) + dt.timedelta(days=1), 10)
    unreviewed = make("unreviewed_past", krause, monday_of(-2) + dt.timedelta(days=2), 14,
                      mode=Mode.IN_PERSON, room="2.14")
    not_held = make("not_held", boettcher, monday_of(-2) + dt.timedelta(days=4), 10)
    cancelled = make("cancelled", krause, monday_of(-1) + dt.timedelta(days=1), 16)
    walk_in_session = make("with_walk_in", boettcher, monday_of(-1) + dt.timedelta(days=3), 10)

    # --- The weeks to come --------------------------------------------------
    #
    # Next week is deliberately already at `weekly_session_cap`, so the block of
    # §6.1 can be tried without first having to create it.
    make("next_week_a", boettcher, monday_of(1) + dt.timedelta(days=1), 10)
    make("next_week_b", krause, monday_of(1) + dt.timedelta(days=3), 14,
         mode=Mode.IN_PERSON, room="1.09")
    make("full", boettcher, monday_of(2) + dt.timedelta(days=1), 10, capacity=2)
    make("roomy", krause, monday_of(3) + dt.timedelta(days=2), 14, minutes=120)

    cancelled.status = SessionStatus.CANCELLED
    cancelled.cancelled_at = reference
    cancelled.cancelled_by = fixture.admin
    cancelled.save()

    # --- Who was where ------------------------------------------------------
    people = fixture.participants

    for participant in people[:4]:
        Registration.objects.create(
            session=reviewed, user=participant, created_at=reference
        )
    # One recorded absence, so `sessions_attended` and `sessions_registered`
    # genuinely differ (§12.2).
    absent = Registration.objects.get(session=reviewed, user=people[3])
    absent.attended = False
    absent.attendance_recorded_at = reference
    absent.attendance_recorded_by = boettcher
    absent.save()
    reviewed.took_place = True
    reviewed.confirmed_at = reference
    reviewed.confirmed_by = boettcher
    reviewed.save()

    for participant in people[4:8]:
        Registration.objects.create(
            session=unreviewed, user=participant, created_at=reference
        )
    for participant in people[:3]:
        Registration.objects.create(
            session=not_held, user=participant, created_at=reference
        )
    for participant in people[8:11]:
        Registration.objects.create(
            session=cancelled, user=participant, created_at=reference,
            cancelled_at=reference,
        )

    for participant in people[:2]:
        Registration.objects.create(
            session=walk_in_session, user=participant, created_at=reference
        )
    # Someone who turned up without signing up: counts as attended, never as
    # registered (D27).
    Registration.objects.create(
        session=walk_in_session,
        user=people[5],
        source=RegistrationSource.ADDED_AT_CONFIRMATION,
        attended=True,
        created_at=reference,
        attendance_recorded_at=reference,
        attendance_recorded_by=boettcher,
    )

    review_service.save_review(
        not_held, by=boettcher, now=reference, took_place=False
    )

    # The one at capacity, for the `Ausgebucht` state and the last-seat race.
    full = fixture.sessions["full"]
    for participant in people[:2]:
        Registration.objects.create(
            session=full, user=participant, created_at=reference
        )
    # And a few people already signed up for next week, so the screens are not
    # uniformly empty.
    for participant in people[2:5]:
        Registration.objects.create(
            session=fixture.sessions["next_week_a"], user=participant,
            created_at=reference,
        )

    return fixture
