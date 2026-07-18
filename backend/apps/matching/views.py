from rest_framework import generics, permissions

from apps.accounts.permissions import RolePermission

from .models import CaregiverProfile, PatientProfile
from .serializers import CaregiverProfileSerializer, PatientProfileSerializer


class CaregiverListView(generics.ListAPIView):
    """GET /api/v1/caregivers/ — active caregiver profiles (authenticated)."""

    serializer_class = CaregiverProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = CaregiverProfile.objects.filter(is_active=True).select_related("user")


class PatientListView(generics.ListAPIView):
    """GET /api/v1/patients/ — patient profiles (admin/auditor only for now)."""

    serializer_class = PatientProfileSerializer
    permission_classes = [RolePermission]
    allowed_roles = ("admin", "auditor")
    queryset = PatientProfile.objects.select_related("user").all()
