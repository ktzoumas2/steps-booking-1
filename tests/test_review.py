"""§12.3 acceptance criteria 43–49 and 52–54 — the assumed-held default (D29).

The point of D29 is that the *normal* case needs nobody to do anything, so most
of these tests are about what is true when no human has touched a thing.
"""

import datetime as dt

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from supervision import counting, registrations as registration_service
from supervision import scheduling
from supervision.clock import (
    FixedClock,
    today_in_berlin,
    using_clock,
    wall_clock_to_instant,
)
from supervision.models import (
    Mode,
    Registration,
    RegistrationSource,
    Role,
    Session,
    SessionStatus,
    User,
)

REFERENCE = wall_clock_to_instant(dt.date(2026, 9, 2), dt.time(10, 0))
BACKEND = "supervision.auth_backends.MagicLinkBackend"


def make_user(email, role, last_name="Muster"):
    return User.objects.create_user(
        first_name="Alex", last_name=last_name, email=email, role=role, now=REFERENCE
    )


def make_session(supervisor, *, in_days, minutes=90, capacity=5, **overrides):
    return Session.objects.create(
        supervisor=supervisor,
        date=today_in_berlin(REFERENCE + dt.timedelta(days=in_days)),
        start_time=overrides.pop("start_time", dt.time(10, 0)),
        duration_minutes=minutes,
        mode=Mode.ONLINE,
        capacity=capacity,
        created_at=REFERENCE,
        updated_at=REFERENCE,
        **overrides,
    )


class ReviewScaffold(TestCase):
    def setUp(self):
        self.clock = FixedClock(REFERENCE)
        self.enterContext(using_clock(self.clock))
        self.scheduler = scheduling.RecordingScheduler()
        self.enterContext(scheduling.using_scheduler(self.scheduler))
        self.supervisor = make_user("sv@example.org", Role.SUPERVISOR, "Böttcher")
        self.other_supervisor = make_user("sv2@example.org", Role.SUPERVISOR, "Krause")
        self.admin = make_user("admin@example.org", Role.ADMIN)
        self.amir = make_user("amir@example.org", Role.PARTICIPANT, "Haddad")
        self.nour = make_user("nour@example.org", Role.PARTICIPANT, "Saleh")

        self.session = make_session(self.supervisor, in_days=-7)
        for participant in (self.amir, self.nour):
            Registration.objects.create(
                session=self.session, user=participant, created_at=REFERENCE
            )

    def now(self):
        return self.clock.now()

    def review(self, data=None, user=None, session=None):
        self.client.force_login(user or self.supervisor, backend=BACKEND)
        return self.client.post(
            reverse("session_review", args=[(session or self.session).pk]),
            data or {"action": "as_planned"},
        )

    def held_by(self, supervisor):
        rows = counting.sessions_held_by_supervisor(self.now())
        return next(
            (r["sessions_held"] for r in rows if r["supervisor"] == supervisor), 0
        )

    def attended_by(self, participant):
        return len(counting.attended_registrations(self.now(), participant=participant))


class AssumedHeldTests(ReviewScaffold):
    """Criterion 43 — the end time passing is the only event."""

    def test_a_session_counts_for_everyone_the_moment_it_ends_untouched(self):
        mail.outbox.clear()
        future = make_session(self.supervisor, in_days=7)
        Registration.objects.create(
            session=future, user=self.amir, created_at=REFERENCE
        )

        # Before it ends it counts for nobody...
        self.clock.set(future.starts_at + dt.timedelta(minutes=1))
        self.assertEqual(self.held_by(self.supervisor), 1)  # only the older one
        self.assertEqual(self.attended_by(self.amir), 1)

        # ...and the instant it ends, it counts for both, with nobody having
        # touched it and no mail sent.
        self.clock.set(future.ends_at)
        self.assertEqual(self.held_by(self.supervisor), 2)
        self.assertEqual(self.attended_by(self.amir), 2)
        self.assertIsNone(future.took_place)
        self.assertFalse(future.is_reviewed)
        self.assertEqual(mail.outbox, [])

    def test_an_unreviewed_session_counts_exactly_like_a_reviewed_one(self):
        # Criterion 49.
        reviewed = make_session(self.supervisor, in_days=-14)
        Registration.objects.create(
            session=reviewed, user=self.amir, created_at=REFERENCE
        )
        self.review(session=reviewed)

        self.assertEqual(self.held_by(self.supervisor), 2)
        self.assertEqual(self.attended_by(self.amir), 2)
        # The only difference is what A2 is shown before exporting.
        unreviewed = counting.unreviewed_in_range(self.now())
        self.assertEqual([s.pk for s in unreviewed], [self.session.pk])

    def test_a_sixty_and_a_hundred_and_twenty_minute_session_each_count_as_one(self):
        # Criterion 54 — duration never enters the billing figure.
        make_session(self.supervisor, in_days=-6, minutes=60)
        make_session(self.supervisor, in_days=-5, minutes=120)

        row = counting.sessions_held_by_supervisor(self.now())[0]

        self.assertEqual(row["sessions_held"], 3)
        self.assertEqual(row["total_minutes"], 90 + 60 + 120)

    def test_a_cancelled_session_counts_for_nobody(self):
        self.session.status = SessionStatus.CANCELLED
        self.session.save()

        self.assertEqual(self.held_by(self.supervisor), 0)
        self.assertEqual(self.attended_by(self.amir), 0)


class SavingUnchangedTests(ReviewScaffold):
    """Criterion 44 — "I looked, it was fine" is a real action."""

    def test_saving_unchanged_marks_it_reviewed_and_moves_no_count(self):
        before = self.held_by(self.supervisor)
        mail.outbox.clear()

        self.review()

        self.session.refresh_from_db()
        self.assertTrue(self.session.is_reviewed)
        self.assertEqual(self.session.confirmed_at, REFERENCE)
        self.assertEqual(self.session.confirmed_by, self.supervisor)
        self.assertEqual(self.held_by(self.supervisor), before)
        self.assertEqual(self.attended_by(self.amir), 1)
        # Criterion 52 — no email or invite for a review.
        self.assertEqual(mail.outbox, [])

    def test_saving_unchanged_leaves_the_registrations_alone(self):
        # Nobody made a claim about any individual, and the rows should say so:
        # `attendance_recorded_by` is what gets reached for when a correction is
        # disputed (§4.3).
        self.review()

        for registration in Registration.objects.all():
            self.assertIsNone(registration.attended)
            self.assertIsNone(registration.attendance_recorded_by)

    def test_reopening_shows_who_last_reviewed_it_and_when(self):
        self.review()

        self.client.force_login(self.supervisor, backend=BACKEND)
        response = self.client.get(reverse("session_review", args=[self.session.pk]))

        self.assertContains(response, "Zuletzt geprüft von Alex Böttcher")
        self.assertContains(response, "02.09.2026")


class DidNotTakePlaceTests(ReviewScaffold):
    """Criterion 45 — it counts for nobody, and the app warns first."""

    def test_the_screen_warns_before_saving(self):
        self.client.force_login(self.supervisor, backend=BACKEND)

        response = self.client.get(
            reverse("session_not_held", args=[self.session.pk])
        )

        self.assertContains(response, "zählt dann für niemanden mehr")

    def test_recording_it_removes_the_session_from_every_count(self):
        self.assertEqual(self.held_by(self.supervisor), 1)
        self.assertEqual(self.attended_by(self.amir), 1)
        mail.outbox.clear()

        self.review({"action": "not_held"})

        self.session.refresh_from_db()
        self.assertIs(self.session.took_place, False)
        self.assertEqual(self.held_by(self.supervisor), 0)
        self.assertEqual(self.attended_by(self.amir), 0)
        self.assertEqual(self.attended_by(self.nour), 0)
        # D12 — participants are not notified. They were there, or they weren't.
        self.assertEqual(mail.outbox, [])

    def test_it_overrides_attendance_rows_beneath_it(self):
        # §9.1 — a recorded no-show overrides every `attended` below it.
        Registration.objects.update(attended=True)

        self.review({"action": "not_held"})

        self.assertEqual(self.attended_by(self.amir), 0)


class AttendanceCorrectionTests(ReviewScaffold):
    def test_unticking_one_person_leaves_everyone_else_counting(self):
        # Criterion 46.
        amir_row = Registration.objects.get(user=self.amir)
        nour_row = Registration.objects.get(user=self.nour)

        self.review({"action": "save", "present": [str(nour_row.pk)]})

        amir_row.refresh_from_db()
        self.assertIs(amir_row.attended, False)
        self.assertEqual(amir_row.attendance_recorded_by, self.supervisor)
        self.assertEqual(amir_row.attendance_recorded_at, REFERENCE)
        self.assertEqual(self.attended_by(self.amir), 0)
        # The session still counts for the supervisor and for everyone else.
        self.assertEqual(self.held_by(self.supervisor), 1)
        self.assertEqual(self.attended_by(self.nour), 1)

    def test_someone_who_came_without_signing_up_can_be_added(self):
        # Criterion 47.
        walk_in = make_user("w@example.org", Role.PARTICIPANT, "Neumann")
        rows = Registration.objects.filter(session=self.session)

        self.review(
            {
                "action": "save",
                "present": [str(r.pk) for r in rows],
                "add": [str(walk_in.pk)],
            }
        )

        added = Registration.objects.get(user=walk_in)
        self.assertEqual(added.source, RegistrationSource.ADDED_AT_CONFIRMATION)
        self.assertIs(added.attended, True)
        self.assertEqual(self.attended_by(walk_in), 1)

    def test_someone_added_in_error_is_removed_outright(self):
        # Criterion 47, second half.
        walk_in = make_user("w@example.org", Role.PARTICIPANT)
        added = Registration.objects.create(
            session=self.session,
            user=walk_in,
            source=RegistrationSource.ADDED_AT_CONFIRMATION,
            attended=True,
            created_at=REFERENCE,
        )

        self.review({"action": "save", "remove": [str(added.pk)]})

        self.assertFalse(Registration.objects.filter(pk=added.pk).exists())

    def test_a_real_sign_up_removed_in_error_is_marked_absent_not_deleted(self):
        # §6.4 — deleting it would erase the fact that they said they were coming.
        amir_row = Registration.objects.get(user=self.amir)

        self.review({"action": "save", "remove": [str(amir_row.pk)]})

        amir_row.refresh_from_db()
        self.assertIs(amir_row.attended, False)
        self.assertTrue(Registration.objects.filter(pk=amir_row.pk).exists())

    def test_adding_someone_in_the_same_save_that_records_attendance(self):
        # The tick list can only ever name rows that were on the screen, so a
        # row created by this very save must not be swept up by it and marked
        # absent. Found the hard way.
        walk_in = make_user("w@example.org", Role.PARTICIPANT, "Neumann")
        nour_row = Registration.objects.get(user=self.nour)

        self.review(
            {
                "action": "save",
                "present": [str(nour_row.pk)],  # Amir was absent
                "add": [str(walk_in.pk)],       # and someone else turned up
            }
        )

        self.assertEqual(self.attended_by(self.amir), 0)
        self.assertEqual(self.attended_by(self.nour), 1)
        self.assertEqual(self.attended_by(walk_in), 1)

    def test_removing_a_name_beats_ticking_it_in_the_same_save(self):
        amir_row = Registration.objects.get(user=self.amir)

        self.review(
            {
                "action": "save",
                "present": [str(amir_row.pk)],
                "remove": [str(amir_row.pk)],
            }
        )

        amir_row.refresh_from_db()
        self.assertIs(amir_row.attended, False)

    def test_someone_added_at_confirmation_counts_attended_but_not_registered(self):
        # Criterion 60, which the counting rules already decide (D27).
        walk_in = make_user("w@example.org", Role.PARTICIPANT)
        self.review({"action": "save", "add": [str(walk_in.pk)]})

        self.assertEqual(self.attended_by(walk_in), 1)
        self.assertEqual(
            counting.sessions_registered_count(self.now(), walk_in), 0
        )
        self.assertEqual(counting.sessions_registered_count(self.now(), self.amir), 1)


class UndoingAReviewTests(ReviewScaffold):
    """Criterion 48 — nothing about a review is one-way."""

    def test_an_absence_can_be_re_ticked_and_the_count_follows_immediately(self):
        amir_row = Registration.objects.get(user=self.amir)
        nour_row = Registration.objects.get(user=self.nour)
        self.review({"action": "save", "present": [str(nour_row.pk)]})
        self.assertEqual(self.attended_by(self.amir), 0)

        self.review(
            {"action": "save", "present": [str(amir_row.pk), str(nour_row.pk)]}
        )

        amir_row.refresh_from_db()
        self.assertIs(amir_row.attended, True)
        self.assertEqual(self.attended_by(self.amir), 1)

    def test_did_not_take_place_can_be_reversed(self):
        self.review({"action": "not_held"})
        self.assertEqual(self.held_by(self.supervisor), 0)

        self.review({"action": "as_planned"})

        self.session.refresh_from_db()
        self.assertIs(self.session.took_place, True)
        self.assertEqual(self.held_by(self.supervisor), 1)
        self.assertEqual(self.attended_by(self.amir), 1)

    def test_corrections_never_send_mail(self):
        # Criterion 52 — a "you have been marked absent" email starts an
        # argument the app cannot host (D17).
        walk_in = make_user("w@example.org", Role.PARTICIPANT)
        amir_row = Registration.objects.get(user=self.amir)
        mail.outbox.clear()

        self.review({"action": "save", "present": [], "add": [str(walk_in.pk)]})
        self.review({"action": "not_held"})
        self.review({"action": "save", "present": [str(amir_row.pk)]})

        self.assertEqual(mail.outbox, [])


class ReviewPermissionTests(ReviewScaffold):
    def test_a_supervisor_cannot_review_someone_elses_session(self):
        response = self.review(user=self.other_supervisor)

        self.assertRedirects(response, reverse("home"), target_status_code=302)
        self.session.refresh_from_db()
        self.assertFalse(self.session.is_reviewed)

    def test_an_admin_can_review_anyones_session(self):
        self.review(user=self.admin)

        self.session.refresh_from_db()
        self.assertEqual(self.session.confirmed_by, self.admin)

    def test_a_participant_cannot_review_anything(self):
        self.review(user=self.amir)

        self.session.refresh_from_db()
        self.assertFalse(self.session.is_reviewed)

    def test_a_session_that_has_not_ended_cannot_be_reviewed(self):
        future = make_session(self.supervisor, in_days=7)

        response = self.review(session=future)

        self.assertRedirects(response, reverse("home"), target_status_code=302)
        future.refresh_from_db()
        self.assertFalse(future.is_reviewed)

    def test_a_cancelled_session_is_not_reviewed(self):
        # §6.3 — *called off* and *did not happen* are different statements.
        self.session.status = SessionStatus.CANCELLED
        self.session.save()

        response = self.review()

        self.assertRedirects(response, reverse("home"), target_status_code=302)

    def test_there_is_no_time_limit_on_a_correction(self):
        # D16 — a wrong number that cannot be corrected is worse than a late edit.
        self.clock.set(REFERENCE + dt.timedelta(days=400))
        amir_row = Registration.objects.get(user=self.amir)

        self.review({"action": "save", "present": [str(amir_row.pk)]})

        self.session.refresh_from_db()
        self.assertTrue(self.session.is_reviewed)


class CountAgainstAFixtureTests(ReviewScaffold):
    """Criterion 53, against a hand-built fixture of the §12.2 shape."""

    def test_per_supervisor_counts_match_a_fixture_of_every_kind_of_session(self):
        held_unreviewed = self.session  # already in the fixture
        held_reviewed = make_session(self.supervisor, in_days=-6)
        not_held = make_session(self.supervisor, in_days=-5)
        cancelled = make_session(self.supervisor, in_days=-4)
        still_to_come = make_session(self.supervisor, in_days=7)
        someone_elses = make_session(self.other_supervisor, in_days=-3)

        self.review(session=held_reviewed)
        self.review({"action": "not_held"}, session=not_held)
        cancelled.status = SessionStatus.CANCELLED
        cancelled.save()

        rows = {
            row["supervisor"]: row["sessions_held"]
            for row in counting.sessions_held_by_supervisor(self.now())
        }

        # Ended, not cancelled, not recorded as did-not-take-place. Reviewed or
        # not makes no difference (§9.1).
        self.assertEqual(rows[self.supervisor], 2)
        self.assertEqual(rows[self.other_supervisor], 1)
        self.assertNotIn(still_to_come.pk, [s.pk for s in counting.sessions_that_count(self.now())])
        self.assertIn(held_unreviewed.pk, [s.pk for s in counting.sessions_that_count(self.now())])

    def test_the_date_range_is_inclusive_at_both_ends(self):
        older = make_session(self.supervisor, in_days=-20)

        exactly = counting.sessions_held_by_supervisor(
            self.now(), start=older.date, end=self.session.date
        )
        self.assertEqual(exactly[0]["sessions_held"], 2)

        narrower = counting.sessions_held_by_supervisor(
            self.now(),
            start=older.date + dt.timedelta(days=1),
            end=self.session.date - dt.timedelta(days=1),
        )
        self.assertEqual(narrower, [])

    def test_a_cancelled_registration_counts_for_nobody(self):
        # §9.1 — even if the participant turned up anyway; the supervisor adds
        # them back on review and that row is what counts.
        future = make_session(self.supervisor, in_days=7)
        registration_service.sign_up(future, self.amir, REFERENCE)
        registration_service.cancel_place(future, self.amir, REFERENCE)
        self.clock.set(future.ends_at)

        self.assertEqual(self.attended_by(self.amir), 1)  # the older one only
