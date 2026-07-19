from rest_framework import serializers

from .models import CaregiverProfile, PatientProfile


class CaregiverProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    # GeoJSON-ish lon/lat for clients (PostGIS Point → [lon, lat]).
    longitude = serializers.SerializerMethodField()
    latitude = serializers.SerializerMethodField()

    class Meta:
        model = CaregiverProfile
        fields = (
            "id",
            "email",
            "display_name",
            "longitude",
            "latitude",
            "certifications",
            "languages",
            "specialties",
            "care_levels",
            "trust_score",
            "bio",
            "is_active",
            "created_at",
        )
        read_only_fields = fields

    def get_longitude(self, obj):
        return obj.location.x if obj.location else None

    def get_latitude(self, obj):
        return obj.location.y if obj.location else None


class PatientProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    longitude = serializers.SerializerMethodField()
    latitude = serializers.SerializerMethodField()

    class Meta:
        model = PatientProfile
        fields = (
            "id",
            "email",
            "display_name",
            "longitude",
            "latitude",
            "preferred_language",
            "conditions",
            "care_level",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_longitude(self, obj):
        return obj.location.x if obj.location else None

    def get_latitude(self, obj):
        return obj.location.y if obj.location else None


class MatchRequestSerializer(serializers.Serializer):
    condition = serializers.CharField(required=False, allow_blank=True, max_length=120)
    language = serializers.CharField(required=False, allow_blank=True, max_length=16)
    care_level = serializers.CharField(required=False, allow_blank=True, max_length=16)
    query = serializers.CharField(required=False, allow_blank=True, max_length=500)
    longitude = serializers.FloatField(required=False, allow_null=True)
    latitude = serializers.FloatField(required=False, allow_null=True)
    k = serializers.IntegerField(required=False, min_value=1, max_value=25, default=10)
    emergency = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        texts = [
            (attrs.get("condition") or "").strip(),
            (attrs.get("language") or "").strip(),
            (attrs.get("care_level") or "").strip(),
            (attrs.get("query") or "").strip(),
        ]
        if not any(texts):
            raise serializers.ValidationError(
                "Provide at least one of condition, language, care_level, or query."
            )
        lon, lat = attrs.get("longitude"), attrs.get("latitude")
        if (lon is None) ^ (lat is None):
            raise serializers.ValidationError("longitude and latitude must be provided together.")
        return attrs
