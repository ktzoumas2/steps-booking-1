"""§5.1 — the one account created outside the app.

Rules 2 and 6 of §5 together lock an empty database: every account is created by
an admin, from a screen only an admin can reach. This command breaks that
deadlock exactly once, at install time, and then refuses to run again.

It sends no email. Whoever runs it knows the address they typed and requests a
magic link in the normal way.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from supervision.clock import get_clock
from supervision.models import Role, User


class Command(BaseCommand):
    help = "Create the install-time administrator (§5.1). Sends no email."

    def add_arguments(self, parser):
        parser.add_argument("--first-name", required=True)
        parser.add_argument("--last-name", required=True)
        parser.add_argument("--email", required=True)

    def handle(self, *args, **options):
        # A command that mints administrators is a way in: it must work once, at
        # install, and never become a standing back door.
        existing = User.objects.filter(role=Role.ADMIN, is_active=True).first()
        if existing is not None:
            raise CommandError(
                f"An active administrator already exists ({existing.email}). "
                "This command creates the install-time admin only — every later "
                "account, including every later admin, is added from the People "
                "screen (§7.3 A3)."
            )

        email = options["email"].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise CommandError(
                f"{email} is already registered. Ask an administrator to change "
                "that account's role instead."
            )

        try:
            admin = User.objects.create_user(
                first_name=options["first_name"].strip(),
                last_name=options["last_name"].strip(),
                email=email,
                role=Role.ADMIN,
                now=get_clock().now(),
            )
        except IntegrityError as exc:
            raise CommandError(f"Could not create the administrator: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Administrator created: {admin.full_name} <{admin.email}>"
            )
        )
        self.stdout.write(
            "No email was sent. Sign in by requesting a magic link for this "
            "address; locally the link is printed to the console."
        )
