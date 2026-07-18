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
