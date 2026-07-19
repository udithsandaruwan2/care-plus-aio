"""Seed / refresh canonical ConditionTerm rows."""

from django.core.management.base import BaseCommand

from apps.vocab.models import ConditionTerm
from apps.vocab.resolver import clear_resolver_cache
from apps.vocab.seed_data import SEED_CONDITIONS


class Command(BaseCommand):
    help = "Upsert ≥30 Sri Lanka medical ConditionTerm rows (Step 15b)."

    def handle(self, *args, **options):
        created = updated = 0
        for slug, canonical, synonyms, notes in SEED_CONDITIONS:
            obj, was_created = ConditionTerm.objects.update_or_create(
                slug=slug,
                defaults={
                    "canonical_en": canonical,
                    "synonyms": synonyms,
                    "active": True,
                    "version": 1,
                    "notes": notes,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1
        clear_resolver_cache()
        total = ConditionTerm.objects.filter(active=True).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Vocab seed complete: +{created} ~{updated} · active={total}"
            )
        )
