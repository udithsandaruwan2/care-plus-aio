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
from django.utils import timezone

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


class ModelKind(models.TextChoices):
    CF = "cf", "Collaborative filtering (ALS)"
    FAISS = "faiss", "FAISS caregiver index"
    SLOT_CLASSIFIER = "slot_classifier", "Offline slot classifier"


class ModelVersion(models.Model):
    """Registry row for a trained ranking / index / classifier artifact (Step 88)."""

    kind = models.CharField(max_length=32, choices=ModelKind.choices, db_index=True)
    version = models.CharField(max_length=64)
    trained_at = models.DateTimeField()
    rows_trained_on = models.PositiveIntegerField(default=0)
    metrics = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=False, db_index=True)
    artifact_path = models.CharField(max_length=512, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-trained_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("kind", "version"),
                name="matching_modelversion_kind_version_uniq",
            ),
            models.UniqueConstraint(
                fields=("kind",),
                condition=models.Q(is_active=True),
                name="matching_modelversion_one_active_per_kind",
            ),
        ]

    def __str__(self) -> str:
        flag = "active" if self.is_active else "inactive"
        return f"{self.kind}:{self.version} ({flag})"


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
    date_of_birth = models.DateField(null=True, blank=True)
    years_experience = models.PositiveSmallIntegerField(null=True, blank=True)
    service_radius_km = models.FloatField(
        default=25.0,
        validators=[MinValueValidator(1.0), MaxValueValidator(200.0)],
    )
    # Certification file metadata (storage path + scan status). Files land in MEDIA_ROOT.
    certification_docs = models.JSONField(default=list, blank=True)
    photo = models.ImageField(upload_to="profile_photos/caregivers/%Y/%m/", blank=True)
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

    @property
    def age(self) -> int | None:
        """Whole years since ``date_of_birth`` (None when not shared)."""
        if not self.date_of_birth:
            return None
        today = timezone.localdate()
        born = self.date_of_birth
        years = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        return years if 0 < years < 130 else None


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
    photo = models.ImageField(upload_to="profile_photos/patients/%Y/%m/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self):
        return self.display_name or f"patient:{self.user_id}"


class MatchRun(models.Model):
    """One VEHMF invocation (request + latency + weights used).

    Step 68: query (transcript) and condition encrypted at rest.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="match_runs",
        null=True,
        blank=True,
    )
    query_ciphertext = models.TextField(blank=True, default="")
    condition_ciphertext = models.TextField(blank=True, default="")
    language = models.CharField(max_length=16, blank=True, default="")
    care_level = models.CharField(max_length=16, blank=True, default="")
    emergency = models.BooleanField(default=False)
    weights = ArrayField(models.FloatField(), size=4, default=list)
    latency_ms = models.PositiveIntegerField(default=0)
    cf_version = models.CharField(max_length=64, blank=True, default="")
    embedding_backend = models.CharField(max_length=32, blank=True, default="")
    index_version = models.CharField(max_length=64, blank=True, default="", db_index=True)
    weights_source = models.CharField(max_length=64, blank=True, default="")
    # Step 102 — online A/B weight variant id (empty when experiment off).
    variant = models.CharField(max_length=64, blank=True, default="", db_index=True)
    filters = models.JSONField(default=dict, blank=True)
    cf_model = models.ForeignKey(
        "matching.ModelVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cf_match_runs",
    )
    faiss_model = models.ForeignKey(
        "matching.ModelVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="faiss_match_runs",
    )
    voice_intent = models.ForeignKey(
        "voice.VoiceIntent",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="match_runs",
    )
    request_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Step 104 — soft-delete for user-facing history (kept for audit linkage).
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"MatchRun#{self.pk} ({self.latency_ms}ms)"

    @property
    def query(self) -> str:
        from apps.common.encryption import decrypt_field

        return decrypt_field(self.query_ciphertext)

    @query.setter
    def query(self, value: str) -> None:
        from apps.common.encryption import encrypt_field

        self.query_ciphertext = encrypt_field(value or "")

    @property
    def condition(self) -> str:
        from apps.common.encryption import decrypt_field

        return decrypt_field(self.condition_ciphertext)

    @condition.setter
    def condition(self, value: str) -> None:
        from apps.common.encryption import encrypt_field

        self.condition_ciphertext = encrypt_field(value or "")


def create_match_run(
    *,
    user=None,
    query: str = "",
    condition: str = "",
    language: str = "",
    care_level: str = "",
    emergency: bool = False,
    weights=None,
    latency_ms: int = 0,
    source: str = "",
    cf_version: str = "",
    embedding_backend: str = "",
    index_version: str = "",
    weights_source: str = "",
    variant: str = "",
    filters: dict | None = None,
    voice_intent=None,
    request_id: str = "",
) -> MatchRun:
    from apps.accounts.audit import current_request_id

    run = MatchRun(
        user=user,
        language=language or "",
        care_level=care_level or "",
        emergency=bool(emergency),
        weights=list(weights or []),
        latency_ms=int(latency_ms or 0),
        cf_version=cf_version or "",
        embedding_backend=embedding_backend or "",
        index_version=index_version or "",
        weights_source=weights_source or "",
        variant=variant or "",
        filters=filters or {},
        voice_intent=voice_intent,
        request_id=request_id or current_request_id(),
    )
    run.query = query or ""
    run.condition = condition or ""
    from .model_registry import resolve_model_version

    run.cf_model = resolve_model_version(ModelKind.CF, cf_version or "")
    run.faiss_model = resolve_model_version(ModelKind.FAISS, index_version or "")
    run.save()
    from apps.accounts.audit import record_audit
    from apps.accounts.models import AuditAction

    record_audit(
        actor=user,
        action=AuditAction.RUN_MATCH,
        target_type="match_run",
        target_id=run.pk,
        metadata={
            "emergency": bool(emergency),
            "latency_ms": int(latency_ms or 0),
            "source": source or "",
        },
        async_=False,
    )
    return run


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
    # Step 100 — True when this hit filled the epsilon-greedy exploration slot.
    was_exploratory = models.BooleanField(default=False)

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
    REJECT = "reject", "Reject"


# Implicit-feedback confidence weights for ALS (Step 21 / Step 76 / Step 92).
# REJECT is stored negative; Step 92 trains it as a hard negative (pref=0, high confidence).
# VIEW-only (shown, no stronger action) becomes a weak negative under CF_USE_NEGATIVES.
INTERACTION_WEIGHTS: dict[str, float] = {
    InteractionKind.VIEW: 1.0,
    InteractionKind.REQUEST: 3.0,
    InteractionKind.ACCEPT: 5.0,
    InteractionKind.COMPLETE: 8.0,
    InteractionKind.RATE: 1.0,
    InteractionKind.REJECT: -1.0,
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
    # Step 28 — mid-TTL reminder (email/push) sent once at ~N/2.
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
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


class ReviewStatus(models.TextChoices):
    PENDING = "pending", "Pending moderation"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class Review(models.Model):
    """Patient feedback for a completed care relationship (Step 42)."""

    relationship = models.OneToOneField(
        CareRelationship,
        on_delete=models.CASCADE,
        related_name="review",
    )
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews_written",
    )
    caregiver = models.ForeignKey(
        CaregiverProfile,
        on_delete=models.CASCADE,
        related_name="reviews_received",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
        db_index=True,
    )
    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviews_moderated",
    )
    moderated_at = models.DateTimeField(null=True, blank=True)
    moderation_reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["caregiver", "status", "-created_at"], name="review_cg_status_idx"),
            models.Index(fields=["patient", "-created_at"], name="review_pt_created_idx"),
        ]

    def __str__(self):
        return (
            f"Review#{self.pk} {self.status} rating={self.rating} "
            f"patient={self.patient_id} cg={self.caregiver_id}"
        )


class AvailabilityWeekday(models.IntegerChoices):
    MONDAY = 0, "Monday"
    TUESDAY = 1, "Tuesday"
    WEDNESDAY = 2, "Wednesday"
    THURSDAY = 3, "Thursday"
    FRIDAY = 4, "Friday"
    SATURDAY = 5, "Saturday"
    SUNDAY = 6, "Sunday"


class CaregiverAvailabilitySlot(models.Model):
    """Weekly recurring caregiver availability window (Step 50)."""

    caregiver = models.ForeignKey(
        CaregiverProfile,
        on_delete=models.CASCADE,
        related_name="availability_slots",
    )
    weekday = models.PositiveSmallIntegerField(choices=AvailabilityWeekday.choices, db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    timezone = models.CharField(max_length=64, default="Asia/Colombo")
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("weekday", "start_time")
        indexes = [
            models.Index(
                fields=["caregiver", "is_active", "weekday", "start_time"],
                name="cg_slot_lookup_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["caregiver", "weekday", "start_time", "end_time"],
                name="uniq_cg_slot_window",
            )
        ]

    def __str__(self):
        return (
            f"Slot#{self.pk} cg={self.caregiver_id} day={self.weekday} "
            f"{self.start_time}-{self.end_time}"
        )


class ShiftStatus(models.TextChoices):
    BOOKED = "booked", "Booked"
    CANCELLED = "cancelled", "Cancelled"


class Shift(models.Model):
    """Dated care shift booking protected by Redis schedule lock (Step 51)."""

    caregiver = models.ForeignKey(
        CaregiverProfile,
        on_delete=models.CASCADE,
        related_name="shifts",
    )
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shifts",
    )
    availability_slot = models.ForeignKey(
        CaregiverAvailabilitySlot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shifts",
    )
    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField(db_index=True)
    timezone = models.CharField(max_length=64, default="Asia/Colombo")
    status = models.CharField(
        max_length=16,
        choices=ShiftStatus.choices,
        default=ShiftStatus.BOOKED,
        db_index=True,
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-starts_at",)
        indexes = [
            models.Index(
                fields=["caregiver", "status", "starts_at", "ends_at"],
                name="shift_cg_window_idx",
            ),
            models.Index(
                fields=["patient", "status", "starts_at"],
                name="shift_pt_status_idx",
            ),
        ]

    def __str__(self):
        return f"Shift#{self.pk} cg={self.caregiver_id} {self.starts_at}-{self.ends_at} ({self.status})"
