# Product Specification — STEPS Supervision Booking

**This is the single source of truth for the product** — intent *and* detail. It
absorbed the original `initial-brief.md` on 2026-07-28; that document is gone, and what
it carried that this one did not — the organisational context, the problem being solved,
the scope boundary and the success criteria — is now §1 and §12.1.

**It specifies behaviour, data and rules in plain terms** — not schema syntax, not code.
Where it names a field or a value, that is the rule, not the column definition.

**The stack is now part of this document** (§15). Earlier drafts kept it deliberately
technology-free and left the choice to a separate technical plan; that plan never
materialised, and a spec you cannot build from is not finished. §15 carries the technical
decisions with the same reasoning as everything else, and flags the three that become
expensive to reverse once the first migration has run.

**Decisions taken while specifying** are marked **[D]** and listed together in §13.
Anything still unresolved is marked **[?]**.

---

## 1. Context, problem and scope

### 1.1 What STEPS is

STEPS is a counselling project of the **Psychologische Hochschule Berlin (PHB)**, started
in spring 2022 as an initiative of psychology students and trainees at PHB and the
Berliner Akademie für Psychotherapie (BAP). It offers free psychotherapeutic counselling
("psychotherapeutische Beratung") — up to 10 sessions — to people with refugee experience
("Menschen mit Fluchterfahrung"), in their own language, regardless of residency status
or insurance. Based at Am Köllnischen Park 1, 10179 Berlin.
Site: <http://www.steps-phb.de/>

The counselling is delivered by trainee psychotherapists ("Psychotherapeut\*innen i.A.")
working across behavioural, depth-psychological and systemic approaches, with interpreters
where needed. PHB backs them with a training curriculum and regular **supervision** from
professors and licensed psychotherapists. Project direction: Prof. Dr. Johanna Böttcher.
Roughly 12 trainees plus administrative and support staff.

**This app is about the *supervision* layer only** — scheduling and recording the
supervision sessions the trainees attend. It has nothing to do with booking client
counselling appointments, and it stores no client data. That boundary is the reason §11
can keep the data-protection surface as small as it is.

### 1.2 Why we are replacing the spreadsheet

Supervision is currently managed in Excel. Where that falls down — each of these is a
thing the app has to actually fix, and §12.1 measures whether it did:

- **No self-service.** Participants can't see what's on offer or sign themselves up.
- **No reminders.** Nothing goes out before a session; the Zoom link gets re-sent by hand.
- **Sessions cluster.** Nothing stops several sessions landing in the same week.
- **Counting hours is manual.** Attendance has to be tallied by hand for billing.
- **One file, many hands.** Concurrent edits, versions travelling by email.

> **The most important requirement is ease of use.** None of the users are tech-savvy,
> so the interface must be very simple and self-explanatory. Wherever this spec implies a
> trade-off between simplicity and completeness, **simplicity wins.** This is the primary
> design constraint, not a preference.

### 1.3 The product in one paragraph

A small web app that replaces a spreadsheet. Supervisors offer supervision sessions;
trainee psychotherapists browse the coming weeks, filter by supervisor and sign
themselves up; everyone gets reminded by email, with a calendar invite so the session
lands in their own calendar; a session that has ended counts as held with everyone
present, and the supervisor or admin only steps in when something was different; the
administrator counts sessions per supervisor for billing, and every participant can see
their own participation record. Roughly 12 participants, a handful of supervisors, one admin.
**The users are not technical — simplicity beats completeness everywhere in this spec.**

### 1.4 What this app is not

Out of scope for v1. This list is load-bearing: most of these are things someone will
reasonably suggest, and the answer is "yes, and deliberately not now".

| Not building | Why not |
| --- | --- |
| Booking client counselling appointments, or anything touching client data | A different system entirely; §1.1 draws the line |
| Payments, invoicing or invoice generation | We export the counts (§9.2); billing happens elsewhere |
| Creating Zoom meetings via API | One fixed link in settings is enough (§4.4) |
| A subscribable calendar feed or two-way calendar sync | Invites cover "the session is in my calendar" (§8.2). A feed is revisitable — §13 open question 10 |
| Waiting lists when a session is full | Full is full; with ~5 seats and ~12 people, the next session is days away |
| Recurring-session templates ("every Tuesday for 10 weeks") | A handful of sessions a month, entered by hand, does not justify it |
| Notification by anything but email — SMS, push, WhatsApp | Email carries the invites (§8.2) and everyone already has it |
| In-app messaging between supervisors and participants | Email exists; a message inbox is a support surface nobody will staff |
| Reporting beyond the counts and CSV exports in §9 | Anything else can be built from the session-level export |
| Attendance certificates, or anything official generated from participation | Recorded and shown (§7.1 P3), but not yet an official document — see §13 open question 2 |
| Multi-tenancy | This serves STEPS only |
| A native mobile app | Mobile-first web is the requirement (§11) |
| A calendar-grid view of sessions | **[D]** Screens are lists (§7). At ~1–2 sessions a week a month grid is mostly empty, and it is the harder thing to make work on a phone. Week grouping (§7.1) gives the same "what's coming" read |

Adjacent systems we do **not** own: the STEPS website (steps-phb.de) stays separate — at
most it links to the app; Zoom is one pasted link, never an integration; and PHB
university logins are assumed unavailable to trainees, which is why sign-in is a magic
link (§5).

## 2. Glossary

| Term | Meaning |
| --- | --- |
| **Supervision session** ("SV") | A single scheduled supervision meeting, held by one supervisor, attended by several participants |
| **Supervisor** | Professor or licensed psychotherapist who holds sessions |
| **Participant** | Trainee psychotherapist ("Psychotherapeut\*in i.A.") who attends |
| **Administrator** | The Projektträger (PHB); oversees everything |
| **Schwerpunkt** | A supervisor's focus area, free text, e.g. "psychodynamic therapy, focus on trauma" |
| **Took place** ("SV hat stattgefunden") | Whether a session actually happened. Assumed true once it has ended; recorded explicitly only when it did **not** (§6.4) |
| **Attendance** ("Teilnahme") | Whether one participant was present at a session that took place. Assumed true for everyone registered; recorded explicitly only for absences |
| **Reviewed** ("geprüft") | Whether a human has opened a past session and saved it. Never affects any count — only what the admin is shown before exporting (§7.3 A2) |
| **Participation record** | A participant's history of attended sessions — how many, and which ones (§9.1) |
| **Calendar invite** | An iCalendar (`.ics`) attachment shipped with a session email, which Apple Calendar, Google Calendar and Outlook all import (§8.2) |
| **Calendar week** | ISO week, Monday–Sunday, in Europe/Berlin |

## 3. Roles and permissions

One role per person. **[D]** A person cannot be both supervisor and participant; if
that turns out to be needed, it becomes a second account (see §13).

| Action | Participant | Supervisor | Admin |
| --- | :---: | :---: | :---: |
| Sign in by magic link | ✓ | ✓ | ✓ |
| View offered sessions, filtered by supervisor and week | ✓ | ✓ | ✓ |
| Sign up for / cancel own registration | ✓ | — | — |
| See who else is registered for a session | ✓ | ✓ | ✓ |
| Create / edit / cancel **own** sessions | — | ✓ | ✓ |
| Create / edit / cancel **anyone's** sessions | — | — | ✓ |
| Review a past session — record a no-show or an absence — for **own** sessions | — | ✓ | ✓ |
| Review **anyone's** sessions | — | — | ✓ |
| **Correct** a review afterwards, for the sessions they may review | — | ✓ | ✓ |
| Export billing figures, acknowledging unreviewed sessions | — | — | ✓ |
| View **own** participation record | ✓ | — | — |
| View **anyone's** participation record | — | — | ✓ |
| Edit own profile (name, Schwerpunkt, profile link) | name only | ✓ | ✓ |
| View counts and export CSV | — | own sessions only | ✓ (all) |
| Add / deactivate people, set roles | — | — | ✓ |
| Edit global settings | — | — | ✓ |
| Override the weekly cap | — | — | ✓ |

**[D]** Supervisors can see their own session counts (they invoice against them);
they cannot see other supervisors' counts or participant counts.

**[D]** A participant sees the attendance of their **own** registrations only. They
already see who else is registered for a session (that is on the session detail
screen), but not whether those others were marked present — that is between the other
participant and the programme.

## 4. Data model

Field types are described in plain terms. `?` marks nullable.

### 4.1 `User`

| Field | Type | Notes |
| --- | --- | --- |
| `id` | id | |
| `first_name` | text | required |
| `last_name` | text | required |
| `email` | text | required, **unique, compared case-insensitively**; the login identity |
| `role` | enum | `participant` \| `supervisor` \| `admin` |
| `focus_area` | text? | Schwerpunkt — supervisors only |
| `profile_url` | text? | supervisors only, optional |
| `locale` | enum | `de` \| `en`, default `de` |
| `is_active` | bool | default true; inactive users cannot sign in and are hidden from pickers, but their history is preserved |
| `created_at` | timestamp | UTC instant |

Deactivate, never delete — deleting a user would orphan past sessions and attendance
records that billing depends on. See §11 for the retention exception.

**What deactivation does to future commitments** — preserving history is not enough:

- **Deactivating a participant** cancels their active registrations for sessions not yet
  started. Seats free immediately, and they get the usual `registration_cancelled` mail
  and cancellation invite (§8). Past registrations and recorded attendance are untouched
  and still count (§9.1).
- **Deactivating a supervisor is blocked** while they hold upcoming `offered` sessions;
  the message names those sessions so the admin cancels or reassigns them first. **[D]**
  Leaving them offered strands participants with a supervisor who cannot sign in;
  auto-cancelling fires mail the admin never chose to send. Making them choose is the
  only option that surprises nobody.
- **Reactivating restores nothing.** Cancelled registrations and sessions stay cancelled;
  the person signs up again like anyone else.

**Changing someone's email** (admin only, §7.3 A3) moves the login identity and all future
mail, but cannot reach backwards: invites already delivered name the old address as
`ATTENDEE`, so later updates or cancellations never reach the calendar entries sitting in
the old mailbox. **[D]** Accepted rather than solved — the app warns the admin at the
point of change. Chasing it properly means reissuing every future invite, which is a lot
of machinery for something that will happen perhaps twice.

### 4.2 `Session`

| Field | Type | Notes |
| --- | --- | --- |
| `id` | id | |
| `supervisor_id` | → User | must have role `supervisor` |
| `date` | date | local calendar date, Europe/Berlin |
| `start_time` | time | local wall-clock time, Europe/Berlin |
| `duration_minutes` | integer | required, varies per session; pre-filled from settings default |
| `mode` | enum | `online` \| `in_person` |
| `room` | text? | required when `mode = in_person`, otherwise empty |
| `capacity` | integer | default from settings (5); minimum 1 |
| `status` | enum | `offered` \| `cancelled` |
| `cancelled_at` | timestamp? | when `status` became `cancelled` |
| `cancelled_by` | → User? | supervisor or admin who cancelled it |
| `took_place` | bool? | `null` = **nobody has reviewed it**; once the end time passes that counts as *held* (§6.4) |
| `confirmed_at` | timestamp? | `null` = never reviewed by a human; otherwise when it was last reviewed |
| `confirmed_by` | → User? | supervisor or admin who last reviewed it |
| `calendar_uid` | text | stable iCalendar `UID`, generated once at creation, never reused or changed (§8.2) |
| `calendar_sequence` | integer | starts at 0; **incremented on every change that is sent out as an updated invite**, and on cancellation |
| `created_at`, `updated_at` | timestamp | UTC instants |

**Online sessions carry no per-session link.** The Zoom URL lives once in settings
(§4.4) and is read at display/send time, so changing it fixes every future session at
once.

`calendar_uid` and `calendar_sequence` exist so that a calendar client recognises an
updated or cancelled invite as *the same event* and replaces it, instead of leaving the
participant with two entries for one session. This is the whole difficulty of calendar
invites; see §8.2.

`cancelled_at` / `cancelled_by` are recorded for the same reason as `confirmed_by`: a
cancelled session vanishes from a supervisor's billing count, an admin may cancel any
supervisor's session (§3), and "who cancelled this, and when" must be answerable.

**Derived state** (never stored — compute it):

| Derived state | Condition |
| --- | --- |
| Upcoming | `status = offered` and start is in the future |
| In progress | `status = offered` and now is between start and start + duration |
| Held | `status = offered`, ended, and `took_place is not false` |
| Not held | `took_place = false` |
| Cancelled | `status = cancelled` |
| *(overlay)* Not reviewed | `confirmed_at is null` — orthogonal to the above, not a state of its own |

**Held is derived, never written** — the end time passing is the only event, and it needs
no job because it follows from `date`, `start_time` and `duration_minutes` at read time.
The default behind it is §6.4; *reviewed* is orthogonal and never affects a count.

### 4.3 `Registration`

| Field | Type | Notes |
| --- | --- | --- |
| `id` | id | |
| `session_id` | → Session | |
| `user_id` | → User | must have role `participant` |
| `source` | enum | `self_signup` \| `added_at_confirmation` — how the row came to exist |
| `created_at` | timestamp | when they signed up |
| `cancelled_at` | timestamp? | set when the participant withdraws; the row stays |
| `attended` | bool? | `null` = **nobody said otherwise**, which counts as *present* at a held session (§6.4) |
| `attendance_recorded_at` | timestamp? | when `attended` was **last** written |
| `attendance_recorded_by` | → User? | supervisor or admin who last wrote it |
| `reminder_message_id` | text? | the email provider's handle for this person's scheduled reminder, so it can be cancelled or rescheduled (§8.3) |

**Uniqueness:** at most one *active* (`cancelled_at is null`) registration per
(session, user). A participant who cancels and signs up again reuses or replaces the
row rather than accumulating duplicates.

Cancelled registrations are kept, not deleted — they explain why a seat freed up.

`source = added_at_confirmation` marks someone the supervisor added afterwards because
they turned up without signing up (§6.4). Those rows do **not** occupy a seat
retrospectively and are exempt from the capacity check — the session is over; capacity
is a sign-up rule, not a room limit to enforce after the fact.

`attendance_recorded_at` / `attendance_recorded_by` exist because attendance can be
corrected long after the session (§6.4) and it is the figure the participation record
and the participant counts are built on. When a correction is disputed, "who ticked
this, and when" is the only question that gets asked.

### 4.4 `Settings` (single row)

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `zoom_url` | text | — | the one link used for all online sessions |
| `default_duration_minutes` | integer | 90 **[D]** | pre-fills the session form |
| `default_capacity` | integer | 5 | pre-fills the session form |
| `weekly_session_cap` | integer | 2 | programme-wide, see §6.1 |
| `reminder_lead_hours` | integer | 24 **[D]** | how far ahead the reminder goes out |

### 4.5 `LoginToken`

| Field | Type | Notes |
| --- | --- | --- |
| `id` | id | |
| `user_id` | → User | |
| `token_hash` | text | **store a hash, never the raw token** |
| `expires_at` | timestamp | issued_at + 15 minutes **[D]** |
| `used_at` | timestamp? | single use — reject if already set |

### 4.6 `EmailLog`

| Field | Type | Notes |
| --- | --- | --- |
| `id` | id | |
| `user_id` | → User | |
| `session_id` | → Session? | null for login emails |
| `kind` | enum | see §8 |
| `sent_at` | timestamp | |

**A plain audit log — no idempotency machinery.** Nothing here enforces send-once,
because nothing needs to: every mail is sent synchronously in response to a user action,
and the one time-delayed mail (`reminder`) is held and delivered by the email provider,
which owns that guarantee (§8.3). There is no scheduler to run twice.

Its remaining job is answering **"was this person ever sent a `REQUEST` for this
session?"**, which decides whether they may be sent a `CANCEL` (§8.3). That is a lookup,
not a lock.

## 5. Authentication and access

1. User enters their email on the sign-in screen.
2. If an **active** user with that email exists, send a magic-link email. **Always show
   the same "Check your email" confirmation either way** — never reveal whether an
   address is registered.
3. The link contains a single-use token, valid 15 minutes. Clicking it signs the user
   in and marks the token used.
4. The signed-in session lasts **30 days** **[D]** with a sliding expiry, then requires
   a new link. Chosen for these users: re-authenticating often is exactly the friction
   §1.2 warns against, and the data is low-sensitivity (no client data).
5. Requesting a link is rate-limited — **[D]** 5 per email per hour, 20 per IP per hour.
6. There is **no self-registration**. The admin adds people (§7.3). Requesting a link
   for an unknown or deactivated address silently sends nothing.
7. A "Sign out" action is available but not prominent.

### 5.1 Where the first admin comes from

Rules 2 and 6 together lock an empty database: every account is created by an admin, from
a screen only an admin can reach. **Exactly one account is therefore created outside the
app** — the initial admin, made by a one-off command at install time, taking a first name,
last name and email.

- It sends **no email**. Whoever ran it knows the address they typed and requests a magic
  link in the normal way.
- It **refuses to run when an active admin already exists**, and says so. A command that
  mints administrators is a way in: it must work once, at install, and never become a
  standing back door.
- It is the **only** exception. Every other account, including every later admin, comes
  from A3 (§7.3).

**[D]** A command rather than a first-run setup page. A setup page has to be reachable by
an unauthenticated stranger and then disabled forever afterwards — a security question
nobody needs to answer, when whoever can run commands on the server is already trusted.

## 6. Business rules

### 6.1 Weekly distribution cap

**The intent is even distribution — roughly one session a week**, so that participants
have a steady supply rather than three in one week and nothing for a fortnight. The cap
is how that intent is enforced.

**Programme-wide**, not per supervisor: all supervisors' sessions count towards the
same weekly total.

- A session's week is its **ISO week (Mon–Sun) in Europe/Berlin**, by `date`.
- The count for a week includes every session with `status = offered` (regardless of
  `took_place`) and excludes `cancelled` ones.
- **[D]** **Nothing is ever blocked.** The cap advises; it does not refuse.
  Whoever is saving, the session can always be saved after confirming — the app
  does not know why a week needs three sessions, and the person in front of it
  usually does. What it can do is make sure nobody clusters sessions by accident.
- When a supervisor saves a session, count what the week *would* then hold:
  - **at `weekly_session_cap`** (default 2) → a **warning**, naming the sessions
    already there, which can be confirmed;
  - **above it** → the **same list, stated more strongly**, which can also be
    confirmed. This is the programme's own limit being exceeded, and it should
    look like it.
- **The check applies on edit too**, not just create — moving a session into a
  busy week is the same problem. Editing a session without changing its date must
  not count the session against itself.
- A cancelled session frees its slot immediately.

### 6.2 Capacity and sign-up

- A participant may sign up for any `offered` session whose start is in the future,
  while active registrations < `capacity`.
- **The last-seat check must be atomic.** Two participants clicking simultaneously on
  the final seat is a realistic race with 12 people watching the same list; the loser
  gets a clear "this session just filled up" message, not an over-booked session.
- A participant cannot hold two active registrations for the same session.
- **[?]** Nothing prevents a participant registering for two sessions in the same week,
  or for two overlapping sessions. Assumed acceptable — see §13.
- No waiting list (out of scope, §1.4).

### 6.3 Cancelling

- **Participant cancels their registration:** allowed any time before the session
  starts. **[D]** No cutoff window. The seat frees immediately. Nobody else is notified —
  with these numbers, the supervisor sees the list when they open the session — but the
  participant themselves gets a short `registration_cancelled` mail carrying a
  cancellation invite (§8.2), so the session disappears from their own calendar. Without
  it they keep a live entry for a session they are no longer registered for.
- **Supervisor or admin cancels a session:** allowed any time **until its end time** —
  including while it is in progress. Sets `status = cancelled`, records `cancelled_at` /
  `cancelled_by`, increments `calendar_sequence`, emails every actively-registered
  participant and the supervisor with a cancellation invite (§8), and the session drops
  out of all lists and counts. A cancelled session cannot be reopened — create a new one.

  **Deliberately open past the start time:** the commonest cancellation — supervisor ill
  — is acted on around the start, and cutting off there would leave the session with no
  available action until its end, while participants waited with a live calendar entry.

- **After the end time** a session can no longer be cancelled; it is recorded as "did
  not take place" instead (§6.4). The two are different statements — *called off* versus
  *did not happen* — and only the first is worth emailing about.

### 6.4 What happened: the session is assumed held

**[D]** **A session that has ended counts as held, with every actively-registered
participant present, until somebody says otherwise.** Nobody has to confirm anything for
the counts to be right in the normal case, and no state, screen or email exists to chase
a confirmation that is usually a formality.

This inverts the obvious design because the obvious design fails quietly: if nothing
counts until a human acts, a supervisor who forgets produces no billing at all — which is
why an earlier draft had to invent a nudge email to prod them. Sessions are held as
scheduled with everyone present the overwhelming majority of the time, so guessing that
and letting a human correct it fails smaller and louder.

The cost — a wrong figure is silently plausible — is paid where it matters: **the admin
cannot export billing figures over a range containing unreviewed sessions without being
shown them first** (§7.3 A2).

**Reviewing a session.** Its supervisor, and the admin for any session, may open a past
session at any time and:

- record that it **did not take place** → `took_place = false`. The session then counts
  for nobody, whatever the attendance rows say. The app warns before saving, since this
  removes the session from the supervisor's billing count and from every participant's
  record. Participants are **not** notified **[D]** — they were there, or they weren't;
- **untick** anyone who was absent → `attended = false` for that registration;
- **add** a participant who attended without registering — attendance genuinely differs
  from sign-ups, and reconciling the two by hand is one of the things this app exists to
  stop (§1.2). Creates a Registration with `source = added_at_confirmation` and
  `attended = true`;
- **remove** someone added in error — a `source = added_at_confirmation` row is deleted
  outright; a row from a real sign-up is instead set to `attended = false`, so the
  sign-up itself stays visible;
- undo any of the above: `took_place` and `attended` can be set back to `true`, and
  `took_place` may be returned to `null` (meaning "no claim either way", which still
  counts as held). Nothing about a review is one-way.

Each save records `confirmed_at` / `confirmed_by` on the session and
`attendance_recorded_at` / `attendance_recorded_by` on each registration it touched.
`confirmed_at` is what makes the session **reviewed**; it is set the first time a human
saves the screen, even if they changed nothing — "I looked, it was fine" is exactly the
statement the billing sign-off needs.

**[D]** There is no time limit on reviews or corrections and no approval step: the people
allowed to record attendance are the same people allowed to fix it, and a wrong number
that cannot be corrected is worse than a late edit. Corrections send no email **[D]** —
participants are told in the room, and a mail saying "you have been marked absent"
invites an argument the app cannot host.

### 6.5 Editing a session

Supervisors may edit their own upcoming sessions. Changing **date, start time, mode,
room, or duration** notifies every actively-registered participant (§8) and ships an
updated calendar invite: increment `calendar_sequence`, keep `calendar_uid` (§8.2).
Changing capacity does not — except that capacity can never be set below the number of
active registrations.

**Moving a session in time reschedules its reminders.** When `date` or `start_time`
changes, cancel each active registration's scheduled reminder at the provider and schedule
a new one for the new time, storing the new `reminder_message_id` (§8.3). A participant
already reminded about the old time is reminded again about the new one.

## 7. Screens

Deliberately few. Everything is mobile-first and works on desktop. Every screen has the
language toggle and a sign-out in the same place.

**Every list screen specifies what it shows when it is empty** — on launch day all of them
are. The rule throughout: say what is missing, say whether that is normal, and, if the
user can do something about it, offer exactly that action and nothing else.

### 7.1 Participant

**P1 — Sessions** (the landing screen). Three tabs: **Available**, **My sessions**,
**My participation**.

**Available** shows every upcoming `offered` session, **grouped by calendar week** under
a week heading — `KW 45 · Mo 03.11. – So 09.11.` — so the answer to "what is on offer
over the next weeks" is the shape of the screen itself rather than something the user
has to assemble by scrolling. Weeks with no sessions are skipped; the list is not capped
at a fixed number of weeks, because at ~1–2 sessions a week the whole term is a short
page. Full sessions stay visible, greyed, rather than disappearing — a participant who
cannot find a session they were told about assumes the app is broken.

Above the list, **one filter: supervisor** — a dropdown of supervisors who have at least
one upcoming session, plus `Alle` (default). **[D]** Supervisor only, not mode or room or
free text: it is the filter users asked for (participants follow a Schwerpunkt), and each
further control competes with a screen whose job is one tap to sign up. The choice
persists across sign-ups, and the header states it plainly
(`Gefiltert: Böttcher · Filter entfernen`) so nobody mistakes a filter for an empty
programme.

Each row shows: date and weekday, start time, duration, `Online` or the room, the
supervisor's name and Schwerpunkt, seats taken vs capacity, and a primary button —
`Anmelden`, `Ausgebucht` or `Platz freigeben` (§14.3). Signing up happens **from the
list**, one tap, no intermediate screen.

Tapping a row opens **P2 — Session detail**: everything above plus the Zoom link (for
online sessions, once registered **[D]**) or the room, the supervisor's profile link,
the list of registered participants by name, and — once registered — a
`Zum Kalender hinzufügen` action that downloads the same `.ics` the emails carry (§8.2), for
anyone who deleted the mail or signed up on a device that does not handle attachments.

**My sessions** lists the participant's upcoming sessions first, then past ones with
whether they took place and whether they were marked present.

**Empty states.** Three distinct cases, and conflating them is how a working app gets
reported as broken:

| Screen | When | Shows |
| --- | --- | --- |
| Available | No upcoming sessions at all | "Zurzeit sind keine Termine eingetragen." Plus: supervisors add them, so check back — there is no action for a participant to take here |
| Available | Sessions exist, none match the supervisor filter | The supervisor's name, that they have nothing upcoming, and a `Filter entfernen` button. **Never the no-sessions-at-all message** — that would be a lie the user can act on wrongly |
| My sessions | Registered for nothing | "Du bist noch für keinen Termin angemeldet." with a link to Available |

**P3 — My participation** answers "how many sessions have I attended, and which ones?"
**[D]** Participants can see their own participation record; this replaces the earlier
assumption that the figure was admin-only (§13, open question 2).

- A single headline number: **sessions attended** — the count defined in §9.1 — with the
  date range it covers (all time by default, with a range picker).
- Below it, the list behind the number: date, start time, duration, supervisor, mode.
  Every total is clickable through to the sessions that produced it.
- Sessions they registered for but were marked absent from appear in a separate, quieter
  group (`Angemeldet, nicht teilgenommen`) — the one reason the two numbers differ, so it
  is shown rather than silently omitted.
- A session counts as soon as it has ended (§6.4), so nothing sits in a pending group
  waiting on someone else. A supervisor who later records that a session did not take
  place removes it from the list, which is the only way a total ever goes down.
- **[?]** No PDF or certificate export. §1.4 puts attendance certificates out of
  scope; if the Ausbildung needs proof of supervision hours, that is a real requirement
  to specify rather than something to approximate with a printed screen (§13).
- **Empty:** before anyone has attended anything, the headline reads `0` — shown, not
  hidden — above "Sobald du an einer Supervision teilgenommen hast, erscheint sie hier."
  A zero with an explanation is trustworthy; a blank screen reads as a bug.

### 7.2 Supervisor

**S1 — My sessions.** Upcoming sessions with registered counts, then past ones showing
`stattgefunden` and `n von m anwesend`, each with a `Prüfen` action opening S3 (§6.4).
Past sessions nobody has reviewed carry a quiet `noch nicht geprüft` marker — a note, not
an alarm: they are already counted, and the supervisor need only open one if something was
different. A prominent `Termin anbieten` button.

**Empty:** a supervisor with no sessions sees only the `Termin anbieten` button, made the
focus of the screen, under "Du hast noch keine Termine angeboten." This is the one empty
state with a real next action, so nothing else competes with it.

**S2 — Offer / edit a session.** Fields: date, start time, duration (pre-filled),
online or in person, room (shown only for in person), capacity (pre-filled). The
weekly-cap check runs on save and, when the chosen date's week is already full,
inline as soon as the date is picked — so the block is never a surprise at the end.

**S3 — Review a session.** Opens on the assumption that everything went as planned: the
session took place and everyone registered is ticked. The question at the top is
*"War etwas anders?"*, not *"Did this happen?"* — and `Alles wie geplant` saves without
changing a value, which is a real action because it sets `confirmed_at` and marks the
session reviewed.

Below it: the attendance list, `Teilnehmer*in hinzufügen` (a picker of active
participants, excluding those already listed), and a less prominent
`Die Supervision hat nicht stattgefunden`, which warns before saving that the session will
stop counting for the supervisor and for everyone who attended.

Reopening a reviewed session shows the recorded answers and who last saved them
(`Zuletzt geprüft von Böttcher, 12.11.2025, 14:20`).

**S4 — My profile.** Name, email (read-only — it is the login identity; only an admin
can change it), Schwerpunkt, profile link, language.

**S5 — My counts.** Sessions held in a date range, with the list behind the number.

### 7.3 Admin

**A1 — All sessions.** Filter by date range, supervisor, and state — including a
`noch nicht geprüft` filter, which is how the admin finds what to look at before a
billing run. Admin can edit, cancel, or review anything here — the same S3 screen, for any
supervisor's session (§6.4).

**Empty:** distinguish "no sessions exist yet" from "none match these filters"; the
second offers to clear them. On an empty database, point at A3 — people come before
sessions.

**A2 — Counts and export.** Pick a date range, then:
- *Per supervisor:* name, sessions held, total minutes (informational only — **billing
  counts sessions, never minutes**).
- *Per participant:* name, sessions attended, sessions registered. Each name opens the
  participant's participation record — the same list the participant sees at P3, over
  the chosen range (§9.1). This is where the admin answers "has this trainee actually
  been coming?" without exporting anything.
- `CSV exportieren` for each, plus a raw session-level export and a participation-detail
  export (§9.2).

**The billing sign-off.** Because sessions count without anyone confirming them (§6.4),
this screen is the one place a human is made to look before the numbers become an invoice.
If the chosen range contains sessions with `confirmed_at is null`, A2 shows — above the
figures, not hidden behind them — how many there are, lists them with a link to each, and
requires an explicit `Ich habe die Liste geprüft` acknowledgement before any export runs.

**[D]** It acknowledges rather than blocks. Requiring every session to be individually
opened would rebuild the confirmation chore this design removed, and an admin facing a
blocked export at invoice time will find a way around it. Being shown exactly which
sessions nobody has checked is the information that makes the choice an informed one; the
`reviewed` column in the export (§9.2) carries the same fact downstream.

**A3 — People.** List of everyone with role and active state. Add a person (first name,
last name, email, role). Edit, deactivate, reactivate. **Every account originates here**,
with the single exception of the install-time admin (§5.1).

Adding someone sends no email **by default** — the admin usually tells them in person and
there is no "welcome" flow to get lost in. But the form carries an **optional
`Einladung senden` checkbox**, off by default, which sends one short mail: what STEPS
Supervision is, the link, and that they sign in with this address and no password.

**[D]** Without it the app cannot reach its own users: every other mail in §8.1 is a reply
to something the user did, and `login` requires already knowing the URL — so on launch day
twelve people would have no message and no link. One optional template fixes that without
inflicting a welcome flow on routine additions.

**Deactivation** follows §4.1: deactivating a participant releases their upcoming
registrations; deactivating a supervisor who still has upcoming sessions is **blocked**,
and the message lists those sessions with a link to each, so the admin can cancel or
reassign them and then try again.

**Empty:** cannot happen — the admin is looking at a list that contains at least
themselves.

**A4 — Settings.** Zoom link, default duration, default capacity, weekly cap, enforce
cap on/off, reminder lead time.

### 7.4 Validation and errors

Every one of these is a moment where a non-technical user is told *no*. The rule for all of
them: **say what happened, and say what to do next.** An error that only reports a failure
leaves the user stuck on a screen they cannot get off. The exact wording, in both
languages, is in §14 under the key given here.

| When | Key | Must contain |
| --- | --- | --- |
| `mode = in_person` saved with no room | `err.room_required` | That in-person sessions need a room |
| Capacity set below current registrations (§6.5) | `err.capacity_below_registered` | The current number registered, so the supervisor knows the floor |
| Week would reach the cap (§6.1) | `warn.week_full` | **The clashing sessions — date, time, supervisor** — so another week can be chosen without hunting for them |
| Week would go above the cap (§6.1) | `confirm.cap_override` | That they are exceeding the programme's own limit. Confirmable, like the one above |
| Start time not on a quarter hour (§7.2) | `err.time_step` | Which times are acceptable, with an example |
| Signing up for a session that just filled (§6.2) | `err.session_just_filled` | That the seat went to someone else in the last moment — **not** a generic failure, which reads as a bug |
| Session date in the past on create or edit | `err.date_in_past` | That sessions cannot be offered backwards |
| Magic link expired | `err.link_expired` | The 15-minute limit, and a button to request a fresh one |
| Magic link already used | `err.link_used` | That links work once, and a button to request a fresh one |
| Deactivating a supervisor with upcoming sessions (§4.1) | `err.supervisor_has_sessions` | **The sessions**, each linked, so the admin can cancel or reassign and come back |
| Exporting with unreviewed sessions in range (§7.3 A2) | `warn.unreviewed_in_range` | How many, and that they are counted regardless |

**[D]** Both weekly-cap messages name the clashing sessions rather than saying "this week
is full". The supervisor's next action is picking a different week, and they cannot do that
without knowing what is already there. This is the one error message in the app that does
real work.

## 8. Emails and calendar invites

### 8.1 The emails

All email is sent in **the recipient's `locale`**. Every email states date, time,
duration, and either the Zoom link or the room. No client data ever appears in email.

| Kind | Trigger | To | Contains | Invite (§8.2) |
| --- | --- | --- | --- | --- |
| `login` | Sign-in requested | The user | The magic link, its 15-minute validity | — |
| `invitation` | Admin adds a person **and ticks `Einladung senden`** (§7.3 A3) | The new user | What the app is, its link, that sign-in is by email with no password | — |
| `registration_confirmed` | Participant signs up | That participant | Session details + how to cancel | `REQUEST` |
| `registration_cancelled` | Participant cancels their place | That participant | Confirmation that the place is released | `CANCEL` |
| `reminder` | `reminder_lead_hours` before start | Every actively-registered participant | Session details, prominent join link or room | `REQUEST` (unchanged `SEQUENCE`) |
| `session_cancelled` | Supervisor/admin cancels | Every actively-registered participant, and the supervisor | Which session, that no action is needed | `CANCEL` |
| `session_changed` | Date, time, mode, room or duration edited | Every actively-registered participant, and the supervisor | What changed, old → new | `REQUEST` (bumped `SEQUENCE`) |
| `session_created` | Supervisor or admin creates a session | The session's supervisor | Session details, link to it | `REQUEST` |

**Every one of these is a synchronous reply to something a person did** — the sole
exception being `reminder`, which is handed to the email provider at sign-up and held by
them until it is due (§8.3). The app itself runs nothing on a timer.

An earlier draft had a `supervisor_nudge` mail chasing supervisors to confirm sessions.
It is gone: under §6.4 sessions count without confirmation, so there is nothing to chase.

**`session_created` and `registration_cancelled` exist only to carry invites** (§6.3) —
neither is worth sending for its text alone, and both are short. `session_created` is an
invite, not a reminder: whether supervisors should also get the `reminder` mail is open
(§13).

### 8.2 Calendar invites

Every session email in the table above carries an **iCalendar (`.ics`) attachment**.
Apple Calendar, Google Calendar (Gmail shows an inline *Add to calendar*), Outlook and
Thunderbird all consume this format; **no per-provider integration, no API, no OAuth,
and no calendar accounts are involved**. Attaching a file is the entire mechanism.

One `.ics` is generated **per recipient**, containing a single `VEVENT`:

| Property | Value |
| --- | --- |
| `UID` | `Session.calendar_uid` — **identical for every recipient and every mail about that session**, forever |
| `SEQUENCE` | `Session.calendar_sequence` |
| `METHOD` | `REQUEST` for a new or updated invite, `CANCEL` when the session or the registration is cancelled |
| `STATUS` | `CONFIRMED`, or `CANCELLED` alongside `METHOD:CANCEL` |
| `DTSTAMP` | UTC instant the mail is generated |
| `DTSTART` / `DTEND` | local wall-clock time with `TZID=Europe/Berlin`, derived from `date`, `start_time`, `duration_minutes`, **with a `VTIMEZONE` component for Europe/Berlin included in the file** |
| `SUMMARY` | `Supervision · <supervisor last name>` |
| `LOCATION` | the room, or `Online (Zoom)` |
| `DESCRIPTION` | supervisor name and Schwerpunkt, duration, the Zoom link for online sessions, and a link to the session in the app |
| `ORGANIZER` | the app's own sending address, named for the programme — **not** the supervisor's mailbox |
| `ATTENDEE` | the recipient, and **only** the recipient, with `PARTSTAT=ACCEPTED` and `RSVP=FALSE` |

Three of those carry reasoning worth keeping:

- **`UID` stable, `SEQUENCE` rising** is the only thing that makes a client *replace* an
  event rather than add a second one. `SEQUENCE` is bumped once per outgoing change
  (§6.5), not per recipient.
- **One recipient per file:** listing every participant as an `ATTENDEE` would disclose
  their names and addresses to each other. The session detail screen is where you see
  who else is coming.
- **`RSVP=FALSE`, `ORGANIZER` = the app.** The app is the source of truth for who is
  registered, so declining in Outlook must not change a booking, and the sending address
  is unmonitored. Sending as the supervisor from another domain would trip DMARC. The
  embedded `VTIMEZONE` is there because Outlook mistrusts a `TZID` it was given no
  definition for.

**[D]** The invite carries **no `VALARM`**. The app already sends its own reminder at
`reminder_lead_hours`; a calendar alarm on top is a second notification on a schedule the
admin cannot see or change. Revisit if users ask for it.

Delivery details:
- Attach as `supervision.ics` **and** as an inline `text/calendar; method=REQUEST;
  charset=UTF-8` part — some clients act only on one, some only on the other.
- The body also carries `Zu Google Calendar hinzufügen` and `Zu Outlook hinzufügen`
  links for clients that ignore attachments. They are built from the session's date,
  time, title and location — **never a participant's name or address**, since a URL is
  handed to a third party the moment it is clicked.
- `reminder` re-sends the current invite unchanged (same `UID`, same `SEQUENCE`).
- **Out of scope:** a subscribable ICS feed or two-way calendar sync (§13).

### 8.3 Sending rules

**Reminders are scheduled with the email provider, not by us.** **[D]** At sign-up, hand
the provider the reminder with a delivery time of `start − reminder_lead_hours` and store
the returned handle in `Registration.reminder_message_id`. The provider holds it and
delivers it once. This is what removes the scheduler, and with it the double-send bug that
§4.6 previously spent a unique constraint defending against.

Every subsequent event is a cancel or a reschedule of that one message:

| Event | What happens to the scheduled reminder |
| --- | --- |
| Participant cancels, or is deactivated (§4.1) | Cancel it |
| Session cancelled | Cancel every one for that session |
| Session date or time changed (§6.5) | Cancel and re-schedule each for the new time |
| Capacity, room or mode changed | Nothing — the reminder reads its content at send time |

- **Registering inside the lead window** — the reminder time has already passed — sends
  the reminder **immediately** instead of scheduling it.
- **[D]** Nothing is sent inside the last hour before a session starts: a reminder arriving
  after the participant has already left is noise. The rule keys on the *session's* start
  time, not on when it was created or registered for — that is the only one of the three
  that describes the reader's situation.
- A cancellation invite is sent **only to recipients who were previously sent a
  `REQUEST`** for that session. Sending `METHOD:CANCEL` for an event a calendar never had
  produces a confusing ghost entry in some clients; `EmailLog` records who received what.
- Attendance corrections (§6.4) send no mail and no invite — the session is over and the
  calendar entry is history.

**Scheduling is an interface, not a provider.** The app expresses exactly three
operations — *schedule a mail for an instant*, *cancel a scheduled mail*, *reschedule it*
— and knows nothing else about how they are carried out. In production they are provider
API calls. Locally, where there is no provider, an implementation that writes the mail to
the console and ignores the timing is complete and correct. Without this the central
mechanism of §8.3 has no defined behaviour on a laptop, and the app cannot be run before
hosting is settled.

**This makes the email provider load-bearing** in a way it was not before. It must accept
a delivery time **at least eight weeks out** — a participant may sign up long before a
session, and the reminder is scheduled at that moment — and it must allow **cancelling and
rescheduling a scheduled message by id**. Not every transactional provider does; several
cap delivery-time scheduling at a few days, which would break this design outright.
**Verify both capabilities before choosing a provider** (§13, open question 7). If none
that meets the other requirements can do it, the fallback is a single daily job that
schedules the next day's reminders — a clock again, but a far smaller one than polling for
what is due.

## 9. Counting and export

### 9.1 The two counts

Both counts follow §6.4's default, so both are written `is not false`, **never `= true`**.
Getting that backwards is the easiest way to break billing: it would silently exclude
every session nobody reviewed, which is most of them.

**Billing figure: sessions that count as held — `status = offered`, ended,
`took_place is not false` — grouped by supervisor, within a date range.** Duration never
enters it.

**Participation figure: active registrations with `attended is not false` on a session
that counts as held, grouped by participant, within a date range.** The matching *list* —
date, time, duration, supervisor, mode — is part of the figure, not an extra: it is what
P3 and the A2 drill-down show.

Three exclusions do the work:

- `took_place = false` excludes the session for **everyone**, whatever the attendance rows
  say — a recorded no-show overrides every `attended` beneath it.
- A session that has not yet ended counts for nobody yet. This is the only "not yet" left;
  unreviewed sessions count normally.
- A cancelled registration counts for nobody, even if the participant turned up anyway;
  the supervisor adds them back on review (§6.4) and that row is what counts. `source`
  never affects `sessions_attended`: attending is attending, whether or not you signed up
  first.

`sessions_registered` — active registrations **with `source = self_signup`** on sessions
that took place, whatever `attended` says — is reported alongside `sessions_attended` so
the gap between the two is visible. It is not a billing figure and nothing depends on it.

**The `source` filter is what makes the figure mean anything.** The number exists to show
signed-up-but-did-not-come; someone added at confirmation never signed up at all, so
counting them would inflate it with the exact population it measures against — and, since
they did attend, narrow the visible gap. Hence the asymmetry with `sessions_attended`,
which ignores `source`: attending is attending, but registering has to have happened.

The date range filters on the session's local `date`, inclusive at both ends, for both
counts.

### 9.2 Exports

**Session-level CSV** — the export the admin can rebuild anything from:

```
session_id, date, start_time, duration_minutes, mode, location,
supervisor_last_name, supervisor_first_name, supervisor_email,
status, took_place, reviewed, registered_count, attended_count
```

`took_place` carries the recorded value — `true`, `false` or empty for "no claim made" —
while `reviewed` says whether a human ever opened the session (`confirmed_at is not
null`). An empty `took_place` with `reviewed = false` is the ordinary case and still
counts; the two columns together are what let anyone downstream tell an assumption from a
statement.

**Per-supervisor CSV:**

```
last_name, first_name, email, sessions_held, total_minutes
```

**Per-participant CSV** — one row per participant, the totals. `sessions_registered`
counts self-sign-ups only; `sessions_attended` counts however they got there (§9.1):

```
last_name, first_name, email, sessions_attended, sessions_registered
```

**Participation-detail CSV** — one row per attended session per participant, the list
behind those totals. This is the export that answers "which sessions did this person
actually attend", which the summary row cannot:

```
participant_last_name, participant_first_name, participant_email,
session_id, date, start_time, duration_minutes, mode,
supervisor_last_name, supervisor_first_name, attended
```

It covers every registration on a session that took place — `attended` is `true` or
`false` — so absences are in the file rather than silently missing from it.

Format: UTF-8 **with BOM**, comma-separated, `YYYY-MM-DD` dates. The BOM matters — this
replaces an Excel workflow, and without it Excel mangles `ö`, `ä` and `ü` on open.

## 10. Language

- German is the default and the language content is authored in; English is a full
  alternative. Every user-facing string exists in both.
- The toggle sits in the same place on every screen; the choice is saved to
  `User.locale` and used for email.
- Dates render per locale: `Mo, 03.11.2025, 10:00 Uhr` (de) / `Mon, 3 Nov 2025, 10:00`
  (en). 24-hour clock in both — German convention, and unambiguous.
- The calendar invite is localised too: `SUMMARY`, `LOCATION` and `DESCRIPTION` are
  written in the recipient's `locale`. `DTSTART`/`DTEND` and the timezone are not — they
  are machine fields and stay Europe/Berlin regardless of language.
- Free text entered by users (Schwerpunkt, room) is **not** translated; it shows as typed.

## 11. Non-functional requirements

**Time.** Sessions are stored as a local date + local wall-clock time in Europe/Berlin,
because that is what users mean — a 10:00 session stays at 10:00 across a DST change.
Instants are derived by interpreting them in Europe/Berlin whenever an actual moment is
needed (reminder scheduling, "has it ended"). Record-keeping timestamps (`created_at`,
`sent_at`, …) are UTC instants. Week boundaries use ISO weeks in Europe/Berlin.

**Data protection.** Personal data is limited to §4: names, emails, Schwerpunkt,
attendance. **No client data, no session content, no notes on what was discussed** —
and the UI must offer nowhere to type such things. Do not log personal data. Do not
send it to third parties beyond the email provider. EU data residency is required.
**[?]** Retention for attendance records to be agreed with PHB; until then nothing is
auto-deleted.

Calendar invites are constrained by the same rules — one named attendee per file, no
personal data in the *Add to calendar* links (§8.2). Attendance data never leaves the
app: it is in no email and no invite.

**Time is supplied, not read.** The current instant is passed into the application rather
than taken from the system clock. Nearly every rule that matters is time-dependent — a
session counts *because* its end time has passed (§6.4), weeks are ISO weeks (§6.1),
reminders are scheduled relative to a start time (§8.3) — and none of it can be tested
against a clock that only moves forwards at one second per second. A test must be able to
stand before, during and after a session at will. This is the difference between
acceptance criteria that run automatically and ones somebody has to sit and watch.

**No background jobs.** The app runs no cron, no worker and no scheduled process. The two
things that would normally need one are handled without: delayed email is held by the
provider (§8.3), and a session becoming *held* is derived from its end time at read time
rather than written by a job (§4.2). This is a deliberate constraint, not an accident of
the current design — a periodic process would bring back retries, double-runs, missed
runs and the reconciliation rules that took the most spec to get right. **Anything
proposing a scheduled task should be treated as a design smell and re-examined.**

**Accessibility.** WCAG 2.1 AA as a target: contrast, full keyboard operation, labelled
form controls, focus visible, errors announced. Not formally audited for v1.

**Usability bar.** A supervisor offers a session, or a participant signs up, in under a
minute on a phone, with no instructions. Any screen needing explanation is a defect.

**Scale.** ~20 users — roughly 12 participants, a handful of supervisors, one admin —
with about 4–5 participants in a session (hence the default capacity of 5) and a few
hundred sessions a year. Small and stable, by the nature of the programme. No performance
engineering is warranted; correctness and clarity matter, throughput does not. **Design
for clarity, not for scale.**

**Browsers.** Current Chrome, Safari, Firefox and Edge, desktop and mobile.

## 12. Success and acceptance criteria

### 12.1 Success criteria

Whether the project worked, judged some months after launch. These are outcomes, not
tests — §12.3 can pass completely while these still fail.

- Supervision scheduling and attendance no longer live in Excel — **the spreadsheet is
  retired within one term of launch.**
- A supervisor can offer a session in under a minute, without being shown instructions.
- A participant can find and sign up for a session in under a minute, on a phone.
- Every registered participant gets a reminder before every session, with the right Zoom
  link or room, without anyone sending it by hand — and the session is in their calendar
  without anyone typing it there.
- The admin can produce per-supervisor session counts for a date range in a few clicks,
  with no manual tallying, and per-participant counts alongside.
- Sessions are visibly better distributed: three-in-one-week collisions stop happening.
- A participant can answer "how many supervision sessions have I attended, and which?"
  without asking anyone.
- **Support load is near zero** — nobody needs to be talked through how to use it. This
  is the one that matters most — §1.2's primary constraint, stated as an outcome.

### 12.2 The test fixture

Several criteria below check counts "against a hand-built fixture". §11 forbids real data,
and an unseeded app shows nothing but empty states, so one fixture serves both the test
suite and local demonstration. It contains, with **invented names and `@example.org`
addresses throughout**:

- one admin, **two supervisors** — so per-supervisor counts can be told apart — and
  **twelve participants**, matching the programme's real shape (§11);
- sessions across **at least four ISO weeks**, including one week already at
  `weekly_session_cap`, so the cap can be tested without first having to create it;
- **one session at capacity**, for the `Full` state and the last-seat race;
- **one cancelled** session and **one recorded as not held** — both must count for nobody,
  for different reasons;
- **one reviewed** and **one unreviewed** past session, since that difference drives the
  export sign-off (§7.3 A2) and must never drive a count (§9.1);
- at least one recorded absence and one participant added at confirmation, so
  `sessions_attended` and `sessions_registered` genuinely differ and the `source` rule
  is exercised.

Sessions are defined **relative to a reference instant**, never as fixed calendar dates —
"three weeks ago", "yesterday", "in four days". Combined with the supplied clock (§11),
this is what lets a test stand at any point in a session's life, and stops the fixture
rotting the moment it is written.

### 12.3 Acceptance criteria

Testable, in build order.

**Access**
1. On an empty database the install command creates one admin, who can then request a
    magic link and reach A3. Without it no account exists and nobody can sign in.
2. Running the install command again, once an active admin exists, refuses and explains
    why.
3. Requesting a link for a registered address delivers a working single-use link.
4. Requesting one for an unknown or deactivated address shows the identical
    confirmation and sends nothing.
5. A used or expired token is rejected with an offer to request a new one.
6. Signing in lands each role on its own home screen.
7. A person added with `Einladung senden` ticked receives the invitation mail; one
    added without it receives nothing.

**Offering sessions**
8. A supervisor creates an in-person session; it appears to participants immediately.
9. An online session shows the settings Zoom link; changing that setting changes it
    everywhere.
10. A second session in an ISO week warns, naming the one already there, and
    saves once confirmed.
11. A third warns more strongly, naming both, and also saves once confirmed.
12. Editing a session's date into a full week is blocked the same way; saving it without
    changing the date is not blocked by its own existence.
13. Nothing is ever blocked: the same save goes through on confirmation,
    whoever is making it.
14. `mode = in_person` cannot be saved without a room.
14a. A start time can be set to 10:15 but not to 10:07 — quarter hours only.

**Browsing and filtering**
15. The Available tab groups upcoming sessions under calendar-week headings, in date
    order, skipping empty weeks.
16. Filtering by a supervisor shows only their upcoming sessions; the active filter is
    stated on screen and can be cleared in one tap.
17. The supervisor dropdown lists only supervisors who have at least one upcoming
    session, plus `Alle`.
18. A full session still appears in the list, greyed, with `Full` instead of `Sign up`.
19. With no upcoming sessions at all, Available explains that none are scheduled. With
    sessions present but none matching the supervisor filter, it says so instead and
    offers to clear the filter — the two messages are never interchanged.
20. My sessions, My participation and the supervisor's session list each show their
    own empty state; My participation shows a visible `0`, not a blank panel.

**Sign-up**
21. A participant signs up from the list in one tap and gets a confirmation email.
22. When active registrations reach capacity, the button reads `Full`.
23. Two simultaneous sign-ups for one remaining seat: exactly one succeeds, the other
    is told the session just filled up. No over-booking.
24. Cancelling frees the seat immediately and allows re-registering.
25. Capacity cannot be edited below the current number of registrations.

**Reminders**
26. Registering schedules exactly one reminder with the provider, for
    `start − reminder_lead_hours`, and stores its id on the registration.
27. Each registered participant receives that reminder at the configured lead time, in
    their own language, with the right link or room.
28. Cancelling a registration cancels its scheduled reminder; the participant receives
    nothing afterwards, and other participants' reminders are unaffected.
29. Cancelling a session cancels every scheduled reminder for it and sends the
    cancellation email.
30. Editing the time sends a change email showing old → new.
31. **A session moved after its reminder was scheduled reminds everyone at the new time**,
    and no reminder arrives at the old one.
32. Someone registering inside the lead window is sent the reminder immediately.
33. Nothing is sent inside the last hour before a session starts.
34. The chosen email provider accepts a delivery time at least eight weeks out and
    supports cancelling and rescheduling by id — verified against the real provider
    before it is adopted, not assumed.

**Calendar invites**
35. The sign-up confirmation carries an `.ics` that imports as one event at the right
    date and time in Apple Calendar, Google Calendar (via Gmail) and Outlook.
36. Moving a session sends an updated invite that **replaces** the existing entry in
    each of those clients — one event afterwards, not two — with the same `UID` and a
    higher `SEQUENCE`.
37. Cancelling a session removes the entry from each client's calendar.
38. A participant who cancels their own place gets a cancellation invite and the entry
    disappears from their calendar; other participants' calendars are untouched.
39. The `.ics` sent to one participant names only that participant as `ATTENDEE` and
    contains no other participant's name or email.
40. A session at 10:00 imports as 10:00 Europe/Berlin on both sides of a DST change,
    and on a device set to another timezone shows the correct corresponding local time.
41. The supervisor gets an invite for a session they created.
42. Accepting or declining the invite in a mail client changes nothing in the app.

**Held by default, review and counting**
43. **A session counts for its supervisor, and for everyone registered, as soon as its
    end time passes — with nobody having touched it.** No email is sent to make this
    happen and no job runs to cause it.
44. Opening the review screen and saving it unchanged alters no count but marks the
    session reviewed.
45. Recording *did not take place* warns first, then removes the session from the
    supervisor's count and from every participant's record.
46. Unticking a participant removes only that participant's attendance; the session still
    counts for the supervisor and for everyone else.
47. Someone unregistered can be added as attended, and someone added in error removed.
48. A review can be undone — attendance re-ticked, *did not take place* reversed — and
    every count follows immediately.
49. Both counts treat an unreviewed session exactly as a reviewed one; the only difference
    is what A2 shows before exporting.
50. A session in progress — started but not yet ended — can still be cancelled, and doing
    so emails participants and removes the entry from their calendars.
51. Cancelling records who cancelled it and when.
52. No email or invite is sent for a review or a correction.
53. Per-supervisor counts equal the number of ended, non-cancelled sessions not recorded
    as *did not take place* — verified against a hand-built fixture containing reviewed,
    unreviewed and not-held sessions.
54. A 60-minute and a 120-minute session each count as **one**.

**Participation record**
55. A participant sees their own attended-session count and the list of exactly those
    sessions, and the two agree.
56. Sessions they registered for but missed appear separately and are not counted.
57. A session appears in the participant's record as soon as it has ended, without
    anyone confirming it, and disappears only if it is recorded as not held.
58. A participant cannot see another participant's attendance anywhere in the app.
59. The admin sees the same record for any participant, over a chosen date range, and
    the participation-detail CSV matches it row for row.
60. Someone added at confirmation counts in `sessions_attended` but **not** in
    `sessions_registered`.
61. Exporting over a range containing unreviewed sessions shows how many and which,
    and requires an explicit acknowledgement before the export runs.
62. The session-level CSV distinguishes an assumed *held* from a recorded one via
    the `took_place` and `reviewed` columns.
63. CSV exports open in Excel with German characters intact.
64. Every validation error in §7.4 appears with the exact wording of §14, in the
    recipient's language, and names what to do about it.
65. With the clock supplied by the test rather than the system, a session can be
    observed before, during and after its end time within a single test run.

**People**
66. Deactivating a participant releases their upcoming seats and sends them a
    cancellation invite; deactivating a supervisor who still has upcoming sessions is
    blocked, and the message names those sessions.

**Language**
67. Switching language changes every visible string and persists across sign-in.
68. Emails arrive in the recipient's chosen language.
69. The calendar invite's title, location and description are in the recipient's
    language, and its times remain Europe/Berlin.

## 13. Decisions and open questions

### Scope changes since the first draft

Four changes were requested on 2026-07-28, after the original brief. Two of them reversed
what that brief had ruled out; both reversals are now resolved in this document's favour
and reflected in §1.4, so nothing here is in tension with anything else. Kept as a record
of *what changed and why*, because two of these were deliberate earlier decisions rather
than oversights.

| # | Change | Previously | Now |
| --- | --- | --- | --- |
| 1 | **Calendar invites on every session email** (§8.2) | "Calendar integration (ICS feed / Google / Outlook sync)" was out of scope | **Reversed, narrowly.** Invites ride on mails we already send — no feed, no sync, no API, no OAuth. A subscribable feed and two-way sync remain out of scope (§1.4, open question 10) |
| 2 | **Participation tracking as a first-class feature**, visible to participants (§7.1 P3, §9.1) | A secondary figure that "drives no billing today and no decision should depend on it", assumed admin-only | **Reversed.** It has its own screen, its own export, and participants see their own record (D13). Attendance certificates stay out of scope — see open question 2 |
| 3 | **Browse the coming weeks, filter by supervisor** (§7.1 P1) | Only "a simple list view per role" | Extension. Week grouping plus one filter (D15) |
| 4 | **Attendance correctable after confirmation, by supervisor or admin** (§6.4) | Admin could already record attendance; correcting it was unspecified | Extension. Correctable indefinitely, no approval step (D16) |

One consequence worth pricing in before build: change 1 makes the email provider a
harder choice than first assumed (open question 7). Invites are ordinary attachments,
but a provider that rewrites or strips MIME parts breaks them.

### Decisions taken here **[D]**

| # | Decision | Rationale |
| --- | --- | --- |
| 1 | Weekly cap is programme-wide, ISO weeks | Confirmed with Kostas |
| 2 | Admin adds all users; no self-registration | Confirmed with Kostas |
| 3 | Reminder lead time is an admin setting, default 24h | Confirmed with Kostas |
| 4 | ~~Added a `supervisor_nudge` email~~ **Reversed by D29** | It existed because nothing else caused attendance to be recorded. Under the assumed-held default there is nothing to chase, so the mail, the setting and the state it chased are all gone |
| 5 | One role per person | No evidence anyone is both; a dual account is the escape hatch |
| 6 | 30-day sign-in, 15-minute magic link | Frequent re-auth is the friction §1.2 warns against; the data is low-sensitivity |
| 7 | Attendance pre-checked as present | Everyone attending is the normal case |
| 8 | No cancellation cutoff for participants | No stated need; a rule to explain is a rule to get wrong |
| 9 | Default duration 90 min, capacity 5 | Placeholder — confirm with STEPS |
| 10 | Adding a person sends no welcome email **by default**, with an optional `Einladung senden` checkbox | Routine additions need no ceremony, but without the option the app has no way of reaching its own users on launch day — every other mail is a reply to something the user did |
| 11 | Zoom link shown to registered participants only | Mild protection for an unchanging shared link |
| 12 | "Did not take place" notifies nobody | They were there or they weren't |
| 13 | Participants see their own participation record | Requested 2026-07-28; the figure had been assumed admin-only, and this settles it in favour of showing it |
| 14 | Own attendance only — nobody sees another participant's | The count is between the participant and the programme; the registration list is already public within the app |
| 15 | Browse filter is supervisor only, and sessions group by calendar week | The one filter asked for; week grouping answers "the next weeks" without a control |
| 16 | Attendance is correctable indefinitely, with no approval step | The people trusted to record it are the people trusted to fix it; an uncorrectable wrong number is worse |
| 17 | Corrections notify nobody | A "you were marked absent" email starts an argument the app cannot host |
| 18 | Invites are `.ics` attachments, not calendar API integrations | Every client reads `.ics`; no OAuth, no accounts, no per-provider work. Keeps the "no API integration" boundary of §1.4 intact |
| 19 | One invite per recipient, listing only that recipient | Avoids disclosing participants' addresses to each other |
| 20 | Invites carry no `VALARM` | The app already sends a reminder; a second alarm is one the admin cannot control |
| 21 | Supervisors get an invite for their own sessions (`session_created`) | The person who has to be there needs it in their calendar most |
| 22 | Cancelling a registration mails that participant a cancellation invite | Otherwise a stale entry stays in their calendar and they turn up |
| 23 | A session stays cancellable until its **end** time, not its start | The commonest cancellation (supervisor ill) is acted on around the start time; closing at the start left a window with no available action and participants waiting |
| 24 | `took_place` may be set back to `null` | With no awaiting-confirmation state to fall back into, `null` simply means "no claim either way", which counts as held. A reviewer who ticked the wrong box must be able to undo it |
| 25 | Deactivating a participant releases their upcoming seats; deactivating a supervisor with upcoming sessions is blocked | The only options that surprise nobody — silently keeping sessions offered strands participants, silently cancelling them fires mail the admin never chose to send |
| 26 | Email change is not chased into already-sent invites | A lot of machinery for something that will happen perhaps twice; the admin is warned instead (§4.1) |
| 27 | `sessions_registered` counts self-sign-ups only | Counting supervisor-added rows would inflate the figure with the exact population it exists to measure against |
| 28 | Every list screen specifies an empty state, and "no sessions" is never shown for "no matches" | On launch day every screen is empty; the two messages lead to different user actions |
| 29 | **A session that has ended is held, with everyone registered present, unless someone records otherwise** | Requiring confirmation means nothing counts when a supervisor forgets — the failure is silent and total. Guessing the overwhelmingly common case and letting a human correct it fails smaller and louder |
| 30 | The risk of D29 is paid at export: A2 lists unreviewed sessions and requires an acknowledgement | One human checkpoint, placed where an assumption turns into an invoice, rather than a chore repeated per session |
| 31 | A2 acknowledges rather than blocks | A blocked export at invoice time gets worked around; being shown exactly what nobody checked is what makes the choice informed |
| 32 | **Reminder timing is handed to the email provider at sign-up**, cancelled and rescheduled as things change | Removes the polling scheduler and with it idempotency, unique constraints, supersession and double-run defences — the largest cluster of edge cases in the spec |
| 33 | **The app runs no background jobs at all** (§11) | Follows from D29 and D32. A periodic process brings back retries, missed runs and reconciliation; keeping it out is worth designing around |
| 34 | The email provider must schedule ≥ 8 weeks ahead and cancel/reschedule by id | D32 makes this load-bearing rather than a nicety; several providers cap scheduling at a few days, which would break the design |
| 35 | **The first admin is created by an install-time command** (§5.1), which refuses to run once an active admin exists | Without it an empty database cannot be signed into at all. A command rather than a setup page, which would have to be open to strangers and then closed forever |
| 36 | **The stack lives in this document** (§15), which is no longer stack-agnostic | The separate technical plan never materialised, and a spec nobody can build from is unfinished |
| 37 | Python 3.13 + Django 5.2 LTS, SQLite locally and Postgres in production | §15. Server-rendered, no separate API and client, at ~20 users |
| 38 | Custom user model, and wall-clock date/time as separate fields, from the first migration | §15.1. Both are painful to change afterwards and cheap to get right at the start |
| 39 | **Translation by catalog, not gettext** | `msgfmt` is absent on the development machine and Django reads only compiled `.mo`. The catalog is §14 itself, so document and code cannot drift |
| 40 | **Users are addressed as *Sie*** | The audience includes professors; formal address is never wrong there, informal sometimes is. Flagged for STEPS to confirm — it is a find-and-replace in §14 |
| 41 | Error messages name what to do next, and the weekly-cap message names the clashing sessions | §7.4. The supervisor's next action is choosing another week, which is impossible without knowing what is already in this one |
| 42 | One fixture serves both the test suite and local demonstration (§12.2) | The same data proves the counts and fills the screens; two sets would diverge |

### Still open **[?]**

1. **Default duration and capacity** (D9) — placeholders. Real values from STEPS.
2. **What the participation record is for.** Participants can now see it (D13), but
   nothing yet depends on it. If it is meant to prove supervision hours for the
   Ausbildung, that is a different requirement — an official, exportable record — and
   §1.4 puts attendance certificates out of scope. Worth settling before someone
   starts screenshotting P3 for a training file.
3. **Should sign-up be prevented for overlapping or same-week sessions?** Currently
   unrestricted.
4. ~~**Confirmation deadline**~~ — **resolved by D29.** Sessions auto-count when they end,
   so there is no deadline to set, nothing to expire and nothing to escalate. What
   replaces it is the export acknowledgement (D30).
5. **Data retention** for attendance records — is there a PHB policy to follow?
6. **Historical Excel data** — import, or start fresh? Getting the actual sheet would
   also validate §4 against what is really tracked, including how attendance has been
   recorded until now.
7. **Email sending domain and provider — now the first technical decision, not a late
   one.** Three hard requirements, all testable before committing: (a) sends
   `text/calendar` parts and `.ics` attachments **unaltered** — some providers rewrite or
   strip MIME parts, or mangle attachments in click-tracking; (b) accepts a scheduled
   delivery time **at least eight weeks out**; (c) allows **cancelling and rescheduling**
   a scheduled message by id. (b) and (c) come from D32 — if no provider meeting (a) and
   the EU-residency requirement can do them, the fallback in §8.3 reintroduces a small
   daily job, so this needs answering before the architecture is fixed.
8. **Hosting, budget, deadline.**
9. **Should supervisors get the `reminder` email too?** They now get an *invite* when a
   session is created (D21), which is not the same thing.
10. **Is a subscribable calendar feed wanted later?** Invites cover "the session is in my
    calendar". A per-user ICS feed URL would also cover "my whole supervision schedule
    stays in sync", at the cost of a permanent unauthenticated-ish URL to manage. Out of
    scope for v1.
11. **Should the admin be able to record attendance in bulk**, e.g. mark a whole session
    attended from A1 without opening it? Only worth it if sessions routinely sit
    unconfirmed and the admin ends up doing the supervisors' work.

## 14. Copy

Every user-facing string, in both languages. **German is the source**; English is a full
alternative, not a fallback (§10). Keys are the catalog keys the implementation uses, so
this table and the running app cannot drift apart — if a string is not here, it is not on
a screen.

`%(name)s`-style placeholders are substituted at render time. Free text entered by users —
Schwerpunkt, room names — is never translated.

**[D] The app addresses users as *Sie*.** The audience includes professors and licensed
psychotherapists alongside trainees, and formal address is never wrong in that room while
informal address sometimes is. Worth confirming with STEPS, who know their own culture —
it is a find-and-replace in this table, not a rewrite.

### 14.1 Global

| Key | de | en |
| --- | --- | --- |
| `app.name` | STEPS Supervision | STEPS Supervision |
| `nav.sessions` | Termine | Sessions |
| `nav.my_sessions` | Meine Termine | My sessions |
| `nav.my_participation` | Meine Teilnahme | My participation |
| `nav.profile` | Mein Profil | My profile |
| `nav.my_counts` | Auswertung | Summary |
| `nav.all_sessions` | Alle Termine | All sessions |
| `nav.counts_export` | Auswertung | Summary |
| `nav.people` | Personen | People |
| `nav.settings` | Einstellungen | Settings |
| `action.sign_out` | Abmelden | Sign out |
| `action.save` | Speichern | Save |
| `action.cancel` | Abbrechen | Cancel |
| `action.back` | Zurück | Back |
| `lang.switch` | English | Deutsch |
| `mode.online` | Online | Online |
| `mode.room` | Raum %(room)s | Room %(room)s |
| `session.duration` | %(minutes)s Min. | %(minutes)s min |
| `label.supervisor` | Supervisor*in | Supervisor |
| `label.focus_area` | Schwerpunkt | Focus area |

### 14.2 Sign-in (§5)

| Key | de | en |
| --- | --- | --- |
| `signin.title` | Anmelden | Sign in |
| `signin.intro` | Geben Sie Ihre E-Mail-Adresse ein. Sie erhalten einen Link zum Anmelden — ein Passwort brauchen Sie nicht. | Enter your email address. You'll get a link to sign in — no password needed. |
| `signin.email_label` | E-Mail-Adresse | Email address |
| `signin.submit` | Link senden | Send link |
| `signin.sent_title` | Schauen Sie in Ihr Postfach | Check your email |
| `signin.sent_body` | Wenn diese Adresse hinterlegt ist, haben wir einen Anmeldelink geschickt. Er gilt 15 Minuten. | If that address is registered, we have sent a sign-in link. It is valid for 15 minutes. |
| `signin.request_new` | Neuen Link anfordern | Request a new link |

### 14.3 P1 — Sessions (§7.1)

| Key | de | en |
| --- | --- | --- |
| `p1.tab_available` | Angebotene Termine | Available |
| `p1.tab_mine` | Meine Termine | My sessions |
| `p1.tab_participation` | Meine Teilnahme | My participation |
| `p1.filter_label` | Supervisor*in | Supervisor |
| `p1.filter_all` | Alle | All |
| `p1.filter_active` | Gefiltert: %(name)s | Filtered: %(name)s |
| `p1.filter_clear` | Filter entfernen | Clear filter |
| `p1.week_heading` | KW %(week)s · %(from)s – %(to)s | Week %(week)s · %(from)s – %(to)s |
| `p1.seats` | %(taken)s von %(capacity)s Plätzen belegt | %(taken)s of %(capacity)s seats taken |
| `p1.action_signup` | Anmelden | Sign up |
| `p1.action_full` | Ausgebucht | Full |
| `p1.action_cancel` | Platz freigeben | Cancel my place |
| `p1.past_sessions` | Vergangene Termine | Past sessions |
| `p1.attended` | teilgenommen | attended |
| `p1.absent` | nicht teilgenommen | did not attend |

### 14.4 P2 — Session detail (§7.1)

| Key | de | en |
| --- | --- | --- |
| `p2.title` | Termin | Session |
| `p2.profile_link` | Profil ansehen | View profile |
| `p2.zoom_link` | Zoom-Link | Zoom link |
| `p2.zoom_hidden` | Der Zoom-Link erscheint hier, sobald Sie angemeldet sind. | The Zoom link appears here once you have signed up. |
| `p2.registered_list` | Angemeldet | Registered |
| `p2.add_to_calendar` | Zum Kalender hinzufügen | Add to calendar |

### 14.5 P3 — My participation (§7.1)

| Key | de | en |
| --- | --- | --- |
| `p3.title` | Meine Teilnahme | My participation |
| `p3.count_label` | Teilgenommene Supervisionen | Sessions attended |
| `p3.range_all` | Gesamter Zeitraum | All time |
| `p3.range_pick` | Zeitraum wählen | Choose a range |
| `p3.absent_group` | Angemeldet, nicht teilgenommen | Registered, did not attend |
| `p3.not_reviewed` | noch nicht geprüft | not yet reviewed |

### 14.6 S1–S3 — Supervisor (§7.2)

| Key | de | en |
| --- | --- | --- |
| `s1.title` | Meine Termine | My sessions |
| `s1.offer` | Termin anbieten | Offer a session |
| `s1.upcoming` | Kommende Termine | Upcoming |
| `s1.past` | Vergangene Termine | Past |
| `s1.registered_count` | %(count)s angemeldet | %(count)s registered |
| `s1.present_count` | %(present)s von %(registered)s anwesend | %(present)s of %(registered)s present |
| `s1.took_place` | stattgefunden | took place |
| `s1.not_held` | hat nicht stattgefunden | did not take place |
| `s1.review` | Prüfen | Review |
| `s2.title_new` | Termin anbieten | Offer a session |
| `s2.title_edit` | Termin bearbeiten | Edit session |
| `s2.date` | Datum | Date |
| `s2.start_time` | Beginn | Start time |
| `s2.duration` | Dauer (Minuten) | Duration (minutes) |
| `s2.mode` | Format | Format |
| `s2.mode_online` | Online | Online |
| `s2.mode_in_person` | Vor Ort | In person |
| `s2.room` | Raum | Room |
| `s2.capacity` | Plätze | Seats |
| `s2.submit` | Termin speichern | Save session |
| `s2.cancel_session` | Termin absagen | Cancel session |
| `s2.cancel_confirm` | Alle angemeldeten Personen werden benachrichtigt und der Termin verschwindet aus ihren Kalendern. | Everyone registered is notified and the session disappears from their calendars. |
| `s3.title` | Termin prüfen | Review session |
| `s3.question` | War etwas anders? | Was anything different? |
| `s3.all_as_planned` | Alles wie geplant | All as planned |
| `s3.attendance` | Anwesenheit | Attendance |
| `s3.add_attendee` | Teilnehmer*in hinzufügen | Add someone who attended |
| `s3.not_held_action` | Die Supervision hat nicht stattgefunden | The session did not take place |
| `s3.not_held_warning` | Der Termin zählt dann für niemanden mehr — weder für Sie noch für die Teilnehmenden. | The session will then count for nobody — not for you, and not for the participants. |
| `s3.last_reviewed` | Zuletzt geprüft von %(name)s, %(when)s | Last reviewed by %(name)s, %(when)s |
| `s4.title` | Mein Profil | My profile |
| `s4.email_readonly` | Ihre E-Mail-Adresse ist Ihre Anmeldung. Nur die Administration kann sie ändern. | Your email address is your sign-in. Only an administrator can change it. |
| `s4.language` | Sprache | Language |
| `s5.title` | Auswertung | Summary |
| `s5.sessions_held` | Durchgeführte Supervisionen | Sessions held |

### 14.7 A1–A4 — Admin (§7.3)

| Key | de | en |
| --- | --- | --- |
| `a1.title` | Alle Termine | All sessions |
| `a1.filter_state` | Status | State |
| `a1.filter_unreviewed` | Nur ungeprüfte | Unreviewed only |
| `a1.filter_range` | Zeitraum | Date range |
| `a2.title` | Supervisionen und Teilnahme | Sessions and attendance |
| `a2.per_supervisor` | Pro Supervisor*in | Per supervisor |
| `a2.per_participant` | Pro Teilnehmer*in | Per participant |
| `a2.sessions_held` | Durchgeführt | Sessions held |
| `a2.total_minutes` | Minuten gesamt | Total minutes |
| `a2.sessions_attended` | Teilgenommen | Attended |
| `a2.sessions_registered` | Angemeldet | Registered |
| `a2.export_csv` | CSV exportieren | Export CSV |
| `a2.signoff_ack` | Ich habe die Liste geprüft | I have checked the list |
| `a2.all_reviewed` | Alle Termine in diesem Zeitraum sind geprüft. | All sessions in this range have been reviewed. |
| `a3.title` | Personen | People |
| `a3.add_person` | Person hinzufügen | Add a person |
| `a3.first_name` | Vorname | First name |
| `a3.last_name` | Nachname | Last name |
| `a3.email` | E-Mail-Adresse | Email address |
| `a3.role` | Rolle | Role |
| `a3.role_participant` | Teilnehmer*in | Participant |
| `a3.role_supervisor` | Supervisor*in | Supervisor |
| `a3.role_admin` | Administration | Administrator |
| `a3.send_invitation` | Einladung senden | Send an invitation |
| `a3.deactivate` | Deaktivieren | Deactivate |
| `a3.reactivate` | Wieder aktivieren | Reactivate |
| `a3.inactive` | inaktiv | inactive |
| `a4.title` | Einstellungen | Settings |
| `a4.zoom_url` | Zoom-Link für alle Online-Termine | Zoom link for all online sessions |
| `a4.default_duration` | Standarddauer (Minuten) | Default duration (minutes) |
| `a4.default_capacity` | Standardanzahl Plätze | Default number of seats |
| `a4.weekly_cap` | Termine pro Woche (Obergrenze) | Sessions per week (cap) |
| `a4.reminder_lead` | Erinnerung senden (Stunden vorher) | Send reminder (hours before) |

### 14.8 Empty states (§7)

| Key | de | en |
| --- | --- | --- |
| `empty.no_sessions` | Zurzeit sind keine Termine eingetragen. Supervisor*innen tragen neue Termine ein — schauen Sie später noch einmal vorbei. | No sessions are scheduled at the moment. Supervisors add them — please check back later. |
| `empty.no_sessions_for_filter` | %(name)s bietet zurzeit keine Termine an. | %(name)s has no upcoming sessions. |
| `empty.no_registrations` | Sie sind noch für keinen Termin angemeldet. | You are not signed up for any session yet. |
| `empty.browse_link` | Termine ansehen | Browse sessions |
| `empty.no_participation` | Sobald Sie an einer Supervision teilgenommen haben, erscheint sie hier. | Once you have attended a session, it will appear here. |
| `empty.no_own_sessions` | Sie haben noch keine Termine angeboten. | You have not offered any sessions yet. |
| `empty.no_sessions_at_all` | Es gibt noch keine Termine. Legen Sie zuerst Personen an. | There are no sessions yet. Start by adding people. |
| `empty.no_matches` | Keine Termine für diese Auswahl. | No sessions match this selection. |

### 14.9 Validation and errors (§7.4)

| Key | de | en |
| --- | --- | --- |
| `err.room_required` | Bitte geben Sie einen Raum an — Termine vor Ort brauchen einen Ort. | Please give a room — in-person sessions need a location. |
| `err.capacity_below_registered` | Es sind bereits %(count)s Personen angemeldet. Weniger Plätze sind nicht möglich. | %(count)s people are already registered. The number of seats cannot go below that. |
| `warn.week_full` | In dieser Woche gibt es bereits %(count)s Termine: %(sessions)s. Trotzdem speichern? | There are already %(count)s sessions that week: %(sessions)s. Save anyway? |
| `confirm.cap_override` | Damit überschreiten Sie die Obergrenze von %(cap)s Terminen pro Woche. | This exceeds the cap of %(cap)s sessions per week. |
| `err.session_just_filled` | Dieser Termin ist gerade belegt worden. Der letzte Platz ist an jemand anderen gegangen. | This session has just filled up. The last seat went to someone else. |
| `err.time_step` | Bitte wählen Sie eine Uhrzeit in 15-Minuten-Schritten, zum Beispiel 10:00 oder 10:15. | Please choose a time in 15-minute steps, for example 10:00 or 10:15. |
| `err.date_in_past` | Das Datum liegt in der Vergangenheit. Termine lassen sich nur für die Zukunft anbieten. | That date is in the past. Sessions can only be offered for the future. |
| `err.link_expired` | Dieser Link ist abgelaufen — er gilt 15 Minuten. Fordern Sie einen neuen an. | This link has expired — links are valid for 15 minutes. Please request a new one. |
| `err.link_used` | Dieser Link wurde bereits verwendet. Jeder Link funktioniert genau einmal. | This link has already been used. Each link works exactly once. |
| `err.supervisor_has_sessions` | %(name)s hat noch kommende Termine: %(sessions)s. Bitte sagen Sie diese zuerst ab oder übertragen Sie sie. | %(name)s still has upcoming sessions: %(sessions)s. Please cancel or reassign them first. |
| `warn.unreviewed_in_range` | %(count)s Termine in diesem Zeitraum wurden noch nicht geprüft. Sie zählen trotzdem mit. | %(count)s sessions in this range have not been reviewed. They are counted regardless. |

### 14.10 Emails (§8.1)

Subjects, plus the one line that carries each mail. Full bodies follow the same rules as
§8.1: date, time, duration, and either the Zoom link or the room.

| Key | de | en |
| --- | --- | --- |
| `email.login.subject` | Ihr Anmeldelink für STEPS Supervision | Your sign-in link for STEPS Supervision |
| `email.login.body` | Klicken Sie auf den Link, um sich anzumelden. Er gilt 15 Minuten. | Click the link to sign in. It is valid for 15 minutes. |
| `email.invitation.subject` | Zugang zu STEPS Supervision | Access to STEPS Supervision |
| `email.invitation.body` | Die Supervisionstermine von STEPS werden ab sofort hier verwaltet. Sie melden sich mit dieser E-Mail-Adresse an — ein Passwort brauchen Sie nicht. | STEPS supervision sessions are now managed here. You sign in with this email address — no password needed. |
| `email.registration_confirmed.subject` | Angemeldet: Supervision am %(date)s | Registered: supervision on %(date)s |
| `email.registration_cancelled.subject` | Abgemeldet: Supervision am %(date)s | Cancelled: supervision on %(date)s |
| `email.registration_cancelled.body` | Ihr Platz ist wieder frei. Der Termin wurde aus Ihrem Kalender entfernt. | Your place has been released. The session has been removed from your calendar. |
| `email.reminder.subject` | Erinnerung: Supervision am %(date)s | Reminder: supervision on %(date)s |
| `email.session_cancelled.subject` | Abgesagt: Supervision am %(date)s | Cancelled: supervision on %(date)s |
| `email.session_cancelled.body` | Dieser Termin findet nicht statt. Sie müssen nichts weiter tun. | This session will not take place. There is nothing you need to do. |
| `email.session_changed.subject` | Geändert: Supervision am %(date)s | Changed: supervision on %(date)s |
| `email.session_changed.body` | Der Termin hat sich geändert: %(old)s → %(new)s | The session has changed: %(old)s → %(new)s |
| `email.session_created.subject` | Ihr Supervisionstermin am %(date)s | Your supervision session on %(date)s |

## 15. Technical decisions

The spec is otherwise about behaviour. This section is about what to build it with, and
exists because the technical plan that was supposed to carry it never materialised — a
specification nobody can build from is unfinished.

| Decision | Choice | Why |
| --- | --- | --- |
| Language | **Python 3.13**, pinned via `uv` | The development machine runs 3.14.5, which is newer than the Django LTS supports. **Check the supported range at install time rather than trusting this row** |
| Framework | **Django 5.2 LTS**, server-rendered templates | Sessions, forms, migrations and translation are most of this app, and Django brings all four. Nothing here justifies a separate API and client at ~20 users |
| Database | **SQLite** locally, **Postgres** in production | No application difference. SQLite inside a transaction satisfies §6.2's atomic last seat |
| Dependencies | **`uv`** | Already present on the machine, and it pins the Python version as well as the packages |
| Background work | **None** | §11 forbids it. Delayed mail belongs to the provider (§8.3); *held* is derived, not written (§4.2) |
| Email, locally | **Console backend** | Magic links print to the terminal. Nothing about running locally waits on the hosting or provider decision |
| Translation | **Catalog-based, no gettext dependency** | GNU `msgfmt` is not installed on the development machine and Django's i18n reads only compiled `.mo` files. A catalog keyed by locale needs no external tooling, and it is §14 — one artefact, not two that drift |
| Time | **Supplied to the application**, never read from the system clock | §11. Every time-dependent rule becomes testable |

### 15.1 The three that are expensive to reverse

These are settled by the first migration and awkward to change afterwards. They belong in
the initial commit, correct.

1. **A custom user model**, email-identified, with a `role` and **no password field**.
   §4.1 has no password — authentication is a magic link (§5) — while Django's default
   user is username-and-password. Changing `AUTH_USER_MODEL` after the first migration is
   notoriously painful and best simply avoided.
2. **`date` and `start_time` as separate date and time fields**, never a single combined
   timestamp. §11 requires wall-clock storage so that a 10:00 session is still 10:00 after
   a DST change; a timezone-aware timestamp field silently converts to UTC and quietly
   breaks exactly that. The actual instant is derived when one is needed.
3. **Record-keeping timestamps as UTC instants**, with the project timezone set to
   Europe/Berlin. Also §11, and distinct from the point above: `created_at` and `sent_at`
   are moments, while a session's date and time are a wall-clock intention.

### 15.2 What is deliberately not decided here

Hosting, the email provider, and EU data residency (§13, open questions 7 and 8). None of
them blocks a locally running version: the console backend stands in for the provider, and
SQLite stands in for Postgres. The provider decision does need making before reminders can
work for real, and §8.3 sets out what it must support.
