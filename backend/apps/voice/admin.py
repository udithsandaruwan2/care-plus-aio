from django.contrib import admin

from .models import DialogueSession, VoiceIntent


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


@admin.register(DialogueSession)
class DialogueSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "lang", "active", "last_match_run", "updated_at")
    list_filter = ("active", "lang")
    search_fields = ("user__email",)
    readonly_fields = (
        "user",
        "lang",
        "active",
        "intent_chips",
        "route_history",
        "open_questions",
        "last_match_run",
        "turns",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False
