"""Custom user model: email login + role-based access control (RBAC).

Also hosts the ``ConsentLog`` — the PDPA/GDPR consent gate. Consent is stored as
an **append-only** ledger: every grant or revoke is a new immutable row, and the
*current* state for a scope is the most recent row for that (user, scope) pair.
This preserves a full, auditable history of consent changes.
"""

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class Role(models.TextChoices):
    PATIENT = "patient", "Patient"
    CAREGIVER = "caregiver", "Caregiver"
    ADMIN = "admin", "Admin"
    AUDITOR = "auditor", "Auditor"


class ConsentScope(models.TextChoices):
    """Distinct processing purposes a user can consent to (PDPA/GDPR)."""

    AI_PROCESSING = "ai_processing", "AI processing of voice/intent"
    HEALTH_MONITORING = "health_monitoring", "Health time-series monitoring"
    DATA_SHARING = "data_sharing", "Sharing profile with matched caregivers"


class UserManager(BaseUserManager):
    """Manager for the email-based user model."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", Role.ADMIN)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField("email address", unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PATIENT)
    # Step 69 — set when right-to-erasure completes (account stays for audit PROTECT).
    erased_at = models.DateTimeField(null=True, blank=True, db_index=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return f"{self.email} ({self.role})"


class ConsentLog(models.Model):
    """Append-only record of a consent grant/revoke for a single scope.

    Never update or delete rows: to change consent, insert a new row. The latest
    row for a (user, scope) pair is authoritative — see :meth:`is_granted`.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="consent_logs",
    )
    scope = models.CharField(max_length=32, choices=ConsentScope.choices)
    granted = models.BooleanField()
    ts = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-ts",)
        indexes = [
            models.Index(fields=["user", "scope", "-ts"], name="consent_user_scope_ts_idx"),
        ]

    def __str__(self):
        state = "granted" if self.granted else "revoked"
        return f"{self.user_id}:{self.scope} {state} @ {self.ts:%Y-%m-%d %H:%M:%S}"

    @classmethod
    def is_granted(cls, user, scope) -> bool:
        """Return the current consent state for ``scope`` (latest row wins)."""
        if not user or not user.is_authenticated:
            return False
        latest = cls.objects.filter(user=user, scope=scope).order_by("-ts").first()
        return bool(latest and latest.granted)

    @classmethod
    def current_state(cls, user) -> dict[str, bool]:
        """Return ``{scope: granted}`` for every scope the user has ever set."""
        state: dict[str, bool] = {}
        # Rows arrive newest-first (Meta.ordering); keep only the first per scope.
        for scope, granted in cls.objects.filter(user=user).values_list("scope", "granted"):
            state.setdefault(scope, granted)
        return state


class NotificationPreference(models.Model):
    """Per-user email/push toggles by notification event (Step 39)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preference",
    )
    channels = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self):
        return f"NotificationPreference user={self.user_id}"


class PushSubscription(models.Model):
    """Browser Web Push subscription (VAPID) for a user (Step 41)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
    )
    endpoint = models.URLField(max_length=2048, unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    user_agent = models.CharField(max_length=512, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self):
        return f"PushSubscription#{self.pk} user={self.user_id}"


class MobilePushPlatform(models.TextChoices):
    FCM = "fcm", "Firebase Cloud Messaging"
    APNS = "apns", "Apple Push Notification service"


class MobilePushDevice(models.Model):
    """Mobile push token for Expo/native apps (Step 49)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mobile_push_devices",
    )
    token = models.CharField(max_length=512, unique=True)
    platform = models.CharField(
        max_length=16,
        choices=MobilePushPlatform.choices,
        default=MobilePushPlatform.FCM,
    )
    device_id = models.CharField(max_length=128, blank=True, default="")
    app_version = models.CharField(max_length=64, blank=True, default="")
    enabled = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        indexes = [
            models.Index(fields=["user", "enabled", "-updated_at"], name="mpd_user_enabled_ts_idx"),
        ]

    def __str__(self):
        return f"MobilePushDevice#{self.pk} user={self.user_id} {self.platform}"


class AuditAction(models.TextChoices):
    """Well-known audit action codes (HIPAA/PDPA access trail)."""

    VIEW_HEALTH = "view_health", "View patient health data"
    VIEW_CAREGIVER = "view_caregiver", "View caregiver public profile"
    GRANT_CONSENT = "grant_consent", "Grant processing consent"
    REVOKE_CONSENT = "revoke_consent", "Revoke processing consent"
    LOGIN = "login", "User login"
    RUN_MATCH = "run_match", "VEHMF match ranking run"
    CREATE_CARE_REQUEST = "create_care_request", "Patient created care request"
    CANCEL_CARE_REQUEST = "cancel_care_request", "Patient cancelled care request"
    ACCEPT_CARE_REQUEST = "accept_care_request", "Caregiver accepted care request"
    REJECT_CARE_REQUEST = "reject_care_request", "Caregiver rejected care request"
    ACTIVATE_CARE_RELATIONSHIP = "activate_care_relationship", "Care relationship activated"
    END_CARE_RELATIONSHIP = "end_care_relationship", "Care relationship ended"
    CREATE_ORDER = "create_order", "Patient created checkout order"
    CREATE_PAYMENT_INTENT = "create_payment_intent", "Patient created payment intent"
    CONFIRM_PAYMENT = "confirm_payment", "Payment confirmed (mock or webhook)"
    PAYMENT_WEBHOOK = "payment_webhook", "Payment provider webhook received"
    RECEIPT_SENT = "receipt_sent", "Payment receipt emailed to patient"
    CREATE_MEDICAL_RECORD = "create_medical_record", "Patient created medical record"
    UPDATE_MEDICAL_RECORD = "update_medical_record", "Patient updated medical record"
    DELETE_MEDICAL_RECORD = "delete_medical_record", "Patient soft-deleted medical record"
    BOOK_SHIFT = "book_shift", "Patient booked a caregiver shift"
    CANCEL_SHIFT = "cancel_shift", "Shift booking cancelled"
    SHIFT_CONFLICT_FALLBACK = "shift_conflict_fallback", "Shift conflict offered VEHMF fallback"
    DISABLE_USER = "disable_user", "Admin disabled or re-enabled a user account"
    EXPORT_DATA = "export_data", "User exported personal data"
    REQUEST_ERASURE = "request_erasure", "User requested right-to-erasure"


class AuditLog(models.Model):
    """Immutable append-only access / action log.

    Rows are never updated or deleted (enforced in the ORM and by a Postgres
    trigger). Writers should use :func:`apps.accounts.audit.record_audit`.
    """

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="audit_actions",
        null=True,
        blank=True,
        help_text="User who performed the action (null for system).",
    )
    action = models.CharField(max_length=64, choices=AuditAction.choices)
    ts = models.DateTimeField(auto_now_add=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    request_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        help_text="HTTP correlation id from RequestIdMetricsMiddleware (empty for non-HTTP writers).",
    )
    # Optional target of the action (e.g. patient whose health was viewed).
    target_type = models.CharField(max_length=64, blank=True, default="")
    target_id = models.CharField(max_length=64, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-ts",)
        indexes = [
            models.Index(fields=["action", "-ts"], name="audit_action_ts_idx"),
            models.Index(fields=["actor", "-ts"], name="audit_actor_ts_idx"),
        ]

    def __str__(self):
        return f"{self.action} by {self.actor_id} @ {self.ts:%Y-%m-%d %H:%M:%S}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("AuditLog is append-only; updates are forbidden.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("AuditLog is append-only; deletes are forbidden.")


class EmailOtp(models.Model):
    """Short-lived email OTP for optional second-factor elevation (Step 22f)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_otps",
    )
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField(db_index=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["user", "-created_at"], name="email_otp_user_created_idx"),
        ]

    def __str__(self):
        return f"EmailOtp#{self.pk} user={self.user_id}"
