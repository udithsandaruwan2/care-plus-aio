from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from .models import CaregiverProfile, PatientProfile


@admin.register(CaregiverProfile)
class CaregiverProfileAdmin(GISModelAdmin):
    list_display = (
        "display_name",
        "user",
        "trust_score",
        "is_active",
        "languages_display",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("display_name", "user__email", "specialties", "certifications")
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Languages")
    def languages_display(self, obj):
        return ", ".join(obj.languages or [])


@admin.register(PatientProfile)
class PatientProfileAdmin(GISModelAdmin):
    list_display = ("display_name", "user", "preferred_language", "care_level", "updated_at")
    list_filter = ("preferred_language", "care_level")
    search_fields = ("display_name", "user__email", "conditions")
    readonly_fields = ("created_at", "updated_at")
