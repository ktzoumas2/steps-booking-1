"""Authentication backend for magic-link sign-in (§5).

There are no credentials to check, so `authenticate()` never succeeds: a user is
signed in by `django.contrib.auth.login()` after a valid, unused, unexpired token
has been redeemed. This backend exists to load the user back out of the session
on later requests, and to keep a deactivated user from riding an existing session
(§4.1 — "inactive users cannot sign in").
"""

from django.contrib.auth import get_user_model


class MagicLinkBackend:
    def authenticate(self, request, **kwargs):
        return None

    def get_user(self, user_id):
        User = get_user_model()
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
        return user if user.is_active else None
