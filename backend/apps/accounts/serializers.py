from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import AuditLog, ConsentLog, Role
from .tokens import otp_enabled

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    otp_enabled = serializers.SerializerMethodField()
    otp_verified = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "role",
            "first_name",
            "last_name",
            "otp_enabled",
            "otp_verified",
        )
        read_only_fields = ("id", "otp_enabled", "otp_verified")

    def get_otp_enabled(self, obj):
        return otp_enabled()

    def get_otp_verified(self, obj):
        if not otp_enabled():
            return True
        request = self.context.get("request")
        token = getattr(request, "auth", None) if request else None
        if token is not None and hasattr(token, "get"):
            return bool(token.get("otp_verified"))
        return False


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    # Admins/auditors are provisioned internally, not via public self-registration.
    role = serializers.ChoiceField(choices=[Role.PATIENT, Role.CAREGIVER], default=Role.PATIENT)

    class Meta:
        model = User
        fields = ("id", "email", "password", "role", "first_name", "last_name")
        read_only_fields = ("id",)

    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)


class ConsentLogSerializer(serializers.ModelSerializer):
    """Write a new consent grant/revoke; read back the recorded row."""

    class Meta:
        model = ConsentLog
        fields = ("id", "scope", "granted", "ts")
        read_only_fields = ("id", "ts")

    def create(self, validated_data):
        # The user is never client-supplied; it comes from the authenticated request.
        request = self.context["request"]
        validated_data["user"] = request.user
        row = super().create(validated_data)
        from .audit import record_audit
        from .models import AuditAction

        record_audit(
            actor=request.user,
            action=AuditAction.GRANT_CONSENT if row.granted else AuditAction.REVOKE_CONSENT,
            request=request,
            target_type="consent",
            target_id=row.pk,
            metadata={"scope": row.scope, "granted": row.granted},
            async_=False,
        )
        return row


class NotificationPreferenceUpdateSerializer(serializers.Serializer):
    email = serializers.DictField(child=serializers.BooleanField(), required=False)
    push = serializers.DictField(child=serializers.BooleanField(), required=False)


class PushSubscriptionSerializer(serializers.Serializer):
    endpoint = serializers.URLField(max_length=2048)
    keys = serializers.DictField(child=serializers.CharField(max_length=255))
    user_agent = serializers.CharField(max_length=512, required=False, allow_blank=True, default="")

    def validate_keys(self, value):
        p256dh = (value.get("p256dh") or "").strip()
        auth = (value.get("auth") or "").strip()
        if not p256dh or not auth:
            raise serializers.ValidationError("keys.p256dh and keys.auth are required.")
        return {"p256dh": p256dh, "auth": auth}


class MobilePushDeviceSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=512)
    platform = serializers.ChoiceField(choices=["fcm", "apns"], required=False, default="fcm")
    device_id = serializers.CharField(max_length=128, required=False, allow_blank=True, default="")
    app_version = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")


class AuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source="actor.email", read_only=True, allow_null=True)

    class Meta:
        model = AuditLog
        fields = (
            "id",
            "actor",
            "actor_email",
            "action",
            "ts",
            "ip",
            "request_id",
            "target_type",
            "target_id",
            "metadata",
        )
        read_only_fields = fields


class AdminUserSerializer(serializers.ModelSerializer):
    """Admin console user row (Step 54)."""

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "role",
            "first_name",
            "last_name",
            "is_active",
            "date_joined",
            "last_login",
        )
        read_only_fields = fields


class AdminUserUpdateSerializer(serializers.Serializer):
    is_active = serializers.BooleanField(required=True)
