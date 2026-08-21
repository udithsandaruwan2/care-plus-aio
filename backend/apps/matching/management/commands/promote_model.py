"""Promote a CF or slot-classifier artifact to active (Steps 91 / 96).

Usage::

    python manage.py promote_model 20260821120000
    python manage.py promote_model 20260821120000 --kind slot_classifier --force
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.matching.cf_train import promote_cf_version
from apps.matching.models import ModelKind
from apps.voice.slots import promote_slot_version


class Command(BaseCommand):
    help = (
        "Activate a CF or slot_classifier model version after holdout evaluation "
        "(use --force to skip the gate)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "version",
            type=str,
            help="Artifact version string (directory v<version>).",
        )
        parser.add_argument(
            "--kind",
            type=str,
            default=ModelKind.CF,
            choices=[ModelKind.CF, ModelKind.SLOT_CLASSIFIER],
            help="Model kind to promote (default: cf).",
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
        kind = options["kind"]
        force = bool(options["force"])

        try:
            if kind == ModelKind.SLOT_CLASSIFIER:
                result = promote_slot_version(version, force=force, reason="manual")
                label = "slot classifier"
            else:
                result = promote_cf_version(version, force=force, reason="manual")
                label = "CF"
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        if result.get("promoted"):
            self.stdout.write(
                self.style.SUCCESS(
                    f"Promoted {label} v{result.get('candidate_version')} "
                    f"(reason={result.get('reason')})."
                )
            )
            return

        self.stdout.write(
            self.style.WARNING(
                f"Not promoted: reason={result.get('reason')} "
                f"candidate={result.get('candidate_score')} "
                f"incumbent={result.get('incumbent_score')} "
                f"stub={result.get('stub_score')} "
                f"metric={result.get('metric')} margin={result.get('margin')}."
            )
        )
