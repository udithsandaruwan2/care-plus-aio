# Generated manually for Step 29

from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="CarePackage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("description", models.TextField(blank=True, default="")),
                (
                    "care_level",
                    models.CharField(
                        choices=[
                            ("basic", "Basic"),
                            ("intermediate", "Intermediate"),
                            ("advanced", "Advanced"),
                        ],
                        db_index=True,
                        max_length=16,
                    ),
                ),
                (
                    "price_lkr",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=12,
                        validators=[MinValueValidator(0)],
                    ),
                ),
                (
                    "default_days",
                    models.PositiveSmallIntegerField(default=7, validators=[MinValueValidator(1)]),
                ),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("sort_order", "price_lkr", "name"),
            },
        ),
        migrations.CreateModel(
            name="AddOn",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("description", models.TextField(blank=True, default="")),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("hospital", "Hospital support"),
                            ("food", "Food & nutrition"),
                            ("transport", "Transport"),
                            ("supplies", "Care supplies"),
                            ("other", "Other"),
                        ],
                        db_index=True,
                        default="other",
                        max_length=16,
                    ),
                ),
                (
                    "price_lkr",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=12,
                        validators=[MinValueValidator(0)],
                    ),
                ),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("sort_order", "category", "price_lkr", "name"),
            },
        ),
    ]
