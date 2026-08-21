from django.contrib.gis.geos import Point
from django.db.models import Avg
from django.utils import timezone
from rest_framework import serializers

from apps.vocab.models import ConditionTerm

from .caregiver_profile import caregiver_profile_completion
from .models import (
    AvailabilityWeekday,
    CaregiverAvailabilitySlot,
    CaregiverProfile,
    Language,
    PatientProfile,
    Review,
    ReviewStatus,
    Shift,
)
from .patient_profile import patient_profile_completion
from .profile_media import cert_download_path, photo_download_path


def _photo_url(obj) -> str | None:
    if not getattr(obj, "photo", None):
        return None
    kind = "caregiver" if isinstance(obj, CaregiverProfile) else "patient"
    return photo_download_path(kind=kind, profile_id=obj.pk)


def _certification_docs_payload(obj: CaregiverProfile) -> list[dict]:
    out: list[dict] = []
    for doc in obj.certification_docs or []:
        if not isinstance(doc, dict):
            continue
        item = {k: v for k, v in doc.items() if k != "storage_path"}
        doc_id = item.get("id")
        if doc_id:
            item["download_url"] = cert_download_path(
                caregiver_id=obj.pk, doc_id=str(doc_id)
            )
        out.append(item)
    return out


class CaregiverProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    # GeoJSON-ish lon/lat for clients (PostGIS Point → [lon, lat]).
    longitude = serializers.SerializerMethodField()
    latitude = serializers.SerializerMethodField()
    photo_url = serializers.SerializerMethodField()
    age = serializers.SerializerMethodField()
    is_verified = serializers.BooleanField(source="is_approved", read_only=True)
    review_count = serializers.SerializerMethodField()
    review_average = serializers.SerializerMethodField()

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
            "age",
            "years_experience",
            "is_verified",
            "review_count",
            "review_average",
            "is_active",
            "is_available",
            "photo_url",
            "created_at",
        )
        read_only_fields = fields

    def get_longitude(self, obj):
        return obj.location.x if obj.location else None

    def get_latitude(self, obj):
        return obj.location.y if obj.location else None

    def get_photo_url(self, obj):
        return _photo_url(obj)

    def get_age(self, obj):
        return obj.age

    def get_review_count(self, obj):
        # ``CaregiverListView`` annotates these so browse stays one query.
        annotated = getattr(obj, "approved_review_count", None)
        if annotated is not None:
            return int(annotated)
        return Review.objects.filter(caregiver=obj, status=ReviewStatus.APPROVED).count()

    def get_review_average(self, obj):
        if hasattr(obj, "approved_review_average"):
            value = obj.approved_review_average
        else:
            value = Review.objects.filter(
                caregiver=obj, status=ReviewStatus.APPROVED
            ).aggregate(avg=Avg("rating"))["avg"]
        if value is None:
            return None
        return round(float(value), 2)


class CaregiverMeSerializer(CaregiverProfileSerializer):
    """Own-profile payload with onboarding completion (Step 22c)."""

    nic_id = serializers.CharField()
    service_radius_km = serializers.FloatField()
    certification_docs = serializers.SerializerMethodField()
    is_approved = serializers.BooleanField()
    completion_percent = serializers.SerializerMethodField()
    onboarding_complete = serializers.SerializerMethodField()
    is_match_eligible = serializers.SerializerMethodField()
    missing_fields = serializers.SerializerMethodField()

    class Meta(CaregiverProfileSerializer.Meta):
        fields = CaregiverProfileSerializer.Meta.fields + (
            "nic_id",
            "date_of_birth",
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

    def get_certification_docs(self, obj):
        return _certification_docs_payload(obj)


class CaregiverProfileUpdateSerializer(serializers.ModelSerializer):
    longitude = serializers.FloatField(required=False, allow_null=True, write_only=True)
    latitude = serializers.FloatField(required=False, allow_null=True, write_only=True)
    certification_docs = serializers.JSONField(required=False)

    class Meta:
        model = CaregiverProfile
        fields = (
            "display_name",
            "nic_id",
            "date_of_birth",
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

    def validate_date_of_birth(self, value):
        if value is None:
            return value
        today = timezone.localdate()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if not 18 <= age <= 99:
            raise serializers.ValidationError("Caregivers must be between 18 and 99 years old.")
        return value

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

    class Meta(CaregiverProfileSerializer.Meta):
        fields = CaregiverProfileSerializer.Meta.fields + (
            "approximate_area",
            "reviews_teaser",
        )

    def get_approximate_area(self, obj):
        city = (obj.city or "").strip()
        return city or "Sri Lanka"

    def get_reviews_teaser(self, obj):
        rows = (
            Review.objects.filter(caregiver=obj, status=ReviewStatus.APPROVED)
            .order_by("-created_at")[:3]
        )
        return [
            {
                "rating": r.rating,
                "comment": r.comment,
                "created_at": r.created_at,
            }
            for r in rows
        ]

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
    photo_url = serializers.SerializerMethodField()
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
            "photo_url",
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

    def get_photo_url(self, obj):
        return _photo_url(obj)

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


class CaregiverAvailabilitySlotSerializer(serializers.ModelSerializer):
    weekday_label = serializers.CharField(source="get_weekday_display", read_only=True)

    class Meta:
        model = CaregiverAvailabilitySlot
        fields = (
            "id",
            "caregiver",
            "weekday",
            "weekday_label",
            "start_time",
            "end_time",
            "timezone",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "caregiver", "created_at", "updated_at", "weekday_label")


class CaregiverAvailabilitySlotCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CaregiverAvailabilitySlot
        fields = ("weekday", "start_time", "end_time", "timezone", "is_active")

    def validate_weekday(self, value):
        allowed = {c.value for c in AvailabilityWeekday}
        if value not in allowed:
            raise serializers.ValidationError("weekday must be between 0 (Mon) and 6 (Sun).")
        return value

    def validate(self, attrs):
        start = attrs.get("start_time")
        end = attrs.get("end_time")
        if start is not None and end is not None and start >= end:
            raise serializers.ValidationError("end_time must be after start_time.")
        return attrs


class CareRequestSerializer(serializers.ModelSerializer):
    patient_email = serializers.EmailField(source="patient.email", read_only=True)
    caregiver_id = serializers.IntegerField(source="caregiver.id", read_only=True)
    caregiver_name = serializers.CharField(source="caregiver.display_name", read_only=True)
    relationship_id = serializers.SerializerMethodField()
    relationship_status = serializers.SerializerMethodField()

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
            "relationship_status",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_relationship_id(self, obj) -> int | None:
        rel = getattr(obj, "relationship", None)
        if rel is not None:
            return rel.pk
        return None

    def get_relationship_status(self, obj) -> str | None:
        rel = getattr(obj, "relationship", None)
        if rel is not None:
            return rel.status
        return None


class CareRequestCreateSerializer(serializers.Serializer):
    caregiver_id = serializers.IntegerField()
    message = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    match_run_id = serializers.IntegerField(required=False, allow_null=True)
    match_snapshot = serializers.JSONField(required=False)
    idempotency_key = serializers.CharField(
        required=False, allow_blank=True, max_length=128, trim_whitespace=True
    )

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


class CareRelationshipSerializer(serializers.ModelSerializer):
    patient_email = serializers.EmailField(source="patient.email", read_only=True)
    patient_display_name = serializers.SerializerMethodField()
    caregiver_id = serializers.IntegerField(source="caregiver.id", read_only=True)
    caregiver_name = serializers.CharField(source="caregiver.display_name", read_only=True)

    class Meta:
        from .models import CareRelationship

        model = CareRelationship
        fields = (
            "id",
            "patient_email",
            "patient_display_name",
            "caregiver_id",
            "caregiver_name",
            "care_request",
            "status",
            "is_primary",
            "started_at",
            "ended_at",
            "end_reason",
        )
        read_only_fields = fields

    def get_patient_display_name(self, obj) -> str:
        profile = getattr(obj.patient, "patient_profile", None)
        if profile and profile.display_name:
            return profile.display_name
        return obj.patient.email


class CareRelationshipActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["activate", "end"])
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


class ReviewSerializer(serializers.ModelSerializer):
    patient_email = serializers.EmailField(source="patient.email", read_only=True)

    class Meta:
        model = Review
        fields = (
            "id",
            "relationship",
            "patient_email",
            "caregiver_id",
            "rating",
            "comment",
            "status",
            "moderation_reason",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "patient_email",
            "caregiver_id",
            "status",
            "moderation_reason",
            "created_at",
            "updated_at",
        )


class ReviewCreateSerializer(serializers.Serializer):
    relationship_id = serializers.IntegerField(min_value=1)
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class ReviewModerationSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[ReviewStatus.APPROVED, ReviewStatus.REJECTED])
    moderation_reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


class ShiftSerializer(serializers.ModelSerializer):
    caregiver_name = serializers.CharField(source="caregiver.display_name", read_only=True)
    patient_email = serializers.EmailField(source="patient.email", read_only=True)

    class Meta:
        model = Shift
        fields = (
            "id",
            "caregiver",
            "caregiver_name",
            "patient",
            "patient_email",
            "availability_slot",
            "starts_at",
            "ends_at",
            "timezone",
            "status",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ShiftCreateSerializer(serializers.Serializer):
    caregiver_id = serializers.IntegerField(min_value=1)
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    availability_slot_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    timezone = serializers.CharField(required=False, allow_blank=True, max_length=64)

    def validate(self, attrs):
        if attrs["ends_at"] <= attrs["starts_at"]:
            raise serializers.ValidationError("ends_at must be after starts_at.")
        return attrs
