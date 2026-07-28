# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

An appointment booking app for **STEPS** (<http://www.steps-phb.de/>).

One document drives this project:

- `product-spec.md` — the single source of truth, for **intent and detail**:
  context and problem (§1.1–1.2), what is deliberately out of scope (§1.4),
  roles, data model, business rules, screens, emails and calendar invites,
  counting, success and acceptance criteria, and the open questions (§13).

Read it before making decisions about scope, features, or data model. It absorbed
the earlier `initial-brief.md` on 2026-07-28; that file no longer exists, so do
not look for it or reintroduce it. If the spec is silent or self-contradictory on
something, say so and get it decided — don't resolve it silently in code.

## Status

**Decisions recorded, nothing implemented.** No code, no dependencies installed,
no Django project scaffolded. The spec is now complete enough to build from:
every screen's copy is in §14, the stack is in §15.

The first version is meant to cover **all twelve screens** (P1–P3, S1–S5, A1–A4)
with sign-up, offering a session, the weekly cap, review and counts working, and
to run locally on SQLite. Deliberately out of that first version: calendar
invites (§8.2), real email delivery, and reminder scheduling (§8.3) — all three
wait on the hosting and provider decisions, and none is needed to see how the
app looks and behaves.

## Stack

Decided 2026-07-28. **Reasoning is in `product-spec.md` §15** — don't duplicate
it here, and don't change any of this without reading it.

- Language: **Python 3.13**, pinned with `uv`. The machine's own Python is
  3.14.5, which is newer than the Django LTS supports.
- Framework: **Django 5.2 LTS**, server-rendered templates. No separate API or
  client app.
- Database: **SQLite** locally, **Postgres** in production.
- Dependencies: **`uv`**.
- Translation: **catalog-based, not gettext** — `msgfmt` is not installed and
  Django reads only compiled `.mo`. The catalog is §14.
- Background work: **none**, ever. §11 forbids it; if something seems to need a
  scheduled job, that is a design smell, not a requirement.
- Hosting: **still open** (§13, open question 8), as is the email provider
  (open question 7). Neither blocks local work.

Three things are settled by the first migration and painful afterwards — a
custom user model with no password, separate date and time fields rather than a
combined timestamp, and UTC record-keeping timestamps. See §15.1 before writing
any model code.

Ask before adding a dependency beyond Django itself.

## Commands

**Not yet verified — no code exists to run them against.** These are the intended
commands; correct them against reality as soon as the project is scaffolded, and
delete this warning then.

```
uv sync                                   # install, pinned to Python 3.13
uv run manage.py migrate                  # create/update the database
uv run manage.py create_admin             # the install-time admin (§5.1)
uv run manage.py seed_demo                # the §12.2 fixture — synthetic data only
uv run manage.py runserver                # http://127.0.0.1:8000
uv run manage.py test                     # the acceptance criteria (§12.3)
```

Locally, email is written to the console — including magic links, which is how
you sign in without a mail provider (§15).

## Planned layout

Recorded so the "ask before adding a top-level directory" rule below is already
satisfied when scaffolding starts:

```
config/         Django project — settings, urls
supervision/    the single app — models, views, forms, templates, commands
templates/      base templates shared across the app
static/         css; no build step, no bundler
tests/          acceptance criteria from §12.3
pyproject.toml  dependencies, Python pin
```

## Conventions

- Language of the product UI: German (STEPS is a German organisation), with
  English as a full alternative. Keep code, comments, commit messages, and
  identifiers in English; keep user-facing copy in German. **Every user-facing
  string comes from `product-spec.md` §14** — if it isn't there, it doesn't go
  on a screen. Users are addressed as *Sie*.
- Dates and times: STEPS operates in Europe/Berlin. Sessions are stored as a
  local date + wall-clock time (a 10:00 session stays at 10:00 across DST);
  record-keeping timestamps are UTC instants. Weeks are ISO weeks, Mon–Sun.
  See `product-spec.md` §11.
- Personal data (names, contact details, appointment reasons) is GDPR-relevant.
  Do not log it, do not send it to third-party services, and do not commit real
  data or fixtures derived from it.

## Working notes

- Ask before adding a new top-level directory or a new service.
- Prefer small, reviewable changes over large scaffolds generated in one go.
