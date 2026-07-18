from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import ConsentLog, Role

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "role", "first_name", "last_name")
        read_only_fields = ("id",)


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
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)
