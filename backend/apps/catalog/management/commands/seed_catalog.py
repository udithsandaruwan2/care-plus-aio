"""Seed default LKR care packages and add-ons (Step 29)."""

from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.catalog.models import AddOn, AddOnCategory, CareLevel, CarePackage

PACKAGES = [
    {
        "slug": "basic-home-care",
        "name": "Basic Home Care",
        "description": "Daily living support, medication reminders, and companionship.",
        "care_level": CareLevel.BASIC,
        "price_lkr": Decimal("8500.00"),
        "default_days": 7,
        "sort_order": 10,
    },
    {
        "slug": "intermediate-nursing",
        "name": "Intermediate Nursing",
        "description": "Trained nursing support for recovery, wound care, and monitoring.",
        "care_level": CareLevel.INTERMEDIATE,
        "price_lkr": Decimal("14500.00"),
        "default_days": 7,
        "sort_order": 20,
    },
    {
        "slug": "advanced-clinical",
        "name": "Advanced Clinical Care",
        "description": "Higher-acuity clinical care with specialist caregiver coverage.",
        "care_level": CareLevel.ADVANCED,
        "price_lkr": Decimal("22000.00"),
        "default_days": 7,
        "sort_order": 30,
    },
    {
        "slug": "night-respite",
        "name": "Night Respite Care",
        "description": "Overnight companionship and safety checks so family carers can rest.",
        "care_level": CareLevel.BASIC,
        "price_lkr": Decimal("11000.00"),
        "default_days": 5,
        "sort_order": 40,
    },
    {
        "slug": "pediatric-home",
        "name": "Pediatric Home Support",
        "description": "Child-focused home care with family coaching and school-run help.",
        "care_level": CareLevel.INTERMEDIATE,
        "price_lkr": Decimal("16500.00"),
        "default_days": 7,
        "sort_order": 50,
    },
    {
        "slug": "palliative-comfort",
        "name": "Palliative Comfort Care",
        "description": "Comfort-focused advanced care for serious illness at home.",
        "care_level": CareLevel.ADVANCED,
        "price_lkr": Decimal("28000.00"),
        "default_days": 7,
        "sort_order": 60,
    },
    {
        "slug": "post-surgery-recovery",
        "name": "Post-surgery Recovery",
        "description": "Wound care, mobility support, and medication routines after hospital discharge.",
        "care_level": CareLevel.INTERMEDIATE,
        "price_lkr": Decimal("17500.00"),
        "default_days": 10,
        "sort_order": 70,
    },
]

ADDONS = [
    {
        "slug": "hospital-escort",
        "name": "Hospital escort",
        "description": "Accompanied visits to hospital or clinic appointments.",
        "category": AddOnCategory.HOSPITAL,
        "price_lkr": Decimal("3500.00"),
        "sort_order": 10,
    },
    {
        "slug": "meal-support",
        "name": "Meal support",
        "description": "Daily meal preparation tailored to dietary needs.",
        "category": AddOnCategory.FOOD,
        "price_lkr": Decimal("2500.00"),
        "sort_order": 20,
    },
    {
        "slug": "clinic-transport",
        "name": "Clinic transport",
        "description": "Local transport assistance for medical visits.",
        "category": AddOnCategory.TRANSPORT,
        "price_lkr": Decimal("2000.00"),
        "sort_order": 30,
    },
    {
        "slug": "care-supplies-kit",
        "name": "Care supplies kit",
        "description": "Basic consumables and hygiene supplies for the care period.",
        "category": AddOnCategory.SUPPLIES,
        "price_lkr": Decimal("1800.00"),
        "sort_order": 40,
    },
    {
        "slug": "physiotherapy-visit",
        "name": "Physiotherapy visit",
        "description": "In-home mobility and rehabilitation session.",
        "category": AddOnCategory.OTHER,
        "price_lkr": Decimal("4500.00"),
        "sort_order": 50,
    },
    {
        "slug": "overnight-watch",
        "name": "Overnight watch",
        "description": "Extra night-time monitoring for fall risk or post-op patients.",
        "category": AddOnCategory.OTHER,
        "price_lkr": Decimal("6000.00"),
        "sort_order": 60,
    },
    {
        "slug": "language-interpreter",
        "name": "Language interpreter",
        "description": "Sinhala / Tamil / English support for clinic visits.",
        "category": AddOnCategory.OTHER,
        "price_lkr": Decimal("1500.00"),
        "sort_order": 70,
    },
]


class Command(BaseCommand):
    help = "Seed Care Plus LKR care packages and add-ons (idempotent upsert by slug)."

    def handle(self, *args, **options):
        pkg_count = 0
        for row in PACKAGES:
            _, created = CarePackage.objects.update_or_create(
                slug=row["slug"],
                defaults={**row, "is_active": True},
            )
            pkg_count += 1 if created else 0

        addon_count = 0
        for row in ADDONS:
            _, created = AddOn.objects.update_or_create(
                slug=row["slug"],
                defaults={**row, "is_active": True},
            )
            addon_count += 1 if created else 0

        self.stdout.write(
            self.style.SUCCESS(
                f"Catalog seed complete — packages upserted={len(PACKAGES)} "
                f"(new={pkg_count}), addons upserted={len(ADDONS)} (new={addon_count})."
            )
        )
