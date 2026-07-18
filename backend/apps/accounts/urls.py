from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    AdminOnlyView,
    AuditLogListView,
    ConsentGateCheckView,
    ConsentView,
    DemoViewHealthView,
    MeView,
    RegisterView,
)

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("auth/admin-only/", AdminOnlyView.as_view(), name="admin_only"),
    path("consent/", ConsentView.as_view(), name="consent"),
    path("consent/gate-check/", ConsentGateCheckView.as_view(), name="consent_gate_check"),
    path("audit/", AuditLogListView.as_view(), name="audit_list"),
    path("audit/demo-view-health/", DemoViewHealthView.as_view(), name="audit_demo_view_health"),
]
