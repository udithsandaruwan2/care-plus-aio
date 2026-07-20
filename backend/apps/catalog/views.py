from rest_framework import generics, permissions

from .models import AddOn, CarePackage
from .serializers import AddOnSerializer, CarePackageSerializer


class CarePackageListView(generics.ListAPIView):
    """GET /api/v1/catalog/packages/ — active LKR care packages."""

    permission_classes = [permissions.AllowAny]
    serializer_class = CarePackageSerializer
    pagination_class = None

    def get_queryset(self):
        qs = CarePackage.objects.filter(is_active=True)
        level = (self.request.query_params.get("care_level") or "").strip()
        if level:
            qs = qs.filter(care_level=level)
        return qs


class AddOnListView(generics.ListAPIView):
    """GET /api/v1/catalog/addons/ — active LKR add-ons."""

    permission_classes = [permissions.AllowAny]
    serializer_class = AddOnSerializer
    pagination_class = None

    def get_queryset(self):
        qs = AddOn.objects.filter(is_active=True)
        category = (self.request.query_params.get("category") or "").strip()
        if category:
            qs = qs.filter(category=category)
        return qs
