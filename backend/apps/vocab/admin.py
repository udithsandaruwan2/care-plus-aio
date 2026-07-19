from django.contrib import admin

from .models import ConditionTerm


@admin.register(ConditionTerm)
class ConditionTermAdmin(admin.ModelAdmin):
    list_display = ("canonical_en", "slug", "active", "version", "updated_at")
    list_filter = ("active", "version")
    search_fields = ("slug", "canonical_en", "synonyms", "notes")
    prepopulated_fields = {"slug": ("canonical_en",)}
    readonly_fields = ("created_at", "updated_at")
