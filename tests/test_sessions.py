"""§12.3 acceptance criteria 8–14 — offering sessions, and the weekly cap.

Every session below is placed relative to a reference instant, never on a fixed
calendar date (§12.2), so these tests do not rot and can stand at any point in a
session's life.
"""

import datetime as dt

from django.core import mail
from django.test import TestCase
from django.urls import reverse

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
    Role,
    Session,
    SessionStatus,
    Settings,
    User,
)
from supervision.sessions import check_weekly_cap

# A Wednesday, 10:00 Berlin. Every date below is an offset from this.
REFERENCE = wall_clock_to_instant(dt.date(2026, 9, 2), dt.time(10, 0))


def make_user(email, role, **overrides):
    return User.objects.create_user(
        first_name="Alex",
        last_name=overrides.pop("last_name", "Muster"),
        email=email,
        role=role,
        now=REFERENCE,
        **overrides,
    )


def make_session(supervisor, *, days_from_reference, hour=10, **overrides):
    fields = {
        "date": today_in_berlin(REFERENCE + dt.timedelta(days=days_from_reference)),
        "start_time": dt.time(hour, 0),
        "duration_minutes": 90,
        "mode": Mode.ONLINE,
        "capacity": 5,
        "created_at": REFERENCE,
        "updated_at": REFERENCE,
    } | overrides
    return Session.objects.create(supervisor=supervisor, **fields)


class SessionScaffold(TestCase):
    def setUp(self):
        self.clock = FixedClock(REFERENCE)
        self.enterContext(using_clock(self.clock))
        self.supervisor = make_user("sv@example.org", Role.SUPERVISOR, last_name="Böttcher")
        self.other_supervisor = make_user("sv2@example.org", Role.SUPERVISOR, last_name="Krause")
        self.admin = make_user("admin@example.org", Role.ADMIN)
        self.participant = make_user("p@example.org", Role.PARTICIPANT)

    def sign_in(self, user):
        self.client.force_login(user, backend="supervision.auth_backends.MagicLinkBackend")

    def offer(self, user=None, confirm=False, **overrides):
        """Post the S2 form the way the screen does."""
        self.sign_in(user or self.supervisor)
        form = {
            "date": (REFERENCE + dt.timedelta(days=7)).date().isoformat(),
            "start_time": "10:00",
            "duration_minutes": "90",
            "mode": Mode.ONLINE,
            "room": "",
            "capacity": "5",
        } | overrides
        if confirm:
            form["confirm_week"] = "1"
        return self.client.post(reverse("session_new"), form)


class OfferingSessionsTests(SessionScaffold):
    def test_an_in_person_session_appears_to_participants_immediately(self):
        # Criterion 8.
        self.offer(mode=Mode.IN_PERSON, room="2.14")

        session = Session.objects.get()
        self.assertEqual(session.supervisor, self.supervisor)
        self.assertEqual(session.room, "2.14")
        self.assertEqual(session.status, SessionStatus.OFFERED)

        self.sign_in(self.participant)
        listing = self.client.get(reverse("participant_home"))
        self.assertContains(listing, "Raum 2.14")
        self.assertContains(listing, "Böttcher")

    def test_in_person_cannot_be_saved_without_a_room(self):
        # Criterion 14, with the exact wording of §14.9.
        response = self.offer(mode=Mode.IN_PERSON, room="")

        self.assertEqual(Session.objects.count(), 0)
        self.assertContains(response, "Termine vor Ort brauchen einen Ort")

    def test_an_online_session_shows_the_settings_zoom_link_everywhere(self):
        # Criterion 9 — the link lives once in settings (§4.2) and is read at
        # send time, so changing it changes every future session at once.
        settings = Settings.load()
        settings.zoom_url = "https://zoom.example.org/j/first"
        settings.save()

        self.offer(mode=Mode.ONLINE)
        self.assertIn("https://zoom.example.org/j/first", mail.outbox[-1].body)

        settings.zoom_url = "https://zoom.example.org/j/second"
        settings.save()

        session = Session.objects.get()
        from supervision import mail as mailer

        mailer.send(
            EmailKind.SESSION_CREATED,
            user=self.supervisor,
            now=self.clock.now(),
            session=session,
            subject_params={"date": "x"},
        )
        self.assertIn("https://zoom.example.org/j/second", mail.outbox[-1].body)
        self.assertNotIn("first", mail.outbox[-1].body)

    def test_a_session_cannot_be_offered_in_the_past(self):
        response = self.offer(
            date=(REFERENCE - dt.timedelta(days=1)).date().isoformat()
        )

        self.assertEqual(Session.objects.count(), 0)
        self.assertContains(response, "liegt in der Vergangenheit")

    def test_the_supervisor_is_sent_an_invite_for_their_own_session(self):
        # §8.1, D21 — the person who has to be there needs it in their calendar.
        self.offer()

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["sv@example.org"])
        logged = EmailLog.objects.get(kind=EmailKind.SESSION_CREATED)
        self.assertEqual(logged.session, Session.objects.get())

    def test_a_new_session_gets_a_calendar_uid_and_sequence_zero(self):
        # §4.2, §8.2 — generated once, never reused or changed.
        self.offer()

        session = Session.objects.get()
        self.assertTrue(session.calendar_uid)
        self.assertEqual(session.calendar_sequence, 0)

    def test_a_participant_cannot_offer_a_session(self):
        response = self.offer(user=self.participant)

        self.assertEqual(Session.objects.count(), 0)
        self.assertRedirects(response, reverse("home"), target_status_code=302)


class ScreensRenderTests(SessionScaffold):
    """The screens themselves open — the forms, not only the posts to them."""

    def test_the_offer_form_opens_prefilled_from_settings(self):
        # §7.2 — duration and capacity are pre-filled (§4.4).
        self.sign_in(self.supervisor)

        response = self.client.get(reverse("session_new"))

        self.assertContains(response, "Termin anbieten")
        self.assertContains(response, 'value="90"')
        self.assertContains(response, 'value="5"')

    def test_the_edit_form_opens_on_an_existing_session(self):
        session = make_session(self.supervisor, days_from_reference=7)
        self.sign_in(self.supervisor)

        response = self.client.get(reverse("session_edit", args=[session.pk]))

        self.assertContains(response, "Termin bearbeiten")

    def test_the_cancel_screen_states_the_consequence_before_the_button(self):
        # §6.3 — a cancelled session cannot be reopened.
        session = make_session(self.supervisor, days_from_reference=7)
        self.sign_in(self.supervisor)

        response = self.client.get(reverse("session_cancel", args=[session.pk]))

        self.assertContains(response, "verschwindet aus ihren Kalendern")

    def test_only_an_admin_is_asked_which_supervisor(self):
        # §3 — a supervisor offers their own sessions and never anyone else's.
        self.sign_in(self.supervisor)
        self.assertNotContains(self.client.get(reverse("session_new")), 'name="supervisor"')

        self.sign_in(self.admin)
        self.assertContains(self.client.get(reverse("session_new")), 'name="supervisor"')


class WeeklyCapTests(SessionScaffold):
    """§6.1 — programme-wide, ISO weeks, and the message names the clash."""

    def fill_the_week(self):
        """Two sessions in the week the tests then try to add a third to."""
        monday = (REFERENCE + dt.timedelta(days=5)).date()  # the following Monday
        while monday.isoweekday() != 1:
            monday += dt.timedelta(days=1)
        first = make_session(self.supervisor, days_from_reference=0, hour=10)
        first.date = monday
        first.save()
        second = make_session(self.other_supervisor, days_from_reference=0, hour=14)
        second.date = monday + dt.timedelta(days=2)
        second.save()
        return monday, [first, second]

    def test_a_third_session_in_a_full_week_is_blocked_and_names_the_other_two(self):
        # Criterion 10.
        monday, existing = self.fill_the_week()

        response = self.offer(date=(monday + dt.timedelta(days=4)).isoformat())

        self.assertEqual(Session.objects.count(), 2)
        self.assertContains(response, "Bitte wählen Sie eine andere Woche")
        # Both clashing sessions are named — date, time and supervisor (D41).
        self.assertContains(response, "Böttcher")
        self.assertContains(response, "Krause")
        self.assertContains(response, "10:00 Uhr")
        self.assertContains(response, "14:00 Uhr")

    def test_the_cap_counts_every_supervisor_not_just_the_one_saving(self):
        # §6.1 — programme-wide, not per supervisor.
        monday, _ = self.fill_the_week()

        response = self.offer(
            user=self.other_supervisor, date=(monday + dt.timedelta(days=4)).isoformat()
        )

        self.assertEqual(Session.objects.count(), 2)
        self.assertContains(response, "Bitte wählen Sie eine andere Woche")

    def test_with_enforcement_off_the_same_attempt_warns_and_can_be_confirmed(self):
        # Criterion 11.
        settings = Settings.load()
        settings.enforce_weekly_cap = False
        settings.save()
        monday, _ = self.fill_the_week()
        date = (monday + dt.timedelta(days=4)).isoformat()

        warned = self.offer(date=date)
        self.assertEqual(Session.objects.count(), 2)
        self.assertContains(warned, "Trotzdem speichern?")

        self.offer(date=date, confirm=True)
        self.assertEqual(Session.objects.count(), 3)

    def test_an_admin_can_override_the_block(self):
        # Criterion 13 — with an explicit confirmation step (§6.1).
        monday, _ = self.fill_the_week()
        date = (monday + dt.timedelta(days=4)).isoformat()

        asked = self.offer(user=self.admin, date=date, supervisor=self.supervisor.pk)
        self.assertEqual(Session.objects.count(), 2)
        self.assertContains(asked, "überschreiten Sie die Obergrenze")

        self.offer(
            user=self.admin, date=date, supervisor=self.supervisor.pk, confirm=True
        )
        self.assertEqual(Session.objects.count(), 3)

    def test_a_cancelled_session_frees_its_slot_immediately(self):
        monday, existing = self.fill_the_week()
        existing[0].status = SessionStatus.CANCELLED
        existing[0].save()

        self.offer(date=(monday + dt.timedelta(days=4)).isoformat())

        self.assertEqual(Session.objects.filter(status=SessionStatus.OFFERED).count(), 2)

    def test_the_week_is_an_iso_week_so_sunday_and_monday_are_different_weeks(self):
        monday, _ = self.fill_the_week()
        sunday = monday - dt.timedelta(days=1)

        # The Sunday before belongs to the previous ISO week, so it is not full.
        self.offer(date=sunday.isoformat())

        self.assertEqual(Session.objects.count(), 3)


class EditingTests(SessionScaffold):
    """§6.5 — and criterion 12, the trap of a session blocking its own edit."""

    def setUp(self):
        super().setUp()
        self.session = make_session(self.supervisor, days_from_reference=7)

    def edit(self, user=None, confirm=False, **overrides):
        self.sign_in(user or self.supervisor)
        form = {
            "date": self.session.date.isoformat(),
            "start_time": self.session.start_time.strftime("%H:%M"),
            "duration_minutes": str(self.session.duration_minutes),
            "mode": self.session.mode,
            "room": self.session.room,
            "capacity": str(self.session.capacity),
        } | overrides
        if confirm:
            form["confirm_week"] = "1"
        return self.client.post(
            reverse("session_edit", args=[self.session.pk]), form
        )

    def test_saving_without_moving_the_date_is_not_blocked_by_its_own_existence(self):
        # Criterion 12, second half. Fill the session's own week to the cap so
        # that counting itself would block the save.
        make_session(self.other_supervisor, days_from_reference=8)
        self.assertEqual(Settings.load().weekly_session_cap, 2)

        response = self.edit(capacity="6")

        self.assertRedirects(response, reverse("supervisor_home"))
        self.session.refresh_from_db()
        self.assertEqual(self.session.capacity, 6)

    def test_moving_a_session_into_a_full_week_is_blocked_the_same_way(self):
        # Criterion 12, first half.
        full_week_monday = self.session.date + dt.timedelta(days=14)
        while full_week_monday.isoweekday() != 1:
            full_week_monday += dt.timedelta(days=1)
        for offset, supervisor in ((0, self.supervisor), (1, self.other_supervisor)):
            existing = make_session(supervisor, days_from_reference=30)
            existing.date = full_week_monday + dt.timedelta(days=offset)
            existing.save()

        response = self.edit(date=(full_week_monday + dt.timedelta(days=3)).isoformat())

        self.assertContains(response, "Bitte wählen Sie eine andere Woche")
        self.session.refresh_from_db()
        self.assertNotEqual(self.session.date, full_week_monday + dt.timedelta(days=3))

    def test_moving_a_session_notifies_and_bumps_the_calendar_sequence(self):
        # §6.5, §8.2 — same UID, higher SEQUENCE, so a calendar replaces the
        # event rather than showing two.
        uid_before = self.session.calendar_uid
        mail.outbox.clear()

        self.edit(start_time="14:00")

        self.session.refresh_from_db()
        self.assertEqual(self.session.start_time, dt.time(14, 0))
        self.assertEqual(self.session.calendar_sequence, 1)
        self.assertEqual(self.session.calendar_uid, uid_before)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("10:00 Uhr", mail.outbox[0].body)  # old
        self.assertIn("14:00 Uhr", mail.outbox[0].body)  # new

    def test_changing_only_capacity_notifies_nobody_and_does_not_bump_the_sequence(self):
        # §6.5 — capacity changes nothing a calendar or a participant needs.
        mail.outbox.clear()

        self.edit(capacity="8")

        self.session.refresh_from_db()
        self.assertEqual(self.session.capacity, 8)
        self.assertEqual(self.session.calendar_sequence, 0)
        self.assertEqual(mail.outbox, [])

    def test_a_supervisor_cannot_edit_someone_elses_session(self):
        response = self.edit(user=self.other_supervisor, capacity="9")

        self.assertRedirects(response, reverse("home"), target_status_code=302)
        self.session.refresh_from_db()
        self.assertEqual(self.session.capacity, 5)

    def test_an_admin_can_edit_anyones_session(self):
        self.edit(user=self.admin, capacity="7", supervisor=self.supervisor.pk)

        self.session.refresh_from_db()
        self.assertEqual(self.session.capacity, 7)


class CancellingTests(SessionScaffold):
    """§6.3 — cancellable until the end time, including while in progress."""

    def setUp(self):
        super().setUp()
        self.session = make_session(self.supervisor, days_from_reference=7)

    def cancel(self, user=None):
        self.sign_in(user or self.supervisor)
        return self.client.post(reverse("session_cancel", args=[self.session.pk]))

    def test_cancelling_records_who_did_it_and_when(self):
        # Criterion 51.
        mail.outbox.clear()

        self.cancel()

        self.session.refresh_from_db()
        self.assertEqual(self.session.status, SessionStatus.CANCELLED)
        self.assertEqual(self.session.cancelled_by, self.supervisor)
        self.assertEqual(self.session.cancelled_at, REFERENCE)
        self.assertEqual(self.session.calendar_sequence, 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_a_cancelled_session_drops_out_of_the_participant_list(self):
        self.cancel()

        self.sign_in(self.participant)
        self.assertContains(
            self.client.get(reverse("participant_home")), "keine Termine eingetragen"
        )

    def test_a_session_in_progress_can_still_be_cancelled(self):
        # Criterion 50 — the commonest cancellation is acted on around the start.
        self.clock.set(self.session.starts_at + dt.timedelta(minutes=10))

        self.cancel()

        self.session.refresh_from_db()
        self.assertEqual(self.session.status, SessionStatus.CANCELLED)

    def test_after_the_end_time_it_can_no_longer_be_cancelled(self):
        # §6.3 — it is recorded as "did not take place" instead (§6.4).
        self.clock.set(self.session.ends_at + dt.timedelta(seconds=1))

        response = self.cancel()

        self.assertRedirects(response, reverse("home"), target_status_code=302)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, SessionStatus.OFFERED)

    def test_an_admin_can_cancel_anyones_session(self):
        self.cancel(user=self.admin)

        self.session.refresh_from_db()
        self.assertEqual(self.session.cancelled_by, self.admin)

    def test_another_supervisor_cannot(self):
        self.cancel(user=self.other_supervisor)

        self.session.refresh_from_db()
        self.assertEqual(self.session.status, SessionStatus.OFFERED)


class DerivedStateTests(SessionScaffold):
    """§4.2 — held is derived from the end time passing, never written.

    Criterion 65: the same session, observed before, during and after its end,
    inside one test run.
    """

    def test_one_session_seen_at_three_points_in_its_life(self):
        session = make_session(self.supervisor, days_from_reference=7)

        self.assertTrue(session.is_upcoming(self.clock.now()))
        self.assertFalse(session.is_held(self.clock.now()))

        self.clock.set(session.starts_at + dt.timedelta(minutes=1))
        self.assertTrue(session.is_in_progress(self.clock.now()))
        self.assertFalse(session.is_held(self.clock.now()))

        self.clock.set(session.ends_at)
        # Nobody has touched it, and it counts (§6.4, D29).
        self.assertTrue(session.is_held(self.clock.now()))
        self.assertFalse(session.is_reviewed)

    def test_a_ten_oclock_session_stays_at_ten_across_a_dst_change(self):
        # §11, §15.1 — the wall-clock intention survives; the instant moves.
        summer = make_session(self.supervisor, days_from_reference=7)
        summer.date = dt.date(2026, 10, 21)  # CEST
        winter = make_session(self.supervisor, days_from_reference=8)
        winter.date = dt.date(2026, 11, 4)  # CET

        self.assertEqual(summer.start_time, dt.time(10, 0))
        self.assertEqual(winter.start_time, dt.time(10, 0))
        self.assertEqual(summer.starts_at.astimezone(dt.UTC).hour, 8)
        self.assertEqual(winter.starts_at.astimezone(dt.UTC).hour, 9)


class CapCheckUnitTests(SessionScaffold):
    """The cap rule itself, away from the form (§6.1)."""

    def test_a_session_does_not_count_against_itself(self):
        session = make_session(self.supervisor, days_from_reference=7)
        settings = Settings.load()

        including = check_weekly_cap(session.date, settings)
        excluding = check_weekly_cap(session.date, settings, exclude=session)

        self.assertEqual(len(including.clashing), 1)
        self.assertEqual(excluding.clashing, [])

    def test_would_exceed_is_about_the_session_being_added(self):
        settings = Settings.load()
        date = (REFERENCE + dt.timedelta(days=7)).date()

        self.assertFalse(check_weekly_cap(date, settings).would_exceed)

        make_session(self.supervisor, days_from_reference=7)
        self.assertFalse(check_weekly_cap(date, settings).would_exceed)

        make_session(self.other_supervisor, days_from_reference=7)
        self.assertTrue(check_weekly_cap(date, settings).would_exceed)
