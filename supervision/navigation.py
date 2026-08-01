"""What each role sees in the header — §7's screens, per §3's roles.

Entries are added as the screens they point at are built, so the header never
carries a link that leads nowhere. The keys are §14.1; the URL names are this
app's own.
"""

from supervision.models import Role

NAV = {
    Role.PARTICIPANT: [
        ("nav.sessions", "participant_home"),
    ],
    Role.SUPERVISOR: [
        ("nav.my_sessions", "supervisor_home"),
        ("nav.my_counts", "supervisor_counts"),
    ],
    Role.ADMIN: [
        ("nav.all_sessions", "admin_home"),
        ("nav.counts_export", "admin_counts"),
    ],
}

HOME_BY_ROLE = {
    Role.PARTICIPANT: "participant_home",
    Role.SUPERVISOR: "supervisor_home",
    Role.ADMIN: "admin_home",
}


def nav_for(user) -> list[dict]:
    if user is None or not user.is_authenticated:
        return []
    return [
        {"key": key, "url_name": url_name} for key, url_name in NAV.get(user.role, [])
    ]
