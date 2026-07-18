from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import RolePermission
from .serializers import RegisterSerializer, UserSerializer


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

    @extend_schema(responses={200: None, 403: None})
    def get(self, request):
        return Response({"ok": True, "role": request.user.role})
