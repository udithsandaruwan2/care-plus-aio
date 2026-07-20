from django.contrib.gis.geos import Point
from rest_framework import serializers

from apps.vocab.models import ConditionTerm

from .caregiver_profile import caregiver_profile_completion
from .models import CaregiverProfile, Language, PatientProfile
from .patient_profile import patient_profile_completion


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
            "city",
            "certifications",
            "languages",
            "specialties",
            "care_levels",
            "trust_score",
            "bio",
            "is_active",
            "is_available",
            "created_at",
        )
        read_only_fields = fields

    def get_longitude(self, obj):
        return obj.location.x if obj.location else None

    def get_latitude(self, obj):
        return obj.location.y if obj.location else None


class CaregiverMeSerializer(CaregiverProfileSerializer):
    """Own-profile payload with onboarding completion (Step 22c)."""

    nic_id = serializers.CharField()
    years_experience = serializers.IntegerField(allow_null=True)
    service_radius_km = serializers.FloatField()
    certification_docs = serializers.JSONField()
    is_approved = serializers.BooleanField()
    completion_percent = serializers.SerializerMethodField()
    onboarding_complete = serializers.SerializerMethodField()
    is_match_eligible = serializers.SerializerMethodField()
    missing_fields = serializers.SerializerMethodField()

    class Meta(CaregiverProfileSerializer.Meta):
        fields = CaregiverProfileSerializer.Meta.fields + (
            "nic_id",
            "years_experience",
            "service_radius_km",
            "certification_docs",
            "is_approved",
            "completion_percent",
            "onboarding_complete",
            "is_match_eligible",
            "missing_fields",
            "updated_at",
        )
        read_only_fields = fields

    def _completion(self, obj):
        return caregiver_profile_completion(obj)

    def get_completion_percent(self, obj):
        return self._completion(obj).percent

    def get_onboarding_complete(self, obj):
        c = self._completion(obj)
        return c.percent >= c.min_percent

    def get_is_match_eligible(self, obj):
        c = self._completion(obj)
        return obj.is_active and obj.is_approved and c.percent >= c.min_percent

    def get_missing_fields(self, obj):
        return self._completion(obj).missing_fields


class CaregiverProfileUpdateSerializer(serializers.ModelSerializer):
    longitude = serializers.FloatField(required=False, allow_null=True, write_only=True)
    latitude = serializers.FloatField(required=False, allow_null=True, write_only=True)
    certification_docs = serializers.JSONField(required=False)

    class Meta:
        model = CaregiverProfile
        fields = (
            "display_name",
            "nic_id",
            "city",
            "longitude",
            "latitude",
            "languages",
            "specialties",
            "care_levels",
            "certifications",
            "years_experience",
            "service_radius_km",
            "bio",
            "certification_docs",
            "is_available",
        )

    def validate_languages(self, value):
        allowed = {c.value for c in Language}
        unknown = [v for v in value if v not in allowed]
        if unknown:
            raise serializers.ValidationError(
                f"languages must be one of {sorted(allowed)} (got {unknown})"
            )
        return value

    def validate_specialties(self, value):
        slugs = [s.strip().lower() for s in value if (s or "").strip()]
        if not slugs:
            return []
        active = set(
            ConditionTerm.objects.filter(active=True, slug__in=slugs).values_list(
                "slug", flat=True
            )
        )
        unknown = sorted(set(slugs) - active)
        if unknown:
            raise serializers.ValidationError(
                f"Unknown specialty slug(s): {', '.join(unknown)}"
            )
        return slugs

    def validate(self, attrs):
        if "longitude" in self.initial_data or "latitude" in self.initial_data:
            lon = attrs.pop("longitude", None)
            lat = attrs.pop("latitude", None)
            if lon is None or lat is None:
                raise serializers.ValidationError(
                    "longitude and latitude must be provided together."
                )
            attrs["location"] = Point(float(lon), float(lat), srid=4326)
        else:
            attrs.pop("longitude", None)
            attrs.pop("latitude", None)
        return attrs


class CaregiverDetailSerializer(CaregiverProfileSerializer):
    """Public detail payload (Step 20d) — approximate area + reviews teaser."""

    approximate_area = serializers.SerializerMethodField()
    reviews_teaser = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()

    class Meta(CaregiverProfileSerializer.Meta):
        fields = CaregiverProfileSerializer.Meta.fields + (
            "approximate_area",
            "reviews_teaser",
            "review_count",
        )

    def get_approximate_area(self, obj):
        city = (obj.city or "").strip()
        return city or "Sri Lanka"

    def get_reviews_teaser(self, obj):
        # Full Review model lands in M10 — empty teaser keeps the UI contract stable.
        return []

    def get_review_count(self, obj):
        return 0

    def get_longitude(self, obj):
        # Fuzz to ~1 km for public detail (browse map still uses list coords).
        if not obj.location:
            return None
        return round(obj.location.x, 2)

    def get_latitude(self, obj):
        if not obj.location:
            return None
        return round(obj.location.y, 2)


class PatientProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    longitude = serializers.SerializerMethodField()
    latitude = serializers.SerializerMethodField()
    completion_percent = serializers.SerializerMethodField()
    can_request_care = serializers.SerializerMethodField()
    missing_fields = serializers.SerializerMethodField()

    class Meta:
        model = PatientProfile
        fields = (
            "id",
            "email",
            "display_name",
            "longitude",
            "latitude",
            "city",
            "preferred_language",
            "languages",
            "conditions",
            "care_level",
            "height_cm",
            "weight_kg",
            "blood_type",
            "medications",
            "allergies",
            "emergency_contact_name",
            "emergency_contact_phone",
            "completion_percent",
            "can_request_care",
            "missing_fields",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_longitude(self, obj):
        return obj.location.x if obj.location else None

    def get_latitude(self, obj):
        return obj.location.y if obj.location else None

    def _completion(self, obj):
        return patient_profile_completion(obj)

    def get_completion_percent(self, obj):
        return self._completion(obj).percent

    def get_can_request_care(self, obj):
        return self._completion(obj).can_request_care

    def get_missing_fields(self, obj):
        return self._completion(obj).missing_fields


class PatientProfileUpdateSerializer(serializers.ModelSerializer):
    longitude = serializers.FloatField(required=False, allow_null=True, write_only=True)
    latitude = serializers.FloatField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = PatientProfile
        fields = (
            "display_name",
            "city",
            "longitude",
            "latitude",
            "preferred_language",
            "languages",
            "conditions",
            "care_level",
            "height_cm",
            "weight_kg",
            "blood_type",
            "medications",
            "allergies",
            "emergency_contact_name",
            "emergency_contact_phone",
        )

    def validate_conditions(self, value):
        slugs = [s.strip().lower() for s in value if (s or "").strip()]
        if not slugs:
            return []
        active = set(
            ConditionTerm.objects.filter(active=True, slug__in=slugs).values_list(
                "slug", flat=True
            )
        )
        unknown = sorted(set(slugs) - active)
        if unknown:
            raise serializers.ValidationError(
                f"Unknown condition slug(s): {', '.join(unknown)}"
            )
        return slugs

    def validate_languages(self, value):
        allowed = {c.value for c in Language}
        cleaned = [v for v in value if v in allowed]
        unknown = [v for v in value if v not in allowed]
        if unknown:
            raise serializers.ValidationError(
                f"languages must be one of {sorted(allowed)} (got {unknown})"
            )
        return cleaned

    def validate(self, attrs):
        if "longitude" in self.initial_data or "latitude" in self.initial_data:
            lon = attrs.pop("longitude", None)
            lat = attrs.pop("latitude", None)
            if lon is None or lat is None:
                raise serializers.ValidationError(
                    "longitude and latitude must be provided together."
                )
            attrs["location"] = Point(float(lon), float(lat), srid=4326)
        else:
            attrs.pop("longitude", None)
            attrs.pop("latitude", None)
        return attrs


class CaregiverAvailabilitySerializer(serializers.ModelSerializer):
    """PATCH body for caregiver soft presence (Step 20e)."""

    class Meta:
        model = CaregiverProfile
        fields = ("is_available",)


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


class CareRequestSerializer(serializers.ModelSerializer):
    patient_email = serializers.EmailField(source="patient.email", read_only=True)
    caregiver_id = serializers.IntegerField(source="caregiver.id", read_only=True)
    caregiver_name = serializers.CharField(source="caregiver.display_name", read_only=True)
    relationship_id = serializers.SerializerMethodField()

    class Meta:
        from .models import CareRequest

        model = CareRequest
        fields = (
            "id",
            "patient_email",
            "caregiver_id",
            "caregiver_name",
            "status",
            "message",
            "match_run",
            "match_snapshot",
            "expires_at",
            "responded_at",
            "relationship_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_relationship_id(self, obj) -> int | None:
        rel = getattr(obj, "relationship", None)
        if rel is not None:
            return rel.pk
        return None


class CareRequestCreateSerializer(serializers.Serializer):
    caregiver_id = serializers.IntegerField()
    message = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    match_run_id = serializers.IntegerField(required=False, allow_null=True)
    match_snapshot = serializers.JSONField(required=False)

    def validate_caregiver_id(self, value):
        try:
            caregiver = CaregiverProfile.objects.get(pk=value)
        except CaregiverProfile.DoesNotExist as exc:
            raise serializers.ValidationError("Caregiver not found.") from exc
        self.context["caregiver"] = caregiver
        return value

    def validate_match_run_id(self, value):
        if value is None:
            return value
        from .models import MatchRun

        try:
            run = MatchRun.objects.get(pk=value)
        except MatchRun.DoesNotExist as exc:
            raise serializers.ValidationError("Match run not found.") from exc
        self.context["match_run"] = run
        return value


class CareRequestActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["cancel", "accept", "reject"])
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


class CareRequestCancelSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["cancel"])
