"""Train the offline slot classifier (Step 96).

Usage::

    python manage.py train_slots
    python manage.py train_slots --force
    python manage.py train_slots --no-voice-intents
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.voice.slots import train_slot_classifier


class Command(BaseCommand):
    help = "Train hashed n-gram slot classifier; gated-promote on hand holdout."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Skip holdout gate and activate the new version.",
        )
        parser.add_argument(
            "--no-voice-intents",
            action="store_true",
            help="Use seed corpus only (avoid Gemini-labelled VoiceIntent bias).",
        )

    def handle(self, *args, **options):
        try:
            meta = train_slot_classifier(
                force=bool(options["force"]),
                include_voice_intents=not bool(options["no_voice_intents"]),
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        promo = meta.get("promotion") or {}
        holdout = (meta.get("metrics") or {}).get("holdout") or {}
        stub = (meta.get("metrics") or {}).get("stub_holdout") or {}
        msg = (
            f"v{meta['version']} rows={meta['rows_trained_on']} "
            f"holdout_exact={holdout.get('exact_match', 0):.3f} "
            f"stub_exact={stub.get('exact_match', 0):.3f} "
            f"promoted={promo.get('promoted')} reason={promo.get('reason')}"
        )
        if promo.get("promoted"):
            self.stdout.write(self.style.SUCCESS(msg))
        else:
            self.stdout.write(self.style.WARNING(msg))
