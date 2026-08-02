"""S2 — offer / edit a session (§7.2), with the validation of §7.4.

Every message here comes from §14 by key. The rule for all of them: say what
happened, and say what to do next — an error that only reports a failure leaves
a non-technical user stuck on a screen they cannot get off.
"""

from __future__ import annotations

import datetime as dt

from django import forms

from supervision.catalog import t
from supervision.clock import today_in_berlin
from supervision.models import Mode, Role, Session, Settings, User  # noqa: F401


class SessionForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = [
            "supervisor",
            "date",
            "start_time",
            "duration_minutes",
            "mode",
            "room",
            "capacity",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            # §7.2 — quarter hours only. `step` makes the browser's own
            # picker move in 15-minute jumps and refuse anything else, in
            # the reader's language; `clean_start_time` is the real guard.
            "start_time": forms.TimeInput(attrs={"type": "time", "step": 900}),
        }

    def __init__(self, *args, editor: User, now: dt.datetime, locale: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.editor = editor
        self.now = now
        self.locale = locale
        settings = Settings.load()

        # §3 — a supervisor offers their own sessions and never anyone else's;
        # an admin may create and edit anyone's, so only they get to choose.
        if editor.is_admin:
            self.fields["supervisor"].queryset = User.objects.filter(
                role=Role.SUPERVISOR, is_active=True
            )
            self.fields["supervisor"].required = True
        else:
            del self.fields["supervisor"]

        # §7.2 — duration and capacity are pre-filled from settings (§4.4).
        if not self.instance.pk:
            self.fields["duration_minutes"].initial = settings.default_duration_minutes
            self.fields["capacity"].initial = settings.default_capacity
            self.fields["mode"].initial = Mode.ONLINE

    def clean_date(self):
        date = self.cleaned_data["date"]
        # §7.4 — on create *and* on edit: sessions cannot be offered backwards.
        if date < today_in_berlin(self.now):
            raise forms.ValidationError(t("err.date_in_past", self.locale))
        return date

    def clean_start_time(self):
        start_time = self.cleaned_data["start_time"]
        if start_time.minute % 15 or start_time.second:
            raise forms.ValidationError(t("err.time_step", self.locale))
        return start_time

    def clean_capacity(self):
        capacity = self.cleaned_data["capacity"]
        if capacity < 1:
            # §4.2 — minimum 1. A session nobody can attend is not a session.
            raise forms.ValidationError(
                t("err.capacity_below_registered", self.locale, count=1)
            )
        # §6.5 — capacity can never be set below the number of active
        # registrations. The message names that number, so the supervisor knows
        # the floor rather than guessing at it (§7.4).
        if self.instance.pk:
            taken = self.instance.seats_taken
            if capacity < taken:
                raise forms.ValidationError(
                    t("err.capacity_below_registered", self.locale, count=taken)
                )
        return capacity

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get("mode")
        room = (cleaned.get("room") or "").strip()

        if mode == Mode.IN_PERSON and not room:
            self.add_error("room", t("err.room_required", self.locale))
        if mode == Mode.ONLINE:
            # §4.2 — room is required when in person, and otherwise empty.
            cleaned["room"] = ""

        return cleaned


class PersonForm(forms.ModelForm):
    """A3 — add a person (§7.3). Role, name, email; nothing else is settable here."""

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "role"]

    def __init__(self, *args, locale: str = "de", **kwargs):
        super().__init__(*args, **kwargs)
        self.locale = locale

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        # §4.1 — one login identity, compared case-insensitively. The database
        # enforces it too; this is so the admin gets a sentence, not a 500.
        existing = User.objects.filter(email__iexact=email)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError(
                t("a3.email", self.locale) + ": " + email
            )
        return email


class SettingsForm(forms.ModelForm):
    """A4 — the programme-wide settings of §4.4."""

    class Meta:
        model = Settings
        fields = [
            "zoom_url",
            "default_duration_minutes",
            "default_capacity",
            "weekly_session_cap",
            "reminder_lead_hours",
        ]
