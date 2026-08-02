"""Fill a local database with the §12.2 fixture, for looking at the app.

Synthetic data only — invented names, `@example.org` addresses throughout (§11).
It refuses to run outside DEBUG: this exists to demonstrate, and a command that
invents twelve accounts has no business touching a real installation.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from supervision import demo
from supervision.clock import get_clock
from supervision.models import Session, User


class Command(BaseCommand):
    help = "Seed the §12.2 demonstration fixture. Local, synthetic data only."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing people and sessions first.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "seed_demo only runs with DEBUG on. It invents accounts, which "
                "is a demonstration, not an installation step."
            )

        if options["reset"]:
            Session.objects.all().delete()
            User.objects.all().delete()
        elif User.objects.exists() or Session.objects.exists():
            raise CommandError(
                "There are already people or sessions here. Re-run with --reset "
                "to replace them, or point at an empty database."
            )

        fixture = demo.build(get_clock().now())

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(fixture.participants)} participants, "
                f"{len(fixture.supervisors)} supervisors, one admin and "
                f"{len(fixture.sessions)} sessions."
            )
        )
        self.stdout.write("\nSign in as any of these — the link prints to this terminal:")
        for user in [fixture.admin, *fixture.supervisors, fixture.participants[0]]:
            self.stdout.write(f"  {user.role:11}  {user.email}")
