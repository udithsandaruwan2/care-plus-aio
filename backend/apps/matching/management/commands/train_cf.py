"""Train implicit ALS on the interaction log (Steps 21 / 91).

Usage::

    python manage.py train_cf
    python manage.py train_cf --factors 16
    python manage.py train_cf --force
    python manage.py train_cf --patient-scores 42
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.matching.cf_train import patient_cf_scores, train_cf_als


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
            "--force",
            action="store_true",
            help="Promote the new artifact even if holdout metrics do not improve.",
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
            meta = train_cf_als(factors=options["factors"], force=bool(options["force"]))
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"CF v{meta['version']} trained on {meta['n_interactions']} interactions "
                f"({meta['n_patients']} patients × {meta['n_caregivers']} caregivers) "
                f"objective={meta.get('objective', '-')}."
            )
        )
        counts = meta.get("signal_counts") or {}
        if counts:
            self.stdout.write(
                f"  pairs: positive={counts.get('positive', 0)} "
                f"hard_neg={counts.get('hard_negative', 0)} "
                f"weak_neg={counts.get('weak_negative', 0)}"
            )
        if meta.get("promoted"):
            self.stdout.write(
                self.style.SUCCESS(f"Promoted (reason={meta.get('reason')}).")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Not promoted (reason={meta.get('reason')}); "
                    f"incumbent={meta.get('incumbent_version')} remains active."
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
