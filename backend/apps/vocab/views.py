from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdmin, RolePermission

from .models import ConditionTerm
from .resolver import export_vocab_json
from .serializers import (
    AdminConditionTermSerializer,
    AdminConditionTermWriteSerializer,
    ConditionTermSerializer,
)


class ConditionListView(APIView):
    """GET /api/v1/vocab/conditions/ — active canonical medical terms (Step 15b)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = ConditionTerm.objects.filter(active=True).order_by("canonical_en")
        if qs.exists():
            data = ConditionTermSerializer(qs, many=True).data
        else:
            data = export_vocab_json()
        return Response({"count": len(data), "results": data})


class AdminConditionListCreateView(APIView):
    """GET/POST /api/v1/admin/vocab/conditions/ — admin + auditor list; admin create."""

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated(), IsAdmin()]
        return [RolePermission()]

    allowed_roles = ("admin", "auditor")

    def get(self, request):
        qs = ConditionTerm.objects.all().order_by("canonical_en")
        active = (request.query_params.get("active") or "").strip().lower()
        if active in {"true", "1", "yes"}:
            qs = qs.filter(active=True)
        elif active in {"false", "0", "no"}:
            qs = qs.filter(active=False)
        data = AdminConditionTermSerializer(qs, many=True).data
        return Response({"count": len(data), "results": data})

    def post(self, request):
        ser = AdminConditionTermWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        row = ConditionTerm.objects.create(**ser.validated_data)
        return Response(AdminConditionTermSerializer(row).data, status=status.HTTP_201_CREATED)


class AdminConditionDetailView(APIView):
    """GET/PATCH/DELETE /api/v1/admin/vocab/conditions/<slug>/."""

    def get_permissions(self):
        if self.request.method in ("PATCH", "DELETE"):
            return [permissions.IsAuthenticated(), IsAdmin()]
        return [RolePermission()]

    allowed_roles = ("admin", "auditor")

    def _get(self, slug: str) -> ConditionTerm:
        try:
            return ConditionTerm.objects.get(slug=slug)
        except ConditionTerm.DoesNotExist as exc:
            raise NotFound("Condition not found.") from exc

    def get(self, request, slug: str):
        return Response(AdminConditionTermSerializer(self._get(slug)).data)

    def patch(self, request, slug: str):
        row = self._get(slug)
        ser = AdminConditionTermWriteSerializer(row, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        for key, value in ser.validated_data.items():
            setattr(row, key, value)
        row.save()
        return Response(AdminConditionTermSerializer(row).data)

    def delete(self, request, slug: str):
        row = self._get(slug)
        row.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
