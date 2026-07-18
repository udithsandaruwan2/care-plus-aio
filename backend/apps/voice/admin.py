from django.contrib import admin

from .models import VoiceIntent


@admin.register(VoiceIntent)
class VoiceIntentAdmin(admin.ModelAdmin):
    list_display = ("ts", "user", "condition", "language", "care_level", "urgency", "source")
    list_filter = ("language", "care_level", "urgency", "source")
    search_fields = ("user__email", "condition", "raw_text")
    readonly_fields = (
        "user",
        "raw_text",
        "condition",
        "language",
        "care_level",
        "urgency",
        "source",
        "ts",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
