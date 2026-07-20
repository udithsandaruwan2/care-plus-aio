from rest_framework import serializers

from .models import Lead


class LeadCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    email = serializers.EmailField()
    phone = serializers.CharField(required=False, allow_blank=True, max_length=32)
    message = serializers.CharField(required=False, allow_blank=True, max_length=4000)
    city = serializers.CharField(required=False, allow_blank=True, max_length=64)
    preferred_language = serializers.CharField(
        required=False, allow_blank=True, max_length=16
    )
    source = serializers.CharField(required=False, allow_blank=True, max_length=64)

    def validate_name(self, value: str) -> str:
        cleaned = (value or "").strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError("Please enter your name.")
        return cleaned


class LeadSerializer(serializers.ModelSerializer):
    contacted_by_email = serializers.EmailField(
        source="contacted_by.email", read_only=True, allow_null=True
    )

    class Meta:
        model = Lead
        fields = (
            "id",
            "name",
            "email",
            "phone",
            "message",
            "city",
            "preferred_language",
            "source",
            "status",
            "contacted_at",
            "contacted_by_email",
            "admin_notes",
            "ack_email_sent",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class LeadContactSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["contact"])
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)
