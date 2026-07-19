"""Compute / refresh AHP fusion weights (Step 18).

Usage::

    python manage.py build_ahp_weights
    python manage.py build_ahp_weights --path /ml/../config/ahp_weights.json
"""

from pathlib import Path

from django.core.management.base import BaseCommand

from apps.matching.ahp import reset_ahp_cache, write_config


class Command(BaseCommand):
    help = "Solve the AHP pairwise matrix and write config/ahp_weights.json."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            type=str,
            default="",
            help="Output JSON path (default: settings.AHP_WEIGHTS_PATH / repo config/).",
        )

    def handle(self, *args, **options):
        path = Path(options["path"]) if options["path"] else None
        out = write_config(path)
        reset_ahp_cache()
        doc = out.read_text(encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Wrote {out}"))
        self.stdout.write(doc)
