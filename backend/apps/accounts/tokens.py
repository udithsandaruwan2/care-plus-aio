"""JWT helpers — optional ``otp_verified`` claim (Step 22f)."""

from django.conf import settings
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken


def otp_enabled() -> bool:
    return bool(getattr(settings, "OTP_ENABLED", False))


def issue_token_pair(user, *, otp_verified: bool | None = None) -> dict[str, str]:
    if otp_verified is None:
        otp_verified = not otp_enabled()
    refresh = RefreshToken.for_user(user)
    refresh["otp_verified"] = bool(otp_verified)
    refresh["role"] = getattr(user, "role", "")
    access = refresh.access_token
    access["otp_verified"] = bool(otp_verified)
    access["role"] = getattr(user, "role", "")
    return {"access": str(access), "refresh": str(refresh)}


class CarePlusTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Password login never elevates OTP when the feature flag is on."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["otp_verified"] = not otp_enabled()
        token["role"] = getattr(user, "role", "")
        return token
