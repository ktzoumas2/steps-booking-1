"""§12.3 acceptance criteria 1 and 2, and the user model rules of §4.1.

Criterion 1 is only half testable here — "who can then request a magic link and
reach A3" arrives with the sign-in slice. What is testable now is that the empty
database gets exactly one admin, and that the command cannot be used twice.
"""

import datetime as dt
from io import StringIO

from django.core import mail
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.utils import IntegrityError
from django.test import TestCase

from supervision.clock import FixedClock, using_clock
from supervision.models import Role, User

INSTALL_TIME = dt.datetime(2026, 9, 1, 8, 0, tzinfo=dt.UTC)


def create_admin(**overrides):
    options = {
        "first_name": "Johanna",
        "last_name": "Beispiel",
        "email": "johanna@example.org",
    } | overrides
    with using_clock(FixedClock(INSTALL_TIME)):
        call_command("create_admin", stdout=StringIO(), **options)


class CreateAdminTests(TestCase):
    def test_creates_one_active_admin_on_an_empty_database(self):
        create_admin()

        admin = User.objects.get()
        self.assertEqual(admin.role, Role.ADMIN)
        self.assertTrue(admin.is_active)
        self.assertEqual(admin.full_name, "Johanna Beispiel")
        self.assertEqual(admin.locale, "de")

    def test_records_the_supplied_instant_rather_than_the_system_clock(self):
        create_admin()
        self.assertEqual(User.objects.get().created_at, INSTALL_TIME)

    def test_sends_no_email(self):
        create_admin()
        self.assertEqual(mail.outbox, [])

    def test_refuses_once_an_active_admin_exists(self):
        create_admin()

        with self.assertRaises(CommandError) as caught:
            create_admin(email="second@example.org")

        self.assertIn("already exists", str(caught.exception))
        self.assertIn("johanna@example.org", str(caught.exception))
        self.assertEqual(User.objects.count(), 1)

    def test_runs_again_if_the_only_admin_was_deactivated(self):
        # Otherwise deactivating the last admin would lock the installation out
        # for good: §5 has no other way in.
        create_admin()
        User.objects.update(is_active=False)

        create_admin(email="second@example.org")

        self.assertEqual(User.objects.filter(is_active=True).count(), 1)

    def test_refuses_an_address_that_is_already_registered(self):
        create_admin()
        User.objects.update(is_active=False)

        with self.assertRaises(CommandError) as caught:
            create_admin(email="JOHANNA@example.org")

        self.assertIn("already registered", str(caught.exception))


class UserModelTests(TestCase):
    def make(self, email, **overrides):
        fields = {
            "first_name": "Alex",
            "last_name": "Muster",
            "email": email,
            "role": Role.PARTICIPANT,
            "now": INSTALL_TIME,
        } | overrides
        return User.objects.create_user(**fields)

    def test_email_is_unique_case_insensitively(self):
        self.make("anna@example.org")

        # Validation catches it first, so a form can say so in words...
        with self.assertRaises(ValidationError):
            self.make("Anna@Example.org")

        # ...but the constraint is in the database, not only in the form.
        duplicate = User(
            first_name="Alex",
            last_name="Muster",
            email="ANNA@EXAMPLE.ORG",
            role=Role.PARTICIPANT,
            created_at=INSTALL_TIME,
        )
        with self.assertRaises(IntegrityError):
            duplicate.save()

    def test_lookup_by_natural_key_ignores_case(self):
        anna = self.make("anna@example.org")
        self.assertEqual(User.objects.get_by_natural_key("ANNA@example.org"), anna)

    def test_roles_are_readable_as_predicates(self):
        participant = self.make("p@example.org")
        supervisor = self.make("s@example.org", role=Role.SUPERVISOR)

        self.assertTrue(participant.is_participant)
        self.assertFalse(participant.is_supervisor)
        self.assertTrue(supervisor.is_supervisor)
        self.assertFalse(supervisor.is_admin)

    def test_there_is_no_password_field(self):
        # §15.1 — authentication is a magic link; nothing is ever hashed here.
        field_names = {field.name for field in User._meta.get_fields()}
        self.assertNotIn("password", field_names)
        self.assertNotIn("last_login", field_names)
