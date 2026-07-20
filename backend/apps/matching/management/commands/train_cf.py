"""Train implicit ALS on the interaction log (Step 21).

Usage::

    python manage.py train_cf
    python manage.py train_cf --factors 16
    python manage.py train_cf --patient-scores 42
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.matching.cf_train import patient_cf_scores, train_cf_als

User = get_user_model()


class Command(BaseCommand):
    help = "Train ALS collaborative-filtering model from Interaction rows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--factors",
            type=int,
            default=32,
            help="Latent factor count (default: 32).",
        )
        parser.add_argument(
            "--patient-scores",
            type=int,
            default=0,
            metavar="USER_ID",
            help="After training, print top CF scores for this patient user id.",
        )

    def handle(self, *args, **options):
        try:
            meta = train_cf_als(factors=options["factors"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"CF v{meta['version']} trained on {meta['n_interactions']} interactions "
                f"({meta['n_patients']} patients × {meta['n_caregivers']} caregivers)."
            )
        )

        patient_id = options["patient_scores"]
        if patient_id:
            scores = patient_cf_scores(patient_id)
            if not scores:
                self.stdout.write(f"No CF scores for patient user_id={patient_id}.")
            else:
                self.stdout.write(f"Top CF scores for patient user_id={patient_id}:")
                for row in scores:
                    self.stdout.write(
                        f"  caregiver={row['caregiver_id']} cf={row['cf_score']:.4f}"
                    )
