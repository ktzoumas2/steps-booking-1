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

**Everything the spreadsheet did, plus invites and reminders.** Django 5.2.16
on Python 3.13.13, installed with `uv`. All of §4's models exist. **All twelve
screens** (P1–P3, S1–S5, A1–A4), plus sign-in.
Plus the injected clock (§11), the §14 catalog with a test that keeps it and the
spec identical, `create_admin` (§5.1), the weekly cap (§6.1), week grouping and
the supervisor filter (§7.1), the atomic last seat (§6.2), the assumed-held
default and its corrections (§6.4), the two counts of §9.1, the four CSV exports
with their BOM (§9.2), the billing sign-off (§7.3), all eight mails of §8.1
the `.ics` builder (§8.2) and the reminder scheduling port
(§8.3), and all eight mails of §8.1.
Plus the §12.2 fixture, behind `seed_demo`.
**Acceptance criteria 1–33, 43–69 pass — everything except the ten that need a
real email provider or a real calendar client (27, 34, 35–42).**

The first version is complete. What remains is not code: hosting (§13 q8), the
email provider (§13 q7), and STEPS confirming the open questions of §13.

**Known gaps, deliberate and recorded rather than forgotten:**

- **Five strings are missing from §14** and live in
  `supervision/pending_copy.py`, the only place this app holds user-facing
  copy outside the catalog: weekday names, month names, a date range's *from*
  and *to*, and the two *Add to calendar* link labels. Each is explained
  there; all belong in a §14.11.
- **The weekly cap is checked on save only.** §7.2 also wants it inline as soon
  as the date is picked, which needs a little client-side scripting. The cap
  itself now advises rather than refuses (§6.1, rewritten 2026-08-02): at the
  cap a warning, above it a stronger one, neither ever blocking. There is no
  `enforce_weekly_cap` setting any more — it had nothing left to control.
- **The supervisor dropdown auto-submits** via a single inline `onchange`, the
  only JavaScript in the app. Without it a `<select>` needs a submit button, and
  §14 has no label for one — the alternative would be inventing copy. Filtering
  therefore does not work with JavaScript off.
- **A filter naming a supervisor with nothing upcoming is kept, not cleared.**
  §7.1 requires that screen (their name, and a way out); tidying the filter away
  would make criterion 19's second message unreachable. The current choice stays
  in the dropdown so the control still reflects its own state.
- **§14.10 has no `email.registration_confirmed.body`.** §8.1 says that mail
  carries "session details + how to cancel", but there is no string for the
  second half, so the mail currently sends the details alone.
- **Session mails carry no link to the session.** The `.ics` is attached, but
  a URL into the app needs hosting to settle what its base URL is (§13 q8).
- **Locally, reminders are sent at sign-up**, not held: `ImmediateScheduler`
  ignores the timing, which §8.3 sanctions as complete and correct without a
  provider. Tests use `RecordingScheduler`, which models a real one.
- **SQLite needs `transaction_mode: IMMEDIATE`** for §6.2's atomic last seat —
  see the comment in `config/settings.py`. Do not remove it.
- **No control returns `took_place` to `null`.** §6.4 allows it ("no claim
  either way", which still counts), but §14 has no label for such a button, and
  `null` and `true` differ only in the `took_place` column of the §9.2 export.
  `Alles wie geplant` sets `true`, which is the more honest record of a human
  having looked.

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
3. ~~Supervisor: offer / edit / cancel a session, weekly cap~~ — done (8–14,
   and 50, 51, 65 came along with cancelling and the derived state)
4. ~~Participant: browse, filter, week grouping, empty states~~ — done (15–17,
   19, 20). Criterion 18 needs a session to be *full*, so it moved to slice 5.
5. ~~Sign-up, capacity, the last-seat race, cancellation~~ — done (18, 21–25)
6. ~~Review screen and the assumed-held default~~ — done (43–49, 52–54;
   50 and 51 came with slice 3, and 60 fell out of the counting rules)
7. ~~Counts on screen — S5, A2, P3 — the four CSVs, the export sign-off~~ —
   done (55–59, 61–64)
8. ~~Email bodies, the `.ics` builder, the scheduling port~~ — done (26,
   28–33, 69, and the structure behind 35–42)
9. ~~Admin people and settings, the deactivation rules~~ — done (7, 66)
10. ~~The §12.2 seed fixture~~ — done, plus the DEBUG-only role switch

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
uv run manage.py seed_demo [--reset]      # the §12.2 fixture — synthetic only
uv run manage.py runserver                # http://127.0.0.1:8000
```

Locally, email is written to the console — including magic links, which is how
you sign in without a mail provider (§15). With `DEBUG` on, `/dev/sign-in-as/`
skips that for demonstrations; the route 404s in any other configuration.

## Layout

```
config/         Django project — settings, urls, wsgi
supervision/    the single app
  clock.py        §11 — the injected clock, plus Berlin wall-clock and ISO-week helpers
  catalog.py      §14 — every user-facing string, both languages
  formatting.py   §10 — date and time formats (and the weekday names §14 lacks)
  models.py       §4 — the data model
  sessions.py     §6.1, §6.3, §6.5 — the weekly cap, create / update / cancel
  registrations.py §6.2, §6.3 — sign-up, the atomic last seat, giving up a place
  review.py       §6.4 — recording what happened, and correcting it
  people.py       §4.1, §7.3 A3 — adding people, and the deactivation rules
  demo.py         §12.2 — the fixture, shared by the demo and the tests (D42)
  counting.py     §9.1 — the two counts, both written `is not False`
  exports.py      §9.2 — the four CSVs, UTF-8 **with BOM** for Excel
  calendar.py     §8.2 — the .ics: stable UID, rising SEQUENCE, one attendee
  scheduling.py   §8.3 — the three-operation port; the app decides, it carries out
  pending_copy.py the only user-facing strings outside §14, each a flagged gap
  signin.py       §5 — magic-link issue and redemption
  mail.py         §8.1 — one sender for every kind of mail
  forms.py        S2, with the validation of §7.4
  views.py        the screens of §7
  auth_backends.py  §5 — session loading for magic-link sign-in
  management/commands/create_admin.py   §5.1
  templatetags/copy.py     {% t "key" %}
  templatetags/display.py  {% when %} {% where %} {% duration %}
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
- **Check the rendered page, not just the response.** Three defects reached the
  user from one blind spot: asserting that the server did the right thing
  instead of that a person gets the right result.
  - Thirty `{# … #}` comments printed themselves onto every screen for several
    slices. Django's is a *single-line* comment; multi-line ones render as text.
    `tests/test_templates.py` guards this now.
  - The export buttons "did nothing" because every test posted a dict through
    the test client, which bypasses the HTML form entirely, and the server
    refused silently.
  - `step="900"` on a time input satisfied a test and changed nothing a user
    could see; browsers still accept a typed 10:07. It had to become a select.
  When a change is visible, look at it — `curl` the page and read it, or ask
  for a screenshot. A green suite proves less here than thirty seconds of
  looking.
