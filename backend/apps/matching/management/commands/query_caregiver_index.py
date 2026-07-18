"""Query the caregiver FAISS index with a free-text / intent phrase (Step 17).

Usage::

    python manage.py query_caregiver_index "diabetes Sinhala intermediate Colombo"
    python manage.py query_caregiver_index --condition diabetes --language Sinhala -k 5
"""

from django.core.management.base import BaseCommand

from apps.matching.embeddings import get_embedder, intent_to_text
from apps.matching.faiss_index import load_index
from apps.matching.models import CaregiverProfile


class Command(BaseCommand):
    help = "Nearest-neighbour caregiver search against the FAISS index."

    def add_arguments(self, parser):
        parser.add_argument("query", nargs="?", default="", help="Free-text query.")
        parser.add_argument("--condition", default="")
        parser.add_argument("--language", default="")
        parser.add_argument("--care-level", default="")
        parser.add_argument("-k", type=int, default=5)

    def handle(self, *args, **options):
        text = intent_to_text(
            condition=options["condition"],
            language=options["language"],
            care_level=options["care_level"],
            extra=options["query"],
        )
        if not text:
            self.stderr.write("Provide a query string and/or --condition/--language/--care-level.")
            return

        index = load_index()
        if index.size == 0:
            self.stderr.write("Index empty — run build_caregiver_index first.")
            return

        vec = get_embedder().embed([text])[0]
        hits = index.search(vec, k=options["k"])
        self.stdout.write(f"Query: {text!r}  (backend={index.backend}, k={len(hits)})")
        for rank, (cg_id, score) in enumerate(hits, start=1):
            cg = CaregiverProfile.objects.filter(pk=cg_id).first()
            if not cg:
                self.stdout.write(f"  {rank}. id={cg_id} score={score:.4f} (missing row)")
                continue
            specs = ", ".join(cg.specialties or [])
            langs = ", ".join(cg.languages or [])
            self.stdout.write(
                f"  {rank}. {cg.display_name}  score={score:.4f}  " f"[{specs}]  langs=[{langs}]"
            )
