"""§12.3 acceptance criteria 55–59 and 61–64 — the counts on screen, and the CSVs."""

import csv
import datetime as dt
import io

from django.test import TestCase
from django.urls import reverse

from supervision import counting, exports
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
    RegistrationSource,
    Role,
    Session,
    SessionStatus,
    User,
)

REFERENCE = wall_clock_to_instant(dt.date(2026, 9, 2), dt.time(10, 0))
BACKEND = "supervision.auth_backends.MagicLinkBackend"


def make_user(email, role, last_name="Muster", first_name="Alex"):
    return User.objects.create_user(
        first_name=first_name, last_name=last_name, email=email, role=role, now=REFERENCE
    )


class CountsScaffold(TestCase):
    """A fixture of the §12.2 shape: reviewed, unreviewed, not-held, cancelled,
    an absence, and someone added at confirmation."""

    def setUp(self):
        self.clock = FixedClock(REFERENCE)
        self.enterContext(using_clock(self.clock))

        self.boettcher = make_user("b@example.org", Role.SUPERVISOR, "Böttcher", "Johanna")
        self.krause = make_user("k@example.org", Role.SUPERVISOR, "Krause", "Miriam")
        self.admin = make_user("admin@example.org", Role.ADMIN, "Verwaltung")
        self.amir = make_user("amir@example.org", Role.PARTICIPANT, "Haddad", "Amir")
        self.nour = make_user("nour@example.org", Role.PARTICIPANT, "Saleh", "Nour")
        self.lena = make_user("lena@example.org", Role.PARTICIPANT, "Vogt", "Lena")

        # Amir attended two, was absent from one, and one of his sessions was
        # later recorded as not held.
        self.attended_a = self.session(self.boettcher, -21, reviewed=True)
        self.attended_b = self.session(self.krause, -14)
        self.was_absent = self.session(self.boettcher, -7, reviewed=True)
        self.not_held = self.session(self.boettcher, -5, took_place=False, reviewed=True)
        self.cancelled = self.session(self.krause, -4, status=SessionStatus.CANCELLED)
        self.upcoming = self.session(self.boettcher, 7)

        for session in (self.attended_a, self.attended_b, self.not_held):
            Registration.objects.create(
                session=session, user=self.amir, created_at=REFERENCE
            )
        Registration.objects.create(
            session=self.was_absent, user=self.amir, created_at=REFERENCE, attended=False
        )
        # Lena turned up to one without ever signing up.
        Registration.objects.create(
            session=self.attended_a,
            user=self.lena,
            source=RegistrationSource.ADDED_AT_CONFIRMATION,
            attended=True,
            created_at=REFERENCE,
        )

    def session(self, supervisor, in_days, *, reviewed=False, **overrides):
        instance = Session.objects.create(
            supervisor=supervisor,
            date=today_in_berlin(REFERENCE + dt.timedelta(days=in_days)),
            start_time=dt.time(10, 0),
            duration_minutes=overrides.pop("minutes", 90),
            mode=Mode.ONLINE,
            capacity=5,
            created_at=REFERENCE,
            updated_at=REFERENCE,
            **overrides,
        )
        if reviewed:
            instance.confirmed_at = REFERENCE
            instance.confirmed_by = supervisor
            instance.save()
        return instance

    def sign_in(self, user):
        self.client.force_login(user, backend=BACKEND)

    def rows(self, csv_text):
        return list(csv.reader(io.StringIO(csv_text.lstrip("﻿"))))


class ParticipationRecordTests(CountsScaffold):
    """Criteria 55–57 — the number and the list agree, and nothing waits."""

    def test_the_count_and_the_list_agree(self):
        self.sign_in(self.amir)

        response = self.client.get(reverse("participant_participation"))

        self.assertContains(response, ">2<")  # attended_a and attended_b
        self.assertContains(response, "Teilgenommene Supervisionen")
        self.assertEqual(
            len(counting.attended_registrations(self.clock.now(), participant=self.amir)),
            2,
        )

    def test_a_session_missed_is_shown_separately_and_not_counted(self):
        # Criterion 56.
        self.sign_in(self.amir)

        response = self.client.get(reverse("participant_participation"))

        self.assertContains(response, "Angemeldet, nicht teilgenommen")
        self.assertContains(response, ">2<")

    def test_a_session_appears_as_soon_as_it_ends_and_leaves_only_if_not_held(self):
        # Criterion 57.
        future = self.session(self.boettcher, 3)
        Registration.objects.create(
            session=future, user=self.amir, created_at=REFERENCE
        )
        self.sign_in(self.amir)

        self.assertContains(self.client.get(reverse("participant_participation")), ">2<")

        self.clock.set(future.ends_at)
        self.assertContains(self.client.get(reverse("participant_participation")), ">3<")

        future.took_place = False
        future.save()
        self.assertContains(self.client.get(reverse("participant_participation")), ">2<")

    def test_the_range_narrows_the_record(self):
        self.sign_in(self.amir)

        response = self.client.get(
            reverse("participant_participation"),
            {"start": self.attended_b.date.isoformat(), "end": self.was_absent.date.isoformat()},
        )

        self.assertContains(response, ">1<")

    def test_an_unparseable_range_shows_everything_rather_than_nothing(self):
        self.sign_in(self.amir)

        response = self.client.get(
            reverse("participant_participation"), {"start": "not-a-date"}
        )

        self.assertContains(response, ">2<")


class PrivacyTests(CountsScaffold):
    """Criterion 58 — a participant cannot see another participant's attendance."""

    def test_the_session_detail_names_who_is_registered_but_not_who_attended(self):
        self.sign_in(self.nour)

        response = self.client.get(
            reverse("session_detail", args=[self.was_absent.pk])
        )

        self.assertContains(response, "Amir Haddad")  # who is registered: allowed
        self.assertNotContains(response, "nicht teilgenommen")

    def test_a_participant_cannot_open_another_participants_record(self):
        self.sign_in(self.nour)

        response = self.client.get(
            reverse("admin_participant_record", args=[self.amir.pk])
        )

        self.assertRedirects(response, reverse("home"), target_status_code=302)

    def test_a_participant_cannot_open_the_admin_counts(self):
        self.sign_in(self.amir)

        self.assertRedirects(
            self.client.get(reverse("admin_counts")),
            reverse("home"),
            target_status_code=302,
        )

    def test_a_supervisor_sees_only_their_own_counts(self):
        # §3, D-note — supervisors invoice against their own figures and cannot
        # see other supervisors' or participants'.
        self.sign_in(self.boettcher)

        own = self.client.get(reverse("supervisor_counts"))
        self.assertContains(own, ">2<")  # attended_a and was_absent still count
        self.assertNotContains(own, "Krause")

        self.assertRedirects(
            self.client.get(reverse("admin_counts")),
            reverse("home"),
            target_status_code=302,
        )


class AdminCountsTests(CountsScaffold):
    def test_per_supervisor_and_per_participant_figures_are_shown(self):
        self.sign_in(self.admin)

        response = self.client.get(reverse("admin_counts"))

        self.assertContains(response, "Böttcher")
        self.assertContains(response, "Krause")
        self.assertContains(response, "Amir Haddad")

    def test_a_participant_name_opens_the_same_record_they_see(self):
        # Criterion 59, first half.
        self.sign_in(self.admin)

        response = self.client.get(
            reverse("admin_participant_record", args=[self.amir.pk])
        )

        self.assertContains(response, "Amir Haddad")
        self.assertContains(response, ">2<")
        self.assertContains(response, "Angemeldet, nicht teilgenommen")


class SignOffTests(CountsScaffold):
    """Criterion 61 — a human is made to look before the numbers become an invoice."""

    def export(self, which="per_supervisor", **extra):
        return self.client.post(
            reverse("admin_counts"), {"export": which, **extra}
        )

    def test_the_screen_says_how_many_are_unreviewed_and_lists_them(self):
        self.sign_in(self.admin)

        response = self.client.get(reverse("admin_counts"))

        # attended_b and the cancelled one is excluded; only counted sessions.
        self.assertContains(response, "wurden noch nicht geprüft")
        self.assertContains(response, "Sie zählen trotzdem mit")
        self.assertContains(response, reverse("session_review", args=[self.attended_b.pk]))
        self.assertContains(response, "Ich habe die Liste geprüft")

    def test_the_sign_off_is_a_button_that_records_who_looked(self):
        # A tick that evaporates on reload is not a sign-off. §4.2 has
        # confirmed_at / confirmed_by precisely to record that a human looked,
        # and which human.
        self.sign_in(self.admin)
        unreviewed_before = counting.unreviewed_in_range(self.clock.now())
        self.assertTrue(unreviewed_before)

        response = self.client.post(
            reverse("admin_counts"), {"action": "acknowledge"}, follow=True
        )

        self.assertEqual(counting.unreviewed_in_range(self.clock.now()), [])
        for session in unreviewed_before:
            session.refresh_from_db()
            self.assertEqual(session.confirmed_by, self.admin)
            self.assertEqual(session.confirmed_at, REFERENCE)
        # The warning is gone, and something says so in its place.
        self.assertNotContains(response, "wurden noch nicht geprüft")
        self.assertContains(response, t("a2.all_reviewed", "de"))

    def test_signing_off_claims_nothing_about_whether_a_session_happened(self):
        # "I have checked the list" is a statement about the reviewer. Setting
        # took_place would put words in a supervisor's mouth about sessions the
        # admin was not at; §6.4 keeps null meaning "no claim either way".
        self.sign_in(self.admin)
        unreviewed = counting.unreviewed_in_range(self.clock.now())

        self.client.post(reverse("admin_counts"), {"action": "acknowledge"})

        for session in unreviewed:
            session.refresh_from_db()
            self.assertIsNone(session.took_place)

    def test_signing_off_changes_no_count(self):
        # §2, §9.1 — reviewed never affects a figure either way, which is what
        # makes a one-click bulk sign-off safe.
        self.sign_in(self.admin)
        before = counting.sessions_held_by_supervisor(self.clock.now())

        self.client.post(reverse("admin_counts"), {"action": "acknowledge"})

        self.assertEqual(
            [(r["supervisor"].pk, r["sessions_held"]) for r in before],
            [
                (r["supervisor"].pk, r["sessions_held"])
                for r in counting.sessions_held_by_supervisor(self.clock.now())
            ],
        )

    def test_the_sign_off_keeps_the_range_you_were_looking_at(self):
        self.sign_in(self.admin)
        day = self.attended_b.date.isoformat()

        response = self.client.post(
            reverse("admin_counts"),
            {"action": "acknowledge", "start": day, "end": day},
        )

        self.assertIn(f"start={day}", response["Location"])
        self.assertIn(f"end={day}", response["Location"])

    def test_it_redirects_so_a_refresh_cannot_repeat_it(self):
        self.sign_in(self.admin)

        response = self.client.post(reverse("admin_counts"), {"action": "acknowledge"})

        self.assertEqual(response.status_code, 302)

    def test_nothing_is_claimed_about_an_empty_range(self):
        self.sign_in(self.admin)
        far_off = (REFERENCE + dt.timedelta(days=900)).date().isoformat()

        response = self.client.get(
            reverse("admin_counts"), {"start": far_off, "end": far_off}
        )

        self.assertNotContains(response, t("a2.all_reviewed", "de"))
        self.assertNotContains(response, "wurden noch nicht geprüft")

    def test_exporting_without_acknowledging_does_not_export(self):
        self.sign_in(self.admin)

        response = self.export()

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("text/csv", response["Content-Type"])
        self.assertContains(response, "Ich habe die Liste geprüft")

    def test_the_export_runs_once_the_list_has_been_signed_off(self):
        self.sign_in(self.admin)
        self.client.post(reverse("admin_counts"), {"action": "acknowledge"})

        response = self.export()

        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("attachment", response["Content-Disposition"])

    def test_a_range_with_nothing_unreviewed_needs_no_acknowledgement(self):
        # D31 — the checkpoint is placed where an assumption turns into an
        # invoice, not repeated per session.
        self.sign_in(self.admin)

        response = self.export(
            start=self.attended_a.date.isoformat(),
            end=self.attended_a.date.isoformat(),
        )

        self.assertIn("text/csv", response["Content-Type"])


class ExportTests(CountsScaffold):
    def test_every_csv_starts_with_a_bom_so_excel_keeps_the_umlauts(self):
        # Criterion 63 — this replaces an Excel workflow.
        for name, (build, _) in exports.EXPORTS.items():
            with self.subTest(export=name):
                text = build(self.clock.now())
                self.assertTrue(text.startswith("﻿"), name)
                self.assertEqual(text.encode("utf-8")[:3], b"\xef\xbb\xbf")

        self.assertIn("Böttcher", exports.per_supervisor_csv(self.clock.now()))

    def test_the_session_csv_tells_an_assumption_from_a_statement(self):
        # Criterion 62.
        rows = self.rows(exports.sessions_csv(self.clock.now()))
        header = rows[0]
        by_id = {row[0]: dict(zip(header, row)) for row in rows[1:]}

        assumed = by_id[str(self.attended_b.pk)]
        self.assertEqual(assumed["took_place"], "")
        self.assertEqual(assumed["reviewed"], "false")

        recorded = by_id[str(self.not_held.pk)]
        self.assertEqual(recorded["took_place"], "false")
        self.assertEqual(recorded["reviewed"], "true")

        # A cancelled session is in the file, with its status, rather than
        # silently missing from it.
        self.assertEqual(by_id[str(self.cancelled.pk)]["status"], "cancelled")

    def test_the_session_csv_counts_registered_and_attended(self):
        rows = self.rows(exports.sessions_csv(self.clock.now()))
        header = rows[0]
        by_id = {row[0]: dict(zip(header, row)) for row in rows[1:]}

        # attended_a has Amir (no claim) and Lena (added, present).
        self.assertEqual(by_id[str(self.attended_a.pk)]["registered_count"], "2")
        self.assertEqual(by_id[str(self.attended_a.pk)]["attended_count"], "2")
        # was_absent has Amir, marked absent.
        self.assertEqual(by_id[str(self.was_absent.pk)]["registered_count"], "1")
        self.assertEqual(by_id[str(self.was_absent.pk)]["attended_count"], "0")

    def test_the_participation_detail_matches_the_record_row_for_row(self):
        # Criterion 59, second half.
        rows = self.rows(exports.participation_detail_csv(self.clock.now()))
        header, body = rows[0], rows[1:]
        amirs = [dict(zip(header, row)) for row in body if row[2] == "amir@example.org"]

        on_screen = counting.attended_registrations(
            self.clock.now(), participant=self.amir
        )
        absent = counting.absent_registrations(self.clock.now(), participant=self.amir)

        self.assertEqual(len(amirs), len(on_screen) + len(absent))
        self.assertEqual(
            sorted(row["attended"] for row in amirs), ["false", "true", "true"]
        )

    def test_the_per_participant_csv_separates_attended_from_registered(self):
        rows = self.rows(exports.per_participant_csv(self.clock.now()))
        by_email = {row[2]: row for row in rows[1:]}

        # Amir signed up for three that count and attended two of them.
        self.assertEqual(by_email["amir@example.org"][3:], ["2", "3"])
        # Lena attended one and signed up for nothing (D27).
        self.assertEqual(by_email["lena@example.org"][3:], ["1", "0"])

    def test_dates_are_iso_and_a_not_held_session_is_out_of_the_totals(self):
        rows = self.rows(exports.per_supervisor_csv(self.clock.now()))
        by_email = {row[2]: row for row in rows[1:]}

        # Böttcher held attended_a and was_absent; not_held does not count and
        # upcoming has not happened.
        self.assertEqual(by_email["b@example.org"][3], "2")

        detail = self.rows(exports.participation_detail_csv(self.clock.now()))
        self.assertRegex(detail[1][4], r"^\d{4}-\d{2}-\d{2}$")

    def test_the_range_narrows_every_export(self):
        one_day = self.attended_a.date
        rows = self.rows(
            exports.sessions_csv(self.clock.now(), start=one_day, end=one_day)
        )

        self.assertEqual(len(rows), 2)  # header plus one session
