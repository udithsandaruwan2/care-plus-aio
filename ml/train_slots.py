#!/usr/bin/env python3
"""Standalone slot-classifier training entrypoint (Step 96).

Prefer ``python manage.py train_slots`` inside Docker::

    python ml/train_slots.py
    python ml/train_slots.py --force
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "careplus.settings.dev")

import django

django.setup()

from apps.voice.slots import train_slot_classifier  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Train offline slot classifier")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Promote even if holdout gate would reject",
    )
    parser.add_argument(
        "--no-voice-intents",
        action="store_true",
        help="Train on seed corpus only (skip logged VoiceIntent rows)",
    )
    args = parser.parse_args()
    meta = train_slot_classifier(
        force=bool(args.force),
        include_voice_intents=not args.no_voice_intents,
    )
    promo = meta.get("promotion") or {}
    holdout = (meta.get("metrics") or {}).get("holdout") or {}
    stub = (meta.get("metrics") or {}).get("stub_holdout") or {}
    print(
        f"Slot classifier v{meta['version']} — {meta['rows_trained_on']} rows, "
        f"holdout exact={holdout.get('exact_match', 0):.3f} "
        f"stub={stub.get('exact_match', 0):.3f} "
        f"promoted={promo.get('promoted')} reason={promo.get('reason')}"
    )


if __name__ == "__main__":
    main()
