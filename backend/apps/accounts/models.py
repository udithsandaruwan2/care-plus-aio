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
