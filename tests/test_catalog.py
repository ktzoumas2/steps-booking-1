"""The catalog is §14 (D39) — so this reads §14 and insists they are identical.

"If a string is not here, it is not on a screen" is only true if the two cannot
drift. Rather than trusting a transcription, these tests parse the tables out of
`product-spec.md` and compare them with `supervision/catalog.py`, key by key.
"""

import re
from pathlib import Path

from django.conf import settings
from django.template import Context, Template
from django.test import SimpleTestCase

from supervision.catalog import COPY, LOCALES, MissingCopy, t

SPEC = Path(settings.BASE_DIR) / "product-spec.md"

ROW = re.compile(r"^\|\s*`([a-z][a-z0-9_.]*)`\s*\|(.*?)\|(.*?)\|\s*$")
PLACEHOLDER = re.compile(r"%\((\w+)\)s")


def copy_from_spec() -> dict[str, dict[str, str]]:
    """Every `| \\`key\\` | de | en |` row of §14, as a dict."""
    lines = SPEC.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("## 14. Copy"))
    end = next(
        i for i, line in enumerate(lines[start + 1 :], start + 1) if line.startswith("## ")
    )

    entries: dict[str, dict[str, str]] = {}
    for line in lines[start:end]:
        match = ROW.match(line)
        if match:
            key, de, en = match.groups()
            entries[key] = {"de": de.strip(), "en": en.strip()}
    return entries


class SpecAgreementTests(SimpleTestCase):
    def setUp(self):
        self.spec_copy = copy_from_spec()

    def test_the_spec_section_was_actually_found(self):
        # A parser that silently matches nothing would make every other test pass.
        self.assertGreater(len(self.spec_copy), 100)
        self.assertEqual(self.spec_copy["app.name"]["de"], "STEPS Supervision")

    def test_no_key_is_missing_from_the_catalog(self):
        self.assertEqual(sorted(set(self.spec_copy) - set(COPY)), [])

    def test_no_key_is_invented_by_the_catalog(self):
        self.assertEqual(sorted(set(COPY) - set(self.spec_copy)), [])

    def test_every_string_matches_the_spec_exactly(self):
        for key, translations in sorted(self.spec_copy.items()):
            for locale in LOCALES:
                with self.subTest(key=key, locale=locale):
                    self.assertEqual(COPY[key][locale], translations[locale])


class CatalogShapeTests(SimpleTestCase):
    def test_every_key_has_both_languages_and_neither_is_blank(self):
        for key, translations in sorted(COPY.items()):
            with self.subTest(key=key):
                self.assertEqual(set(translations), set(LOCALES))
                for locale in LOCALES:
                    self.assertTrue(translations[locale].strip(), locale)

    def test_placeholders_agree_across_languages(self):
        # A placeholder present in one language and not the other renders a
        # German string with a name in it and an English one without.
        for key, translations in sorted(COPY.items()):
            with self.subTest(key=key):
                self.assertEqual(
                    set(PLACEHOLDER.findall(translations["de"])),
                    set(PLACEHOLDER.findall(translations["en"])),
                )


class RenderingTests(SimpleTestCase):
    def test_returns_german_by_default(self):
        self.assertEqual(t("action.save"), "Speichern")

    def test_substitutes_placeholders(self):
        self.assertEqual(
            t("p1.seats", "en", taken=3, capacity=5), "3 of 5 seats taken"
        )
        self.assertEqual(
            t("p1.seats", "de", taken=3, capacity=5), "3 von 5 Plätzen belegt"
        )

    def test_unknown_key_raises_rather_than_rendering_blank(self):
        with self.assertRaises(MissingCopy):
            t("p1.no_such_key")

    def test_template_tag_uses_the_locale_from_the_context(self):
        template = Template('{% load copy %}{% t "p1.action_full" %}')
        self.assertEqual(template.render(Context({"locale": "en"})), "Full")
        self.assertEqual(template.render(Context({"locale": "de"})), "Ausgebucht")

    def test_template_tag_takes_parameters(self):
        template = Template('{% load copy %}{% t "s1.registered_count" count=4 %}')
        self.assertEqual(template.render(Context({"locale": "de"})), "4 angemeldet")
