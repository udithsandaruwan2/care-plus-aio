"""Care packages and add-ons priced in LKR (Step 29)."""

from django.core.validators import MinValueValidator
from django.db import models


class CareLevel(models.TextChoices):
    BASIC = "basic", "Basic"
    INTERMEDIATE = "intermediate", "Intermediate"
    ADVANCED = "advanced", "Advanced"


class AddOnCategory(models.TextChoices):
    HOSPITAL = "hospital", "Hospital support"
    FOOD = "food", "Food & nutrition"
    TRANSPORT = "transport", "Transport"
    SUPPLIES = "supplies", "Care supplies"
    OTHER = "other", "Other"


class CarePackage(models.Model):
    """Base care package priced in Sri Lankan Rupees."""

    slug = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    care_level = models.CharField(max_length=16, choices=CareLevel.choices, db_index=True)
    price_lkr = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    # Default billed days when starting checkout; Step 30 can override.
    default_days = models.PositiveSmallIntegerField(default=7, validators=[MinValueValidator(1)])
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("sort_order", "price_lkr", "name")

    def __str__(self):
        return f"{self.name} (LKR {self.price_lkr})"


class AddOn(models.Model):
    """Optional hospital / food / other add-on priced in LKR."""

    slug = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    category = models.CharField(
        max_length=16,
        choices=AddOnCategory.choices,
        default=AddOnCategory.OTHER,
        db_index=True,
    )
    price_lkr = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("sort_order", "category", "price_lkr", "name")

    def __str__(self):
        return f"{self.name} [{self.category}] (LKR {self.price_lkr})"
