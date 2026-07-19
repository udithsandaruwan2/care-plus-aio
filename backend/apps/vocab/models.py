"""Canonical medical condition vocabulary (Step 15b)."""

from django.db import models


class ConditionTerm(models.Model):
    """One canonical condition used by voice intent, matching, and admin."""

    slug = models.SlugField(max_length=64, unique=True)
    canonical_en = models.CharField(max_length=120)
    # Synonyms grouped by language code: {"en": [...], "si": [...], "ta": [...]}
    synonyms = models.JSONField(default=dict, blank=True)
    active = models.BooleanField(default=True, db_index=True)
    version = models.PositiveIntegerField(default=1)
    notes = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("canonical_en",)

    def __str__(self):
        return f"{self.canonical_en} ({self.slug})"

    def all_phrases(self) -> list[str]:
        phrases = [self.canonical_en, self.slug.replace("-", " ")]
        for values in (self.synonyms or {}).values():
            if isinstance(values, list):
                phrases.extend(str(v) for v in values if v)
        return phrases
