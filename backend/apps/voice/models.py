"""Voice intent model — structured output of the Cognitive layer.

Stores the transcript plus the fields Gemini (or the stub extractor) mapped to
the Care Plus schema, ready for the VEHMF matcher (M4).
"""

from django.conf import settings
from django.db import models


class Language(models.TextChoices):
    SINHALA = "Sinhala", "Sinhala"
    TAMIL = "Tamil", "Tamil"
    ENGLISH = "English", "English"


class CareLevel(models.TextChoices):
    BASIC = "basic", "Basic"
    INTERMEDIATE = "intermediate", "Intermediate"
    ADVANCED = "advanced", "Advanced"


class Urgency(models.TextChoices):
    ROUTINE = "routine", "Routine"
    URGENT = "urgent", "Urgent"
    CRITICAL = "critical", "Critical"


class VoiceIntent(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="voice_intents",
    )
    raw_text = models.TextField()
    condition = models.CharField(max_length=120, blank=True, default="")
    language = models.CharField(max_length=16, choices=Language.choices)
    # All languages detected in the utterance (Singlish / Tanglish mixes).
    languages = models.JSONField(default=list, blank=True)
    care_level = models.CharField(max_length=16, choices=CareLevel.choices)
    urgency = models.CharField(max_length=16, choices=Urgency.choices, default=Urgency.ROUTINE)
    source = models.CharField(max_length=16, default="stub")
    ts = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-ts",)

    def __str__(self):
        return (
            f"{self.user_id}: {self.condition or '?'} / {self.language} @ {self.ts:%Y-%m-%d %H:%M}"
        )


# Soft caps for JSON memory on DialogueSession (Step 15g).
DIALOGUE_TURN_LIMIT = 12
DIALOGUE_ROUTE_HISTORY_LIMIT = 20


class DialogueSession(models.Model):
    """Multi-turn conversation memory for one Neural Core dialogue (Step 15g)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dialogue_sessions",
    )
    lang = models.CharField(max_length=16, blank=True, default="")
    active = models.BooleanField(default=True, db_index=True)
    intent_chips = models.JSONField(default=dict, blank=True)
    route_history = models.JSONField(default=list, blank=True)
    open_questions = models.JSONField(default=list, blank=True)
    last_match_run = models.ForeignKey(
        "matching.MatchRun",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dialogue_sessions",
    )
    # Last N turns: {role, text, route, situation, ts}
    turns = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        indexes = [
            models.Index(fields=["user", "active", "-updated_at"], name="dlg_user_active_idx"),
        ]

    def __str__(self):
        state = "active" if self.active else "closed"
        return f"DialogueSession {self.pk} ({self.user_id}, {state})"
