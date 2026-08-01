"""§12.3 criteria 26, 28–33 and 69 — reminders and calendar invites.

Criteria 35–42 ask whether Apple Calendar, Gmail and Outlook *behave* correctly,
which no test here can answer — those need real clients and a real provider (§13
question 7). What is testable locally is everything the clients are reacting to:
a stable UID, a rising SEQUENCE, one attendee per file, Europe/Berlin times with
a VTIMEZONE, and CANCEL only where a REQUEST went first. Those are asserted here,
so what remains for a human is confirmation, not discovery.
"""

import datetime as dt

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from supervision import (
    calendar as ics,
    registrations as registration_service,
    scheduling,
    sessions as session_service,
)
from supervision.clock import (
    FixedClock,
    today_in_berlin,
    using_clock,
    wall_clock_to_instant,
)
from supervision.models import (
    EmailKind,
    Mode,
    Registration,
    Role,
    Session,
    Settings,
    User,
)

REFERENCE = wall_clock_to_instant(dt.date(2026, 9, 2), dt.time(10, 0))
BACKEND = "supervision.auth_backends.MagicLinkBackend"


class InviteScaffold(TestCase):
    def setUp(self):
        self.clock = FixedClock(REFERENCE)
        self.enterContext(using_clock(self.clock))
        self.scheduler = scheduling.RecordingScheduler()
        self.enterContext(scheduling.using_scheduler(self.scheduler))

        self.supervisor = self.user("sv@example.org", Role.SUPERVISOR, "Böttcher")
        self.amir = self.user("amir@example.org", Role.PARTICIPANT, "Haddad")
        self.nour = self.user("nour@example.org", Role.PARTICIPANT, "Saleh")
        self.supervisor.focus_area = "Tiefenpsychologie, Schwerpunkt Trauma"
        self.supervisor.save()

        settings = Settings.load()
        settings.zoom_url = "https://zoom.example.org/j/steps"
        settings.save()

        self.session = self.make_session(in_days=7)

    def user(self, email, role, last_name="Muster"):
        return User.objects.create_user(
            first_name="Alex", last_name=last_name, email=email, role=role, now=REFERENCE
        )

    def make_session(self, *, in_days, **overrides):
        return Session.objects.create(
            supervisor=self.supervisor,
            date=today_in_berlin(REFERENCE + dt.timedelta(days=in_days)),
            start_time=overrides.pop("start_time", dt.time(10, 0)),
            duration_minutes=90,
            mode=overrides.pop("mode", Mode.ONLINE),
            capacity=5,
            created_at=REFERENCE,
            updated_at=REFERENCE,
            **overrides,
        )

    def ics_of(self, message):
        """The invite a client would read: unfolded."""
        for attachment in message.attachments:
            name, content, mimetype = attachment
            if "calendar" in mimetype or name.endswith(".ics"):
                return ics.unfold(content)
        return None


class IcsContentTests(InviteScaffold):
    """§8.2 — what the clients of criteria 35–42 are reacting to."""

    def build(self, method=ics.REQUEST):
        # Unfolded: folding may fall mid-address, and a client unfolds before
        # reading. Asserting on the raw form tests the line breaks, not the data.
        return ics.unfold(
            ics.build_ics(
                self.session,
                self.amir,
                now=REFERENCE,
                method=method,
                zoom_url="https://zoom.example.org/j/steps",
            )
        )

    def test_one_event_with_the_sessions_uid_and_sequence(self):
        body = self.build()

        self.assertEqual(body.count("BEGIN:VEVENT"), 1)
        self.assertIn(f"UID:{self.session.calendar_uid}", body)
        self.assertIn("SEQUENCE:0", body)
        self.assertIn("METHOD:REQUEST", body)
        self.assertIn("STATUS:CONFIRMED", body)

    def test_times_are_wall_clock_with_a_timezone_definition(self):
        # Criterion 40 — and Outlook mistrusts a TZID it was given no
        # definition for, hence the embedded VTIMEZONE.
        body = self.build()

        self.assertIn("BEGIN:VTIMEZONE", body)
        self.assertIn("TZID:Europe/Berlin", body)
        self.assertIn(
            f"DTSTART;TZID=Europe/Berlin:{self.session.date:%Y%m%d}T100000", body
        )
        self.assertIn(
            f"DTEND;TZID=Europe/Berlin:{self.session.date:%Y%m%d}T113000", body
        )

    def test_ten_oclock_stays_ten_oclock_across_a_dst_change(self):
        summer = self.make_session(in_days=7)
        summer.date = dt.date(2026, 10, 21)
        winter = self.make_session(in_days=8)
        winter.date = dt.date(2026, 11, 4)

        for session in (summer, winter):
            body = ics.unfold(ics.build_ics(session, self.amir, now=REFERENCE))
            self.assertIn(f"DTSTART;TZID=Europe/Berlin:{session.date:%Y%m%d}T100000", body)

    def test_only_the_recipient_is_named(self):
        # Criterion 39, D19 — listing everyone would disclose their addresses.
        Registration.objects.create(
            session=self.session, user=self.nour, created_at=REFERENCE
        )

        body = self.build()

        self.assertEqual(body.count("ATTENDEE"), 1)
        self.assertIn("amir@example.org", body)
        self.assertNotIn("nour@example.org", body)
        self.assertNotIn("Saleh", body)

    def test_the_app_is_the_organiser_and_nobody_is_asked_to_reply(self):
        body = self.build()

        self.assertIn("mailto:supervision@example.org", body)
        self.assertNotIn("ORGANIZER;CN=Alex Böttcher", body)
        self.assertIn("PARTSTAT=ACCEPTED", body)
        self.assertIn("RSVP=FALSE", body)

    def test_a_cancellation_is_a_cancel_not_a_deletion(self):
        body = self.build(method=ics.CANCEL)

        self.assertIn("METHOD:CANCEL", body)
        self.assertIn("STATUS:CANCELLED", body)
        self.assertIn(f"UID:{self.session.calendar_uid}", body)

    def test_there_is_no_alarm(self):
        # D20 — the app sends its own reminder; a calendar alarm on top is a
        # second notification the admin cannot see or change.
        self.assertNotIn("VALARM", self.build())

    def test_the_invite_is_localised_but_its_times_are_not(self):
        # Criterion 69.
        self.nour.locale = "en"
        self.nour.save()
        in_person = self.make_session(in_days=9, mode=Mode.IN_PERSON, room="2.14")

        german = ics.unfold(ics.build_ics(in_person, self.amir, now=REFERENCE))
        english = ics.unfold(ics.build_ics(in_person, self.nour, now=REFERENCE))

        self.assertIn("LOCATION:2.14", german)
        self.assertIn("Schwerpunkt", german)
        self.assertIn("Focus area", english)
        self.assertIn("90 Min.", german)
        self.assertIn("90 min", english)
        # Machine fields stay Europe/Berlin regardless of language.
        for body in (german, english):
            self.assertIn("TZID=Europe/Berlin", body)

    def test_long_lines_are_folded_without_splitting_a_character(self):
        self.supervisor.focus_area = "Schwerpunkt " + "Traumafolgestörungen " * 6
        self.supervisor.save()

        body = ics.build_ics(self.session, self.amir, now=REFERENCE)

        for line in body.split("\r\n"):
            self.assertLessEqual(len(line.encode("utf-8")), 75, line)

    def test_the_add_to_calendar_links_carry_no_personal_data(self):
        # §8.2, §11 — a URL is handed to a third party the moment it is clicked.
        links = ics.add_to_calendar_links(self.session, "de")

        for url in links.values():
            self.assertNotIn("amir", url)
            self.assertNotIn("Haddad", url)
            self.assertIn("Supervision", url)


class InviteDeliveryTests(InviteScaffold):
    def test_a_sign_up_confirmation_carries_the_invite_twice(self):
        # §8.2 — some clients act only on the attachment, some only on the
        # inline text/calendar part.
        mail.outbox.clear()

        registration_service.sign_up(self.session, self.amir, REFERENCE)

        message = mail.outbox[0]
        kinds = [mimetype for _, _, mimetype in message.attachments]
        self.assertEqual(len(message.attachments), 2)
        self.assertTrue(any("text/calendar" in kind for kind in kinds))
        self.assertTrue(any("method=REQUEST" in kind for kind in kinds))

    def test_moving_a_session_ships_a_higher_sequence_with_the_same_uid(self):
        # Criterion 36's precondition: one event afterwards, not two.
        registration_service.sign_up(self.session, self.amir, REFERENCE)
        uid_before = self.session.calendar_uid
        mail.outbox.clear()

        session_service.update_session(
            self.session, now=REFERENCE, start_time=dt.time(14, 0)
        )

        self.session.refresh_from_db()
        body = self.ics_of(mail.outbox[0])
        self.assertIn(f"UID:{uid_before}", body)
        self.assertIn("SEQUENCE:1", body)
        self.assertIn("METHOD:REQUEST", body)

    def test_cancelling_a_session_sends_a_cancel_to_everyone_registered(self):
        # Criterion 37's precondition, and 29.
        registration_service.sign_up(self.session, self.amir, REFERENCE)
        registration_service.sign_up(self.session, self.nour, REFERENCE)
        mail.outbox.clear()

        session_service.cancel_session(self.session, by=self.supervisor, now=REFERENCE)

        recipients = {message.to[0] for message in mail.outbox}
        self.assertEqual(
            recipients, {"amir@example.org", "nour@example.org", "sv@example.org"}
        )
        for message in mail.outbox:
            if message.to[0] == "amir@example.org":
                self.assertIn("METHOD:CANCEL", self.ics_of(message))

    def test_giving_up_a_place_cancels_only_that_persons_entry(self):
        # Criterion 38 — other participants' calendars are untouched.
        registration_service.sign_up(self.session, self.amir, REFERENCE)
        registration_service.sign_up(self.session, self.nour, REFERENCE)
        mail.outbox.clear()

        registration_service.cancel_place(self.session, self.amir, REFERENCE)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["amir@example.org"])
        self.assertIn("METHOD:CANCEL", self.ics_of(mail.outbox[0]))

    def test_no_cancellation_reaches_a_calendar_that_never_had_the_event(self):
        # §8.3 — METHOD:CANCEL for an event a calendar never had produces a
        # ghost entry in some clients. EmailLog is what answers this.
        walk_in = self.user("w@example.org", Role.PARTICIPANT)
        Registration.objects.create(
            session=self.session, user=walk_in, created_at=REFERENCE
        )
        mail.outbox.clear()

        session_service.cancel_session(self.session, by=self.supervisor, now=REFERENCE)

        theirs = [m for m in mail.outbox if m.to == ["w@example.org"]]
        self.assertEqual(len(theirs), 1)
        self.assertEqual(theirs[0].attachments, [])

    def test_the_detail_screen_offers_the_same_file_to_download(self):
        registration_service.sign_up(self.session, self.amir, REFERENCE)
        self.client.force_login(self.amir, backend=BACKEND)

        response = self.client.get(reverse("session_ics", args=[self.session.pk]))

        self.assertIn("text/calendar", response["Content-Type"])
        self.assertIn("supervision.ics", response["Content-Disposition"])
        self.assertIn(self.session.calendar_uid, response.content.decode())


class ReminderTests(InviteScaffold):
    """§8.3 — the app decides, the provider carries out."""

    def test_registering_schedules_exactly_one_reminder_and_stores_its_id(self):
        # Criterion 26.
        registration_service.sign_up(self.session, self.amir, REFERENCE)

        self.assertEqual(len(self.scheduler.scheduled), 1)
        registration = Registration.objects.get()
        self.assertTrue(registration.reminder_message_id)

        scheduled = self.scheduler.scheduled[registration.reminder_message_id]
        self.assertEqual(
            scheduled.deliver_at, self.session.starts_at - dt.timedelta(hours=24)
        )

    def test_the_reminder_arrives_in_the_recipients_language(self):
        # Criterion 27, as far as a local fake can go.
        self.amir.locale = "en"
        self.amir.save()
        registration_service.sign_up(self.session, self.amir, REFERENCE)
        mail.outbox.clear()

        self.scheduler.deliver_due(self.session.starts_at - dt.timedelta(hours=24))

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Reminder: supervision on", mail.outbox[0].subject)
        self.assertIn("zoom.example.org", mail.outbox[0].body)

    def test_cancelling_a_place_cancels_that_reminder_and_no_other(self):
        # Criterion 28.
        registration_service.sign_up(self.session, self.amir, REFERENCE)
        registration_service.sign_up(self.session, self.nour, REFERENCE)
        amirs = Registration.objects.get(user=self.amir).reminder_message_id

        registration_service.cancel_place(self.session, self.amir, REFERENCE)

        self.assertIn(amirs, self.scheduler.cancelled)
        self.assertEqual(len(self.scheduler.scheduled), 1)
        mail.outbox.clear()
        self.scheduler.deliver_due(self.session.starts_at)
        self.assertEqual([m.to for m in mail.outbox], [["nour@example.org"]])

    def test_cancelling_a_session_cancels_every_reminder_for_it(self):
        # Criterion 29.
        registration_service.sign_up(self.session, self.amir, REFERENCE)
        registration_service.sign_up(self.session, self.nour, REFERENCE)

        session_service.cancel_session(self.session, by=self.supervisor, now=REFERENCE)

        self.assertEqual(self.scheduler.scheduled, {})
        self.assertEqual(len(self.scheduler.cancelled), 2)

    def test_moving_a_session_reminds_everyone_at_the_new_time_and_not_the_old(self):
        # Criterion 31 — the one the whole reschedule dance exists for.
        registration_service.sign_up(self.session, self.amir, REFERENCE)
        old_time = self.session.starts_at - dt.timedelta(hours=24)

        session_service.update_session(
            self.session, now=REFERENCE, date=self.session.date + dt.timedelta(days=1)
        )

        self.session.refresh_from_db()
        new_time = self.session.starts_at - dt.timedelta(hours=24)
        remaining = list(self.scheduler.scheduled.values())
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].deliver_at, new_time)
        self.assertNotEqual(remaining[0].deliver_at, old_time)

        mail.outbox.clear()
        self.scheduler.deliver_due(old_time)
        self.assertEqual(mail.outbox, [])

    def test_registering_inside_the_lead_window_sends_it_at_once(self):
        # Criterion 32.
        self.clock.set(self.session.starts_at - dt.timedelta(hours=5))
        mail.outbox.clear()

        registration_service.sign_up(self.session, self.amir, self.clock.now())

        self.assertEqual(self.scheduler.scheduled, {})
        kinds = [m.subject for m in mail.outbox]
        self.assertEqual(len(kinds), 2)  # confirmation, then the reminder
        self.assertTrue(any("Erinnerung" in subject for subject in kinds))

    def test_nothing_is_sent_inside_the_last_hour(self):
        # Criterion 33 — a reminder arriving after the participant has already
        # left is noise. The rule keys on the session's start time.
        self.clock.set(self.session.starts_at - dt.timedelta(minutes=59))
        mail.outbox.clear()

        registration_service.sign_up(self.session, self.amir, self.clock.now())

        self.assertEqual(self.scheduler.scheduled, {})
        self.assertEqual(
            [m for m in mail.outbox if "Erinnerung" in m.subject], []
        )

    def test_the_lead_time_is_the_admins_setting(self):
        settings = Settings.load()
        settings.reminder_lead_hours = 48
        settings.save()

        registration_service.sign_up(self.session, self.amir, REFERENCE)

        scheduled = list(self.scheduler.scheduled.values())[0]
        self.assertEqual(
            scheduled.deliver_at, self.session.starts_at - dt.timedelta(hours=48)
        )
