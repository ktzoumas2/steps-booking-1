"""§12.3 acceptance criteria 3–6 and 67 — magic-link sign-in and the language.

Criterion 7 (the `Einladung senden` mail) needs the People screen and arrives
with it.
"""

import datetime as dt
import re
from io import StringIO

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from supervision.clock import FixedClock, using_clock
from supervision.models import EmailKind, EmailLog, LoginToken, Role, User
from supervision.signin import REQUESTS_PER_EMAIL_PER_HOUR, hash_token

NOW = dt.datetime(2026, 9, 1, 8, 0, tzinfo=dt.UTC)


def make_user(email, role=Role.PARTICIPANT, **overrides):
    return User.objects.create_user(
        first_name="Alex",
        last_name="Muster",
        email=email,
        role=role,
        now=NOW,
        **overrides,
    )


def link_from_last_email():
    """The magic link, as the recipient would click it."""
    match = re.search(r"https?://\S+/sign-in/(\S+)/", mail.outbox[-1].body)
    return match.group(1) if match else None


class SignInRequestTests(TestCase):
    """§5.1–5.2, §5.6 — and the promise that the screen never gives anyone away."""

    def setUp(self):
        self.clock = FixedClock(NOW)
        self.enterContext(using_clock(self.clock))
        self.user = make_user("anna@example.org")

    def test_registered_address_is_sent_a_working_single_use_link(self):
        # Criterion 3.
        response = self.client.post(reverse("signin"), {"email": "anna@example.org"})
        self.assertRedirects(response, reverse("signin_sent"))

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["anna@example.org"])
        token = LoginToken.objects.get()
        self.assertEqual(token.user, self.user)
        self.assertEqual(token.expires_at, NOW + dt.timedelta(minutes=15))
        self.assertIsNone(token.used_at)

        redeemed = self.client.get(
            reverse("signin_redeem", args=[link_from_last_email()])
        )
        self.assertRedirects(redeemed, reverse("home"), target_status_code=302)

    def test_the_raw_token_is_never_stored(self):
        # §4.5 — what is kept is a hash, and it matches the link that was sent.
        self.client.post(reverse("signin"), {"email": "anna@example.org"})

        raw = link_from_last_email()
        self.assertEqual(LoginToken.objects.get().token_hash, hash_token(raw))
        self.assertFalse(LoginToken.objects.filter(token_hash=raw).exists())

    def test_address_is_matched_case_insensitively(self):
        self.client.post(reverse("signin"), {"email": "ANNA@Example.ORG"})
        self.assertEqual(len(mail.outbox), 1)

    def test_unknown_address_looks_identical_and_sends_nothing(self):
        # Criterion 4.
        known = self.client.post(reverse("signin"), {"email": "anna@example.org"})
        mail.outbox.clear()

        unknown = self.client.post(reverse("signin"), {"email": "nobody@example.org"})

        self.assertEqual(unknown.status_code, known.status_code)
        self.assertEqual(unknown["Location"], known["Location"])
        self.assertEqual(mail.outbox, [])
        self.assertEqual(LoginToken.objects.count(), 1)

    def test_deactivated_address_looks_identical_and_sends_nothing(self):
        # Criterion 4, the other half: §5.6 treats unknown and deactivated alike.
        User.objects.update(is_active=False)

        response = self.client.post(reverse("signin"), {"email": "anna@example.org"})

        self.assertRedirects(response, reverse("signin_sent"))
        self.assertEqual(mail.outbox, [])

    def test_the_confirmation_promises_nothing_about_the_address(self):
        response = self.client.get(reverse("signin_sent"))
        self.assertContains(response, "Wenn diese Adresse hinterlegt ist")

    def test_requests_are_rate_limited_per_address(self):
        # §5.5 — and the screen still says the same thing afterwards.
        for _ in range(REQUESTS_PER_EMAIL_PER_HOUR):
            self.client.post(reverse("signin"), {"email": "anna@example.org"})
        self.assertEqual(len(mail.outbox), REQUESTS_PER_EMAIL_PER_HOUR)

        blocked = self.client.post(reverse("signin"), {"email": "anna@example.org"})

        self.assertRedirects(blocked, reverse("signin_sent"))
        self.assertEqual(len(mail.outbox), REQUESTS_PER_EMAIL_PER_HOUR)

    def test_the_allowance_returns_after_an_hour(self):
        for _ in range(REQUESTS_PER_EMAIL_PER_HOUR):
            self.client.post(reverse("signin"), {"email": "anna@example.org"})

        self.clock.advance(hours=1, seconds=1)
        self.client.post(reverse("signin"), {"email": "anna@example.org"})

        self.assertEqual(len(mail.outbox), REQUESTS_PER_EMAIL_PER_HOUR + 1)

    def test_mail_is_stamped_with_our_own_domain(self):
        # Not cosmetic: Django's default builds this from socket.getfqdn(), which
        # puts the sending machine's hostname in every mail and blocks for a full
        # DNS timeout on a host that does not resolve — 30 seconds, here.
        self.client.post(reverse("signin"), {"email": "anna@example.org"})

        message_id = mail.outbox[0].message()["Message-ID"]
        self.assertTrue(message_id.endswith("@example.org>"), message_id)

    def test_the_login_mail_is_logged(self):
        # §4.6 — and it carries no session, since there is none.
        self.client.post(reverse("signin"), {"email": "anna@example.org"})

        entry = EmailLog.objects.get()
        self.assertEqual(entry.kind, EmailKind.LOGIN)
        self.assertEqual(entry.user, self.user)
        self.assertEqual(entry.sent_at, NOW)


class RedeemTests(TestCase):
    """§5.3 and criterion 5 — a used or expired token is rejected, with an offer."""

    def setUp(self):
        self.clock = FixedClock(NOW)
        self.enterContext(using_clock(self.clock))
        self.user = make_user("anna@example.org")
        self.client.post(reverse("signin"), {"email": "anna@example.org"})
        self.raw_token = link_from_last_email()

    def redeem(self):
        return self.client.get(reverse("signin_redeem", args=[self.raw_token]))

    def test_a_valid_link_signs_the_user_in_and_spends_the_token(self):
        self.redeem()

        self.assertEqual(self.client.session["_auth_user_id"], str(self.user.pk))
        self.assertEqual(LoginToken.objects.get().used_at, NOW)

    def test_a_used_link_is_rejected_and_says_links_work_once(self):
        self.redeem()
        self.client.post(reverse("signout"))

        response = self.redeem()

        self.assertEqual(response.status_code, 410)
        self.assertContains(
            response, "bereits verwendet", status_code=410
        )
        self.assertContains(response, "Neuen Link anfordern", status_code=410)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_an_expired_link_is_rejected_and_names_the_fifteen_minutes(self):
        self.clock.advance(minutes=15, seconds=1)

        response = self.redeem()

        self.assertEqual(response.status_code, 410)
        self.assertContains(response, "15 Minuten", status_code=410)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_a_link_is_still_good_one_second_before_it_expires(self):
        self.clock.advance(minutes=14, seconds=59)

        self.redeem()

        self.assertEqual(self.client.session["_auth_user_id"], str(self.user.pk))

    def test_an_unknown_token_is_rejected(self):
        self.raw_token = "not-a-token-anyone-issued"
        self.assertEqual(self.redeem().status_code, 410)

    def test_deactivation_between_issuing_and_clicking_closes_the_door(self):
        User.objects.update(is_active=False)

        response = self.redeem()

        self.assertEqual(response.status_code, 410)
        self.assertNotIn("_auth_user_id", self.client.session)


class RoleHomeTests(TestCase):
    """Criterion 6 — signing in lands each role on its own home screen."""

    def setUp(self):
        self.enterContext(using_clock(FixedClock(NOW)))

    def sign_in(self, user):
        self.client.post(reverse("signin"), {"email": user.email})
        self.client.get(reverse("signin_redeem", args=[link_from_last_email()]))

    def test_each_role_lands_somewhere_different(self):
        cases = [
            (make_user("p@example.org", Role.PARTICIPANT), "participant_home"),
            (make_user("s@example.org", Role.SUPERVISOR), "supervisor_home"),
            (make_user("a@example.org", Role.ADMIN), "admin_home"),
        ]
        for user, expected in cases:
            with self.subTest(role=user.role):
                self.client.logout()
                self.sign_in(user)

                response = self.client.get(reverse("home"))

                self.assertRedirects(response, reverse(expected))

    def test_each_home_screen_shows_its_own_empty_state(self):
        # §7, D28 — on launch day every screen is empty, and the three messages
        # lead to different user actions.
        cases = [
            (make_user("p@example.org", Role.PARTICIPANT), "keine Termine eingetragen"),
            (make_user("s@example.org", Role.SUPERVISOR), "noch keine Termine angeboten"),
            (make_user("a@example.org", Role.ADMIN), "Legen Sie zuerst Personen an"),
        ]
        for user, expected in cases:
            with self.subTest(role=user.role):
                self.client.logout()
                self.sign_in(user)

                response = self.client.get(reverse("home"), follow=True)

                self.assertContains(response, expected)

    def test_a_role_cannot_open_another_role_s_home_screen(self):
        # §3 — one role per person, and the screens follow the role.
        self.sign_in(make_user("p@example.org", Role.PARTICIPANT))

        response = self.client.get(reverse("admin_home"))

        self.assertRedirects(response, reverse("home"), target_status_code=302)

    def test_signing_out_returns_to_the_sign_in_screen(self):
        self.sign_in(make_user("p@example.org", Role.PARTICIPANT))

        response = self.client.post(reverse("signout"))

        self.assertRedirects(response, reverse("signin"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_a_signed_out_visitor_is_sent_to_sign_in(self):
        self.assertRedirects(self.client.get(reverse("home")), reverse("signin"))


class LanguageTests(TestCase):
    """Criterion 67 — switching language changes every string, and persists."""

    def setUp(self):
        self.enterContext(using_clock(FixedClock(NOW)))
        self.user = make_user("anna@example.org")

    def switch_to(self, locale, from_url):
        return self.client.post(
            reverse("set_language"), {"locale": locale, "next": from_url}
        )

    def test_the_sign_in_screen_switches_before_anyone_has_an_account(self):
        german = self.client.get(reverse("signin"))
        self.assertContains(german, "Geben Sie Ihre E-Mail-Adresse ein")

        self.switch_to("en", reverse("signin"))
        english = self.client.get(reverse("signin"))

        self.assertContains(english, "Enter your email address")
        self.assertNotContains(english, "Geben Sie Ihre E-Mail-Adresse ein")

    def test_a_choice_made_before_signing_in_follows_the_person_into_the_app(self):
        self.switch_to("en", reverse("signin"))

        self.client.post(reverse("signin"), {"email": "anna@example.org"})
        self.client.get(reverse("signin_redeem", args=[link_from_last_email()]))

        self.user.refresh_from_db()
        self.assertEqual(self.user.locale, "en")
        self.assertContains(self.client.get(reverse("participant_home")), "Available")

    def test_a_signed_in_choice_is_saved_to_the_account(self):
        self.client.post(reverse("signin"), {"email": "anna@example.org"})
        self.client.get(reverse("signin_redeem", args=[link_from_last_email()]))

        self.switch_to("en", reverse("participant_home"))

        self.user.refresh_from_db()
        self.assertEqual(self.user.locale, "en")

    def test_the_toggle_returns_to_the_page_it_was_pressed_on(self):
        response = self.switch_to("en", reverse("signin_sent"))
        self.assertRedirects(response, reverse("signin_sent"))

    def test_the_toggle_refuses_to_leave_the_site(self):
        response = self.switch_to("en", "https://example.com/phish")
        self.assertRedirects(response, reverse("home"), target_status_code=302)

    def test_email_arrives_in_the_recipients_language(self):
        # Criterion 68, for the one mail that exists so far.
        User.objects.update(locale="en")

        self.client.post(reverse("signin"), {"email": "anna@example.org"})

        self.assertEqual(
            mail.outbox[0].subject, "Your sign-in link for STEPS Supervision"
        )
        self.assertIn("Click the link to sign in", mail.outbox[0].body)


class InstalledAdminCanSignInTests(TestCase):
    """Criterion 1, completed — the install-time admin can actually get in."""

    def test_the_created_admin_can_request_a_link_and_reach_their_home_screen(self):
        with using_clock(FixedClock(NOW)):
            from django.core.management import call_command

            call_command(
                "create_admin",
                first_name="Johanna",
                last_name="Beispiel",
                email="johanna@example.org",
                stdout=StringIO(),
            )

            self.client.post(reverse("signin"), {"email": "johanna@example.org"})
            self.client.get(reverse("signin_redeem", args=[link_from_last_email()]))

            response = self.client.get(reverse("home"), follow=True)

        self.assertContains(response, "Alle Termine")
