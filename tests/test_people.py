"""§12.3 criteria 7 and 66 — A3, A4, and the deactivation rules of §4.1."""

import datetime as dt

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from supervision import people, registrations as registration_service, scheduling
from supervision.catalog import t
from supervision.clock import (
    FixedClock,
    today_in_berlin,
    using_clock,
    wall_clock_to_instant,
)
from supervision.models import (
    Mode,
    Registration,
    Role,
    Session,
    SessionStatus,
    Settings,
    User,
)

REFERENCE = wall_clock_to_instant(dt.date(2026, 9, 2), dt.time(10, 0))
BACKEND = "supervision.auth_backends.MagicLinkBackend"


class PeopleScaffold(TestCase):
    def setUp(self):
        self.clock = FixedClock(REFERENCE)
        self.enterContext(using_clock(self.clock))
        self.scheduler = scheduling.RecordingScheduler()
        self.enterContext(scheduling.using_scheduler(self.scheduler))

        self.admin = self.user("admin@example.org", Role.ADMIN, "Verwaltung")
        self.supervisor = self.user("sv@example.org", Role.SUPERVISOR, "Böttcher")
        self.amir = self.user("amir@example.org", Role.PARTICIPANT, "Haddad")
        self.client.force_login(self.admin, backend=BACKEND)

    def user(self, email, role, last_name="Muster"):
        return User.objects.create_user(
            first_name="Alex", last_name=last_name, email=email, role=role, now=REFERENCE
        )

    def session(self, *, in_days, supervisor=None):
        return Session.objects.create(
            supervisor=supervisor or self.supervisor,
            date=today_in_berlin(REFERENCE + dt.timedelta(days=in_days)),
            start_time=dt.time(10, 0),
            duration_minutes=90,
            mode=Mode.ONLINE,
            capacity=5,
            created_at=REFERENCE,
            updated_at=REFERENCE,
        )

    def add(self, **overrides):
        form = {
            "action": "add",
            "first_name": "Nour",
            "last_name": "Saleh",
            "email": "nour@example.org",
            "role": Role.PARTICIPANT,
        } | overrides
        return self.client.post(reverse("admin_people"), form)

    def set_state(self, person, action="deactivate"):
        return self.client.post(
            reverse("admin_person_state", args=[person.pk]),
            {"action": action},
            follow=True,
        )


class AddingPeopleTests(PeopleScaffold):
    def test_a_person_is_added_and_appears_in_the_list(self):
        self.add()

        person = User.objects.get(email="nour@example.org")
        self.assertEqual(person.role, Role.PARTICIPANT)
        self.assertTrue(person.is_active)
        self.assertEqual(person.created_at, REFERENCE)
        self.assertContains(self.client.get(reverse("admin_people")), "Nour Saleh")

    def test_adding_someone_sends_nothing_by_default(self):
        # Criterion 7, second half — D10, routine additions need no ceremony.
        mail.outbox.clear()

        self.add()

        self.assertEqual(mail.outbox, [])

    def test_ticking_the_invitation_sends_one_short_mail_with_the_link(self):
        # Criterion 7, first half. Without this the app cannot reach its own
        # users on launch day.
        mail.outbox.clear()

        self.add(send_invitation="1")

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["nour@example.org"])
        self.assertEqual(mail.outbox[0].subject, t("email.invitation.subject", "de"))
        self.assertIn("/sign-in/", mail.outbox[0].body)
        # §8.1 — the invitation carries no calendar invite.
        self.assertEqual(mail.outbox[0].attachments, [])

    def test_a_duplicate_address_is_refused_in_words(self):
        response = self.add(email="AMIR@example.org")

        self.assertEqual(User.objects.filter(email__iexact="amir@example.org").count(), 1)
        self.assertContains(response, "amir@example.org")

    def test_only_an_admin_can_reach_the_people_screen(self):
        self.client.force_login(self.supervisor, backend=BACKEND)

        self.assertRedirects(
            self.client.get(reverse("admin_people")),
            reverse("home"),
            target_status_code=302,
        )


class DeactivationTests(PeopleScaffold):
    """Criterion 66, and §4.1 — preserving history is not enough."""

    def test_deactivating_a_participant_releases_their_upcoming_seats(self):
        upcoming = self.session(in_days=7)
        past = self.session(in_days=-7)
        registration_service.sign_up(upcoming, self.amir, REFERENCE)
        Registration.objects.create(session=past, user=self.amir, created_at=REFERENCE)
        mail.outbox.clear()

        self.set_state(self.amir)

        self.amir.refresh_from_db()
        self.assertFalse(self.amir.is_active)
        # The upcoming seat is free again...
        self.assertEqual(upcoming.seats_taken, 0)
        # ...and the past registration is untouched, because it still counts.
        self.assertTrue(
            Registration.objects.get(session=past, user=self.amir).is_active
        )
        # They get the usual mail, carrying a cancellation invite (§4.1, D22).
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Abgemeldet", mail.outbox[0].subject)
        self.assertIn("METHOD:CANCEL", mail.outbox[0].attachments[0][1])

    def test_their_scheduled_reminder_is_cancelled_too(self):
        upcoming = self.session(in_days=7)
        registration_service.sign_up(upcoming, self.amir, REFERENCE)
        handle = Registration.objects.get().reminder_message_id

        self.set_state(self.amir)

        self.assertIn(handle, self.scheduler.cancelled)

    def test_deactivating_a_supervisor_with_upcoming_sessions_is_blocked(self):
        # D25 — leaving them offered strands participants with a supervisor who
        # cannot sign in; auto-cancelling fires mail the admin never chose to
        # send. Making them choose is the only option that surprises nobody.
        upcoming = self.session(in_days=7)

        response = self.set_state(self.supervisor)

        self.supervisor.refresh_from_db()
        self.assertTrue(self.supervisor.is_active)
        # §7.4 — the message names the sessions, so the admin can act on them.
        self.assertContains(
            response,
            t(
                "err.supervisor_has_sessions",
                "de",
                name=self.supervisor.full_name,
                sessions=people.describe_blocking_sessions([upcoming], "de"),
            ),
        )

    def test_a_supervisor_with_only_past_or_cancelled_sessions_can_be_deactivated(self):
        self.session(in_days=-7)
        cancelled = self.session(in_days=7)
        cancelled.status = SessionStatus.CANCELLED
        cancelled.save()

        self.set_state(self.supervisor)

        self.supervisor.refresh_from_db()
        self.assertFalse(self.supervisor.is_active)

    def test_deactivating_hides_them_from_pickers_but_keeps_their_history(self):
        past = self.session(in_days=-7)
        Registration.objects.create(session=past, user=self.amir, created_at=REFERENCE)

        self.set_state(self.amir)

        # §4.1 — history preserved...
        self.assertEqual(Registration.objects.filter(user=self.amir).count(), 1)
        # ...and they cannot sign in (§5.6 sends nothing at all).
        mail.outbox.clear()
        self.client.post(reverse("signin"), {"email": "amir@example.org"})
        self.assertEqual(mail.outbox, [])

    def test_reactivating_restores_nothing(self):
        # §4.1 — cancelled registrations stay cancelled; they sign up again like
        # anyone else.
        upcoming = self.session(in_days=7)
        registration_service.sign_up(upcoming, self.amir, REFERENCE)
        self.set_state(self.amir)

        self.set_state(self.amir, action="reactivate")

        self.amir.refresh_from_db()
        self.assertTrue(self.amir.is_active)
        self.assertEqual(upcoming.seats_taken, 0)

    def test_a_deactivated_person_is_marked_on_the_list(self):
        self.set_state(self.amir)

        self.assertContains(self.client.get(reverse("admin_people")), "inaktiv")


class SettingsScreenTests(PeopleScaffold):
    """A4 — §4.4."""

    def test_the_zoom_link_can_be_changed_and_reaches_every_future_session(self):
        session = self.session(in_days=7)
        self.client.post(
            reverse("admin_settings"),
            {
                "zoom_url": "https://zoom.example.org/j/new",
                "default_duration_minutes": "90",
                "default_capacity": "5",
                "weekly_session_cap": "2",
                "reminder_lead_hours": "24",
            },
        )

        self.assertEqual(Settings.load().zoom_url, "https://zoom.example.org/j/new")
        mail.outbox.clear()
        registration_service.sign_up(session, self.amir, REFERENCE)
        self.assertIn("zoom.example.org/j/new", mail.outbox[0].body)

    def test_the_weekly_cap_setting_takes_effect_immediately(self):
        self.client.post(
            reverse("admin_settings"),
            {
                "zoom_url": "",
                "default_duration_minutes": "90",
                "default_capacity": "5",
                "weekly_session_cap": "5",
                "reminder_lead_hours": "24",
            },
        )

        self.assertEqual(Settings.load().weekly_session_cap, 5)

    def test_the_defaults_prefill_the_session_form(self):
        self.client.post(
            reverse("admin_settings"),
            {
                "zoom_url": "",
                "default_duration_minutes": "60",
                "default_capacity": "8",
                "weekly_session_cap": "2",
                "reminder_lead_hours": "24",
            },
        )

        response = self.client.get(reverse("session_new"))

        self.assertContains(response, 'value="60"')
        self.assertContains(response, 'value="8"')

    def test_only_an_admin_can_reach_settings(self):
        self.client.force_login(self.supervisor, backend=BACKEND)

        self.assertRedirects(
            self.client.get(reverse("admin_settings")),
            reverse("home"),
            target_status_code=302,
        )
