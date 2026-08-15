"""Issue and verify email OTPs (Step 22f). Dummy mode skips outbound email."""

import hashlib
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import EmailOtp
from .tokens import otp_enabled

logger = logging.getLogger(__name__)


def otp_ttl_seconds() -> int:
    return int(getattr(settings, "OTP_TTL_SECONDS", 600))


def otp_max_attempts() -> int:
    return int(getattr(settings, "OTP_MAX_ATTEMPTS", 5))


def otp_dummy() -> bool:
    return bool(getattr(settings, "OTP_DUMMY", True))


def otp_dummy_code() -> str:
    raw = str(getattr(settings, "OTP_DUMMY_CODE", "123456") or "123456").strip()
    if raw.isdigit() and len(raw) == 6:
        return raw
    return "123456"


def _hash_code(*, user_id: int, code: str) -> str:
    raw = f"{settings.SECRET_KEY}:otp:{user_id}:{code}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def request_otp(user) -> dict:
    if not otp_enabled():
        raise ValidationError("Email OTP is not enabled.")
    EmailOtp.objects.filter(user=user, consumed_at__isnull=True).update(consumed_at=timezone.now())
    dummy = otp_dummy()
    code = otp_dummy_code() if dummy else f"{secrets.randbelow(1_000_000):06d}"
    ttl = otp_ttl_seconds()
    EmailOtp.objects.create(
        user=user,
        code_hash=_hash_code(user_id=user.pk, code=code),
        expires_at=timezone.now() + timedelta(seconds=ttl),
    )
    if dummy:
        logger.info("email OTP dummy issued user_id=%s ttl=%s", user.pk, ttl)
        return {
            "detail": "Demo verification code (no email sent).",
            "expires_in": ttl,
            "demo": True,
            "demo_code": code,
        }

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@careplus.local")
    send_mail(
        "Your Care Plus verification code",
        f"Your Care Plus verification code is {code}.\nIt expires in {ttl // 60} minutes.",
        from_email,
        [user.email],
        fail_silently=False,
    )
    logger.info("email OTP issued user_id=%s ttl=%s", user.pk, ttl)
    return {"detail": "OTP sent.", "expires_in": ttl, "demo": False}


def verify_otp(user, code: str) -> None:
    if not otp_enabled():
        raise ValidationError("Email OTP is not enabled.")
    cleaned = (code or "").strip()
    if not cleaned.isdigit() or len(cleaned) != 6:
        raise ValidationError("Enter the 6-digit code from your email.")
    row = (
        EmailOtp.objects.filter(user=user, consumed_at__isnull=True).order_by("-created_at").first()
    )
    if row is None:
        raise ValidationError("No active verification code. Request a new one.")
    if row.expires_at <= timezone.now():
        row.consumed_at = timezone.now()
        row.save(update_fields=["consumed_at"])
        raise ValidationError("That code has expired. Request a new one.")
    if row.attempts >= otp_max_attempts():
        row.consumed_at = timezone.now()
        row.save(update_fields=["consumed_at"])
        raise ValidationError("Too many attempts. Request a new code.")
    expected = _hash_code(user_id=user.pk, code=cleaned)
    if not secrets.compare_digest(row.code_hash, expected):
        row.attempts += 1
        update = ["attempts"]
        if row.attempts >= otp_max_attempts():
            row.consumed_at = timezone.now()
            update.append("consumed_at")
        row.save(update_fields=update)
        raise ValidationError("Invalid verification code.")
    row.consumed_at = timezone.now()
    row.save(update_fields=["consumed_at"])
