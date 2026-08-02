"""Screens — §7.

This slice carries sign-in (§5), the language toggle (§10) and the three role
home screens, which on an empty database are their own empty states (§7). The
lists behind those empty states arrive with the Session model.
"""

from __future__ import annotations

import datetime as dt

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from supervision import (
    calendar as ics,
    people,
    counting,
    exports,
    mail,
    registrations as registration_service,
    review as review_service,
    sessions as session_service,
    signin,
)
from supervision.catalog import LOCALES, t
from supervision.forms import PersonForm, SessionForm, SettingsForm
from supervision.middleware import LOCALE_COOKIE
from supervision.models import EmailKind, Role, Session, SessionStatus, Settings, User
from supervision.navigation import HOME_BY_ROLE

SIGNIN_BACKEND = "supervision.auth_backends.MagicLinkBackend"


def home(request):
    """§12.3 #6 — each role lands on its own home screen."""
    if not request.user.is_authenticated:
        return redirect("signin")
    return redirect(HOME_BY_ROLE[request.user.role])


# --- Sign-in (§5) ---------------------------------------------------------


def signin_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method != "POST":
        return render(request, "signin/signin.html")

    email = request.POST.get("email", "")
    user = signin.find_recipient(email)

    # §5.2 and §5.6 — an unknown or deactivated address, and an address that has
    # asked too often this hour, all take the same path out of this view as a
    # successful one. Anything else would answer "is this person registered?" to
    # whoever asked.
    if user is not None and not signin.is_rate_limited(user, request.now):
        issued = signin.issue_token(user, request.now)
        mail.send(
            EmailKind.LOGIN,
            user=user,
            now=request.now,
            link=request.build_absolute_uri(
                reverse("signin_redeem", args=[issued.raw_token])
            ),
        )

    return redirect("signin_sent")


def signin_sent(request):
    return render(request, "signin/sent.html")


def signin_redeem(request, raw_token):
    """Clicking the link in the mail (§5.3)."""
    try:
        user = signin.redeem_token(raw_token, request.now)
    except signin.RedemptionError as failure:
        # §7.4 — say what happened, and say what to do next: both link failures
        # are shown with a button that requests a fresh one.
        return render(
            request,
            "signin/link_failed.html",
            {"error_key": failure.copy_key},
            status=410,
        )

    # §10, #67 — a language chosen on the sign-in screen, before there was an
    # account to keep it on, follows the person into their account.
    chosen = request.COOKIES.get(LOCALE_COOKIE)
    if chosen in LOCALES and chosen != user.locale:
        user.locale = chosen
        user.save(update_fields=["locale"])

    login(request, user, backend=SIGNIN_BACKEND)
    response = redirect("home")
    response.delete_cookie(LOCALE_COOKIE)
    return response


@require_POST
def signout(request):
    logout(request)
    return redirect("signin")


# --- Language (§10) -------------------------------------------------------


@require_POST
def set_language(request):
    locale = request.POST.get("locale")
    if locale not in LOCALES:
        return redirect("home")

    if request.user.is_authenticated:
        request.user.locale = locale
        request.user.save(update_fields=["locale"])

    response = _redirect_back(request)
    if not request.user.is_authenticated:
        response.set_cookie(
            LOCALE_COOKIE, locale, max_age=60 * 60 * 24 * 365, samesite="Lax"
        )
    return response


def _redirect_back(request) -> HttpResponseRedirect:
    """Back to the page the toggle was pressed on, if that page is ours."""
    target = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(target)
    return redirect("home")


# --- Role home screens (§7.1 P1, §7.2 S1, §7.3 A1) ------------------------


def _require_role(request, role):
    return request.user.is_authenticated and request.user.role == role


def _with_seat_counts(queryset):
    """Sessions with `taken` annotated, so a list does not count once per row."""
    return list(
        queryset.select_related("supervisor").annotate(
            taken=Count(
                "registrations",
                filter=Q(registrations__cancelled_at__isnull=True),
            )
        )
    )


# The supervisor filter outlives one page view: §7.1 asks for the choice to
# persist across sign-ups, and a participant who signs up should come back to
# the list they were reading, not to everything.
SUPERVISOR_FILTER = "supervisor_filter"


@login_required
def participant_home(request):
    """P1 — Available (§7.1): every upcoming session, grouped by calendar week."""
    if not _require_role(request, Role.PARTICIPANT):
        return redirect("home")

    upcoming = session_service.upcoming_sessions(request.now)
    supervisors = session_service.supervisors_with_upcoming(upcoming)

    if "supervisor" in request.GET:
        chosen = request.GET["supervisor"]
        request.session[SUPERVISOR_FILTER] = int(chosen) if chosen.isdigit() else None
    filtered_to_id = request.session.get(SUPERVISOR_FILTER)

    filtered_to = None
    if filtered_to_id is not None:
        filtered_to = User.objects.filter(pk=filtered_to_id).first()

    # A filter on a supervisor who has nothing upcoming is deliberately *kept*,
    # not tidied away: §7.1 requires that exact screen — their name, that they
    # have nothing, and a way out. Dropping the filter would make the message
    # unreachable and leave the participant wondering what they are looking at.
    if filtered_to is not None and filtered_to not in supervisors:
        # The control still has to reflect its own state, so the current choice
        # stays in the dropdown even though it is not one to offer afresh.
        supervisors = supervisors + [filtered_to]

    shown = (
        [s for s in upcoming if s.supervisor_id == filtered_to.pk]
        if filtered_to is not None
        else upcoming
    )

    # §7.1 — a full session stays visible, greyed, rather than disappearing: a
    # participant who cannot find a session they were told about assumes the app
    # is broken.
    mine = registration_service.registered_session_ids(request.user)
    for session in shown:
        session.i_am_registered = session.pk in mine
        # Not `is_full`: that is a model property which asks the database once
        # per row. `taken` is already annotated on the queryset.
        session.full = session.taken >= session.capacity

    return render(
        request,
        "screens/p1_sessions.html",
        {
            "tab": "available",
            "weeks": session_service.group_by_week(shown, request.locale),
            "any_upcoming": bool(upcoming),
            "supervisors": supervisors,
            "filtered_to": filtered_to,
        },
    )


@login_required
def participant_my_sessions(request):
    """P1 — My sessions (§7.1): upcoming first, then past ones with whether they
    took place and whether the participant was marked present."""
    if not _require_role(request, Role.PARTICIPANT):
        return redirect("home")

    mine = registration_service.registrations_for(request.user)
    return render(
        request,
        "screens/p1_my_sessions.html",
        {
            "tab": "mine",
            "upcoming": [r for r in mine if not r.session.has_ended(request.now)],
            "past": [r for r in mine if r.session.has_ended(request.now)],
        },
    )


def _date_range(source) -> tuple[dt.date | None, dt.date | None]:
    """Read a `start`/`end` range off a request, ignoring anything unparseable.

    All time, by default (§7.1 P3): the range is a narrowing, and a typo in a
    date field should show more than the user asked for, never less.
    """

    def parse(name):
        raw = (source.get(name) or "").strip()
        try:
            return dt.date.fromisoformat(raw)
        except ValueError:
            return None

    return parse("start"), parse("end")


def _participation_record(now, participant, start, end) -> dict:
    """P3's content, which A2's drill-down reuses verbatim (§7.3).

    The admin sees exactly what the participant sees, which is the point: one
    definition of the figure, not two that can disagree.
    """
    attended = counting.attended_registrations(
        now, participant=participant, start=start, end=end
    )
    return {
        "participant": participant,
        "attended_count": len(attended),
        "attended": attended,
        "absent": counting.absent_registrations(
            now, participant=participant, start=start, end=end
        ),
        "start": start,
        "end": end,
    }


@login_required
def participant_participation(request):
    """P3 — My participation (§7.1), the answer to "how many, and which ones?"."""
    if not _require_role(request, Role.PARTICIPANT):
        return redirect("home")

    start, end = _date_range(request.GET)
    context = _participation_record(request.now, request.user, start, end)
    context["tab"] = "participation"
    return render(request, "screens/p3_participation.html", context)


# --- S5 and A2 — the counts (§7.2, §7.3, §9) ------------------------------


@login_required
def supervisor_counts(request):
    """S5 — My counts (§7.2). A supervisor sees their own and nobody else's (§3)."""
    if not _require_role(request, Role.SUPERVISOR):
        return redirect("home")

    start, end = _date_range(request.GET)
    held = counting.sessions_that_count(
        request.now, supervisor=request.user, start=start, end=end
    )
    return render(
        request,
        "screens/s5_counts.html",
        {"held": held, "count": len(held), "start": start, "end": end},
    )


@login_required
def admin_counts(request):
    """A2 — Counts and export (§7.3), including the billing sign-off."""
    if not _require_role(request, Role.ADMIN):
        return redirect("home")

    source = request.POST if request.method == "POST" else request.GET
    start, end = _date_range(source)
    unreviewed = counting.unreviewed_in_range(request.now, start=start, end=end)

    if request.method == "POST":
        wanted = request.POST.get("export")
        acknowledged = request.POST.get("ack") == "1"

        # §7.3, D30–D31 — the one place a human is made to look before the
        # numbers become an invoice. It acknowledges rather than blocks:
        # requiring every session to be opened would rebuild the confirmation
        # chore D29 removed, and an admin facing a blocked export at invoice
        # time will find a way around it.
        if wanted in exports.EXPORTS and (acknowledged or not unreviewed):
            build, filename = exports.EXPORTS[wanted]
            body = build(request.now, start=start, end=end)
            response = HttpResponse(body, content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = (
                f'attachment; filename="{filename}.csv"'
            )
            return response

    return render(
        request,
        "screens/a2_counts.html",
        {
            "per_supervisor": counting.sessions_held_by_supervisor(
                request.now, start=start, end=end
            ),
            "per_participant": counting.participation_by_participant(
                request.now, start=start, end=end
            ),
            "unreviewed": unreviewed,
            "needs_acknowledgement": bool(unreviewed),
            "acknowledged": request.POST.get("ack") == "1",
            "start": start,
            "end": end,
        },
    )


@login_required
def admin_participant_record(request, pk):
    """§7.3 A2 — where the admin answers "has this trainee actually been
    coming?" without exporting anything."""
    if not _require_role(request, Role.ADMIN):
        return redirect("home")

    participant = get_object_or_404(User, pk=pk, role=Role.PARTICIPANT)
    start, end = _date_range(request.GET)
    context = _participation_record(request.now, participant, start, end)
    return render(request, "screens/a2_participant_record.html", context)


@login_required
def session_detail(request, pk):
    """P2 — Session detail (§7.1)."""
    session = get_object_or_404(
        Session.objects.select_related("supervisor"), pk=pk
    )
    # D11 — the Zoom link is for registered participants, mild protection for a
    # link that never changes. The supervisor holding the session and the admin
    # see it too: they need it, and `p2.zoom_hidden` tells them to sign up for
    # something they cannot sign up for.
    registered = list(
        session.active_registrations().select_related("user").order_by("created_at")
    )
    i_am_registered = any(r.user_id == request.user.pk for r in registered)
    may_see_zoom = (
        i_am_registered
        or request.user.is_admin
        or session.supervisor_id == request.user.pk
    )

    return render(
        request,
        "screens/p2_session_detail.html",
        {
            "session": session,
            "zoom_url": Settings.load().zoom_url,
            "may_see_zoom": may_see_zoom,
            "i_am_registered": i_am_registered,
            "registered": [r.user for r in registered],
            "is_full": len(registered) >= session.capacity,
            "still_to_come": session.is_upcoming(request.now),
        },
    )


# --- S3 — reviewing a past session (§6.4, §7.2) ---------------------------


@login_required
def session_review(request, pk):
    """S3 — opens on the assumption that everything went as planned.

    The question at the top is "War etwas anders?", not "Did this happen?": the
    session already counts, and the screen exists to record the exceptions.
    """
    session = get_object_or_404(
        Session.objects.select_related("supervisor", "confirmed_by"), pk=pk
    )
    if not review_service.may_review(request.user, session):
        return redirect("home")
    if not review_service.is_reviewable(session, request.now):
        return redirect("home")

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "not_held":
            # §6.4 — warned about on its own screen first, because it removes
            # the session from the supervisor's count and from every
            # participant's record.
            review_service.save_review(
                session, by=request.user, now=request.now, took_place=False
            )
        elif action == "as_planned":
            # A real action: it changes no value but sets confirmed_at, which is
            # exactly the statement the billing sign-off needs (§7.3 A2).
            review_service.save_review(session, by=request.user, now=request.now)
        else:
            review_service.save_review(
                session,
                by=request.user,
                now=request.now,
                took_place=True,
                present_registration_ids={
                    int(value) for value in request.POST.getlist("present")
                },
                add_participant_ids=[
                    int(value) for value in request.POST.getlist("add") if value
                ],
                remove_registration_ids=[
                    int(value) for value in request.POST.getlist("remove")
                ],
            )
        return redirect(HOME_BY_ROLE[request.user.role])

    return render(
        request,
        "screens/s3_review.html",
        {
            "session": session,
            "registrations": list(
                session.active_registrations().select_related("user")
            ),
            "candidates": review_service.candidates_to_add(session),
        },
    )


@login_required
def session_not_held(request, pk):
    """The warning §6.4 requires before recording that a session did not happen."""
    session = get_object_or_404(Session, pk=pk)
    if not review_service.may_review(
        request.user, session
    ) or not review_service.is_reviewable(session, request.now):
        return redirect("home")

    return render(request, "screens/s3_not_held.html", {"session": session})


# --- Development only -----------------------------------------------------


def dev_sign_in_as(request, pk=None):
    """Sign in as anyone, without a magic link. **DEBUG only.**

    Agreed 2026-07-29 as a demonstration aid: showing three roles to someone
    otherwise means fishing a link out of the terminal for each. It is hard
    gated — with DEBUG off this route does not exist at all — and the real
    magic-link flow of §5 is untouched and independently tested.
    """
    if not settings.DEBUG:
        raise Http404

    if pk is None:
        return render(
            request,
            "screens/dev_sign_in_as.html",
            {"people": User.objects.filter(is_active=True).order_by("role", "last_name")},
        )

    person = get_object_or_404(User, pk=pk, is_active=True)
    login(request, person, backend=SIGNIN_BACKEND)
    return redirect("home")


# --- A3 and A4 — people and settings (§7.3) -------------------------------


@login_required
def admin_people(request):
    """A3 — every account originates here, bar the install-time admin (§5.1)."""
    if not _require_role(request, Role.ADMIN):
        return redirect("home")

    form = PersonForm(locale=request.locale)
    if request.method == "POST" and request.POST.get("action") == "add":
        form = PersonForm(request.POST, locale=request.locale)
        if form.is_valid():
            people.add_person(
                now=request.now,
                send_invitation=request.POST.get("send_invitation") == "1",
                link=request.build_absolute_uri(reverse("signin")),
                **form.cleaned_data,
            )
            return redirect("admin_people")

    return render(
        request,
        "screens/a3_people.html",
        {
            "form": form,
            "people": people.everyone(),
            "role_labels": dict(people.role_choices()),
        },
    )


@login_required
def admin_person_state(request, pk):
    """Deactivate or reactivate (§4.1). Never delete: that would orphan the
    sessions and attendance records billing depends on."""
    if not _require_role(request, Role.ADMIN):
        return redirect("home")

    person = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        if request.POST.get("action") == "reactivate":
            people.reactivate(person)
        else:
            try:
                people.deactivate(person, now=request.now)
            except people.DeactivationBlocked as blocked:
                # §7.4 — the message names the sessions, each linked, so the
                # admin can cancel or reassign them and come back.
                messages.error(
                    request,
                    t(
                        blocked.copy_key,
                        request.locale,
                        name=person.full_name,
                        sessions=people.describe_blocking_sessions(
                            blocked.sessions, request.locale
                        ),
                    ),
                )
    return redirect("admin_people")


@login_required
def admin_settings(request):
    """A4 — the programme-wide settings of §4.4."""
    if not _require_role(request, Role.ADMIN):
        return redirect("home")

    settings_row = Settings.load()
    form = SettingsForm(instance=settings_row)
    if request.method == "POST":
        form = SettingsForm(request.POST, instance=settings_row)
        if form.is_valid():
            form.save()
            return redirect("admin_settings")

    return render(request, "screens/a4_settings.html", {"form": form})


@login_required
def session_ics(request, pk):
    """§7.1 P2 — `Zum Kalender hinzufügen`, the same .ics the emails carry.

    For anyone who deleted the mail or signed up on a device that does not
    handle attachments.
    """
    session = get_object_or_404(
        Session.objects.select_related("supervisor"), pk=pk
    )
    body = ics.build_ics(
        session,
        request.user,
        now=request.now,
        method=ics.REQUEST,
        zoom_url=Settings.load().zoom_url,
    )
    response = HttpResponse(body, content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="supervision.ics"'
    return response


# --- Signing up and giving up a place (§6.2, §6.3) ------------------------


@login_required
@require_POST
def session_sign_up(request, pk):
    """§7.1 — one tap, from the list, no intermediate screen."""
    if not _require_role(request, Role.PARTICIPANT):
        return redirect("home")

    session = get_object_or_404(Session, pk=pk)
    try:
        registration_service.sign_up(session, request.user, request.now)
    except registration_service.SignUpRefused as refusal:
        # §7.4 — "this session just filled up", not a generic failure, which
        # reads as a bug.
        messages.error(request, t(refusal.copy_key, request.locale))
    return _redirect_back(request)


@login_required
@require_POST
def session_give_up_place(request, pk):
    if not _require_role(request, Role.PARTICIPANT):
        return redirect("home")

    session = get_object_or_404(Session, pk=pk)
    try:
        registration_service.cancel_place(session, request.user, request.now)
    except registration_service.SignUpRefused as refusal:
        messages.error(request, t(refusal.copy_key, request.locale))
    return _redirect_back(request)


@login_required
def supervisor_home(request):
    """S1 — My sessions (§7.2)."""
    if not _require_role(request, Role.SUPERVISOR):
        return redirect("home")

    mine = _with_seat_counts(Session.objects.filter(supervisor=request.user))
    return render(
        request,
        "screens/s1_my_sessions.html",
        {
            "sessions": mine,
            "upcoming": [s for s in mine if not s.has_ended(request.now)],
            "past": [s for s in mine if s.has_ended(request.now)],
        },
    )


@login_required
def admin_home(request):
    """A1 — All sessions (§7.3). Filters arrive with the admin slice."""
    if not _require_role(request, Role.ADMIN):
        return redirect("home")

    everything = _with_seat_counts(Session.objects.all())
    return render(
        request,
        "screens/a1_all_sessions.html",
        {
            "sessions": everything,
            "upcoming": [s for s in everything if not s.has_ended(request.now)],
            "past": [s for s in everything if s.has_ended(request.now)],
        },
    )


# --- S2 — offer / edit / cancel a session (§7.2, §6.1, §6.3, §6.5) --------


def _may_manage(user, session=None) -> bool:
    """§3 — a supervisor manages their own sessions, an admin manages anyone's."""
    if user.is_admin:
        return True
    if not user.is_supervisor:
        return False
    return session is None or session.supervisor_id == user.pk


def _cap_decision(check, editor, locale):
    """What the weekly cap (§6.1) has to say, in the words of §7.4.

    Three different answers, and conflating them would be a mistake: an admin is
    always allowed through after confirming (§6.1), enforcement on is a block a
    supervisor cannot argue with, and enforcement off is a warning they can.
    """
    if not check.would_exceed:
        return None

    listed = {
        "count": len(check.clashing),
        "sessions": session_service.describe_sessions(check.clashing, locale),
    }

    if editor.is_admin:
        return {
            "confirmable": True,
            "message": t("confirm.cap_override", locale, cap=check.cap),
            "clashing": check.clashing,
        }
    if check.enforced:
        return {
            "confirmable": False,
            "message": t("err.week_full", locale, **listed),
            "clashing": check.clashing,
        }
    return {
        "confirmable": True,
        "message": t("warn.week_full", locale, **listed),
        "clashing": check.clashing,
    }


@login_required
def session_new(request):
    if not _may_manage(request.user):
        return redirect("home")
    return _session_form(request, session=None)


@login_required
def session_edit(request, pk):
    session = get_object_or_404(Session, pk=pk)
    if not _may_manage(request.user, session):
        return redirect("home")
    # §6.5 — supervisors edit upcoming sessions. A session that has started is
    # cancelled (§6.3) or reviewed (§6.4); it is not rescheduled underneath the
    # people sitting in it.
    if not session.is_upcoming(request.now):
        return redirect("home")
    return _session_form(request, session=session)


def _session_form(request, session):
    form_kwargs = {
        "editor": request.user,
        "now": request.now,
        "locale": request.locale,
        "instance": session,
    }

    if request.method != "POST":
        return render(
            request,
            "screens/s2_session_form.html",
            {"form": SessionForm(**form_kwargs), "session": session},
        )

    form = SessionForm(request.POST, **form_kwargs)
    decision = None

    if form.is_valid():
        settings = Settings.load()
        check = session_service.check_weekly_cap(
            form.cleaned_data["date"], settings, exclude=session
        )
        decision = _cap_decision(check, request.user, request.locale)
        confirmed = request.POST.get("confirm_week") == "1"

        if decision is None or (decision["confirmable"] and confirmed):
            fields = dict(form.cleaned_data)
            supervisor = fields.pop("supervisor", None) or (
                session.supervisor if session else request.user
            )
            if session is None:
                session_service.create_session(
                    supervisor=supervisor, now=request.now, **fields
                )
            else:
                session_service.update_session(
                    session, now=request.now, supervisor=supervisor, **fields
                )
            return redirect(HOME_BY_ROLE[request.user.role])

    return render(
        request,
        "screens/s2_session_form.html",
        {"form": form, "session": session, "cap": decision},
    )


@login_required
def session_cancel(request, pk):
    """§6.3 — cancellable until the end time, including while in progress."""
    session = get_object_or_404(Session, pk=pk)
    if not _may_manage(request.user, session) or not session.can_be_cancelled(
        request.now
    ):
        return redirect("home")

    if request.method != "POST":
        return render(
            request, "screens/s2_cancel_session.html", {"session": session}
        )

    session_service.cancel_session(session, by=request.user, now=request.now)
    return redirect(HOME_BY_ROLE[request.user.role])
