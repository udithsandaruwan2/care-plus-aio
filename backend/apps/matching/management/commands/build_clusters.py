"""Build caregiver/intent clusters and CF cold-start vectors (Step 99).

Usage::

    python manage.py build_clusters
    python manage.py build_clusters --caregiver-k 4 --intent-k 3
    python manage.py build_clusters --no-vocab-drafts
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.matching.clustering import build_and_persist_all


class Command(BaseCommand):
    help = "Cluster caregiver/intent embeddings and seed CF cold-start vectors."

    def add_arguments(self, parser):
        parser.add_argument("--caregiver-k", type=int, default=0, help="Override caregiver K (0=auto).")
        parser.add_argument("--intent-k", type=int, default=0, help="Override intent K (0=auto).")
        parser.add_argument(
            "--no-vocab-drafts",
            action="store_true",
            help="Do not create inactive ConditionTerm drafts from novel intent clusters.",
        )

    def handle(self, *args, **options):
        cg_k = options["caregiver_k"] or None
        intent_k = options["intent_k"] or None
        summary = build_and_persist_all(
            caregiver_k=cg_k,
            intent_k=intent_k,
            create_vocab_drafts=not options["no_vocab_drafts"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"caregiver_clusters={summary['caregiver_clusters']} "
                f"({summary['caregiver_members']} members); "
                f"intent_clusters={summary['intent_clusters']} "
                f"({summary['intent_members']} members); "
                f"cold_start_seeded={summary['cold_start_seeded']}; "
                f"vocab_novel={summary['vocab_novel']} "
                f"drafts={summary['vocab_drafts_created']}"
            )
        )
        if summary.get("novel_slugs"):
            self.stdout.write("  novel: " + ", ".join(summary["novel_slugs"]))
