"""Root URL configuration."""

from django.contrib import admin
from django.urls import include, path

api_v1 = [
    path("", include("apps.common.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.voice.urls")),
    path("", include("apps.matching.urls")),
    path("", include("apps.vocab.urls")),
    path("", include("apps.leads.urls")),
    path("", include("apps.catalog.urls")),
    path("", include("apps.medical_records.urls")),
    path("", include("apps.messaging.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include((api_v1, "v1"))),
    # DRF Browsable API login/logout (session auth for the in-browser API UI).
    path("api-auth/", include("rest_framework.urls")),
]
