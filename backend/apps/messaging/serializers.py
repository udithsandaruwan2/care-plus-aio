from rest_framework import serializers

from apps.accounts.models import Role

from .models import Message, MessageThread


class MessageSerializer(serializers.ModelSerializer):
    sender_role = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = (
            "id",
            "thread_id",
            "sender_id",
            "sender_role",
            "body",
            "created_at",
            "read_at",
            "is_mine",
        )
        read_only_fields = fields

    def get_sender_role(self, obj) -> str:
        return getattr(obj.sender, "role", "") or ""

    def get_is_mine(self, obj) -> bool:
        request = self.context.get("request")
        if request is None or not getattr(request.user, "is_authenticated", False):
            return False
        return obj.sender_id == request.user.pk


class MessageCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=4000, trim_whitespace=True)


class MessageReadSerializer(serializers.Serializer):
    last_read_message_id = serializers.IntegerField(min_value=1)


class MessageThreadSerializer(serializers.ModelSerializer):
    relationship_id = serializers.IntegerField(read_only=True)
    patient_id = serializers.IntegerField(source="relationship.patient_id", read_only=True)
    caregiver_id = serializers.IntegerField(
        source="relationship.caregiver_id", read_only=True
    )
    partner_label = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = MessageThread
        fields = (
            "id",
            "relationship_id",
            "patient_id",
            "caregiver_id",
            "partner_label",
            "unread_count",
            "created_at",
        )
        read_only_fields = fields

    def get_partner_label(self, obj) -> str:
        request = self.context.get("request")
        if request is None:
            return ""
        rel = obj.relationship
        if getattr(request.user, "role", None) == Role.PATIENT:
            return rel.caregiver.display_name
        return (
            getattr(rel.patient, "patient_profile", None)
            and rel.patient.patient_profile.display_name
        ) or rel.patient.email

    def get_unread_count(self, obj) -> int:
        request = self.context.get("request")
        if request is None or not getattr(request.user, "is_authenticated", False):
            return 0
        return obj.messages.filter(read_at__isnull=True).exclude(sender=request.user).count()
