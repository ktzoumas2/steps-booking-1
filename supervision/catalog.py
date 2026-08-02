"""Every user-facing string, in both languages — §14, transcribed.

Translation is catalog-based rather than gettext (D39): `msgfmt` is not installed
on the development machine and Django's i18n reads only compiled `.mo` files. The
catalog *is* §14, so the document and the running app cannot drift apart —
`tests/test_catalog.py` reads the tables out of `product-spec.md` and fails if
this file and that one disagree.

German is the source; English is a full alternative, not a fallback (§10). Users
are addressed as *Sie* (D40). If a string is not here, it does not go on a screen.

Free text entered by users — Schwerpunkt, room names — is never translated.
"""

from __future__ import annotations

LOCALES = ("de", "en")
DEFAULT_LOCALE = "de"


class MissingCopy(KeyError):
    """Raised for a key that is not in §14 — loudly, because §14 is the rule."""


# §14.1 Global
COPY: dict[str, dict[str, str]] = {
    "app.name": {"de": "STEPS Supervision", "en": "STEPS Supervision"},
    "nav.sessions": {"de": "Termine", "en": "Sessions"},
    "nav.my_sessions": {"de": "Meine Termine", "en": "My sessions"},
    "nav.my_participation": {"de": "Meine Teilnahme", "en": "My participation"},
    "nav.profile": {"de": "Mein Profil", "en": "My profile"},
    "nav.my_counts": {"de": "Durchgeführte Termine", "en": "Sessions held"},
    "nav.all_sessions": {"de": "Alle Termine", "en": "All sessions"},
    "nav.counts_export": {"de": "Auswertung", "en": "Summary"},
    "nav.people": {"de": "Personen", "en": "People"},
    "nav.settings": {"de": "Einstellungen", "en": "Settings"},
    "action.sign_out": {"de": "Abmelden", "en": "Sign out"},
    "action.save": {"de": "Speichern", "en": "Save"},
    "action.cancel": {"de": "Abbrechen", "en": "Cancel"},
    "action.back": {"de": "Zurück", "en": "Back"},
    "lang.switch": {"de": "English", "en": "Deutsch"},
    "mode.online": {"de": "Online", "en": "Online"},
    "mode.room": {"de": "Raum %(room)s", "en": "Room %(room)s"},
    "session.duration": {"de": "%(minutes)s Min.", "en": "%(minutes)s min"},
    "label.supervisor": {"de": "Supervisor*in", "en": "Supervisor"},
    "label.focus_area": {"de": "Schwerpunkt", "en": "Focus area"},
    # §14.2 Sign-in (§5)
    "signin.title": {"de": "Anmelden", "en": "Sign in"},
    "signin.intro": {
        "de": "Geben Sie Ihre E-Mail-Adresse ein. Sie erhalten einen Link zum "
        "Anmelden — ein Passwort brauchen Sie nicht.",
        "en": "Enter your email address. You'll get a link to sign in — no "
        "password needed.",
    },
    "signin.email_label": {"de": "E-Mail-Adresse", "en": "Email address"},
    "signin.submit": {"de": "Link senden", "en": "Send link"},
    "signin.sent_title": {
        "de": "Schauen Sie in Ihr Postfach",
        "en": "Check your email",
    },
    "signin.sent_body": {
        "de": "Wenn diese Adresse hinterlegt ist, haben wir einen Anmeldelink "
        "geschickt. Er gilt 15 Minuten.",
        "en": "If that address is registered, we have sent a sign-in link. It is "
        "valid for 15 minutes.",
    },
    "signin.request_new": {
        "de": "Neuen Link anfordern",
        "en": "Request a new link",
    },
    # §14.3 P1 — Sessions (§7.1)
    "p1.tab_available": {"de": "Angebotene Termine", "en": "Available"},
    "p1.tab_mine": {"de": "Meine Termine", "en": "My sessions"},
    "p1.tab_participation": {"de": "Meine Teilnahme", "en": "My participation"},
    "p1.filter_label": {"de": "Supervisor*in", "en": "Supervisor"},
    "p1.filter_all": {"de": "Alle", "en": "All"},
    "p1.filter_active": {"de": "Gefiltert: %(name)s", "en": "Filtered: %(name)s"},
    "p1.filter_clear": {"de": "Filter entfernen", "en": "Clear filter"},
    "p1.week_heading": {
        "de": "KW %(week)s · %(from)s – %(to)s",
        "en": "Week %(week)s · %(from)s – %(to)s",
    },
    "p1.seats": {
        "de": "%(taken)s von %(capacity)s Plätzen belegt",
        "en": "%(taken)s of %(capacity)s seats taken",
    },
    "p1.action_signup": {"de": "Anmelden", "en": "Sign up"},
    "p1.action_full": {"de": "Ausgebucht", "en": "Full"},
    "p1.action_cancel": {"de": "Platz freigeben", "en": "Cancel my place"},
    "p1.past_sessions": {"de": "Vergangene Termine", "en": "Past sessions"},
    "p1.attended": {"de": "teilgenommen", "en": "attended"},
    "p1.absent": {"de": "nicht teilgenommen", "en": "did not attend"},
    # §14.4 P2 — Session detail (§7.1)
    "p2.title": {"de": "Termin", "en": "Session"},
    "p2.profile_link": {"de": "Profil ansehen", "en": "View profile"},
    "p2.zoom_link": {"de": "Zoom-Link", "en": "Zoom link"},
    "p2.zoom_hidden": {
        "de": "Der Zoom-Link erscheint hier, sobald Sie angemeldet sind.",
        "en": "The Zoom link appears here once you have signed up.",
    },
    "p2.registered_list": {"de": "Angemeldet", "en": "Registered"},
    "p2.add_to_calendar": {"de": "Zum Kalender hinzufügen", "en": "Add to calendar"},
    # §14.5 P3 — My participation (§7.1)
    "p3.title": {"de": "Meine Teilnahme", "en": "My participation"},
    "p3.count_label": {
        "de": "Teilgenommene Supervisionen",
        "en": "Sessions attended",
    },
    "p3.range_all": {"de": "Gesamter Zeitraum", "en": "All time"},
    "p3.range_pick": {"de": "Zeitraum wählen", "en": "Choose a range"},
    "p3.absent_group": {
        "de": "Angemeldet, nicht teilgenommen",
        "en": "Registered, did not attend",
    },
    "p3.not_reviewed": {"de": "noch nicht geprüft", "en": "not yet reviewed"},
    # §14.6 S1–S5 — Supervisor (§7.2)
    "s1.title": {"de": "Meine Termine", "en": "My sessions"},
    "s1.offer": {"de": "Termin anbieten", "en": "Offer a session"},
    "s1.upcoming": {"de": "Kommende Termine", "en": "Upcoming"},
    "s1.past": {"de": "Vergangene Termine", "en": "Past"},
    "s1.registered_count": {
        "de": "%(count)s angemeldet",
        "en": "%(count)s registered",
    },
    "s1.present_count": {
        "de": "%(present)s von %(registered)s anwesend",
        "en": "%(present)s of %(registered)s present",
    },
    "s1.took_place": {"de": "stattgefunden", "en": "took place"},
    "s1.not_held": {"de": "hat nicht stattgefunden", "en": "did not take place"},
    "s1.review": {"de": "Prüfen", "en": "Review"},
    "s2.title_new": {"de": "Termin anbieten", "en": "Offer a session"},
    "s2.title_edit": {"de": "Termin bearbeiten", "en": "Edit session"},
    "s2.date": {"de": "Datum", "en": "Date"},
    "s2.start_time": {"de": "Beginn", "en": "Start time"},
    "s2.duration": {"de": "Dauer (Minuten)", "en": "Duration (minutes)"},
    "s2.mode": {"de": "Format", "en": "Format"},
    "s2.mode_online": {"de": "Online", "en": "Online"},
    "s2.mode_in_person": {"de": "Vor Ort", "en": "In person"},
    "s2.room": {"de": "Raum", "en": "Room"},
    "s2.capacity": {"de": "Plätze", "en": "Seats"},
    "s2.submit": {"de": "Termin speichern", "en": "Save session"},
    "s2.cancel_session": {"de": "Termin absagen", "en": "Cancel session"},
    "s2.cancel_confirm": {
        "de": "Alle angemeldeten Personen werden benachrichtigt und der Termin "
        "verschwindet aus ihren Kalendern.",
        "en": "Everyone registered is notified and the session disappears from "
        "their calendars.",
    },
    "s3.title": {"de": "Termin prüfen", "en": "Review session"},
    "s3.question": {"de": "War etwas anders?", "en": "Was anything different?"},
    "s3.all_as_planned": {"de": "Alles wie geplant", "en": "All as planned"},
    "s3.attendance": {"de": "Anwesenheit", "en": "Attendance"},
    "s3.add_attendee": {
        "de": "Teilnehmer*in hinzufügen",
        "en": "Add someone who attended",
    },
    "s3.not_held_action": {
        "de": "Die Supervision hat nicht stattgefunden",
        "en": "The session did not take place",
    },
    "s3.not_held_warning": {
        "de": "Der Termin zählt dann für niemanden mehr — weder für Sie noch für "
        "die Teilnehmenden.",
        "en": "The session will then count for nobody — not for you, and not for "
        "the participants.",
    },
    "s3.last_reviewed": {
        "de": "Zuletzt geprüft von %(name)s, %(when)s",
        "en": "Last reviewed by %(name)s, %(when)s",
    },
    "s4.title": {"de": "Mein Profil", "en": "My profile"},
    "s4.email_readonly": {
        "de": "Ihre E-Mail-Adresse ist Ihre Anmeldung. Nur die Administration "
        "kann sie ändern.",
        "en": "Your email address is your sign-in. Only an administrator can "
        "change it.",
    },
    "s4.language": {"de": "Sprache", "en": "Language"},
    "s5.title": {"de": "Durchgeführte Supervisionen", "en": "Sessions held"},
    "s5.sessions_held": {
        "de": "Durchgeführte Supervisionen",
        "en": "Sessions held",
    },
    # §14.7 A1–A4 — Admin (§7.3)
    "a1.title": {"de": "Alle Termine", "en": "All sessions"},
    "a1.filter_state": {"de": "Status", "en": "State"},
    "a1.filter_unreviewed": {"de": "Nur ungeprüfte", "en": "Unreviewed only"},
    "a1.filter_range": {"de": "Zeitraum", "en": "Date range"},
    "a2.title": {"de": "Supervisionen und Teilnahme", "en": "Sessions and attendance"},
    "a2.per_supervisor": {"de": "Pro Supervisor*in", "en": "Per supervisor"},
    "a2.per_participant": {"de": "Pro Teilnehmer*in", "en": "Per participant"},
    "a2.sessions_held": {"de": "Durchgeführt", "en": "Sessions held"},
    "a2.total_minutes": {"de": "Minuten gesamt", "en": "Total minutes"},
    "a2.sessions_attended": {"de": "Teilgenommen", "en": "Attended"},
    "a2.sessions_registered": {"de": "Angemeldet", "en": "Registered"},
    "a2.export_csv": {"de": "CSV exportieren", "en": "Export CSV"},
    "a2.signoff_ack": {
        "de": "Ich habe die Liste geprüft",
        "en": "I have checked the list",
    },
    "a3.title": {"de": "Personen", "en": "People"},
    "a3.add_person": {"de": "Person hinzufügen", "en": "Add a person"},
    "a3.first_name": {"de": "Vorname", "en": "First name"},
    "a3.last_name": {"de": "Nachname", "en": "Last name"},
    "a3.email": {"de": "E-Mail-Adresse", "en": "Email address"},
    "a3.role": {"de": "Rolle", "en": "Role"},
    "a3.role_participant": {"de": "Teilnehmer*in", "en": "Participant"},
    "a3.role_supervisor": {"de": "Supervisor*in", "en": "Supervisor"},
    "a3.role_admin": {"de": "Administration", "en": "Administrator"},
    "a3.send_invitation": {"de": "Einladung senden", "en": "Send an invitation"},
    "a3.deactivate": {"de": "Deaktivieren", "en": "Deactivate"},
    "a3.reactivate": {"de": "Wieder aktivieren", "en": "Reactivate"},
    "a3.inactive": {"de": "inaktiv", "en": "inactive"},
    "a4.title": {"de": "Einstellungen", "en": "Settings"},
    "a4.zoom_url": {
        "de": "Zoom-Link für alle Online-Termine",
        "en": "Zoom link for all online sessions",
    },
    "a4.default_duration": {
        "de": "Standarddauer (Minuten)",
        "en": "Default duration (minutes)",
    },
    "a4.default_capacity": {
        "de": "Standardanzahl Plätze",
        "en": "Default number of seats",
    },
    "a4.weekly_cap": {
        "de": "Termine pro Woche (Obergrenze)",
        "en": "Sessions per week (cap)",
    },
    "a4.enforce_cap": {"de": "Obergrenze durchsetzen", "en": "Enforce the cap"},
    "a4.reminder_lead": {
        "de": "Erinnerung senden (Stunden vorher)",
        "en": "Send reminder (hours before)",
    },
    # §14.8 Empty states (§7)
    "empty.no_sessions": {
        "de": "Zurzeit sind keine Termine eingetragen. Supervisor*innen tragen "
        "neue Termine ein — schauen Sie später noch einmal vorbei.",
        "en": "No sessions are scheduled at the moment. Supervisors add them — "
        "please check back later.",
    },
    "empty.no_sessions_for_filter": {
        "de": "%(name)s bietet zurzeit keine Termine an.",
        "en": "%(name)s has no upcoming sessions.",
    },
    "empty.no_registrations": {
        "de": "Sie sind noch für keinen Termin angemeldet.",
        "en": "You are not signed up for any session yet.",
    },
    "empty.browse_link": {"de": "Termine ansehen", "en": "Browse sessions"},
    "empty.no_participation": {
        "de": "Sobald Sie an einer Supervision teilgenommen haben, erscheint sie "
        "hier.",
        "en": "Once you have attended a session, it will appear here.",
    },
    "empty.no_own_sessions": {
        "de": "Sie haben noch keine Termine angeboten.",
        "en": "You have not offered any sessions yet.",
    },
    "empty.no_sessions_at_all": {
        "de": "Es gibt noch keine Termine. Legen Sie zuerst Personen an.",
        "en": "There are no sessions yet. Start by adding people.",
    },
    "empty.no_matches": {
        "de": "Keine Termine für diese Auswahl.",
        "en": "No sessions match this selection.",
    },
    # §14.9 Validation and errors (§7.4)
    "err.room_required": {
        "de": "Bitte geben Sie einen Raum an — Termine vor Ort brauchen einen Ort.",
        "en": "Please give a room — in-person sessions need a location.",
    },
    "err.capacity_below_registered": {
        "de": "Es sind bereits %(count)s Personen angemeldet. Weniger Plätze sind "
        "nicht möglich.",
        "en": "%(count)s people are already registered. The number of seats "
        "cannot go below that.",
    },
    "err.week_full": {
        "de": "In dieser Woche gibt es bereits %(count)s Termine: %(sessions)s. "
        "Bitte wählen Sie eine andere Woche.",
        "en": "There are already %(count)s sessions that week: %(sessions)s. "
        "Please choose a different week.",
    },
    "warn.week_full": {
        "de": "In dieser Woche gibt es bereits %(count)s Termine: %(sessions)s. "
        "Trotzdem speichern?",
        "en": "There are already %(count)s sessions that week: %(sessions)s. "
        "Save anyway?",
    },
    "confirm.cap_override": {
        "de": "Damit überschreiten Sie die Obergrenze von %(cap)s Terminen pro "
        "Woche.",
        "en": "This exceeds the cap of %(cap)s sessions per week.",
    },
    "err.session_just_filled": {
        "de": "Dieser Termin ist gerade belegt worden. Der letzte Platz ist an "
        "jemand anderen gegangen.",
        "en": "This session has just filled up. The last seat went to someone "
        "else.",
    },
    "err.date_in_past": {
        "de": "Das Datum liegt in der Vergangenheit. Termine lassen sich nur für "
        "die Zukunft anbieten.",
        "en": "That date is in the past. Sessions can only be offered for the "
        "future.",
    },
    "err.link_expired": {
        "de": "Dieser Link ist abgelaufen — er gilt 15 Minuten. Fordern Sie einen "
        "neuen an.",
        "en": "This link has expired — links are valid for 15 minutes. Please "
        "request a new one.",
    },
    "err.link_used": {
        "de": "Dieser Link wurde bereits verwendet. Jeder Link funktioniert genau "
        "einmal.",
        "en": "This link has already been used. Each link works exactly once.",
    },
    "err.supervisor_has_sessions": {
        "de": "%(name)s hat noch kommende Termine: %(sessions)s. Bitte sagen Sie "
        "diese zuerst ab oder übertragen Sie sie.",
        "en": "%(name)s still has upcoming sessions: %(sessions)s. Please cancel "
        "or reassign them first.",
    },
    "warn.unreviewed_in_range": {
        "de": "%(count)s Termine in diesem Zeitraum wurden noch nicht geprüft. "
        "Sie zählen trotzdem mit.",
        "en": "%(count)s sessions in this range have not been reviewed. They are "
        "counted regardless.",
    },
    # §14.10 Emails (§8.1)
    "email.login.subject": {
        "de": "Ihr Anmeldelink für STEPS Supervision",
        "en": "Your sign-in link for STEPS Supervision",
    },
    "email.login.body": {
        "de": "Klicken Sie auf den Link, um sich anzumelden. Er gilt 15 Minuten.",
        "en": "Click the link to sign in. It is valid for 15 minutes.",
    },
    "email.invitation.subject": {
        "de": "Zugang zu STEPS Supervision",
        "en": "Access to STEPS Supervision",
    },
    "email.invitation.body": {
        "de": "Die Supervisionstermine von STEPS werden ab sofort hier verwaltet. "
        "Sie melden sich mit dieser E-Mail-Adresse an — ein Passwort brauchen "
        "Sie nicht.",
        "en": "STEPS supervision sessions are now managed here. You sign in with "
        "this email address — no password needed.",
    },
    "email.registration_confirmed.subject": {
        "de": "Angemeldet: Supervision am %(date)s",
        "en": "Registered: supervision on %(date)s",
    },
    "email.registration_cancelled.subject": {
        "de": "Abgemeldet: Supervision am %(date)s",
        "en": "Cancelled: supervision on %(date)s",
    },
    "email.registration_cancelled.body": {
        "de": "Ihr Platz ist wieder frei. Der Termin wurde aus Ihrem Kalender "
        "entfernt.",
        "en": "Your place has been released. The session has been removed from "
        "your calendar.",
    },
    "email.reminder.subject": {
        "de": "Erinnerung: Supervision am %(date)s",
        "en": "Reminder: supervision on %(date)s",
    },
    "email.session_cancelled.subject": {
        "de": "Abgesagt: Supervision am %(date)s",
        "en": "Cancelled: supervision on %(date)s",
    },
    "email.session_cancelled.body": {
        "de": "Dieser Termin findet nicht statt. Sie müssen nichts weiter tun.",
        "en": "This session will not take place. There is nothing you need to do.",
    },
    "email.session_changed.subject": {
        "de": "Geändert: Supervision am %(date)s",
        "en": "Changed: supervision on %(date)s",
    },
    "email.session_changed.body": {
        "de": "Der Termin hat sich geändert: %(old)s → %(new)s",
        "en": "The session has changed: %(old)s → %(new)s",
    },
    "email.session_created.subject": {
        "de": "Ihr Supervisionstermin am %(date)s",
        "en": "Your supervision session on %(date)s",
    },
}


def t(key: str, locale: str = DEFAULT_LOCALE, **params) -> str:
    """The §14 string for `key` in `locale`, with `%(name)s` placeholders filled.

    An unknown key raises rather than rendering blank: a string that is not in
    §14 does not belong on a screen, and a silently empty label is the kind of
    defect that reaches users.
    """
    try:
        entry = COPY[key]
    except KeyError:
        raise MissingCopy(key) from None
    text = entry.get(locale, entry[DEFAULT_LOCALE])
    return text % params if params else text
