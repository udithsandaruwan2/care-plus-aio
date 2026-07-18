"""Load realistic Sri Lanka caregiver + patient profiles (Step 16).

Usage::

    python manage.py seed_profiles
    python manage.py seed_profiles --caregivers 30 --patients 8 --flush
"""

from __future__ import annotations

import random

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Role
from apps.matching.models import CaregiverProfile, PatientProfile
from apps.matching.seed_data import (
    CARE_LEVELS,
    CAREGIVER_NAMES,
    CERTIFICATIONS,
    LANGUAGES,
    PATIENT_NAMES,
    SPECIALTIES,
    SRI_LANKA_CITIES,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Seed CaregiverProfile + PatientProfile rows with Sri Lanka geodata."

    def add_arguments(self, parser):
        parser.add_argument(
            "--caregivers",
            type=int,
            default=25,
            help="Number of caregiver profiles to ensure (default: 25).",
        )
        parser.add_argument(
            "--patients",
            type=int,
            default=6,
            help="Number of patient profiles to ensure (default: 6).",
        )
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing seeded profiles/users before inserting.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=20260718,
            help="PRNG seed for reproducible layouts (default: 20260718).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(options["seed"])
        n_cg = options["caregivers"]
        n_pt = options["patients"]

        if options["flush"]:
            CaregiverProfile.objects.filter(user__email__startswith="seed.cg.").delete()
            PatientProfile.objects.filter(user__email__startswith="seed.pt.").delete()
            User.objects.filter(email__startswith="seed.cg.").delete()
            User.objects.filter(email__startswith="seed.pt.").delete()
            self.stdout.write(self.style.WARNING("Flushed previous seed.cg.* / seed.pt.* rows."))

        created_cg = self._seed_caregivers(rng, n_cg)
        created_pt = self._seed_patients(rng, n_pt)

        total_cg = CaregiverProfile.objects.filter(is_active=True).count()
        with_geom = CaregiverProfile.objects.exclude(location__isnull=True).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded +{created_cg} caregivers, +{created_pt} patients. "
                f"Active caregivers with geometry: {with_geom}/{total_cg}."
            )
        )

    def _seed_caregivers(self, rng: random.Random, n: int) -> int:
        created = 0
        for i in range(n):
            email = f"seed.cg.{i:03d}@careplus.local"
            if User.objects.filter(email=email).exists():
                continue
            name = CAREGIVER_NAMES[i % len(CAREGIVER_NAMES)]
            city_name, lon, lat = SRI_LANKA_CITIES[i % len(SRI_LANKA_CITIES)]
            # Small jitter so caregivers in the same city aren't stacked.
            lon += rng.uniform(-0.04, 0.04)
            lat += rng.uniform(-0.04, 0.04)

            user = User.objects.create_user(
                email=email,
                password="seed-pass-change-me",
                role=Role.CAREGIVER,
                first_name=name.split()[0],
                last_name=" ".join(name.split()[1:]) or "Caregiver",
            )
            langs = self._pick_languages(rng, i)
            CaregiverProfile.objects.create(
                user=user,
                display_name=name,
                location=Point(lon, lat, srid=4326),
                certifications=rng.sample(CERTIFICATIONS, k=rng.randint(2, 4)),
                languages=langs,
                specialties=rng.sample(SPECIALTIES, k=rng.randint(2, 5)),
                care_levels=sorted(
                    rng.sample(CARE_LEVELS, k=rng.randint(1, 3)),
                    key=CARE_LEVELS.index,
                ),
                trust_score=round(rng.uniform(0.55, 0.98), 3),
                embedding=[],
                bio=f"Community caregiver based near {city_name}.",
                is_active=True,
            )
            created += 1
        return created

    def _seed_patients(self, rng: random.Random, n: int) -> int:
        created = 0
        for i in range(n):
            email = f"seed.pt.{i:03d}@careplus.local"
            if User.objects.filter(email=email).exists():
                continue
            name = PATIENT_NAMES[i % len(PATIENT_NAMES)]
            city_name, lon, lat = SRI_LANKA_CITIES[(i * 3) % len(SRI_LANKA_CITIES)]
            lon += rng.uniform(-0.03, 0.03)
            lat += rng.uniform(-0.03, 0.03)

            user = User.objects.create_user(
                email=email,
                password="seed-pass-change-me",
                role=Role.PATIENT,
                first_name=name.split()[0],
                last_name=" ".join(name.split()[1:]) or "Patient",
            )
            PatientProfile.objects.create(
                user=user,
                display_name=name,
                location=Point(lon, lat, srid=4326),
                preferred_language=rng.choice(LANGUAGES),
                conditions=rng.sample(SPECIALTIES, k=rng.randint(1, 2)),
                care_level=rng.choice(CARE_LEVELS),
            )
            created += 1
        return created

    @staticmethod
    def _pick_languages(rng: random.Random, index: int) -> list[str]:
        # Bias: coastal/west more Sinhala+English; north/east more Tamil+English.
        if index % 5 == 0:
            return ["Tamil", "English"]
        if index % 5 == 1:
            return ["Sinhala", "Tamil", "English"]
        if index % 3 == 0:
            return ["Sinhala", "English"]
        return rng.sample(LANGUAGES, k=rng.randint(1, 2))
