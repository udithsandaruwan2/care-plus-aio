from rest_framework import serializers

from .models import ConditionTerm


class ConditionTermSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConditionTerm
        fields = ("slug", "canonical_en", "synonyms", "active", "version", "notes")


class AdminConditionTermSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConditionTerm
        fields = (
            "id",
            "slug",
            "canonical_en",
            "synonyms",
            "active",
            "version",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class AdminConditionTermWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConditionTerm
        fields = ("slug", "canonical_en", "synonyms", "active", "version", "notes")

    def validate_synonyms(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("synonyms must be an object of language → string[].")
        cleaned = {}
        for lang, phrases in value.items():
            if not isinstance(phrases, list):
                raise serializers.ValidationError(f"synonyms.{lang} must be a list of strings.")
            cleaned[str(lang)] = [str(p).strip() for p in phrases if str(p).strip()]
        return cleaned
