"""Domain profiles that feed the VEHMF matcher (M4).

``CaregiverProfile`` holds PostGIS location, skills, trust, and (later) the
embedding vector loaded into FAISS. ``PatientProfile`` is the matching-side
counterpart for geo + preference scoring.
"""

from django.conf import settings
from django.contrib.gis.db import models as gis_models
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

# multilingual-e5-base output dim — filled in Step 17; kept empty until then.
EMBEDDING_DIM = 768


class CareLevel(models.TextChoices):
    BASIC = "basic", "Basic"
    INTERMEDIATE = "intermediate", "Intermediate"
    ADVANCED = "advanced", "Advanced"


class BloodType(models.TextChoices):
    A_POS = "A+", "A+"
    A_NEG = "A-", "A-"
    B_POS = "B+", "B+"
    B_NEG = "B-", "B-"
    AB_POS = "AB+", "AB+"
    AB_NEG = "AB-", "AB-"
    O_POS = "O+", "O+"
    O_NEG = "O-", "O-"
    UNKNOWN = "unknown", "Unknown"


class Language(models.TextChoices):
    SINHALA = "Sinhala", "Sinhala"
    TAMIL = "Tamil", "Tamil"
    ENGLISH = "English", "English"


class CaregiverProfile(models.Model):
    """A caregiver's matchable profile (skills + geo + trust + embedding slot)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="caregiver_profile",
    )
    display_name = models.CharField(max_length=120)
    # SRID 4326 lon/lat; geography=True so Step 19 can use metre-based distance.
    location = gis_models.PointField(geography=True, srid=4326)
    certifications = ArrayField(models.CharField(max_length=64), default=list, blank=True)
    languages = ArrayField(models.CharField(max_length=16), default=list, blank=True)
    # Conditions / specialties this caregiver can support (e.g. "diabetes").
    specialties = ArrayField(models.CharField(max_length=64), default=list, blank=True)
    care_levels = ArrayField(models.CharField(max_length=16), default=list, blank=True)
    trust_score = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    # L2-normalized embedding (len == EMBEDDING_DIM once Step 17 fills it).
    embedding = ArrayField(models.FloatField(), default=list, blank=True)
    bio = models.TextField(blank=True, default="")
    city = models.CharField(max_length=64, blank=True, default="", db_index=True)
    # Step 22c — onboarding + approval before appearing in match/browse.
    nic_id = models.CharField(max_length=20, blank=True, default="")
    years_experience = models.PositiveSmallIntegerField(null=True, blank=True)
    service_radius_km = models.FloatField(
        default=25.0,
        validators=[MinValueValidator(1.0), MaxValueValidator(200.0)],
    )
    # Placeholder metadata until Step 22d file uploads land.
    certification_docs = models.JSONField(default=list, blank=True)
    is_approved = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=False)
    # Soft presence — browse/match can filter on this (Step 20b / 20e).
    is_available = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-trust_score", "display_name")
        indexes = [
            models.Index(fields=["is_active", "-trust_score"], name="cg_active_trust_idx"),
        ]

    def __str__(self):
        return f"{self.display_name} (trust={self.trust_score:.2f})"


class PatientProfile(models.Model):
    """A patient's location + care preferences for matching."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="patient_profile",
    )
    display_name = models.CharField(max_length=120, blank=True, default="")
    location = gis_models.PointField(geography=True, srid=4326, null=True, blank=True)
    city = models.CharField(max_length=64, blank=True, default="", db_index=True)
    preferred_language = models.CharField(
        max_length=16, choices=Language.choices, default=Language.ENGLISH
    )
    languages = ArrayField(models.CharField(max_length=16), default=list, blank=True)
    conditions = ArrayField(models.CharField(max_length=64), default=list, blank=True)
    care_level = models.CharField(max_length=16, choices=CareLevel.choices, default=CareLevel.BASIC)
    height_cm = models.PositiveSmallIntegerField(null=True, blank=True)
    weight_kg = models.FloatField(null=True, blank=True)
    blood_type = models.CharField(
        max_length=8, choices=BloodType.choices, blank=True, default=""
    )
    medications = ArrayField(models.CharField(max_length=120), default=list, blank=True)
    allergies = ArrayField(models.CharField(max_length=120), default=list, blank=True)
    emergency_contact_name = models.CharField(max_length=120, blank=True, default="")
    emergency_contact_phone = models.CharField(max_length=32, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self):
        return self.display_name or f"patient:{self.user_id}"


class MatchRun(models.Model):
    """One VEHMF invocation (request + latency + weights used)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="match_runs",
        null=True,
        blank=True,
    )
    query = models.TextField()
    condition = models.CharField(max_length=120, blank=True, default="")
    language = models.CharField(max_length=16, blank=True, default="")
    care_level = models.CharField(max_length=16, blank=True, default="")
    emergency = models.BooleanField(default=False)
    weights = ArrayField(models.FloatField(), size=4, default=list)
    latency_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"MatchRun#{self.pk} ({self.latency_ms}ms)"


class MatchResult(models.Model):
    """One ranked caregiver row belonging to a ``MatchRun``."""

    run = models.ForeignKey(MatchRun, on_delete=models.CASCADE, related_name="results")
    caregiver = models.ForeignKey(
        CaregiverProfile, on_delete=models.CASCADE, related_name="match_hits"
    )
    rank = models.PositiveSmallIntegerField()
    score = models.FloatField()
    cbf = models.FloatField()
    cf = models.FloatField()
    geo = models.FloatField()
    trust = models.FloatField()
    explanation = models.CharField(max_length=255)
    distance_m = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ("run", "rank")
        unique_together = ("run", "rank")

    def __str__(self):
        return f"#{self.rank} caregiver={self.caregiver_id} score={self.score:.3f}"


class InteractionKind(models.TextChoices):
    VIEW = "view", "View"
    REQUEST = "request", "Request"
    ACCEPT = "accept", "Accept"
    COMPLETE = "complete", "Complete"
    RATE = "rate", "Rate"


# Implicit-feedback confidence weights for ALS (Step 21).
INTERACTION_WEIGHTS: dict[str, float] = {
    InteractionKind.VIEW: 1.0,
    InteractionKind.REQUEST: 3.0,
    InteractionKind.ACCEPT: 5.0,
    InteractionKind.COMPLETE: 8.0,
    InteractionKind.RATE: 1.0,
}


class Interaction(models.Model):
    """Patient ↔ caregiver event log feeding offline CF training (Step 21)."""

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="caregiver_interactions",
    )
    caregiver = models.ForeignKey(
        CaregiverProfile,
        on_delete=models.CASCADE,
        related_name="patient_interactions",
    )
    kind = models.CharField(max_length=16, choices=InteractionKind.choices, db_index=True)
    weight = models.FloatField(default=1.0)
    rating = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["patient", "caregiver"], name="interaction_patient_cg_idx"),
            models.Index(fields=["kind", "-created_at"], name="interaction_kind_created_idx"),
        ]

    def __str__(self):
        return f"{self.kind} patient={self.patient_id} caregiver={self.caregiver_id}"


class CareRequestStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PENDING = "pending", "Pending"
    ACCEPTED = "accepted", "Accepted"
    REJECTED = "rejected", "Rejected"
    CANCELLED = "cancelled", "Cancelled"
    EXPIRED = "expired", "Expired"


# Statuses that block a new request for the same patient↔caregiver pair.
ACTIVE_CARE_REQUEST_STATUSES = frozenset(
    {
        CareRequestStatus.DRAFT,
        CareRequestStatus.PENDING,
        CareRequestStatus.ACCEPTED,
    }
)


class CareRequest(models.Model):
    """Patient hire request to a caregiver (Step 23)."""

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="care_requests_sent",
    )
    caregiver = models.ForeignKey(
        CaregiverProfile,
        on_delete=models.CASCADE,
        related_name="care_requests_received",
    )
    status = models.CharField(
        max_length=16,
        choices=CareRequestStatus.choices,
        default=CareRequestStatus.PENDING,
        db_index=True,
    )
    message = models.TextField(blank=True, default="")
    match_run = models.ForeignKey(
        MatchRun,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="care_requests",
    )
    # Snapshot of VEHMF scores / intent at request time.
    match_snapshot = models.JSONField(default=dict, blank=True)
    expires_at = models.DateTimeField(db_index=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["caregiver", "status", "-created_at"], name="cr_cg_status_idx"),
            models.Index(fields=["patient", "status", "-created_at"], name="cr_pt_status_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["patient", "caregiver"],
                condition=models.Q(status=CareRequestStatus.PENDING),
                name="unique_pending_care_request",
            ),
        ]

    def __str__(self):
        return f"CareRequest#{self.pk} {self.status} patient={self.patient_id} cg={self.caregiver_id}"


class CareRelationshipStatus(models.TextChoices):
    PENDING_PAYMENT = "pending_payment", "Pending payment"
    ACTIVE = "active", "Active"
    ENDED = "ended", "Ended"


class CareRelationship(models.Model):
    """Active care link between patient and caregiver (Step 24 provisional → Step 25)."""

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="care_relationships_as_patient",
    )
    caregiver = models.ForeignKey(
        CaregiverProfile,
        on_delete=models.CASCADE,
        related_name="care_relationships_as_caregiver",
    )
    care_request = models.OneToOneField(
        CareRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="relationship",
    )
    status = models.CharField(
        max_length=20,
        choices=CareRelationshipStatus.choices,
        default=CareRelationshipStatus.PENDING_PAYMENT,
        db_index=True,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    end_reason = models.TextField(blank=True, default="")
    is_primary = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ("-started_at",)
        indexes = [
            models.Index(
                fields=["patient", "status", "-started_at"],
                name="cr_rel_patient_status_idx",
            ),
            models.Index(
                fields=["caregiver", "status", "-started_at"],
                name="cr_rel_cg_status_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["patient"],
                condition=models.Q(status="active", is_primary=True),
                name="unique_primary_active_care_relationship",
            ),
        ]

    def __str__(self):
        return (
            f"CareRelationship#{self.pk} {self.status} "
            f"patient={self.patient_id} cg={self.caregiver_id}"
        )
