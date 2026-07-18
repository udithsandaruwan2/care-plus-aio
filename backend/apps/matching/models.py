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
    is_active = models.BooleanField(default=True)
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
    preferred_language = models.CharField(
        max_length=16, choices=Language.choices, default=Language.ENGLISH
    )
    conditions = ArrayField(models.CharField(max_length=64), default=list, blank=True)
    care_level = models.CharField(max_length=16, choices=CareLevel.choices, default=CareLevel.BASIC)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self):
        return self.display_name or f"patient:{self.user_id}"
