"""Templates render what they mean to render.

The first of these exists because of a real defect: Django's `{# ... #}` is a
**single-line** comment. When the closing `#}` sits on a later line, the opening
token is not recognised at all and the whole "comment" is emitted as page text —
so thirty explanatory notes were being printed onto the screens, in front of
users, for several slices. It is invisible in a diff and invisible in a passing
test suite; the only way to notice is to read a rendered page, or to check for
it deliberately, as here.
"""

import datetime as dt
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from supervision.clock import FixedClock, using_clock, wall_clock_to_instant
from supervision.models import Role, User

TEMPLATES = sorted(
    path for path in (Path(settings.BASE_DIR) / "templates").rglob("*") if path.is_file()
)
REFERENCE = wall_clock_to_instant(dt.date(2026, 9, 2), dt.time(10, 0))


class TemplateSyntaxTests(SimpleTestCase):
    def test_there_are_templates_to_check(self):
        # A glob that silently matches nothing would make the next test pass.
        self.assertGreater(len(TEMPLATES), 15)

    def test_no_comment_spans_lines_with_the_single_line_syntax(self):
        offenders = []
        for path in TEMPLATES:
            for number, line in enumerate(path.read_text().splitlines(), 1):
                if "{#" in line and "#}" not in line:
                    offenders.append(f"{path.name}:{number}")

        self.assertEqual(
            offenders,
            [],
            "Multi-line comments must use {% comment %}…{% endcomment %}; "
            "{# … #} only closes on its own line and otherwise renders as text.",
        )

    def test_every_comment_tag_is_closed(self):
        for path in TEMPLATES:
            body = path.read_text()
            with self.subTest(template=path.name):
                self.assertEqual(
                    body.count("{% comment %}"), body.count("{% endcomment %}")
                )


class RenderedPageTests(TestCase):
    """The other half: no template plumbing reaches the page."""

    LEAKS = re.compile(r"\{#|#\}|\{%\s*(comment|endcomment|if|for|block)\b")

    def setUp(self):
        self.enterContext(using_clock(FixedClock(REFERENCE)))
        self.people = {
            role: User.objects.create_user(
                first_name="Alex", last_name=role.title(),
                email=f"{role}@example.org", role=role, now=REFERENCE,
            )
            for role in (Role.PARTICIPANT, Role.SUPERVISOR, Role.ADMIN)
        }

    def sign_in(self, role):
        self.client.force_login(
            self.people[role], backend="supervision.auth_backends.MagicLinkBackend"
        )

    def assert_clean(self, response, where):
        body = response.content.decode()
        found = self.LEAKS.search(body)
        self.assertIsNone(found, f"{where} leaked template source: {found}")

    def test_no_screen_shows_its_own_source(self):
        screens = [
            (None, "signin"),
            (None, "signin_sent"),
            (Role.PARTICIPANT, "participant_home"),
            (Role.PARTICIPANT, "participant_my_sessions"),
            (Role.PARTICIPANT, "participant_participation"),
            (Role.SUPERVISOR, "supervisor_home"),
            (Role.SUPERVISOR, "supervisor_counts"),
            (Role.SUPERVISOR, "session_new"),
            (Role.ADMIN, "admin_home"),
            (Role.ADMIN, "admin_counts"),
            (Role.ADMIN, "admin_people"),
            (Role.ADMIN, "admin_settings"),
        ]
        for role, name in screens:
            with self.subTest(screen=name):
                self.client.logout()
                if role is not None:
                    self.sign_in(role)
                self.assert_clean(self.client.get(reverse(name)), name)
