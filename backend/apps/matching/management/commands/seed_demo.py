"""Load a full Care Plus showcase dataset (vocab, catalog, profiles, situations).

Usage::

    python manage.py seed_demo
    python manage.py seed_demo --flush
"""

from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.matching.demo_seed import (
    DEMO_PASSWORD,
    build_showcase,
    showcase_already_present,
)
from apps.matching.models import CareRequest, CaregiverProfile, PatientProfile
from apps.matching.patient_profile import patient_profile_completion


class Command(BaseCommand):
    help = "Seed vocab, catalog, Sri Lanka profiles, and every product situation for demos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Flush seed.cg/seed.pt profiles before inserting (does not delete demo.*).",
        )
        parser.add_argument(
            "--caregivers",
            type=int,
            default=30,
            help="Marketplace caregiver count (default: 30).",
        )
        parser.add_argument(
            "--patients",
            type=int,
            default=10,
            help="Marketplace patient count (default: 10).",
        )

    def handle(self, *args, **options):
        call_command("seed_vocab", verbosity=options["verbosity"])
        call_command("seed_catalog", verbosity=options["verbosity"])
        call_command(
            "seed_profiles",
            caregivers=options["caregivers"],
            patients=options["patients"],
            flush=options["flush"],
            verbosity=options["verbosity"],
        )
        self._backfill_seed_patients()
        call_command("seed_interactions", verbosity=options["verbosity"])

        if showcase_already_present():
            self.stdout.write(
                self.style.WARNING(
                    "Showcase care requests already exist — skipping situation graph. "
                    "Delete [showcase] requests (or use a fresh DB) to rebuild."
                )
            )
        else:
            with transaction.atomic():
                stats = build_showcase()
            self.stdout.write(self.style.SUCCESS(f"Showcase graph: {stats}"))

        call_command("backfill_interactions", verbosity=options["verbosity"])

        hireable = sum(
            1
            for p in PatientProfile.objects.select_related("user")
            if patient_profile_completion(p).can_request_care
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Demo login password: {DEMO_PASSWORD}\n"
                "  demo.patient@careplus.local     active care + Serah + vitals\n"
                "  demo.caregiver@careplus.local   inbox / schedule / messages\n"
                "  demo.admin@careplus.local       admin hub\n"
                "  demo.pay@careplus.local         awaiting payment\n"
                "  demo.onboarding@careplus.local  incomplete profile\n"
                f"Hire-ready patients: {hireable}. "
                f"Active caregivers: {CaregiverProfile.objects.filter(is_active=True).count()}. "
                f"Care requests: {CareRequest.objects.count()}."
            )
        )

    def _backfill_seed_patients(self) -> None:
        """Older seed.pt rows were ~50% complete and could not hire."""
        updated = 0
        for profile in PatientProfile.objects.filter(user__email__startswith="seed.pt."):
            completion = patient_profile_completion(profile)
            if completion.can_request_care:
                continue
            if not profile.city:
                profile.city = "Colombo"
            if not profile.languages:
                profile.languages = [profile.preferred_language or "English"]
            if profile.height_cm is None:
                profile.height_cm = 165
            if profile.weight_kg is None:
                profile.weight_kg = 62.0
            if not profile.blood_type:
                profile.blood_type = "O+"
            if not profile.emergency_contact_name:
                profile.emergency_contact_name = "Family contact"
            if not profile.emergency_contact_phone:
                profile.emergency_contact_phone = "+94770000000"
            profile.save()
            updated += 1
        if updated:
            self.stdout.write(f"Backfilled {updated} incomplete seed patient profile(s).")
