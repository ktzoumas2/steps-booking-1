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

Greenfield. No code, no stack chosen, no dependencies installed yet.

## Stack

_Not yet decided._ Once chosen, record here:

- Language / framework:
- Database:
- Hosting / deploy target:

Do not introduce a framework, ORM, or hosting dependency without asking first —
this decision is still open and should be made deliberately.

## Commands

_None yet._ Add install / dev / build / test / lint commands here as soon as
they exist, so they don't have to be rediscovered.

## Conventions

- Language of the product UI: German (STEPS is a German organisation). Keep
  code, comments, commit messages, and identifiers in English; keep user-facing
  copy in German.
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
