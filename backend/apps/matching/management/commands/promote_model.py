"""Promote a trained CF artifact to active (Step 91).

Usage::

    python manage.py promote_model 20260821120000
    python manage.py promote_model 20260821120000 --force
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.matching.cf_train import promote_cf_version


class Command(BaseCommand):
    help = (
        "Activate a CF model version after holdout evaluation "
        "(use --force to skip the gate)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "version",
            type=str,
            help="CF artifact version string (directory v<version>).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Skip holdout gate and activate immediately.",
        )

    def handle(self, *args, **options):
        version = options["version"].strip()
        if version.startswith("v") and version[1:].isdigit():
            version = version[1:]
        try:
            result = promote_cf_version(version, force=bool(options["force"]), reason="manual")
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        if result.get("promoted"):
            self.stdout.write(
                self.style.SUCCESS(
                    f"Promoted CF v{result.get('candidate_version')} "
                    f"(reason={result.get('reason')})."
                )
            )
            return

        self.stdout.write(
            self.style.WARNING(
                f"Not promoted: reason={result.get('reason')} "
                f"candidate={result.get('candidate_score')} "
                f"incumbent={result.get('incumbent_score')} "
                f"metric={result.get('metric')} margin={result.get('margin')}."
            )
        )
