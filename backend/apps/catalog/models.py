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
    # Step 33 — idempotent receipt email after paid.
    receipt_email_sent = models.BooleanField(default=False)
    receipt_sent_at = models.DateTimeField(null=True, blank=True)
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


class PaymentProviderName(models.TextChoices):
    MOCK = "mock", "Mock (dev)"
    PAYHERE = "payhere", "PayHere"


class PaymentIntentStatus(models.TextChoices):
    REQUIRES_PAYMENT = "requires_payment", "Requires payment"
    PROCESSING = "processing", "Processing"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


class PaymentIntent(models.Model):
    """Provider-backed payment attempt for an Order (Step 31).

    Orders are never marked paid without a confirmed intent (mock confirm or
    verified webhook). Relationship activation stays in Step 32.
    """

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="payment_intents")
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payment_intents",
    )
    provider = models.CharField(
        max_length=16,
        choices=PaymentProviderName.choices,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=PaymentIntentStatus.choices,
        default=PaymentIntentStatus.REQUIRES_PAYMENT,
        db_index=True,
    )
    amount_lkr = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    currency = models.CharField(max_length=3, default="LKR")
    provider_intent_id = models.CharField(max_length=64, unique=True, db_index=True)
    idempotency_key = models.CharField(max_length=64, unique=True)
    client_payload = models.JSONField(default=dict, blank=True)
    provider_response = models.JSONField(default=dict, blank=True)
    webhook_payload = models.JSONField(default=dict, blank=True)
    failure_code = models.CharField(max_length=64, blank=True, default="")
    failure_message = models.TextField(blank=True, default="")
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["order", "status", "-created_at"], name="pi_order_status_idx"),
            models.Index(fields=["patient", "-created_at"], name="pi_patient_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["order"],
                condition=models.Q(status__in=["requires_payment", "processing"]),
                name="unique_open_payment_intent_per_order",
            ),
        ]

    def __str__(self):
        return f"PaymentIntent#{self.pk} {self.provider} {self.status}"
