from django.contrib.auth import get_user_model
from django.http import HttpResponse
from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .audit import record_audit
from .audit_filters import CSV_ROW_CAP, filtered_audit_logs
from .models import (
    AuditAction,
    AuditLog,
    ConsentLog,
    ConsentScope,
    MobilePushDevice,
    NotificationPreference,
    PushSubscription,
    Role,
)
from .permissions import HasAIConsent, IsAdmin, RolePermission
from .serializers import (
    AdminUserSerializer,
    AdminUserUpdateSerializer,
    AuditLogSerializer,
    ConsentLogSerializer,
    MobilePushDeviceSerializer,
    NotificationPreferenceUpdateSerializer,
    PushSubscriptionSerializer,
    RegisterSerializer,
    UserSerializer,
)

User = get_user_model()


class UserPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class AuditPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


class AdminUserListView(generics.ListAPIView):
    """GET /api/v1/users/ — admin + auditor user directory (Step 54)."""

    serializer_class = AdminUserSerializer
    permission_classes = [RolePermission]
    allowed_roles = ("admin", "auditor")
    pagination_class = UserPagination

    def get_queryset(self):
        qs = User.objects.all().order_by("-date_joined")
        role = (self.request.query_params.get("role") or "").strip()
        if role:
            if role not in {c.value for c in Role}:
                raise ValidationError({"role": "Invalid role filter."})
            qs = qs.filter(role=role)
        active = (self.request.query_params.get("is_active") or "").strip().lower()
        if active in {"true", "1", "yes"}:
            qs = qs.filter(is_active=True)
        elif active in {"false", "0", "no"}:
            qs = qs.filter(is_active=False)
        q = (self.request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(email__icontains=q)
        return qs


class AdminUserDetailView(APIView):
    """PATCH /api/v1/users/<id>/ — admin disable/enable account (Step 54)."""

    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def patch(self, request, pk: int):
        try:
            target = User.objects.get(pk=pk)
        except User.DoesNotExist as exc:
            raise NotFound("User not found.") from exc

        ser = AdminUserUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        is_active = ser.validated_data["is_active"]

        if target.pk == request.user.pk and is_active is False:
            raise ValidationError("You cannot disable your own account.")

        if target.is_active == is_active:
            return Response(AdminUserSerializer(target).data)

        target.is_active = is_active
        target.save(update_fields=["is_active"])
        record_audit(
            actor=request.user,
            action=AuditAction.DISABLE_USER,
            request=request,
            target_type="user",
            target_id=target.pk,
            metadata={"is_active": is_active, "email": target.email, "role": target.role},
        )
        return Response(AdminUserSerializer(target).data)


class ThrottledTokenObtainPairView(TokenObtainPairView):
    """POST /api/v1/auth/token/ — JWT login with auth-scope throttle (Step 70)."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class ThrottledTokenRefreshView(TokenRefreshView):
    """POST /api/v1/auth/token/refresh/ — JWT refresh with auth-scope throttle."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class RegisterView(generics.CreateAPIView):
    """POST /api/v1/auth/register/ — public self-registration (patient/caregiver)."""

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class MeView(generics.RetrieveAPIView):
    """GET /api/v1/auth/me/ — the authenticated user's profile."""

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class AdminOnlyView(APIView):
    """GET /api/v1/auth/admin-only/ — RBAC demo; requires the admin role."""

    permission_classes = [RolePermission]
    allowed_roles = ("admin",)

    def get(self, request):
        return Response({"ok": True, "role": request.user.role})


class ConsentView(generics.ListCreateAPIView):
    """/api/v1/consent/ — record (POST) and inspect (GET) processing consent.

    POST appends an immutable grant/revoke row for the authenticated user.
    GET returns the current state per scope plus the full list of valid scopes.
    """

    serializer_class = ConsentLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ConsentLog.objects.filter(user=self.request.user)

    def get(self, request, *args, **kwargs):
        return Response(
            {
                "scopes": {value: label for value, label in ConsentScope.choices},
                "current": ConsentLog.current_state(request.user),
            }
        )


class ConsentGateCheckView(APIView):
    """GET /api/v1/consent/gate-check/ — demo endpoint behind the AI consent gate.

    Proves the PDPA/GDPR gate end to end: 401 unauthenticated, 451 without
    ``ai_processing`` consent, 200 once granted. The real voice pipeline
    (Step 14) reuses the same ``HasAIConsent`` permission.
    """

    permission_classes = [permissions.IsAuthenticated, HasAIConsent]

    def get(self, request):
        return Response({"ok": True, "scope": ConsentScope.AI_PROCESSING.value})


class NotificationPreferenceView(APIView):
    """GET/PATCH /notification-preferences/ — email/push toggles per event."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .notification_preferences import merge_preferences, preferences_payload

        pref, _ = NotificationPreference.objects.get_or_create(user=request.user)
        merged = merge_preferences(pref.channels)
        return Response(preferences_payload(merged))

    def patch(self, request):
        from .notification_preferences import (
            apply_preference_patch,
            merge_preferences,
            preferences_payload,
        )

        ser = NotificationPreferenceUpdateSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        pref, _ = NotificationPreference.objects.get_or_create(user=request.user)
        current = merge_preferences(pref.channels)
        try:
            merged = apply_preference_patch(current, ser.validated_data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        pref.channels = merged
        pref.save(update_fields=["channels", "updated_at"])
        return Response(preferences_payload(merged))


class VapidPublicKeyView(APIView):
    """GET /push/vapid-public-key/ — public key for browser subscribe."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .webpush import vapid_configured, vapid_public_key

        key = vapid_public_key()
        return Response(
            {
                "public_key": key,
                "configured": vapid_configured(),
            }
        )


class PushSubscriptionView(APIView):
    """POST /push/subscriptions/ — register browser push subscription.
    DELETE /push/subscriptions/ — remove by endpoint.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        ser = PushSubscriptionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        keys = data["keys"]
        endpoint = data["endpoint"]
        ua = data.get("user_agent") or request.META.get("HTTP_USER_AGENT", "")[:512]
        sub, created = PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                "user": request.user,
                "p256dh": keys["p256dh"],
                "auth": keys["auth"],
                "user_agent": ua,
            },
        )
        return Response(
            {"id": sub.pk, "endpoint": sub.endpoint, "created": created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request):
        endpoint = (request.data.get("endpoint") or request.query_params.get("endpoint") or "").strip()
        if not endpoint:
            return Response({"detail": "endpoint is required."}, status=status.HTTP_400_BAD_REQUEST)
        deleted, _ = PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
        return Response({"deleted": deleted})


class MobilePushDeviceView(APIView):
    """POST/DELETE /push/mobile/devices/ — register/remove mobile device token."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        ser = MobilePushDeviceSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        row, created = MobilePushDevice.objects.update_or_create(
            token=data["token"],
            defaults={
                "user": request.user,
                "platform": data.get("platform", "fcm"),
                "device_id": data.get("device_id", ""),
                "app_version": data.get("app_version", ""),
                "enabled": True,
            },
        )
        return Response(
            {"id": row.pk, "token": row.token, "platform": row.platform, "created": created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request):
        token = (request.data.get("token") or request.query_params.get("token") or "").strip()
        if not token:
            return Response({"detail": "token is required."}, status=status.HTTP_400_BAD_REQUEST)
        deleted, _ = MobilePushDevice.objects.filter(user=request.user, token=token).delete()
        return Response({"deleted": deleted})


class AuditLogListView(generics.ListAPIView):
    """GET /api/v1/audit/ — filtered audit rows (admin + auditor; Step 58)."""

    serializer_class = AuditLogSerializer
    permission_classes = [RolePermission]
    allowed_roles = ("admin", "auditor")
    pagination_class = AuditPagination

    def get_queryset(self):
        return filtered_audit_logs(self.request.query_params)


class AuditLogExportView(APIView):
    """GET /api/v1/audit/export/ — CSV export with the same filters (Step 58)."""

    permission_classes = [RolePermission]
    allowed_roles = ("admin", "auditor")

    def get(self, request):
        import csv
        import io
        import json

        qs = filtered_audit_logs(request.query_params)[:CSV_ROW_CAP]
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "id",
                "ts",
                "actor_id",
                "actor_email",
                "action",
                "ip",
                "target_type",
                "target_id",
                "metadata",
            ]
        )
        for row in qs.iterator():
            writer.writerow(
                [
                    row.pk,
                    row.ts.isoformat() if row.ts else "",
                    row.actor_id or "",
                    getattr(row.actor, "email", "") if row.actor_id else "",
                    row.action,
                    row.ip or "",
                    row.target_type,
                    row.target_id,
                    json.dumps(row.metadata or {}, ensure_ascii=False),
                ]
            )
        response = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="careplus-audit.csv"'
        return response


class DemoViewHealthView(APIView):
    """GET /api/v1/audit/demo-view-health/?patient_id=<id>

    Stand-in for viewing a patient's health record. Writes exactly one
    immutable ``view_health`` audit row (via Celery / eager). Real health
    views (M6) will call the same ``record_audit`` helper.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        patient_id = request.query_params.get("patient_id")
        if not patient_id:
            return Response(
                {"detail": "patient_id query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        record_audit(
            actor=request.user,
            action=AuditAction.VIEW_HEALTH,
            request=request,
            target_type="patient",
            target_id=patient_id,
            metadata={"source": "demo_view_health"},
            async_=False,
        )
        return Response(
            {
                "ok": True,
                "action": AuditAction.VIEW_HEALTH.value,
                "target_id": str(patient_id),
            }
        )


class PrivacyExportView(APIView):
    """GET /api/v1/privacy/export/?export_format=json|pdf — personal data portability (Step 69)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.accounts.privacy import build_user_export, render_export_pdf

        fmt = (request.query_params.get("export_format") or request.query_params.get("as") or "json").strip().lower()
        if fmt not in ("json", "pdf"):
            return Response(
                {"detail": "export_format must be json or pdf."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if getattr(request.user, "erased_at", None):
            return Response(
                {"detail": "Account already erased."},
                status=status.HTTP_410_GONE,
            )

        payload = build_user_export(request.user)
        record_audit(
            actor=request.user,
            action=AuditAction.EXPORT_DATA,
            request=request,
            target_type="user",
            target_id=request.user.pk,
            metadata={"format": fmt},
            async_=False,
        )
        if fmt == "pdf":
            pdf = render_export_pdf(payload)
            response = HttpResponse(pdf, content_type="application/pdf")
            response["Content-Disposition"] = 'attachment; filename="careplus-data-export.pdf"'
            return response
        return Response(payload)


class PrivacyEraseView(APIView):
    """POST /api/v1/privacy/erase/ — right-to-erasure with password confirm (Step 69)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from apps.accounts.privacy import erase_user_account
        from rest_framework.exceptions import AuthenticationFailed, ValidationError

        password = request.data.get("password") or ""
        confirm = (request.data.get("confirm") or "").strip().lower()
        if confirm not in ("erase", "delete", "yes"):
            return Response(
                {"detail": 'Send confirm as "erase" to proceed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            result = erase_user_account(user=request.user, password=password, request=request)
        except ValidationError as exc:
            return Response({"detail": exc.detail}, status=status.HTTP_400_BAD_REQUEST)
        except AuthenticationFailed as exc:
            return Response({"detail": str(exc.detail)}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(result, status=status.HTTP_200_OK)
