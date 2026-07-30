"""§12.3 acceptance criteria 15–17, 19 and 20 — browsing and filtering (§7.1).

Criterion 18 — a full session stays visible, greyed, reading `Ausgebucht` —
needs registrations before a session can be full, and goes with them.
"""

import datetime as dt
import re

from django.test import TestCase
from django.urls import reverse

from supervision.clock import FixedClock, today_in_berlin, using_clock, wall_clock_to_instant
from supervision.models import Mode, Role, Session, SessionStatus, User

# A Wednesday, 10:00 Berlin — ISO week 36 of 2026.
REFERENCE = wall_clock_to_instant(dt.date(2026, 9, 2), dt.time(10, 0))


def make_user(email, role, last_name="Muster", **overrides):
    return User.objects.create_user(
        first_name="Alex",
        last_name=last_name,
        email=email,
        role=role,
        now=REFERENCE,
        **overrides,
    )


class BrowsingScaffold(TestCase):
    def setUp(self):
        self.clock = FixedClock(REFERENCE)
        self.enterContext(using_clock(self.clock))
        self.boettcher = make_user("b@example.org", Role.SUPERVISOR, "Böttcher")
        self.krause = make_user("k@example.org", Role.SUPERVISOR, "Krause")
        self.participant = make_user("p@example.org", Role.PARTICIPANT)
        self.client.force_login(
            self.participant, backend="supervision.auth_backends.MagicLinkBackend"
        )

    def make_session(self, supervisor, *, in_days, hour=10, **overrides):
        return Session.objects.create(
            supervisor=supervisor,
            date=today_in_berlin(REFERENCE + dt.timedelta(days=in_days)),
            start_time=dt.time(hour, 0),
            duration_minutes=90,
            mode=overrides.pop("mode", Mode.ONLINE),
            capacity=5,
            created_at=REFERENCE,
            updated_at=REFERENCE,
            **overrides,
        )

    def available(self, **params):
        return self.client.get(reverse("participant_home"), params)

    def listed_supervisors(self, response) -> list[str]:
        """Whose sessions are actually *in the list*.

        Not the same as "whose name appears on the page": criterion 17 puts every
        supervisor with something upcoming into the filter dropdown, so asserting
        against the whole document would confuse a choice with a result.
        """
        return re.findall(
            r'class="session__supervisor">\s*([^<]+?)\s*(?:<|$)',
            response.content.decode(),
        )


class WeekGroupingTests(BrowsingScaffold):
    """Criterion 15 — week headings, date order, empty weeks skipped."""

    def test_sessions_are_grouped_under_week_headings_in_date_order(self):
        self.make_session(self.boettcher, in_days=8, hour=14)   # week 37
        self.make_session(self.boettcher, in_days=7, hour=9)    # week 37, earlier
        self.make_session(self.krause, in_days=21)              # week 39

        body = self.available().content.decode()

        self.assertIn("KW 37", body)
        self.assertIn("KW 39", body)
        # Week 38 has nothing in it and is skipped, not shown empty.
        self.assertNotIn("KW 38", body)
        # Headings in order, and within a week the earlier session first.
        self.assertLess(body.index("KW 37"), body.index("KW 39"))
        self.assertLess(body.index("09:00"), body.index("14:00"))

    def test_the_heading_names_the_monday_and_the_sunday(self):
        self.make_session(self.boettcher, in_days=7)

        # ISO week 37 of 2026 runs Mon 07.09. – Sun 13.09.
        self.assertContains(self.available(), "KW 37 · Mo 07.09. – So 13.09.")

    def test_a_week_heading_reads_in_english_too(self):
        self.make_session(self.boettcher, in_days=7)
        User.objects.filter(pk=self.participant.pk).update(locale="en")

        self.assertContains(self.available(), "Week 37 · Mon 7 Sep – Sun 13 Sep")

    def test_past_and_cancelled_sessions_are_not_on_offer(self):
        self.make_session(self.boettcher, in_days=-7)
        self.make_session(self.krause, in_days=7, status=SessionStatus.CANCELLED)

        self.assertContains(self.available(), "keine Termine eingetragen")

    def test_a_session_drops_off_the_list_the_moment_it_starts(self):
        session = self.make_session(self.boettcher, in_days=7)

        self.assertContains(self.available(), "KW 37")

        self.clock.set(session.starts_at)
        self.assertContains(self.available(), "keine Termine eingetragen")


class FilterTests(BrowsingScaffold):
    """Criteria 16 and 17 — one filter, and only supervisors who have sessions."""

    def setUp(self):
        super().setUp()
        self.by_boettcher = self.make_session(self.boettcher, in_days=7)
        self.by_krause = self.make_session(self.krause, in_days=8)

    def test_filtering_shows_only_that_supervisors_sessions(self):
        response = self.available(supervisor=self.boettcher.pk)

        self.assertEqual(self.listed_supervisors(response), ["Alex Böttcher"])

    def test_the_active_filter_is_stated_and_clears_in_one_tap(self):
        filtered = self.available(supervisor=self.boettcher.pk)
        self.assertContains(filtered, "Gefiltert: Alex Böttcher")
        self.assertContains(filtered, "Filter entfernen")

        cleared = self.available(supervisor="")
        self.assertNotContains(cleared, "Gefiltert:")
        self.assertEqual(
            sorted(self.listed_supervisors(cleared)), ["Alex Böttcher", "Alex Krause"]
        )

    def test_the_choice_persists_to_the_next_visit(self):
        # §7.1 — it persists across sign-ups, so it must outlive one page view.
        self.available(supervisor=self.boettcher.pk)

        later = self.available()

        self.assertContains(later, "Gefiltert: Alex Böttcher")
        self.assertEqual(self.listed_supervisors(later), ["Alex Böttcher"])

    def test_the_dropdown_lists_only_supervisors_with_something_upcoming(self):
        # Criterion 17.
        quiet = make_user("q@example.org", Role.SUPERVISOR, "Neumann")
        self.make_session(quiet, in_days=-7)  # only a past session

        response = self.available()

        self.assertContains(response, "Böttcher")
        self.assertContains(response, "Krause")
        self.assertNotContains(response, "Neumann")
        self.assertContains(response, "Alle")

    def test_a_filter_on_a_supervisor_who_has_nothing_left_is_kept_not_tidied(self):
        # §7.1 requires that exact screen to be reachable: their name, that they
        # have nothing upcoming, and a way out. Clearing the filter for the user
        # would make the message of criterion 19 unreachable.
        self.available(supervisor=self.krause.pk)
        self.by_krause.status = SessionStatus.CANCELLED
        self.by_krause.save()

        response = self.available()

        self.assertContains(response, "Gefiltert: Alex Krause")
        self.assertContains(response, "Alex Krause bietet zurzeit keine Termine an")
        self.assertContains(response, "Filter entfernen")
        self.assertEqual(self.listed_supervisors(response), [])

    def test_the_current_choice_stays_in_the_dropdown_so_it_reflects_its_state(self):
        self.available(supervisor=self.krause.pk)
        self.by_krause.status = SessionStatus.CANCELLED
        self.by_krause.save()

        response = self.available()

        self.assertContains(response, f'value="{self.krause.pk}"')
        self.assertContains(response, "selected")


class EmptyStateTests(BrowsingScaffold):
    """Criterion 19, D28 — the two messages are never interchanged."""

    def test_no_sessions_at_all_says_none_are_scheduled(self):
        response = self.available()

        self.assertContains(response, "Zurzeit sind keine Termine eingetragen")
        self.assertNotContains(response, "bietet zurzeit keine Termine an")

    def test_sessions_exist_but_none_match_says_that_instead(self):
        boettchers = self.make_session(self.boettcher, in_days=7)
        self.make_session(self.krause, in_days=8)
        self.available(supervisor=self.boettcher.pk)

        # Böttcher's only session starts, so they have nothing upcoming while
        # the programme still does.
        self.clock.set(boettchers.starts_at)
        response = self.available()

        self.assertContains(response, "Alex Böttcher bietet zurzeit keine Termine an")
        # Never the no-sessions-at-all message: that would be a lie the user can
        # act on wrongly (D28).
        self.assertNotContains(response, "Zurzeit sind keine Termine eingetragen")
        self.assertContains(response, "Filter entfernen")

    def test_clearing_the_filter_from_that_screen_brings_the_programme_back(self):
        boettchers = self.make_session(self.boettcher, in_days=7)
        self.make_session(self.krause, in_days=8)
        self.available(supervisor=self.boettcher.pk)
        self.clock.set(boettchers.starts_at)

        cleared = self.available(supervisor="")

        self.assertEqual(self.listed_supervisors(cleared), ["Alex Krause"])

    def test_my_sessions_and_my_participation_have_their_own_empty_states(self):
        # Criterion 20.
        mine = self.client.get(reverse("participant_my_sessions"))
        self.assertContains(mine, "Sie sind noch für keinen Termin angemeldet")
        self.assertContains(mine, "Termine ansehen")

        participation = self.client.get(reverse("participant_participation"))
        self.assertContains(participation, "Sobald Sie an einer Supervision")
        # A visible 0, not a blank panel: a zero with an explanation is
        # trustworthy, a blank screen reads as a bug.
        self.assertContains(participation, ">0<")
        self.assertContains(participation, "Teilgenommene Supervisionen")


class TabTests(BrowsingScaffold):
    def test_all_three_tabs_are_reachable_and_mark_where_you_are(self):
        for url_name, expected in [
            ("participant_home", "Angebotene Termine"),
            ("participant_my_sessions", "Meine Termine"),
            ("participant_participation", "Meine Teilnahme"),
        ]:
            with self.subTest(tab=url_name):
                response = self.client.get(reverse(url_name))
                self.assertContains(response, expected)
                self.assertContains(response, 'aria-current="page"')

    def test_a_supervisor_cannot_open_the_participant_tabs(self):
        self.client.force_login(
            self.boettcher, backend="supervision.auth_backends.MagicLinkBackend"
        )

        response = self.client.get(reverse("participant_participation"))

        self.assertRedirects(response, reverse("home"), target_status_code=302)


class SessionDetailTests(BrowsingScaffold):
    """P2 (§7.1) — and D11, the Zoom link."""

    def setUp(self):
        super().setUp()
        self.boettcher.focus_area = "Tiefenpsychologie, Schwerpunkt Trauma"
        self.boettcher.profile_url = "https://example.org/boettcher"
        self.boettcher.save()
        self.session = self.make_session(self.boettcher, in_days=7)

    def test_the_detail_screen_shows_the_supervisor_and_their_schwerpunkt(self):
        response = self.client.get(reverse("session_detail", args=[self.session.pk]))

        self.assertContains(response, "Böttcher")
        self.assertContains(response, "Tiefenpsychologie, Schwerpunkt Trauma")
        self.assertContains(response, "Profil ansehen")

    def test_an_unregistered_participant_is_told_where_the_zoom_link_will_be(self):
        from supervision.models import Settings

        settings = Settings.load()
        settings.zoom_url = "https://zoom.example.org/j/steps"
        settings.save()

        response = self.client.get(reverse("session_detail", args=[self.session.pk]))

        self.assertNotContains(response, "zoom.example.org")
        self.assertContains(response, "sobald Sie angemeldet sind")

    def test_the_supervisor_holding_it_sees_the_link(self):
        from supervision.models import Settings

        settings = Settings.load()
        settings.zoom_url = "https://zoom.example.org/j/steps"
        settings.save()
        self.client.force_login(
            self.boettcher, backend="supervision.auth_backends.MagicLinkBackend"
        )

        response = self.client.get(reverse("session_detail", args=[self.session.pk]))

        self.assertContains(response, "zoom.example.org")

    def test_an_in_person_session_shows_the_room_and_no_zoom_section(self):
        room_session = self.make_session(
            self.krause, in_days=9, mode=Mode.IN_PERSON, room="2.14"
        )

        response = self.client.get(reverse("session_detail", args=[room_session.pk]))

        self.assertContains(response, "Raum 2.14")
        self.assertNotContains(response, "Zoom")

    def test_a_row_on_the_list_opens_the_detail_screen(self):
        response = self.available()

        self.assertContains(
            response, reverse("session_detail", args=[self.session.pk])
        )
