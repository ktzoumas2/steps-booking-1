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

**Runs locally, and you can sign into it.** Django 5.2.16 on Python 3.13.13,
installed with `uv`. What exists: the layout below, the `User`, `LoginToken` and
`EmailLog` models (§4.1, §4.5, §4.6), the injected clock (§11), the §14 copy
catalog with a test that keeps it and the spec identical, `create_admin` (§5.1),
magic-link sign-in (§5), the language toggle (§10), and the three role home
screens showing their real empty states. Acceptance criteria 1–6, 67 and 68 pass.

Not built yet: the `Session` and `Registration` models, and every screen that
needs them — which is most of §7.

The first version is meant to cover **all twelve screens** (P1–P3, S1–S5, A1–A4)
with sign-up, offering a session, the weekly cap, review and counts working, and
to run locally on SQLite. Deliberately out of that first version: calendar
invites (§8.2), real email delivery, and reminder scheduling (§8.3) — all three
wait on the hosting and provider decisions, and none is needed to see how the
app looks and behaves.

## Build order

Agreed 2026-07-29. Each slice ends somewhere clickable, and the numbers are
§12.3 acceptance criteria.

1. ~~Scaffold, user model, clock, catalog, `create_admin`~~ — done (1–2)
2. ~~Magic link, sessions, roles, sign-out, language toggle~~ — done (3–6, 67,
   and 68 for the one mail that exists). Criterion 7 needs A3 and moved to
   slice 9.
3. Supervisor: offer / edit / cancel a session, weekly cap (8–14)
4. Participant: browse, filter, week grouping, empty states (15–20)
5. Sign-up, capacity, the last-seat race, cancellation (21–25)
6. Review screen and the assumed-held default (43–54)
7. Counts, P3, A2, the four CSVs, the export sign-off (55–65)
8. Email bodies, the `.ics` builder, the two mail ports against fakes (26, 28–33)
9. Admin people and settings, the deactivation rules (66)
10. The §12.2 seed fixture — the data the demo is shown with

Two things sit deliberately outside the numbering, both agreed 2026-07-29:

- **The `.ics` builder is built now, in slice 8**, not deferred with the rest of
  the calendar work. Generating the `VEVENT` is a pure function and needs no
  provider; only verifying that a provider ships it unaltered does (§13 q7a).
  It also makes P2's `Zum Kalender hinzufügen` work locally.
- **A dev-only "sign in as" switch**, hard-gated on `DEBUG`, so showing three
  roles to a user does not mean fishing magic links out of the terminal. The
  real magic-link flow is built and tested regardless.

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

Verified against the code, except where marked.

```
uv sync                                   # install, pinned to Python 3.13
uv run manage.py migrate                  # create/update the database
uv run manage.py test                     # the acceptance criteria (§12.3)
uv run manage.py create_admin \
    --first-name X --last-name Y --email z@example.org
                                          # the install-time admin (§5.1)
uv run manage.py seed_demo                # NOT BUILT YET — the §12.2 fixture
uv run manage.py runserver                # runs, but there are no screens yet
```

Locally, email is written to the console — including magic links, which is how
you sign in without a mail provider (§15).

## Layout

```
config/         Django project — settings, urls, wsgi
supervision/    the single app
  clock.py        §11 — the injected clock, plus Berlin wall-clock and ISO-week helpers
  catalog.py      §14 — every user-facing string, both languages
  models.py       §4 — the data model
  auth_backends.py  §5 — session loading for magic-link sign-in
  management/commands/create_admin.py   §5.1
  templatetags/copy.py   {% t "key" %}
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
- **Never read the clock.** No `timezone.now()`, no `auto_now_add`, no
  `auto_now`, no `datetime.now()` outside `supervision/clock.py`. The instant is
  passed in — services take a `now` argument, the request layer resolves it once.
  §11 requires it and every time-dependent acceptance criterion depends on it.
- Personal data (names, contact details, appointment reasons) is GDPR-relevant.
  Do not log it, do not send it to third-party services, and do not commit real
  data or fixtures derived from it.

## Working notes

- Ask before adding a new top-level directory or a new service.
- Prefer small, reviewable changes over large scaffolds generated in one go.
