from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ConsentLog, ConsentScope
from .permissions import HasAIConsent, RolePermission
from .serializers import ConsentLogSerializer, RegisterSerializer, UserSerializer


class RegisterView(generics.CreateAPIView):
    """POST /api/v1/auth/register/ — public self-registration (patient/caregiver)."""

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


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
