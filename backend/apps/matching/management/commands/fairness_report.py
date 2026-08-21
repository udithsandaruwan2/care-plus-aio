"""Print caregiver exposure fairness by language and city (Step 103).

Usage::

    python manage.py fairness_report
    python manage.py fairness_report --days 30
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from apps.matching.fairness import build_fairness_report


class Command(BaseCommand):
    help = "Report MatchResult exposure by city and language over a rolling window."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=14,
            help="Lookback window in days (default: 14).",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Emit raw JSON instead of a human-readable table.",
        )

    def handle(self, *args, **options):
        report = build_fairness_report(days=int(options["days"]))
        if options["json"]:
            self.stdout.write(json.dumps(report, indent=2))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Fairness report — last {report['window_days']}d: "
                f"{report['n_impressions']} impressions, "
                f"{report['n_unique_caregivers']} caregivers, "
                f"gini={report['exposure_gini']}"
            )
        )
        self.stdout.write("By city:")
        for row in report["by_city"][:15]:
            self.stdout.write(
                f"  {row['city']}: {row['count']} ({row['share'] * 100:.1f}%)"
            )
        self.stdout.write("By language (primary):")
        for row in report["by_language"][:15]:
            self.stdout.write(
                f"  {row['language']}: {row['count']} ({row['share'] * 100:.1f}%)"
            )
