from django.http import FileResponse
from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError as DRFValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import IsPatient

from .access import can_read_medical_record, read_medical_record
from .attachments import (
    attachment_download_path,
    build_signed_download_token,
    get_attachment_or_404,
    resolve_signed_download_token,
)
from .models import MedicalRecord, MedicalRecordAttachment
from .serializers import (
    MedicalRecordAttachmentSerializer,
    MedicalRecordCreateSerializer,
    MedicalRecordDetailSerializer,
    MedicalRecordListSerializer,
    SignedDownloadUrlSerializer,
)
from .services import create_medical_record, records_queryset_for_user, upload_attachment


class MedicalRecordListCreateView(generics.ListCreateAPIView):
    """GET list / POST create (multipart) medical records."""

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return MedicalRecordCreateSerializer
        return MedicalRecordListSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated(), IsPatient()]
        return super().get_permissions()

    def get_queryset(self):
        qs = records_queryset_for_user(self.request.user)
        patient_id = (self.request.query_params.get("patient_id") or "").strip()
        if patient_id and getattr(self.request.user, "role", None) in (Role.ADMIN, Role.AUDITOR):
            qs = qs.filter(patient_id=patient_id)
        return qs.order_by("-recorded_at", "-created_at")

    def create(self, request, *args, **kwargs):
        ser = MedicalRecordCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        upload_file = request.FILES.get("file")
        try:
            record = create_medical_record(
                patient=request.user,
                condition_slug=data["condition_slug"],
                title=data["title"],
                description=data.get("description", ""),
                sensitive_notes=data.get("sensitive_notes", ""),
                recorded_at=data.get("recorded_at"),
                upload_file=upload_file,
            )
        except PermissionDenied:
            raise
        except DRFValidationError:
            raise
        except Exception as exc:
            raise DRFValidationError(str(exc)) from exc

        record = read_medical_record(user=request.user, record=record, request=request)
        out = MedicalRecordDetailSerializer(record)
        return Response(out.data, status=status.HTTP_201_CREATED)


class MedicalRecordDetailView(generics.RetrieveAPIView):
    """GET /medical-records/<id>/ — audited detail with decrypted notes."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MedicalRecordDetailSerializer
    lookup_url_kwarg = "pk"

    def get_queryset(self):
        return records_queryset_for_user(self.request.user)

    def retrieve(self, request, *args, **kwargs):
        record = self.get_object()
        record = read_medical_record(user=request.user, record=record, request=request)
        serializer = self.get_serializer(record)
        return Response(serializer.data)


class MedicalRecordAttachmentUploadView(APIView):
    """POST /medical-records/<id>/attachments/ — multipart file upload."""

    permission_classes = [permissions.IsAuthenticated, IsPatient]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk: int):
        try:
            record = MedicalRecord.objects.get(pk=pk, patient=request.user)
        except MedicalRecord.DoesNotExist as exc:
            raise NotFound("Medical record not found.") from exc

        uploaded_file = request.FILES.get("file")
        if uploaded_file is None:
            raise DRFValidationError("Missing file field 'file'.")

        try:
            attachment = upload_attachment(
                record=record,
                patient=request.user,
                uploaded_file=uploaded_file,
            )
        except PermissionDenied:
            raise
        except DRFValidationError:
            raise
        except Exception as exc:
            raise DRFValidationError(str(exc)) from exc

        return Response(
            MedicalRecordAttachmentSerializer(attachment).data,
            status=status.HTTP_201_CREATED,
        )


class MedicalRecordAttachmentDownloadUrlView(APIView):
    """POST /medical-records/attachments/<id>/download-url/ — signed download link."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk: int):
        attachment = get_attachment_or_404(pk)
        if not can_read_medical_record(request.user, attachment.record):
            raise PermissionDenied("You cannot access this attachment.")

        token = build_signed_download_token(attachment.pk)
        from .attachments import download_url_ttl_seconds

        payload = {
            "attachment_id": attachment.pk,
            "url": attachment_download_path(token),
            "expires_in": download_url_ttl_seconds(),
        }
        return Response(SignedDownloadUrlSerializer(payload).data)


class MedicalRecordAttachmentDownloadView(APIView):
    """GET /medical-records/attachments/download/?token= — signed file download."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        token = (request.query_params.get("token") or "").strip()
        if not token:
            raise DRFValidationError("Missing token.")

        try:
            attachment_id = resolve_signed_download_token(token)
            attachment = get_attachment_or_404(attachment_id)
        except DRFValidationError:
            raise

        if not attachment.file:
            raise NotFound("Attachment file not found.")

        # Signed URL is the gate; optional audit when actor is authenticated.
        if request.user and request.user.is_authenticated:
            if can_read_medical_record(request.user, attachment.record):
                read_medical_record(
                    user=request.user,
                    record=attachment.record,
                    request=request,
                )

        response = FileResponse(
            attachment.file.open("rb"),
            content_type=attachment.content_type or "application/octet-stream",
            as_attachment=True,
            filename=attachment.original_name or attachment.file.name,
        )
        return response
