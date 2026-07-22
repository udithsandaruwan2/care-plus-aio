"""Medical record attachment validation and signed download URLs (Step 35)."""

from __future__ import annotations

from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from rest_framework.exceptions import ValidationError

from .models import MedicalRecordAttachment

SIGNER_SALT = "medical-record-attachment-download"

DEFAULT_ALLOWED_MIMES = frozenset(
    {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
        "text/plain",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)


def allowed_mimes() -> frozenset[str]:
    raw = getattr(settings, "MEDICAL_RECORD_ALLOWED_MIMES", None)
    if not raw:
        return DEFAULT_ALLOWED_MIMES
    if isinstance(raw, (list, tuple, set, frozenset)):
        return frozenset(str(x).strip().lower() for x in raw if str(x).strip())
    return frozenset(x.strip().lower() for x in str(raw).split(",") if x.strip())


def max_upload_bytes() -> int:
    return int(getattr(settings, "MEDICAL_RECORD_MAX_UPLOAD_BYTES", 10 * 1024 * 1024))


def download_url_ttl_seconds() -> int:
    return int(getattr(settings, "MEDICAL_RECORD_DOWNLOAD_URL_TTL_SECONDS", 3600))


def normalize_content_type(content_type: str) -> str:
    ct = (content_type or "application/octet-stream").split(";")[0].strip().lower()
    if ct == "image/jpg":
        return "image/jpeg"
    return ct


def validate_upload_file(uploaded_file) -> str:
    """Return normalized MIME type or raise ValidationError."""
    if uploaded_file is None:
        raise ValidationError("No file uploaded.")

    size = getattr(uploaded_file, "size", None)
    if size is None:
        data = uploaded_file.read()
        size = len(data)
        uploaded_file.seek(0)
    if size <= 0:
        raise ValidationError("Uploaded file is empty.")
    if size > max_upload_bytes():
        raise ValidationError(
            f"File exceeds maximum size of {max_upload_bytes()} bytes.",
            code="file_too_large",
        )

    content_type = normalize_content_type(getattr(uploaded_file, "content_type", ""))
    if content_type not in allowed_mimes():
        raise ValidationError(
            f"File type '{content_type}' is not allowed.",
            code="mime_not_allowed",
        )
    return content_type


def build_signed_download_token(attachment_id: int) -> str:
    signer = TimestampSigner(salt=SIGNER_SALT)
    return signer.sign(str(attachment_id))


def resolve_signed_download_token(token: str) -> int:
    signer = TimestampSigner(salt=SIGNER_SALT)
    try:
        raw = signer.unsign(token, max_age=download_url_ttl_seconds())
    except SignatureExpired as exc:
        raise ValidationError("Download link has expired.") from exc
    except BadSignature as exc:
        raise ValidationError("Invalid download link.") from exc
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Invalid download link.") from exc


def attachment_download_path(token: str) -> str:
    return f"/api/v1/medical-records/attachments/download/?token={token}"


def get_attachment_or_404(attachment_id: int) -> MedicalRecordAttachment:
    try:
        attachment = MedicalRecordAttachment.objects.select_related(
            "record",
            "record__condition",
            "record__patient",
        ).get(pk=attachment_id)
    except MedicalRecordAttachment.DoesNotExist as exc:
        raise ValidationError("Attachment not found.") from exc
    if attachment.record.deleted_at is not None:
        raise ValidationError("Attachment not found.")
    return attachment
