"""Delayed mail — §8.3.

**Scheduling is an interface, not a provider.** The app expresses exactly three
operations — schedule a mail for an instant, cancel a scheduled mail, reschedule
it — and knows nothing else about how they are carried out. In production they
are provider API calls. Locally, where there is no provider, an implementation
that writes the mail to the console and ignores the timing is complete and
correct; without that, the central mechanism of §8.3 has no defined behaviour on
a laptop and the app cannot be run before hosting is settled.

**The decisions stay here, in the app.** The port carries out *what* and *when*;
it never decides *whether*. Two rules of §8.3 therefore live in `plan_reminder`
below rather than in any adapter:

* registering inside the lead window sends the reminder immediately;
* nothing is sent inside the last hour before a session starts — a reminder
  arriving after the participant has already left is noise, and the rule keys on
  the *session's* start time, the only one of the candidates that describes the
  reader's situation.

This is what removes the scheduler, and with it the double-send bug that §4.6
would otherwise need a unique constraint to defend against. **The app runs
nothing on a timer** (§11).
"""

from __future__ import annotations

import datetime as dt
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Protocol

from django.conf import settings
from django.utils.module_loading import import_string

# §8.3 — a reminder arriving inside this window is noise, not a reminder.
QUIET_PERIOD = dt.timedelta(hours=1)


class ReminderScheduler(Protocol):
    """The three operations, and nothing else."""

    def schedule(self, *, deliver_at: dt.datetime, send) -> str:
        """Hand over a mail to be delivered later; return the provider's handle."""
        ...

    def cancel(self, message_id: str) -> None: ...

    def reschedule(self, message_id: str, *, deliver_at: dt.datetime, send) -> str: ...


class ImmediateScheduler:
    """The local stand-in: deliver now, ignore the timing (§8.3, §15).

    Sanctioned by the spec rather than a shortcut — it means a laptop can run
    the whole flow with no provider chosen. What it cannot do is un-send, so
    `cancel` is a no-op here; the tests use a scheduler that records instead.
    """

    def schedule(self, *, deliver_at: dt.datetime, send) -> str:
        send()
        return f"local-{uuid.uuid4()}"

    def cancel(self, message_id: str) -> None:
        return None

    def reschedule(self, message_id: str, *, deliver_at: dt.datetime, send) -> str:
        return self.schedule(deliver_at=deliver_at, send=send)


@dataclass
class ScheduledMail:
    message_id: str
    deliver_at: dt.datetime
    send: object


class RecordingScheduler:
    """Records instead of sending. For tests, and for seeing what *would* happen."""

    def __init__(self):
        self.scheduled: dict[str, ScheduledMail] = {}
        self.cancelled: list[str] = []

    def schedule(self, *, deliver_at: dt.datetime, send) -> str:
        message_id = f"fake-{len(self.scheduled) + len(self.cancelled) + 1}"
        self.scheduled[message_id] = ScheduledMail(message_id, deliver_at, send)
        return message_id

    def cancel(self, message_id: str) -> None:
        self.cancelled.append(message_id)
        self.scheduled.pop(message_id, None)

    def reschedule(self, message_id: str, *, deliver_at: dt.datetime, send) -> str:
        self.cancel(message_id)
        return self.schedule(deliver_at=deliver_at, send=send)

    def deliver_due(self, now: dt.datetime) -> int:
        """Play the provider: deliver everything whose time has come."""
        due = [m for m in self.scheduled.values() if m.deliver_at <= now]
        for message in due:
            message.send()
            self.scheduled.pop(message.message_id, None)
        return len(due)


_scheduler: ReminderScheduler | None = None


def get_scheduler() -> ReminderScheduler:
    global _scheduler
    if _scheduler is None:
        path = getattr(
            settings,
            "REMINDER_SCHEDULER",
            "supervision.scheduling.ImmediateScheduler",
        )
        _scheduler = import_string(path)()
    return _scheduler


def set_scheduler(scheduler: ReminderScheduler | None) -> None:
    """Swap the implementation. Tests use this; nothing else should."""
    global _scheduler
    _scheduler = scheduler


@contextmanager
def using_scheduler(scheduler: ReminderScheduler):
    """Run a block against a different scheduler.

    Tests use `RecordingScheduler`, which models what a provider actually does —
    hold the mail until it is due. `ImmediateScheduler` is the local stand-in and
    sends at once, so a test using it would see reminders arrive at sign-up and
    could never observe the timing rules at all.
    """
    previous = _scheduler
    set_scheduler(scheduler)
    try:
        yield scheduler
    finally:
        set_scheduler(previous)


@dataclass(frozen=True)
class ReminderPlan:
    """What §8.3 says to do about one participant's reminder."""

    action: str  # "schedule" | "send_now" | "nothing"
    deliver_at: dt.datetime | None = None


def plan_reminder(
    session, now: dt.datetime, lead_hours: int
) -> ReminderPlan:
    starts_at = session.starts_at
    if now >= starts_at - QUIET_PERIOD:
        return ReminderPlan("nothing")

    deliver_at = starts_at - dt.timedelta(hours=lead_hours)
    if deliver_at <= now:
        # The reminder time has already passed — send it rather than schedule a
        # delivery in the past.
        return ReminderPlan("send_now")
    return ReminderPlan("schedule", deliver_at)
