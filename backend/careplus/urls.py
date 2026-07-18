"""Root URL configuration."""

from django.contrib import admin
from django.urls import include, path

api_v1 = [
    path("", include("apps.common.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.voice.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include((api_v1, "v1"))),
    # DRF Browsable API login/logout (session auth for the in-browser API UI).
    path("api-auth/", include("rest_framework.urls")),
]
