"""Django settings for the STEPS supervision app.

The stack decisions behind this file are in product-spec.md §15. Hosting and the
email provider are still open (§13, questions 7 and 8); nothing here depends on
either — SQLite stands in for Postgres and the console backend for the provider.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Development default. Production must supply DJANGO_SECRET_KEY from the
# environment; there is no hosting yet, so there is nothing else to read it from.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", "dev-only-insecure-key-do-not-use-in-production"
)

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "supervision",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# SQLite locally, Postgres in production (§15). No application difference:
# SQLite inside a transaction satisfies §6.2's atomic last-seat check.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# §15.1 — a custom, email-identified user with a role and no password field.
# Settled by the first migration and painful to change afterwards.
AUTH_USER_MODEL = "supervision.User"

# Sign-in is a magic link (§5); no password is ever checked, so the password
# backend would only be dead weight.
AUTHENTICATION_BACKENDS = ["supervision.auth_backends.MagicLinkBackend"]

# §5.4 — the signed-in session lasts 30 days with a sliding expiry.
SESSION_COOKIE_AGE = 30 * 24 * 60 * 60
SESSION_SAVE_EVERY_REQUEST = True

# §11 — sessions are wall-clock in Europe/Berlin; record-keeping timestamps are
# UTC instants, which is what USE_TZ gives us.
TIME_ZONE = "Europe/Berlin"
USE_TZ = True

# Translation is catalog-based, not gettext (§15, D39): msgfmt is absent here and
# Django's i18n reads only compiled .mo files. The catalog is supervision/catalog.py,
# transcribed from §14.
USE_I18N = False
LANGUAGE_CODE = "de"

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Locally the magic links print to the terminal, which is how you sign in
# without a mail provider (§15).
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "STEPS Supervision <supervision@example.org>"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
