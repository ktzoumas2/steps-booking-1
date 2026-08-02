"""§12.3 criterion 64 — every validation error of §7.4, word for word.

The other test files assert recognisable fragments, which is right for reading
but would not notice a message drifting from §14. These assert the *whole*
string, built from the catalog with the same parameters the view uses, so a
reworded message fails here rather than reaching a user in two versions.

§7.4 lists eleven. Ten are reachable now; `err.supervisor_has_sessions` needs the
People screen and is asserted with it.
"""

import datetime as dt

from django.test import TestCase
from django.urls import reverse

from supervision import registrations as registration_service, sessions as session_service
from supervision.catalog import t
from supervision import scheduling
from supervision.clock import (
    FixedClock,
    today_in_berlin,
    using_clock,
    wall_clock_to_instant,
)
from supervision.models import Mode, Registration, Role, Session, Settings, User

REFERENCE = wall_clock_to_instant(dt.date(2026, 9, 2), dt.time(10, 0))
BACKEND = "supervision.auth_backends.MagicLinkBackend"


class ErrorWordingScaffold(TestCase):
    def setUp(self):
        self.clock = FixedClock(REFERENCE)
        self.enterContext(using_clock(self.clock))
        self.scheduler = scheduling.RecordingScheduler()
        self.enterContext(scheduling.using_scheduler(self.scheduler))
        self.supervisor = self.user("sv@example.org", Role.SUPERVISOR, "Böttcher")
        self.other = self.user("sv2@example.org", Role.SUPERVISOR, "Krause")
        self.admin = self.user("admin@example.org", Role.ADMIN)
        self.amir = self.user("amir@example.org", Role.PARTICIPANT, "Haddad")
        self.nour = self.user("nour@example.org", Role.PARTICIPANT, "Saleh")

    def user(self, email, role, last_name="Muster"):
        return User.objects.create_user(
            first_name="Alex", last_name=last_name, email=email, role=role, now=REFERENCE
        )

    def session(self, supervisor, in_days, **overrides):
        return Session.objects.create(
            supervisor=supervisor,
            date=today_in_berlin(REFERENCE + dt.timedelta(days=in_days)),
            start_time=overrides.pop("start_time", dt.time(10, 0)),
            duration_minutes=90,
            mode=Mode.ONLINE,
            capacity=overrides.pop("capacity", 5),
            created_at=REFERENCE,
            updated_at=REFERENCE,
            **overrides,
        )

    def sign_in(self, user):
        self.client.force_login(user, backend=BACKEND)

    def offer(self, **overrides):
        form = {
            "date": today_in_berlin(REFERENCE + dt.timedelta(days=7)).isoformat(),
            "start_time": "10:00",
            "duration_minutes": "90",
            "mode": Mode.ONLINE,
            "room": "",
            "capacity": "5",
        } | overrides
        return self.client.post(reverse("session_new"), form)


class SessionFormWordingTests(ErrorWordingScaffold):
    def test_err_room_required(self):
        self.sign_in(self.supervisor)

        response = self.offer(mode=Mode.IN_PERSON, room="")

        self.assertContains(response, t("err.room_required", "de"))

    def test_err_date_in_past(self):
        self.sign_in(self.supervisor)

        response = self.offer(
            date=today_in_berlin(REFERENCE - dt.timedelta(days=1)).isoformat()
        )

        self.assertContains(response, t("err.date_in_past", "de"))

    def test_err_capacity_below_registered(self):
        session = self.session(self.supervisor, 7, capacity=3)
        for participant in (self.amir, self.nour):
            Registration.objects.create(
                session=session, user=participant, created_at=REFERENCE
            )
        self.sign_in(self.supervisor)

        response = self.client.post(
            reverse("session_edit", args=[session.pk]),
            {
                "date": session.date.isoformat(),
                "start_time": "10:00",
                "duration_minutes": "90",
                "mode": Mode.ONLINE,
                "room": "",
                "capacity": "1",
            },
        )

        self.assertContains(
            response, t("err.capacity_below_registered", "de", count=2)
        )


class WeeklyCapWordingTests(ErrorWordingScaffold):
    """The one error message in the app that does real work (D41)."""

    def fill_the_week(self, count=2):
        monday = today_in_berlin(REFERENCE + dt.timedelta(days=7))
        while monday.isoweekday() != 1:
            monday += dt.timedelta(days=1)
        existing = []
        for index in range(count):
            session = self.session(
                self.supervisor if index % 2 == 0 else self.other,
                30,
                start_time=dt.time(10 + index * 4, 0),
            )
            session.date = monday + dt.timedelta(days=index)
            session.save()
            existing.append(session)
        return monday, existing

    def expected(self, key, clashing, locale="de"):
        return t(
            key,
            locale,
            count=len(clashing),
            sessions=session_service.describe_sessions(clashing, locale),
        )

    def test_warn_week_full_at_the_cap(self):
        monday, clashing = self.fill_the_week(1)
        self.sign_in(self.supervisor)

        response = self.offer(date=(monday + dt.timedelta(days=4)).isoformat())

        self.assertContains(response, self.expected("warn.week_full", clashing))

    def test_confirm_cap_override_above_the_cap(self):
        monday, _ = self.fill_the_week(2)
        self.sign_in(self.supervisor)

        response = self.offer(date=(monday + dt.timedelta(days=4)).isoformat())

        self.assertContains(response, t("confirm.cap_override", "de", cap=2))

    def test_it_reads_in_english_for_an_english_speaker(self):
        # §7.4 — "in the recipient's language".
        User.objects.filter(pk=self.supervisor.pk).update(locale="en")
        monday, clashing = self.fill_the_week(1)
        self.sign_in(self.supervisor)

        response = self.offer(date=(monday + dt.timedelta(days=4)).isoformat())

        self.assertContains(response, self.expected("warn.week_full", clashing, "en"))

    def test_err_time_step(self):
        self.sign_in(self.supervisor)

        response = self.offer(start_time="10:07")

        self.assertContains(response, t("err.time_step", "de"))


class SignUpAndLinkWordingTests(ErrorWordingScaffold):
    def test_err_session_just_filled(self):
        session = self.session(self.supervisor, 7, capacity=1)
        registration_service.sign_up(session, self.nour, REFERENCE)
        self.sign_in(self.amir)

        response = self.client.post(
            reverse("session_sign_up", args=[session.pk]),
            {"next": reverse("participant_home")},
            follow=True,
        )

        self.assertContains(response, t("err.session_just_filled", "de"))

    def test_err_link_expired(self):
        self.client.post(reverse("signin"), {"email": "amir@example.org"})
        self.clock.advance(minutes=16)

        from tests.test_signin import link_from_last_email

        response = self.client.get(
            reverse("signin_redeem", args=[link_from_last_email()])
        )

        self.assertContains(response, t("err.link_expired", "de"), status_code=410)

    def test_err_link_used(self):
        self.client.post(reverse("signin"), {"email": "amir@example.org"})

        from tests.test_signin import link_from_last_email

        token = link_from_last_email()
        self.client.get(reverse("signin_redeem", args=[token]))
        self.client.post(reverse("signout"))
        response = self.client.get(reverse("signin_redeem", args=[token]))

        self.assertContains(response, t("err.link_used", "de"), status_code=410)


class ExportWordingTests(ErrorWordingScaffold):
    def test_warn_unreviewed_in_range(self):
        self.session(self.supervisor, -7)
        self.session(self.supervisor, -6)
        self.sign_in(self.admin)

        response = self.client.get(reverse("admin_counts"))

        self.assertContains(response, t("warn.unreviewed_in_range", "de", count=2))
