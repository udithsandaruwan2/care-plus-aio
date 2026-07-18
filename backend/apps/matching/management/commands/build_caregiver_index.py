"""Build caregiver FAISS index and persist embeddings (Step 17).

Usage::

    python manage.py build_caregiver_index
    python manage.py build_caregiver_index --no-persist
"""

from django.core.management.base import BaseCommand

from apps.matching.faiss_index import artifact_dir, build_index, reset_cache


class Command(BaseCommand):
    help = "Embed active caregivers and build FAISS IndexFlatIP artifacts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-persist",
            action="store_true",
            help="Skip writing ml/artifacts (still updates DB embedding columns).",
        )

    def handle(self, *args, **options):
        reset_cache()
        persist = not options["no_persist"]
        built = build_index(persist=persist)
        self.stdout.write(
            self.style.SUCCESS(
                f"Indexed {built.size} caregivers "
                f"(backend={built.backend}, dim={built.index.d})."
            )
        )
        if persist:
            self.stdout.write(f"Artifacts → {artifact_dir()}")
