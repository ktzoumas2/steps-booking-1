"""Reviewing a past session — §6.4.

The default this sits on top of (D29): **a session that has ended counts as
held, with every actively-registered participant present, until somebody says
otherwise.** Nobody has to confirm anything for the counts to be right in the
normal case, and no state, screen or email exists to chase a confirmation that
is usually a formality.

So everything here is *correction*, not entry. Two consequences run through the
whole file:

* nothing sent from here sends mail (D17). Participants are told in the room,
  and "you have been marked absent" invites an argument the app cannot host;
* `confirmed_at` is what makes a session *reviewed*, and it is set even when a
  human changed nothing — "I looked, it was fine" is exactly the statement the
  billing sign-off needs (§7.3 A2).

There is no time limit and no approval step (D16): the people allowed to record
attendance are the people allowed to fix it, and a wrong number that cannot be
corrected is worse than a late edit.
"""

from __future__ import annotations

import datetime as dt

from django.db import transaction

from supervision.models import (
    Registration,
    RegistrationSource,
    Role,
    Session,
    User,
)


def may_review(user: User, session: Session) -> bool:
    """§3 — a supervisor reviews their own sessions, an admin reviews anyone's."""
    if user.is_admin:
        return True
    return user.is_supervisor and session.supervisor_id == user.pk


def is_reviewable(session: Session, now: dt.datetime) -> bool:
    """A session is reviewed once it is over, and never if it was called off.

    A cancelled session and one that did not take place are different statements
    — *called off* versus *did not happen* — and only the first is worth
    emailing about (§6.3). Neither is reviewed here.
    """
    return not session.is_cancelled and session.has_ended(now)


def candidates_to_add(session: Session) -> list[User]:
    """§7.2 S3 — active participants, excluding those already on the list."""
    already = set(
        session.active_registrations().values_list("user_id", flat=True)
    )
    return list(
        User.objects.filter(role=Role.PARTICIPANT, is_active=True)
        .exclude(pk__in=already)
        .order_by("last_name", "first_name")
    )


@transaction.atomic
def mark_reviewed(sessions, *, by: User, now: dt.datetime) -> int:
    """The billing sign-off of §7.3 A2: a human states they looked at the list.

    Writes `confirmed_at` and `confirmed_by` and **nothing else**. In
    particular it does not touch `took_place`: "I have checked the list" is a
    statement about the reviewer, not about whether each session happened, and
    §6.4 keeps `null` meaning "no claim either way" — which still counts. An
    admin signing off a range must not silently put words in a supervisor's
    mouth about sessions they were not at.

    Being *reviewed* never affects a count either way (§2, §9.1); it only
    changes what A2 shows before exporting. So this is a safe thing to do in
    bulk, which is exactly why the acknowledgement can stay one click (D31).
    """
    touched = 0
    for session in sessions:
        if session.is_reviewed:
            continue
        session.confirmed_at = now
        session.confirmed_by = by
        session.updated_at = now
        session.save(update_fields=["confirmed_at", "confirmed_by", "updated_at"])
        touched += 1
    return touched


@transaction.atomic
def save_review(
    session: Session,
    *,
    by: User,
    now: dt.datetime,
    took_place: bool = True,
    present_registration_ids: set[int] | None = None,
    add_participant_ids: list[int] | None = None,
    remove_registration_ids: list[int] | None = None,
) -> Session:
    """Record what happened, and mark the session reviewed.

    `present_registration_ids` of None means "no statement about attendance" —
    what the `Alles wie geplant` shortcut sends, since the screen opens on the
    assumption that everyone registered was there.
    """
    # Order matters, and each step overrides the one before it:
    #
    # 1. the ticks describe the rows that were *on the screen*;
    # 2. an explicit removal beats a tick — someone who ticked a name and then
    #    removed it meant the removal;
    # 3. additions come last, because a person added as having attended must not
    #    then be swept up by step 1, whose list of ticks could not have named a
    #    row that did not exist when the screen was drawn.
    if present_registration_ids is not None:
        _record_attendance(session, present_registration_ids, by=by, now=now)
    _remove(session, remove_registration_ids or [], by=by, now=now)
    _add(session, add_participant_ids or [], by=by, now=now)

    session.took_place = took_place
    session.confirmed_at = now
    session.confirmed_by = by
    session.updated_at = now
    session.save(
        update_fields=["took_place", "confirmed_at", "confirmed_by", "updated_at"]
    )
    return session


def _record_attendance(
    session: Session, present_ids: set[int], *, by: User, now: dt.datetime
) -> None:
    """Write only what actually moved.

    A row left alone keeps `attended = null`, which counts as present (§6.4) and
    says truthfully that nobody made a claim about it. Stamping every row on
    every save would turn "I looked at the screen" into "I personally attest to
    each of these", and `attendance_recorded_by` is the field somebody reaches
    for when a correction is disputed (§4.3).
    """
    for registration in session.active_registrations():
        was_present = registration.pk in present_ids

        if was_present and registration.attended is False:
            # Putting someone back — an explicit statement this time.
            _stamp(registration, True, by=by, now=now)
        elif not was_present and registration.attended is not False:
            _stamp(registration, False, by=by, now=now)


def _stamp(
    registration: Registration, attended: bool, *, by: User, now: dt.datetime
) -> None:
    registration.attended = attended
    registration.attendance_recorded_at = now
    registration.attendance_recorded_by = by
    registration.save(
        update_fields=["attended", "attendance_recorded_at", "attendance_recorded_by"]
    )


def _add(
    session: Session, participant_ids: list[int], *, by: User, now: dt.datetime
) -> None:
    """§6.4 — somebody who turned up without signing up.

    Attendance genuinely differs from sign-ups, and reconciling the two by hand
    is one of the things this app exists to stop (§1.2). These rows do not
    occupy a seat retrospectively and are exempt from the capacity check: the
    session is over, and capacity is a sign-up rule, not a room limit to enforce
    after the fact (§4.3).
    """
    for participant_id in participant_ids:
        participant = User.objects.filter(
            pk=participant_id, role=Role.PARTICIPANT, is_active=True
        ).first()
        if participant is None:
            continue

        registration = Registration.objects.filter(
            session=session, user=participant
        ).first()
        if registration is None:
            registration = Registration(session=session, user=participant)
        registration.source = RegistrationSource.ADDED_AT_CONFIRMATION
        registration.created_at = now
        registration.cancelled_at = None
        registration.attended = True
        registration.attendance_recorded_at = now
        registration.attendance_recorded_by = by
        registration.save()


def _remove(
    session: Session, registration_ids: list[int], *, by: User, now: dt.datetime
) -> None:
    """§6.4 — somebody added in error.

    The two cases are deliberately different: a row the supervisor created is
    deleted outright, while a row from a real sign-up is only marked absent, so
    that the sign-up itself stays visible. Deleting the second would erase the
    fact that the person said they were coming.
    """
    for registration in Registration.objects.filter(
        pk__in=registration_ids, session=session
    ):
        if registration.source == RegistrationSource.ADDED_AT_CONFIRMATION:
            registration.delete()
        else:
            _stamp(registration, False, by=by, now=now)
