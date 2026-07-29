"""Root URL configuration.

Screens are added slice by slice; §7 lists the twelve that exist in the end.
"""

from django.urls import include, path

urlpatterns = [
    path("", include("supervision.urls")),
]
