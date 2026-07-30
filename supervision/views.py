"""Screens — §7.

This slice carries sign-in (§5), the language toggle (§10) and the three role
home screens, which on an empty database are their own empty states (§7). The
lists behind those empty states arrive with the Session model.
"""

from __future__ import annotations

from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from supervision import mail, sessions as session_service, signin
from supervision.catalog import LOCALES, t
from supervision.forms import SessionForm
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
    """P1 — My sessions (§7.1). The lists behind it arrive with registrations."""
    if not _require_role(request, Role.PARTICIPANT):
        return redirect("home")
    return render(
        request,
        "screens/p1_my_sessions.html",
        {"tab": "mine", "upcoming": [], "past": []},
    )


@login_required
def participant_participation(request):
    """P3 — My participation (§7.1). The count is real; it is simply 0 until
    somebody has attended something, and §7.1 insists that be shown rather than
    hidden — a zero with an explanation is trustworthy, a blank screen reads as
    a bug."""
    if not _require_role(request, Role.PARTICIPANT):
        return redirect("home")
    return render(
        request,
        "screens/p3_participation.html",
        {"tab": "participation", "attended_count": 0, "attended": [], "absent": []},
    )


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
    may_see_zoom = request.user.is_admin or session.supervisor_id == request.user.pk

    return render(
        request,
        "screens/p2_session_detail.html",
        {
            "session": session,
            "zoom_url": Settings.load().zoom_url,
            "may_see_zoom": may_see_zoom,
            "registered": [],
        },
    )


@login_required
def supervisor_home(request):
    """S1 — My sessions (§7.2)."""
    if not _require_role(request, Role.SUPERVISOR):
        return redirect("home")

    mine = Session.objects.filter(supervisor=request.user).select_related("supervisor")
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

    everything = Session.objects.all().select_related("supervisor")
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
