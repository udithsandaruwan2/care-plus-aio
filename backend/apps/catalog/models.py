"""Care packages, add-ons, and checkout orders priced in LKR (Steps 29–30)."""

from django.conf import settings
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


class OrderStatus(models.TextChoices):
    AWAITING_PAYMENT = "awaiting_payment", "Awaiting payment"
    PAID = "paid", "Paid"
    CANCELLED = "cancelled", "Cancelled"
    EXPIRED = "expired", "Expired"


class OrderLineKind(models.TextChoices):
    PACKAGE = "package", "Care package"
    ADDON = "addon", "Add-on"


class Order(models.Model):
    """Priced checkout bound to an accepted CareRequest (Step 30)."""

    care_request = models.ForeignKey(
        "matching.CareRequest",
        on_delete=models.PROTECT,
        related_name="orders",
    )
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.AWAITING_PAYMENT,
        db_index=True,
    )
    days = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    currency = models.CharField(max_length=3, default="LKR")
    subtotal_lkr = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    total_lkr = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["patient", "status", "-created_at"], name="order_pt_status_idx"),
            models.Index(fields=["care_request", "status"], name="order_cr_status_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["care_request"],
                condition=models.Q(status="awaiting_payment"),
                name="unique_awaiting_payment_order_per_request",
            ),
        ]

    def __str__(self):
        return f"Order#{self.pk} {self.status} LKR {self.total_lkr}"


class OrderLineItem(models.Model):
    """Persisted price snapshot for a package or add-on line."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="lines")
    kind = models.CharField(max_length=16, choices=OrderLineKind.choices)
    catalog_id = models.PositiveIntegerField()
    slug = models.SlugField(max_length=64)
    name = models.CharField(max_length=120)
    unit_price_lkr = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    quantity = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    line_total_lkr = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    class Meta:
        ordering = ("id",)

    def __str__(self):
        return f"{self.kind}:{self.slug} x{self.quantity} = LKR {self.line_total_lkr}"
