from rest_framework import serializers

from .models import MedicalRecord, MedicalRecordAttachment


class MedicalRecordAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalRecordAttachment
        fields = (
            "id",
            "record_id",
            "original_name",
            "content_type",
            "size_bytes",
            "uploaded_at",
        )
        read_only_fields = fields


class MedicalRecordListSerializer(serializers.ModelSerializer):
    condition_slug = serializers.CharField(source="condition.slug", read_only=True)
    condition_name = serializers.CharField(source="condition.canonical_en", read_only=True)
    attachment_count = serializers.SerializerMethodField()

    class Meta:
        model = MedicalRecord
        fields = (
            "id",
            "patient_id",
            "condition_slug",
            "condition_name",
            "title",
            "description",
            "recorded_at",
            "attachment_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_attachment_count(self, obj) -> int:
        if hasattr(obj, "_prefetched_objects_cache") and "attachments" in obj._prefetched_objects_cache:
            return len(obj.attachments.all())
        return obj.attachments.count()


class MedicalRecordDetailSerializer(MedicalRecordListSerializer):
    sensitive_notes = serializers.CharField(read_only=True)
    attachments = MedicalRecordAttachmentSerializer(many=True, read_only=True)

    class Meta(MedicalRecordListSerializer.Meta):
        fields = MedicalRecordListSerializer.Meta.fields + (
            "sensitive_notes",
            "attachments",
        )


class MedicalRecordCreateSerializer(serializers.Serializer):
    condition_slug = serializers.SlugField(max_length=64)
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    sensitive_notes = serializers.CharField(required=False, allow_blank=True, default="")
    recorded_at = serializers.DateField(required=False, allow_null=True)


class SignedDownloadUrlSerializer(serializers.Serializer):
    attachment_id = serializers.IntegerField()
    url = serializers.CharField()
    expires_in = serializers.IntegerField()
