"""Train learned VEHMF fusion weights by segment (Step 101).

Usage::

    python manage.py train_weights
    python manage.py train_weights --force
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.matching.weights_train import train_fusion_weights


class Command(BaseCommand):
    help = "Fit segment fusion weights from MatchResult accept outcomes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Promote learned vectors even when holdout NDCG does not improve.",
        )

    def handle(self, *args, **options):
        summary = train_fusion_weights(force=bool(options["force"]))
        self.stdout.write(
            self.style.SUCCESS(
                f"fusion weights v{summary['version']}: "
                f"learned={summary['learned_count']} "
                f"ahp_fallback={summary['ahp_fallback_count']} "
                f"→ {summary['artifact_dir']}"
            )
        )
        for key, seg in (summary.get("segments") or {}).items():
            self.stdout.write(
                f"  {key}: source={seg['source']} reason={seg['reason']} "
                f"n={seg['n_train']} "
                f"ndcg_learned={seg['ndcg_at_5_learned']} "
                f"ndcg_ahp={seg['ndcg_at_5_ahp']}"
            )
