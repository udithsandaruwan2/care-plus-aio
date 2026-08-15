"""Authenticated profile photo / certification document uploads (Step 22d)."""

from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path

from django.contrib.gis.geos import Point
from django.core.files.storage import default_storage
from django.http import FileResponse
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsCaregiver, IsPatient

from .models import CaregiverProfile, PatientProfile
from .profile_media import (
    resolve_cert_token,
    resolve_photo_token,
    validate_document,
    validate_photo,
)
from .serializers import CaregiverMeSerializer, PatientProfileSerializer


def _caregiver_profile(user) -> CaregiverProfile:
    profile, _ = CaregiverProfile.objects.get_or_create(
        user=user,
        defaults={
            "display_name": user.first_name or user.email.split("@")[0],
            "location": Point(79.8612, 6.9271, srid=4326),
            "city": "",
            "is_active": False,
            "is_approved": False,
        },
    )
    return profile


def _patient_profile(user) -> PatientProfile:
    profile, _ = PatientProfile.objects.get_or_create(user=user)
    return profile


def _uploaded_file(request):
    return request.FILES.get("file") or request.FILES.get("photo") or request.FILES.get("document")


class CaregiverPhotoUploadView(APIView):
    """POST /caregivers/me/photo/ — jpeg/png/webp, virus-scan stub."""

    permission_classes = [permissions.IsAuthenticated, IsCaregiver]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        profile = _caregiver_profile(request.user)
        uploaded = _uploaded_file(request)
        validate_photo(uploaded)
        if profile.photo:
            profile.photo.delete(save=False)
        profile.photo = uploaded
        profile.save(update_fields=["photo", "updated_at"])
        return Response(CaregiverMeSerializer(profile).data, status=status.HTTP_200_OK)


class PatientPhotoUploadView(APIView):
    """POST /patients/me/photo/ — jpeg/png/webp, virus-scan stub."""

    permission_classes = [permissions.IsAuthenticated, IsPatient]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        profile = _patient_profile(request.user)
        uploaded = _uploaded_file(request)
        validate_photo(uploaded)
        if profile.photo:
            profile.photo.delete(save=False)
        profile.photo = uploaded
        profile.save(update_fields=["photo", "updated_at"])
        return Response(PatientProfileSerializer(profile).data, status=status.HTTP_200_OK)


class CaregiverDocumentUploadView(APIView):
    """POST /caregivers/me/documents/ — PDF/image cert files + JSON metadata."""

    permission_classes = [permissions.IsAuthenticated, IsCaregiver]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        profile = _caregiver_profile(request.user)
        uploaded = _uploaded_file(request)
        content_type = validate_document(uploaded)
        doc_id = uuid.uuid4().hex
        ext = Path(getattr(uploaded, "name", "") or "").suffix.lower() or ".bin"
        storage_name = default_storage.save(
            f"cert_docs/caregivers/{timezone.now():%Y/%m}/{doc_id}{ext}",
            uploaded,
        )
        docs = list(profile.certification_docs or [])
        docs.append(
            {
                "id": doc_id,
                "name": Path(getattr(uploaded, "name", "") or "document").name,
                "content_type": content_type,
                "size": int(getattr(uploaded, "size", 0) or 0),
                "storage_path": storage_name,
                "scan": {"status": "clean", "engine": "stub"},
                "uploaded_at": timezone.now().isoformat(),
            }
        )
        profile.certification_docs = docs
        profile.save(update_fields=["certification_docs", "updated_at"])
        return Response(CaregiverMeSerializer(profile).data, status=status.HTTP_201_CREATED)


class ProfilePhotoDownloadView(APIView):
    """GET /profile-media/photos/?token= — signed, not a public bucket listing."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        token = (request.query_params.get("token") or "").strip()
        if not token:
            raise ValidationError("Missing token.")
        kind, profile_id = resolve_photo_token(token)
        if kind == "caregiver":
            try:
                profile = CaregiverProfile.objects.get(pk=profile_id)
            except CaregiverProfile.DoesNotExist as exc:
                raise NotFound("Photo not found.") from exc
        else:
            try:
                profile = PatientProfile.objects.get(pk=profile_id)
            except PatientProfile.DoesNotExist as exc:
                raise NotFound("Photo not found.") from exc
        if not profile.photo:
            raise NotFound("Photo not found.")
        content_type = mimetypes.guess_type(profile.photo.name)[0] or "image/jpeg"
        return FileResponse(
            profile.photo.open("rb"),
            content_type=content_type,
            as_attachment=False,
            filename=Path(profile.photo.name).name,
        )


class ProfileDocumentDownloadView(APIView):
    """GET /profile-media/documents/?token= — signed cert download."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        token = (request.query_params.get("token") or "").strip()
        if not token:
            raise ValidationError("Missing token.")
        caregiver_id, doc_id = resolve_cert_token(token)
        try:
            profile = CaregiverProfile.objects.get(pk=caregiver_id)
        except CaregiverProfile.DoesNotExist as exc:
            raise NotFound("Document not found.") from exc
        match = None
        for doc in profile.certification_docs or []:
            if isinstance(doc, dict) and str(doc.get("id")) == doc_id:
                match = doc
                break
        if not match or not match.get("storage_path"):
            raise NotFound("Document not found.")
        storage_path = str(match["storage_path"])
        if not default_storage.exists(storage_path):
            raise NotFound("Document not found.")
        content_type = match.get("content_type") or mimetypes.guess_type(storage_path)[0]
        return FileResponse(
            default_storage.open(storage_path, "rb"),
            content_type=content_type or "application/octet-stream",
            as_attachment=True,
            filename=str(match.get("name") or Path(storage_path).name),
        )
