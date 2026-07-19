from rest_framework import serializers

from .models import VoiceIntent


class VoiceIntentInputSerializer(serializers.Serializer):
    text = serializers.CharField(min_length=1, max_length=2000, trim_whitespace=True)
    language = serializers.ChoiceField(
        choices=["Sinhala", "Tamil", "English"], required=False, allow_null=True
    )


class VoiceIntentSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoiceIntent
        fields = (
            "id",
            "raw_text",
            "condition",
            "language",
            "languages",
            "care_level",
            "urgency",
            "source",
            "ts",
        )
        read_only_fields = fields
