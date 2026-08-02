"""The §12.2 fixture is the shape §12.2 asks for — and D42's single source.

Several acceptance criteria check counts "against a hand-built fixture". This
asserts the fixture actually contains each thing those criteria need, so a
change that quietly drops, say, the participant added at confirmation fails here
rather than making some other test pass for the wrong reason.
"""

import datetime as dt

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from io import StringIO

from supervision import counting, demo, scheduling
from supervision.clock import (
    FixedClock,
    iso_week,
    using_clock,
    wall_clock_to_instant,
)
from supervision.models import (
    Registration,
    RegistrationSource,
    Role,
    Session,
    SessionStatus,
    Settings,
    User,
)

REFERENCE = wall_clock_to_instant(dt.date(2026, 9, 2), dt.time(10, 0))


class FixtureShapeTests(TestCase):
    def setUp(self):
        self.clock = FixedClock(REFERENCE)
        self.enterContext(using_clock(self.clock))
        self.enterContext(scheduling.using_scheduler(scheduling.RecordingScheduler()))
        self.fixture = demo.build(REFERENCE)

    def test_the_programmes_real_shape(self):
        # §12.2, §11 — roughly twelve participants, a handful of supervisors,
        # one admin.
        self.assertEqual(User.objects.filter(role=Role.ADMIN).count(), 1)
        self.assertEqual(User.objects.filter(role=Role.SUPERVISOR).count(), 2)
        self.assertEqual(User.objects.filter(role=Role.PARTICIPANT).count(), 12)

    def test_nothing_but_invented_names_and_example_addresses(self):
        # §11 — no real data, and no fixture derived from it.
        for email in User.objects.values_list("email", flat=True):
            self.assertTrue(email.endswith("@example.org"), email)
        self.assertNotIn("phb.de", Settings.load().zoom_url)

    def test_sessions_span_at_least_four_iso_weeks(self):
        weeks = {iso_week(session.date) for session in Session.objects.all()}
        self.assertGreaterEqual(len(weeks), 4)

    def test_one_week_is_already_at_the_cap(self):
        # So the block of §6.1 can be tried without first having to create it.
        cap = Settings.load().weekly_session_cap
        weeks = {}
        for session in Session.objects.filter(status=SessionStatus.OFFERED):
            weeks[iso_week(session.date)] = weeks.get(iso_week(session.date), 0) + 1
        self.assertIn(cap, weeks.values())

    def test_one_session_is_at_capacity(self):
        full = self.fixture.sessions["full"]
        self.assertTrue(full.is_full)
        self.assertTrue(full.is_upcoming(REFERENCE))

    def test_one_cancelled_and_one_not_held_counting_for_nobody_each(self):
        cancelled = self.fixture.sessions["cancelled"]
        not_held = self.fixture.sessions["not_held"]
        not_held.refresh_from_db()

        self.assertEqual(cancelled.status, SessionStatus.CANCELLED)
        self.assertIs(not_held.took_place, False)

        counted = {s.pk for s in counting.sessions_that_count(REFERENCE)}
        self.assertNotIn(cancelled.pk, counted)
        self.assertNotIn(not_held.pk, counted)

    def test_one_reviewed_and_one_unreviewed_past_session(self):
        reviewed = self.fixture.sessions["reviewed_past"]
        unreviewed = self.fixture.sessions["unreviewed_past"]

        self.assertTrue(reviewed.is_reviewed)
        self.assertFalse(unreviewed.is_reviewed)
        # And the difference drives the export sign-off, never a count (§9.1).
        counted = {s.pk for s in counting.sessions_that_count(REFERENCE)}
        self.assertIn(reviewed.pk, counted)
        self.assertIn(unreviewed.pk, counted)

    def test_an_absence_and_a_walk_in_make_the_two_figures_differ(self):
        absent = Registration.objects.filter(attended=False)
        walk_ins = Registration.objects.filter(
            source=RegistrationSource.ADDED_AT_CONFIRMATION
        )
        self.assertTrue(absent.exists())
        self.assertTrue(walk_ins.exists())

        rows = {
            row["participant"].pk: row
            for row in counting.participation_by_participant(REFERENCE)
        }
        walk_in = walk_ins.first()
        # Attended without ever signing up (D27).
        self.assertGreaterEqual(rows[walk_in.user_id]["sessions_attended"], 1)

        differ = [
            row
            for row in rows.values()
            if row["sessions_attended"] != row["sessions_registered"]
        ]
        self.assertTrue(differ, "the two figures should not be identical for everyone")

    def test_the_fixture_moves_with_the_reference_instant(self):
        # §12.2 — relative, never fixed dates, so it cannot rot.
        earliest = Session.objects.order_by("date").first().date
        latest = Session.objects.order_by("-date").first().date

        self.assertLess(earliest, REFERENCE.date())
        self.assertGreater(latest, REFERENCE.date())


class SeedCommandTests(TestCase):
    def test_it_refuses_to_run_on_a_database_that_already_has_people(self):
        with using_clock(FixedClock(REFERENCE)):
            User.objects.create_user(
                first_name="A", last_name="B", email="a@example.org",
                role=Role.ADMIN, now=REFERENCE,
            )
            with self.assertRaises(CommandError):
                call_command("seed_demo", stdout=StringIO())

    @override_settings(DEBUG=False)
    def test_it_refuses_to_run_outside_debug(self):
        # It invents twelve accounts; that is a demonstration, not an
        # installation step.
        with self.assertRaises(CommandError) as caught:
            call_command("seed_demo", stdout=StringIO())

        self.assertIn("DEBUG", str(caught.exception))


class DevSignInTests(TestCase):
    """The demonstration shortcut is hard gated."""

    def setUp(self):
        self.enterContext(using_clock(FixedClock(REFERENCE)))
        self.person = User.objects.create_user(
            first_name="Kim", last_name="Ackermann", email="admin@example.org",
            role=Role.ADMIN, now=REFERENCE,
        )

    @override_settings(DEBUG=True)
    def test_with_debug_on_it_signs_you_in(self):
        response = self.client.get(
            reverse("dev_sign_in_as_person", args=[self.person.pk])
        )

        self.assertRedirects(response, reverse("home"), target_status_code=302)
        self.assertEqual(self.client.session["_auth_user_id"], str(self.person.pk))

    @override_settings(DEBUG=False)
    def test_with_debug_off_the_route_does_not_exist(self):
        for url in (
            reverse("dev_sign_in_as"),
            reverse("dev_sign_in_as_person", args=[self.person.pk]),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertNotIn("_auth_user_id", self.client.session)
