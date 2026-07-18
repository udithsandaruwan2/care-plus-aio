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
