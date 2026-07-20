"""Marketing lead appointments (Step 27).

Public contact form submissions land here for admin follow-up.
"""

from django.conf import settings
from django.db import models


class LeadStatus(models.TextChoices):
    NEW = "new", "New"
    CONTACTED = "contacted", "Contacted"
    CLOSED = "closed", "Closed"


class Lead(models.Model):
    """Inbound marketing / appointment lead from the public contact form."""

    name = models.CharField(max_length=120)
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=32, blank=True, default="")
    message = models.TextField(blank=True, default="")
    city = models.CharField(max_length=64, blank=True, default="")
    preferred_language = models.CharField(max_length=16, blank=True, default="")
    source = models.CharField(max_length=64, blank=True, default="marketing_form")
    status = models.CharField(
        max_length=16,
        choices=LeadStatus.choices,
        default=LeadStatus.NEW,
        db_index=True,
    )
    contacted_at = models.DateTimeField(null=True, blank=True)
    contacted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads_contacted",
    )
    admin_notes = models.TextField(blank=True, default="")
    ack_email_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["status", "-created_at"], name="lead_status_created_idx"),
        ]

    def __str__(self):
        return f"Lead#{self.pk} {self.status} {self.email}"
