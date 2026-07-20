"""Seed synthetic patient ↔ caregiver interactions for CF training (Step 21).

Usage::

    python manage.py seed_interactions
    python manage.py seed_interactions --flush
"""

from __future__ import annotations

import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Role
from apps.matching.interactions import log_interaction
from apps.matching.models import CaregiverProfile, Interaction, InteractionKind

User = get_user_model()


class Command(BaseCommand):
    help = "Create synthetic Interaction rows (view/request/accept/complete/rate)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete all Interaction rows before seeding.",
        )
        parser.add_argument(
            "--views-per-patient",
            type=int,
            default=12,
            help="Random caregiver views per patient (default: 12).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["flush"]:
            deleted, _ = Interaction.objects.all().delete()
            self.stdout.write(f"Flushed {deleted} interaction(s).")

        patients = list(
            User.objects.filter(role=Role.PATIENT)
            .filter(patient_profile__isnull=False)
            .select_related("patient_profile")
        )
        caregivers = list(CaregiverProfile.objects.filter(is_active=True).only("id"))
        if not patients:
            self.stderr.write(
                "No patient users found — run seed_profiles first."
            )
            return
        if len(caregivers) < 3:
            self.stderr.write(
                "Need at least 3 active caregivers — run seed_profiles first."
            )
            return

        views_per = options["views_per_patient"]
        created = 0
        for patient in patients:
            sample = random.sample(caregivers, k=min(views_per, len(caregivers)))
            for cg in sample:
                log_interaction(patient, cg, InteractionKind.VIEW, metadata={"seed": True})
                created += 1

            # Funnel: request → accept → complete → rate on a subset.
            funnel = sample[: max(1, len(sample) // 3)]
            for cg in funnel[:2]:
                log_interaction(patient, cg, InteractionKind.REQUEST, metadata={"seed": True})
                created += 1
            for cg in funnel[:1]:
                log_interaction(patient, cg, InteractionKind.ACCEPT, metadata={"seed": True})
                log_interaction(patient, cg, InteractionKind.COMPLETE, metadata={"seed": True})
                log_interaction(
                    patient,
                    cg,
                    InteractionKind.RATE,
                    rating=random.randint(4, 5),
                    metadata={"seed": True},
                )
                created += 4

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {created} interactions for {len(patients)} patient(s)."
            )
        )
