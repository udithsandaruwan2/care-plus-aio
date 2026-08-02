from rest_framework import serializers

from .models import HealthMetric, HealthMetricKind


class HealthMetricIngestSerializer(serializers.Serializer):
    patient_id = serializers.IntegerField(required=False, min_value=1)
    kind = serializers.ChoiceField(choices=HealthMetricKind.choices)
    value = serializers.FloatField()
    unit = serializers.CharField(required=False, allow_blank=True, max_length=24)
    source = serializers.CharField(required=False, allow_blank=True, max_length=64)
    recorded_at = serializers.DateTimeField(required=False)
    metadata = serializers.JSONField(required=False)


class HealthMetricSerializer(serializers.ModelSerializer):
    metadata = serializers.JSONField(read_only=True)

    class Meta:
        model = HealthMetric
        fields = (
            "id",
            "patient",
            "kind",
            "value",
            "unit",
            "source",
            "recorded_at",
            "metadata",
            "created_at",
        )
        read_only_fields = fields
