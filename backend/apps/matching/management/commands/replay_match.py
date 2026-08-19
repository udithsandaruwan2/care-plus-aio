"""Replay a stored VEHMF MatchRun against current artifacts (Step 79).

Usage::

    python manage.py replay_match 42
"""

from django.core.management.base import BaseCommand, CommandError

from apps.matching.models import MatchRun
from apps.matching.replay import replay_match_run


class Command(BaseCommand):
    help = "Re-run VEHMF for a stored MatchRun and report ranking/artifact drift."

    def add_arguments(self, parser):
        parser.add_argument("run_id", type=int)

    def handle(self, *args, **options):
        run_id = options["run_id"]
        try:
            run = MatchRun.objects.get(pk=run_id)
        except MatchRun.DoesNotExist as exc:
            raise CommandError(f"MatchRun {run_id} not found.") from exc

        report = replay_match_run(run)
        if report["ok"]:
            self.stdout.write(self.style.SUCCESS(f"MATCH run={run_id} ranking identical"))
            return

        self.stderr.write(self.style.ERROR(f"MISMATCH run={run_id}"))
        for reason in report["reasons"]:
            self.stderr.write(f"  {reason}")
        raise CommandError("replay ranking or artifacts do not match the stored run")
