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
from supervision.models import Mode, Role, Session, Settings, User


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
            "start_time": forms.TimeInput(attrs={"type": "time"}),
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

    def clean_capacity(self):
        capacity = self.cleaned_data["capacity"]
        if capacity < 1:
            # §4.2 — minimum 1. A session nobody can attend is not a session.
            raise forms.ValidationError(
                t("err.capacity_below_registered", self.locale, count=1)
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
