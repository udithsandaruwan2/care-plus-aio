#!/usr/bin/env python3
"""Standalone CF training entrypoint (Step 21).

Runs Django setup then trains ALS on the interaction log. Prefer
``python manage.py train_cf`` inside Docker; this script is for CI or
direct invocation from the repo root::

    python ml/train_cf.py
"""

from __future__ import annotations

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

from apps.matching.cf_train import train_cf_als  # noqa: E402


def main() -> None:
    meta = train_cf_als()
    print(
        f"CF v{meta['version']} — {meta['n_interactions']} interactions, "
        f"{meta['n_patients']} patients, {meta['n_caregivers']} caregivers"
    )


if __name__ == "__main__":
    main()
