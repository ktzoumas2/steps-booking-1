"""Screens — §7.

This slice carries sign-in (§5), the language toggle (§10) and the three role
home screens, which on an empty database are their own empty states (§7). The
lists behind those empty states arrive with the Session model.
"""

from __future__ import annotations

from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from supervision import mail, signin
from supervision.catalog import LOCALES
from supervision.middleware import LOCALE_COOKIE
from supervision.models import EmailKind, Role
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
#
# Each is the real screen for its role, showing the real §14 empty state. On an
# empty database that is the whole screen; the lists, filters and actions arrive
# with the slices that build them.


def _require_role(request, role):
    return request.user.is_authenticated and request.user.role == role


@login_required
def participant_home(request):
    if not _require_role(request, Role.PARTICIPANT):
        return redirect("home")
    return render(request, "screens/p1_sessions.html", {"sessions": []})


@login_required
def supervisor_home(request):
    if not _require_role(request, Role.SUPERVISOR):
        return redirect("home")
    return render(request, "screens/s1_my_sessions.html", {"sessions": []})


@login_required
def admin_home(request):
    if not _require_role(request, Role.ADMIN):
        return redirect("home")
    return render(request, "screens/a1_all_sessions.html", {"sessions": []})
