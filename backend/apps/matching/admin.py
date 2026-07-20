from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from .models import CaregiverProfile, Interaction, MatchResult, MatchRun, PatientProfile


@admin.register(CaregiverProfile)
class CaregiverProfileAdmin(GISModelAdmin):
    list_display = (
        "display_name",
        "user",
        "city",
        "trust_score",
        "is_active",
        "is_available",
        "languages_display",
        "created_at",
    )
    list_filter = ("is_active", "is_available", "city")
    search_fields = ("display_name", "user__email", "specialties", "certifications", "city")
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


class MatchResultInline(admin.TabularInline):
    model = MatchResult
    extra = 0
    readonly_fields = (
        "rank",
        "caregiver",
        "score",
        "cbf",
        "cf",
        "geo",
        "trust",
        "explanation",
        "distance_m",
    )
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(MatchRun)
class MatchRunAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "query", "emergency", "latency_ms", "created_at")
    list_filter = ("emergency",)
    search_fields = ("query", "user__email", "condition")
    readonly_fields = (
        "user",
        "query",
        "condition",
        "language",
        "care_level",
        "emergency",
        "weights",
        "latency_ms",
        "created_at",
    )
    inlines = [MatchResultInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Interaction)
class InteractionAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "caregiver", "kind", "weight", "rating", "created_at")
    list_filter = ("kind",)
    search_fields = ("patient__email", "caregiver__display_name")
    readonly_fields = ("created_at",)
