"""Profile photo + certification document uploads (Step 22d).

Files live on local MEDIA_ROOT (or a volume). Downloads use short-lived signed
tokens — not a public open bucket. Virus scanning is a stub until ClamAV.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from rest_framework.exceptions import ValidationError

logger = logging.getLogger(__name__)

PHOTO_SALT = "careplus-profile-photo"
DOC_SALT = "careplus-cert-doc"

PHOTO_MIMES = frozenset({"image/jpeg", "image/png", "image/webp"})
DOC_MIMES = frozenset(
    {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
    }
)


def photo_max_bytes() -> int:
    return int(getattr(settings, "PROFILE_PHOTO_MAX_BYTES", 2 * 1024 * 1024))


def doc_max_bytes() -> int:
    return int(getattr(settings, "PROFILE_DOC_MAX_BYTES", 8 * 1024 * 1024))


def photo_url_ttl_seconds() -> int:
    return int(getattr(settings, "PROFILE_MEDIA_URL_TTL_SECONDS", 3600))


def normalize_content_type(content_type: str) -> str:
    ct = (content_type or "application/octet-stream").split(";")[0].strip().lower()
    if ct == "image/jpg":
        return "image/jpeg"
    return ct


def stub_virus_scan(uploaded_file) -> dict:
    """Always clean. Replace with ClamAV/ICAP in production if required."""
    name = getattr(uploaded_file, "name", "") or ""
    logger.info("profile media virus-scan stub clean name=%s", name)
    return {"status": "clean", "engine": "stub"}


def _validate_file(uploaded_file, *, allowed: frozenset[str], max_bytes: int) -> str:
    if uploaded_file is None:
        raise ValidationError("No file uploaded.")
    size = getattr(uploaded_file, "size", None)
    if size is None:
        data = uploaded_file.read()
        size = len(data)
        uploaded_file.seek(0)
    if size <= 0:
        raise ValidationError("Uploaded file is empty.")
    if size > max_bytes:
        raise ValidationError(f"File exceeds maximum size of {max_bytes} bytes.")
    content_type = normalize_content_type(getattr(uploaded_file, "content_type", ""))
    if content_type not in allowed:
        raise ValidationError(f"File type '{content_type}' is not allowed.")
    scan = stub_virus_scan(uploaded_file)
    if scan.get("status") != "clean":
        raise ValidationError("File failed virus scan.")
    return content_type


def validate_photo(uploaded_file) -> str:
    return _validate_file(uploaded_file, allowed=PHOTO_MIMES, max_bytes=photo_max_bytes())


def validate_document(uploaded_file) -> str:
    return _validate_file(uploaded_file, allowed=DOC_MIMES, max_bytes=doc_max_bytes())


def build_photo_token(*, kind: str, profile_id: int) -> str:
    signer = TimestampSigner(salt=PHOTO_SALT)
    return signer.sign(f"{kind}:{profile_id}")


def resolve_photo_token(token: str) -> tuple[str, int]:
    signer = TimestampSigner(salt=PHOTO_SALT)
    try:
        raw = signer.unsign(token, max_age=photo_url_ttl_seconds())
    except SignatureExpired as exc:
        raise ValidationError("Photo link has expired.") from exc
    except BadSignature as exc:
        raise ValidationError("Invalid photo link.") from exc
    kind, _, pk = str(raw).partition(":")
    if kind not in {"patient", "caregiver"}:
        raise ValidationError("Invalid photo link.")
    try:
        return kind, int(pk)
    except ValueError as exc:
        raise ValidationError("Invalid photo link.") from exc


def photo_download_path(*, kind: str, profile_id: int) -> str:
    token = build_photo_token(kind=kind, profile_id=profile_id)
    return f"/api/v1/profile-media/photos/?token={token}"


def build_cert_token(*, caregiver_id: int, doc_id: str) -> str:
    signer = TimestampSigner(salt=DOC_SALT)
    return signer.sign(f"{caregiver_id}:{doc_id}")


def resolve_cert_token(token: str) -> tuple[int, str]:
    signer = TimestampSigner(salt=DOC_SALT)
    try:
        raw = signer.unsign(token, max_age=photo_url_ttl_seconds())
    except SignatureExpired as exc:
        raise ValidationError("Document link has expired.") from exc
    except BadSignature as exc:
        raise ValidationError("Invalid document link.") from exc
    caregiver_raw, _, doc_id = str(raw).partition(":")
    if not doc_id:
        raise ValidationError("Invalid document link.")
    try:
        return int(caregiver_raw), doc_id
    except ValueError as exc:
        raise ValidationError("Invalid document link.") from exc


def cert_download_path(*, caregiver_id: int, doc_id: str) -> str:
    token = build_cert_token(caregiver_id=caregiver_id, doc_id=doc_id)
    return f"/api/v1/profile-media/documents/?token={token}"
