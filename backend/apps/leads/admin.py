from django.contrib import admin

from .models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "email",
        "phone",
        "city",
        "status",
        "ack_email_sent",
        "created_at",
    )
    list_filter = ("status", "preferred_language", "ack_email_sent")
    search_fields = ("name", "email", "phone", "message", "city")
    readonly_fields = ("created_at", "updated_at", "contacted_at", "ack_email_sent")
    raw_id_fields = ("contacted_by",)
