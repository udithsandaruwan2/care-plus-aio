"""Load realistic Sri Lanka caregiver + patient profiles (Step 16).

Usage::

    python manage.py seed_profiles
    python manage.py seed_profiles --caregivers 30 --patients 8 --flush
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role
from apps.matching.models import CaregiverProfile, PatientProfile
from apps.matching.seed_avatars import ensure_caregiver_avatar
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


def _random_dob(rng: random.Random) -> date:
    """Plausible working-age caregiver birthday (24–58)."""
    age = rng.randint(24, 58)
    return timezone.localdate() - timedelta(days=age * 365 + rng.randint(0, 364))


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
        backfilled = self._backfill_cities()
        dobs, photos = self._backfill_presentation(rng)

        total_cg = CaregiverProfile.objects.filter(is_active=True).count()
        with_geom = CaregiverProfile.objects.exclude(location__isnull=True).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded +{created_cg} caregivers, +{created_pt} patients "
                f"(city backfill {backfilled}, +{dobs} birthdays, +{photos} avatars). "
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
                city=city_name,
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
                nic_id=f"19{900000000 + i:09d}"[:12],
                date_of_birth=_random_dob(rng),
                years_experience=rng.randint(2, 15),
                service_radius_km=round(rng.uniform(15.0, 50.0), 1),
                certification_docs=[
                    {"name": c, "status": "verified"} for c in rng.sample(CERTIFICATIONS, k=2)
                ],
                is_approved=True,
                is_active=True,
                # Soft presence demo: ~every 10th seed caregiver starts unavailable.
                is_available=(i % 10 != 0),
            )
            created += 1
        return created

    def _backfill_presentation(self, rng: random.Random) -> tuple[int, int]:
        """Give older seed rows a birthday + avatar so browse cards look real."""
        dobs = 0
        photos = 0
        for cg in CaregiverProfile.objects.filter(is_active=True):
            if cg.date_of_birth is None:
                cg.date_of_birth = _random_dob(rng)
                cg.save(update_fields=["date_of_birth", "updated_at"])
                dobs += 1
            if ensure_caregiver_avatar(cg):
                photos += 1
        return dobs, photos

    def _backfill_cities(self) -> int:
        """Fill city on older seed rows that predate the city field."""
        updated = 0
        for i, cg in enumerate(
            CaregiverProfile.objects.filter(user__email__startswith="seed.cg.", city="")
        ):
            city_name, _, _ = SRI_LANKA_CITIES[i % len(SRI_LANKA_CITIES)]
            # Prefer city from bio "near X." when present.
            bio = cg.bio or ""
            if "near " in bio:
                city_name = bio.split("near ", 1)[-1].rstrip(".").strip() or city_name
            cg.city = city_name
            cg.save(update_fields=["city", "updated_at"])
            updated += 1
        return updated

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
            preferred = rng.choice(LANGUAGES)

            user = User.objects.create_user(
                email=email,
                password="seed-pass-change-me",
                role=Role.PATIENT,
                first_name=name.split()[0],
                last_name=" ".join(name.split()[1:]) or "Patient",
            )
            langs = [preferred]
            if preferred != "English" and rng.random() > 0.3:
                langs.append("English")
            conditions = rng.sample(SPECIALTIES, k=rng.randint(1, 2))
            PatientProfile.objects.create(
                user=user,
                display_name=name,
                location=Point(lon, lat, srid=4326),
                city=city_name,
                preferred_language=preferred,
                languages=langs,
                conditions=conditions,
                care_level=rng.choice(CARE_LEVELS),
                height_cm=rng.randint(148, 178),
                weight_kg=round(rng.uniform(48.0, 88.0), 1),
                blood_type=rng.choice(["A+", "O+", "B+", "AB+", "O-", "B-"]),
                medications=["Metformin 500mg"] if "diabetes" in conditions else [],
                allergies=["Penicillin"] if i % 5 == 0 else [],
                emergency_contact_name=f"{name.split()[0]} family",
                emergency_contact_phone=f"+9477{2000000 + i:07d}"[:12],
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
