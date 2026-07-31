from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    AdminOnlyView,
    AdminUserDetailView,
    AdminUserListView,
    AuditLogExportView,
    AuditLogListView,
    ConsentGateCheckView,
    ConsentView,
    DemoViewHealthView,
    MeView,
    MobilePushDeviceView,
    NotificationPreferenceView,
    PushSubscriptionView,
    RegisterView,
    VapidPublicKeyView,
)

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("auth/admin-only/", AdminOnlyView.as_view(), name="admin_only"),
    path("users/", AdminUserListView.as_view(), name="admin_user_list"),
    path("users/<int:pk>/", AdminUserDetailView.as_view(), name="admin_user_detail"),
    path("consent/", ConsentView.as_view(), name="consent"),
    path("consent/gate-check/", ConsentGateCheckView.as_view(), name="consent_gate_check"),
    path(
        "notification-preferences/",
        NotificationPreferenceView.as_view(),
        name="notification_preferences",
    ),
    path("push/vapid-public-key/", VapidPublicKeyView.as_view(), name="vapid_public_key"),
    path("push/subscriptions/", PushSubscriptionView.as_view(), name="push_subscriptions"),
    path("push/mobile/devices/", MobilePushDeviceView.as_view(), name="mobile_push_devices"),
    path("audit/", AuditLogListView.as_view(), name="audit_list"),
    path("audit/export/", AuditLogExportView.as_view(), name="audit_export"),
    path("audit/demo-view-health/", DemoViewHealthView.as_view(), name="audit_demo_view_health"),
]
