from rest_framework import serializers

from .models import ConditionTerm


class ConditionTermSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConditionTerm
        fields = ("slug", "canonical_en", "synonyms", "active", "version", "notes")
