"""Backfill generated avatars (and ages) for caregivers without a photo.

Usage::

    python manage.py seed_avatars
    python manage.py seed_avatars --force --with-dob
"""

from __future__ import annotations

import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.matching.models import CaregiverProfile
from apps.matching.seed_avatars import ensure_caregiver_avatar


class Command(BaseCommand):
    help = "Generate placeholder avatars for caregivers that have no photo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Replace existing photos too (regenerates every avatar).",
        )
        parser.add_argument(
            "--with-dob",
            action="store_true",
            help="Also fill a plausible birthday, plus experience for seed.cg.* rows.",
        )
        parser.add_argument("--seed", type=int, default=20260821)

    def handle(self, *args, **options):
        rng = random.Random(options["seed"])
        photos = 0
        dobs = 0
        experience = 0
        for profile in CaregiverProfile.objects.select_related("user").order_by("pk"):
            if options["with_dob"] and profile.date_of_birth is None:
                age = rng.randint(24, 58)
                profile.date_of_birth = timezone.localdate() - timedelta(
                    days=age * 365 + rng.randint(0, 364)
                )
                profile.save(update_fields=["date_of_birth", "updated_at"])
                dobs += 1
            # Only marketplace seed rows: demo.* profiles encode deliberate
            # onboarding states that years_experience feeds into.
            if (
                options["with_dob"]
                and profile.years_experience is None
                and profile.user.email.startswith("seed.cg.")
            ):
                profile.years_experience = rng.randint(2, 15)
                profile.save(update_fields=["years_experience", "updated_at"])
                experience += 1
            if ensure_caregiver_avatar(profile, force=options["force"]):
                photos += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Avatars written: {photos}. Birthdays filled: {dobs}. "
                f"Experience filled: {experience}."
            )
        )
