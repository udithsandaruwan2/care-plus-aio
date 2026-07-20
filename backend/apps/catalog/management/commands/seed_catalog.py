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
