"""Backfill COMPLETE / RATE / REJECT interactions from existing records (Step 76).

Usage::

    python manage.py backfill_interactions
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.matching.interactions import backfill_outcome_interactions


class Command(BaseCommand):
    help = (
        "Create missing COMPLETE / RATE / REJECT Interaction rows from ended "
        "relationships, reviews, and rejected care requests. Safe to re-run."
    )

    def handle(self, *args, **options):
        created = backfill_outcome_interactions()
        total = sum(created.values())
        self.stdout.write(
            self.style.SUCCESS(
                f"Backfilled {total} outcome interaction(s): "
                f"complete={created['complete']} rate={created['rate']} "
                f"reject={created['reject']}."
            )
        )
