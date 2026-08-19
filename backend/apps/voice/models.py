"""Voice intent model — structured output of the Cognitive layer.

Stores the transcript plus the fields Gemini (or the stub extractor) mapped to
the Care Plus schema, ready for the VEHMF matcher (M4).

Step 68: transcribed intent (raw_text) and condition are encrypted at rest.
"""

from django.conf import settings
from django.db import models

from apps.common.encryption import decrypt_field, decrypt_json, encrypt_field, encrypt_json


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
    raw_text_ciphertext = models.TextField(blank=True, default="")
    condition_ciphertext = models.TextField(blank=True, default="")
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

    @property
    def raw_text(self) -> str:
        return decrypt_field(self.raw_text_ciphertext)

    @raw_text.setter
    def raw_text(self, value: str) -> None:
        self.raw_text_ciphertext = encrypt_field(value or "")

    @property
    def condition(self) -> str:
        return decrypt_field(self.condition_ciphertext)

    @condition.setter
    def condition(self, value: str) -> None:
        self.condition_ciphertext = encrypt_field(value or "")


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
    intent_chips_ciphertext = models.TextField(blank=True, default="")
    route_history = models.JSONField(default=list, blank=True)
    open_questions = models.JSONField(default=list, blank=True)
    last_match_run = models.ForeignKey(
        "matching.MatchRun",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dialogue_sessions",
    )
    # Last N turns: {role, text, route, situation, ts} — encrypted at rest (Step 68).
    turns_ciphertext = models.TextField(blank=True, default="")
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

    @property
    def intent_chips(self) -> dict:
        return decrypt_json(self.intent_chips_ciphertext, default={})

    @intent_chips.setter
    def intent_chips(self, value: dict | None) -> None:
        self.intent_chips_ciphertext = encrypt_json(value or {})

    @property
    def turns(self) -> list:
        return decrypt_json(self.turns_ciphertext, default=[])

    @turns.setter
    def turns(self, value: list | None) -> None:
        self.turns_ciphertext = encrypt_json(value or [])


class VoiceTurnTiming(models.Model):
    """Per-stage latency for one ``POST /voice/turn/`` (Step 77). No transcript/PHI."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="voice_turn_timings",
    )
    request_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    route = models.CharField(max_length=16, blank=True, default="")
    situation = models.CharField(max_length=32, blank=True, default="")
    asr_ms = models.PositiveIntegerField(default=0)
    intent_ms = models.PositiveIntegerField(default=0)
    route_ms = models.PositiveIntegerField(default=0)
    match_ms = models.PositiveIntegerField(default=0)
    chat_ms = models.PositiveIntegerField(default=0)
    tts_ms = models.PositiveIntegerField(default=0)
    total_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"VoiceTurnTiming#{self.pk} total={self.total_ms}ms route={self.route}"


def create_voice_intent(*, user, **fields) -> VoiceIntent:
    """Persist a VoiceIntent with encrypted raw_text / condition."""
    intent = VoiceIntent(
        user=user,
        language=fields.get("language") or "English",
        languages=fields.get("languages") or [fields.get("language") or "English"],
        care_level=fields.get("care_level") or "intermediate",
        urgency=fields.get("urgency") or Urgency.ROUTINE,
        source=fields.get("source") or "stub",
    )
    intent.raw_text = fields.get("raw_text") or ""
    intent.condition = fields.get("condition") or ""
    intent.save()
    return intent
