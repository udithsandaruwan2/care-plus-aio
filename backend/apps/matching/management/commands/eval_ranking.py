"""Replay held-out MatchRuns and report ranking metrics (Step 90).

Usage::

    python manage.py eval_ranking
    python manage.py eval_ranking --days 14 --limit 50
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.matching.cf_eval import evaluate_ranking


class Command(BaseCommand):
    help = (
        "Replay MatchRuns in a recent holdout window against the active CF model "
        "and print NDCG@5, MAP, recall@10, precision@5, coverage, and exposure Gini."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=14,
            help="Holdout window length in days ending now (default: 14).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Optional max MatchRuns to replay (0 = all in window).",
        )
        parser.add_argument(
            "--verbose-runs",
            action="store_true",
            help="Print per-run metric rows in addition to the aggregate table.",
        )

    def handle(self, *args, **options):
        limit = options["limit"] or None
        report = evaluate_ranking(days=options["days"], limit=limit)

        self.stdout.write("metric            value")
        self.stdout.write("----------------  ----------")
        for name, value in report.as_table_rows():
            self.stdout.write(f"{name:<16}  {value}")

        if options["verbose_runs"]:
            self.stdout.write("")
            self.stdout.write("per-run:")
            for row in report.per_run:
                self.stdout.write(f"  {row}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Evaluated {report.n_labelled}/{report.n_runs} labelled MatchRun(s) "
                f"in holdout window."
            )
        )
