"""§12.3 acceptance criteria 18, 21–25 — signing up, seats, and the last seat."""

import datetime as dt
import threading

from django.core import mail
from django.db import connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from supervision import registrations as registration_service
from supervision.clock import (
    FixedClock,
    today_in_berlin,
    using_clock,
    wall_clock_to_instant,
)
from supervision.models import (
    EmailKind,
    EmailLog,
    Mode,
    Registration,
    RegistrationSource,
    Role,
    Session,
    User,
)

REFERENCE = wall_clock_to_instant(dt.date(2026, 9, 2), dt.time(10, 0))
BACKEND = "supervision.auth_backends.MagicLinkBackend"


def make_user(email, role, last_name="Muster"):
    return User.objects.create_user(
        first_name="Alex", last_name=last_name, email=email, role=role, now=REFERENCE
    )


def make_session(supervisor, *, in_days=7, capacity=5, **overrides):
    return Session.objects.create(
        supervisor=supervisor,
        date=today_in_berlin(REFERENCE + dt.timedelta(days=in_days)),
        start_time=dt.time(10, 0),
        duration_minutes=90,
        mode=overrides.pop("mode", Mode.ONLINE),
        capacity=capacity,
        created_at=REFERENCE,
        updated_at=REFERENCE,
        **overrides,
    )


class SignUpScaffold(TestCase):
    def setUp(self):
        self.clock = FixedClock(REFERENCE)
        self.enterContext(using_clock(self.clock))
        self.supervisor = make_user("sv@example.org", Role.SUPERVISOR, "Böttcher")
        self.amir = make_user("amir@example.org", Role.PARTICIPANT, "Haddad")
        self.nour = make_user("nour@example.org", Role.PARTICIPANT, "Saleh")
        self.session = make_session(self.supervisor, capacity=2)
        self.client.force_login(self.amir, backend=BACKEND)

    def sign_up(self, session=None, follow=False):
        return self.client.post(
            reverse("session_sign_up", args=[(session or self.session).pk]),
            {"next": reverse("participant_home")},
            follow=follow,
        )

    def give_up(self, session=None, follow=False):
        return self.client.post(
            reverse("session_give_up_place", args=[(session or self.session).pk]),
            {"next": reverse("participant_home")},
            follow=follow,
        )

    def available(self):
        return self.client.get(reverse("participant_home"))


class SigningUpTests(SignUpScaffold):
    def test_one_tap_from_the_list_registers_and_confirms_by_email(self):
        # Criterion 21.
        mail.outbox.clear()

        response = self.sign_up()

        self.assertRedirects(response, reverse("participant_home"))
        registration = Registration.objects.get()
        self.assertEqual(registration.user, self.amir)
        self.assertEqual(registration.session, self.session)
        self.assertEqual(registration.source, RegistrationSource.SELF_SIGNUP)
        self.assertEqual(registration.created_at, REFERENCE)
        self.assertTrue(registration.is_active)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["amir@example.org"])
        self.assertIn("Angemeldet", mail.outbox[0].subject)
        self.assertEqual(
            EmailLog.objects.get(kind=EmailKind.REGISTRATION_CONFIRMED).session,
            self.session,
        )

    def test_the_button_becomes_give_up_my_place_once_registered(self):
        self.sign_up()

        listing = self.available()

        self.assertContains(listing, "Platz freigeben")
        self.assertNotContains(listing, "Anmelden</button>")

    def test_the_seat_count_is_shown_and_moves(self):
        self.assertContains(self.available(), "0 von 2 Plätzen belegt")

        self.sign_up()

        self.assertContains(self.available(), "1 von 2 Plätzen belegt")

    def test_signing_up_twice_is_not_two_places(self):
        # §6.2 — a participant cannot hold two active registrations.
        self.sign_up()
        self.sign_up()

        self.assertEqual(Registration.objects.filter(cancelled_at__isnull=True).count(), 1)

    def test_a_session_that_has_started_cannot_be_signed_up_for(self):
        self.clock.set(self.session.starts_at)

        self.sign_up()

        self.assertEqual(Registration.objects.count(), 0)

    def test_a_supervisor_cannot_sign_up(self):
        # §3 — sign-up is a participant action, and one role per person (D5).
        self.client.force_login(self.supervisor, backend=BACKEND)

        self.sign_up()

        self.assertEqual(Registration.objects.count(), 0)


class FullSessionTests(SignUpScaffold):
    def fill(self):
        registration_service.sign_up(self.session, self.amir, REFERENCE)
        registration_service.sign_up(self.session, self.nour, REFERENCE)

    def test_a_full_session_reads_full_instead_of_sign_up(self):
        # Criterion 22.
        third = make_user("t@example.org", Role.PARTICIPANT)
        self.fill()
        self.client.force_login(third, backend=BACKEND)

        listing = self.available()

        self.assertContains(listing, "Ausgebucht")
        self.assertContains(listing, "2 von 2 Plätzen belegt")

    def test_a_full_session_stays_visible_and_greyed(self):
        # Criterion 18 — a participant who cannot find a session they were told
        # about assumes the app is broken.
        third = make_user("t@example.org", Role.PARTICIPANT)
        self.fill()
        self.client.force_login(third, backend=BACKEND)

        listing = self.available()

        self.assertContains(listing, "session--full")
        self.assertContains(listing, "Mi, 09.09.2026")

    def test_someone_registered_still_sees_their_own_cancel_button_when_full(self):
        self.fill()

        listing = self.available()

        self.assertContains(listing, "Platz freigeben")
        self.assertNotContains(listing, "session--full")

    def test_signing_up_for_a_session_that_just_filled_says_exactly_that(self):
        third = make_user("t@example.org", Role.PARTICIPANT)
        self.fill()
        self.client.force_login(third, backend=BACKEND)

        response = self.sign_up(follow=True)

        # §7.4 — not a generic failure, which reads as a bug.
        self.assertContains(response, "Der letzte Platz ist an jemand anderen gegangen")
        self.assertEqual(
            Registration.objects.filter(cancelled_at__isnull=True).count(), 2
        )


class GivingUpAPlaceTests(SignUpScaffold):
    def test_cancelling_frees_the_seat_immediately_and_allows_re_registering(self):
        # Criterion 24.
        self.sign_up()
        mail.outbox.clear()

        self.give_up()

        registration = Registration.objects.get()
        self.assertFalse(registration.is_active)
        self.assertEqual(registration.cancelled_at, REFERENCE)
        self.assertContains(self.available(), "0 von 2 Plätzen belegt")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Abgemeldet", mail.outbox[0].subject)

        # And straight back in.
        self.sign_up()
        self.assertEqual(
            Registration.objects.filter(cancelled_at__isnull=True).count(), 1
        )

    def test_re_registering_reuses_the_row_rather_than_accumulating(self):
        # §4.3 — at most one active registration per (session, user), and no pile
        # of historical rows for one person changing their mind.
        for _ in range(3):
            self.sign_up()
            self.give_up()
        self.sign_up()

        self.assertEqual(Registration.objects.count(), 1)
        self.assertTrue(Registration.objects.get().is_active)

    def test_the_seat_a_cancellation_frees_can_be_taken_by_someone_else(self):
        registration_service.sign_up(self.session, self.amir, REFERENCE)
        registration_service.sign_up(self.session, self.nour, REFERENCE)
        third = make_user("t@example.org", Role.PARTICIPANT)

        registration_service.cancel_place(self.session, self.nour, REFERENCE)
        registration_service.sign_up(self.session, third, REFERENCE)

        self.assertEqual(
            set(
                Registration.objects.filter(cancelled_at__isnull=True).values_list(
                    "user__email", flat=True
                )
            ),
            {"amir@example.org", "t@example.org"},
        )

    def test_a_place_cannot_be_given_up_once_the_session_has_started(self):
        # §6.3 — allowed any time *before* the session starts.
        self.sign_up()
        self.clock.set(self.session.starts_at)

        self.give_up()

        self.assertTrue(Registration.objects.get().is_active)

    def test_the_cancelled_row_is_kept_because_it_explains_the_free_seat(self):
        self.sign_up()
        self.give_up()

        self.assertEqual(Registration.objects.count(), 1)
        self.assertIsNotNone(Registration.objects.get().cancelled_at)


class CapacityFloorTests(SignUpScaffold):
    """Criterion 25 — capacity cannot be edited below what is already taken."""

    def edit_capacity(self, to):
        self.client.force_login(self.supervisor, backend=BACKEND)
        return self.client.post(
            reverse("session_edit", args=[self.session.pk]),
            {
                "date": self.session.date.isoformat(),
                "start_time": "10:00",
                "duration_minutes": "90",
                "mode": Mode.ONLINE,
                "room": "",
                "capacity": str(to),
            },
        )

    def test_capacity_cannot_go_below_the_number_registered(self):
        registration_service.sign_up(self.session, self.amir, REFERENCE)
        registration_service.sign_up(self.session, self.nour, REFERENCE)

        response = self.edit_capacity(1)

        # §7.4 — the message names the current number, so the supervisor knows
        # the floor rather than guessing at it.
        self.assertContains(response, "Es sind bereits 2 Personen angemeldet")
        self.session.refresh_from_db()
        self.assertEqual(self.session.capacity, 2)

    def test_capacity_can_go_down_to_exactly_the_number_registered(self):
        registration_service.sign_up(self.session, self.amir, REFERENCE)

        self.edit_capacity(1)

        self.session.refresh_from_db()
        self.assertEqual(self.session.capacity, 1)

    def test_a_cancelled_registration_does_not_hold_the_floor_up(self):
        registration_service.sign_up(self.session, self.amir, REFERENCE)
        registration_service.sign_up(self.session, self.nour, REFERENCE)
        registration_service.cancel_place(self.session, self.nour, REFERENCE)

        self.edit_capacity(1)

        self.session.refresh_from_db()
        self.assertEqual(self.session.capacity, 1)


class MySessionsTabTests(SignUpScaffold):
    def test_the_tab_lists_what_the_participant_signed_up_for(self):
        self.sign_up()

        response = self.client.get(reverse("participant_my_sessions"))

        self.assertContains(response, "Mi, 09.09.2026")
        self.assertContains(response, "Böttcher")
        self.assertNotContains(response, "noch für keinen Termin angemeldet")

    def test_a_past_session_reads_as_attended_without_anyone_confirming_it(self):
        # §6.4, D29 — the end time passing is the only event.
        self.sign_up()
        self.clock.set(self.session.ends_at)

        response = self.client.get(reverse("participant_my_sessions"))

        self.assertContains(response, "Vergangene Termine")
        self.assertContains(response, "teilgenommen")

    def test_the_detail_screen_names_who_else_is_coming(self):
        registration_service.sign_up(self.session, self.amir, REFERENCE)
        registration_service.sign_up(self.session, self.nour, REFERENCE)

        response = self.client.get(reverse("session_detail", args=[self.session.pk]))

        self.assertContains(response, "Angemeldet")
        self.assertContains(response, "Alex Haddad")
        self.assertContains(response, "Alex Saleh")

    def test_the_zoom_link_appears_once_registered(self):
        from supervision.models import Settings

        settings = Settings.load()
        settings.zoom_url = "https://zoom.example.org/j/steps"
        settings.save()

        before = self.client.get(reverse("session_detail", args=[self.session.pk]))
        self.assertNotContains(before, "zoom.example.org")

        self.sign_up()

        after = self.client.get(reverse("session_detail", args=[self.session.pk]))
        self.assertContains(after, "zoom.example.org")


class LastSeatRaceTests(TransactionTestCase):
    """Criterion 23 — two simultaneous sign-ups for one remaining seat.

    A real race, on real threads, against the real database: §6.2 calls this out
    as realistic with twelve people watching the same list, and a sequential test
    would pass whether or not the check is actually atomic.
    """

    def test_exactly_one_of_two_simultaneous_signups_wins_the_last_seat(self):
        with using_clock(FixedClock(REFERENCE)):
            supervisor = make_user("sv@example.org", Role.SUPERVISOR)
            first = make_user("one@example.org", Role.PARTICIPANT)
            second = make_user("two@example.org", Role.PARTICIPANT)
            session = make_session(supervisor, capacity=1)

            ready = threading.Barrier(2)
            outcomes = {}

            def attempt(participant):
                try:
                    ready.wait(timeout=5)
                    registration_service.sign_up(session, participant, REFERENCE)
                    outcomes[participant.email] = "in"
                except registration_service.SessionFull:
                    outcomes[participant.email] = "told it filled up"
                except Exception as exc:  # noqa: BLE001 - reported, not swallowed
                    outcomes[participant.email] = f"error: {exc!r}"
                finally:
                    connections.close_all()

            threads = [
                threading.Thread(target=attempt, args=(participant,))
                for participant in (first, second)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=30)

        self.assertEqual(len(outcomes), 2, outcomes)
        # No over-booking, and no unexplained failure: one seat, one winner, and
        # the loser was told why.
        self.assertEqual(sorted(outcomes.values()), ["in", "told it filled up"], outcomes)
        self.assertEqual(
            Registration.objects.filter(
                session=session, cancelled_at__isnull=True
            ).count(),
            1,
        )
