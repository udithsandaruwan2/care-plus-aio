"""Whether model audio may reach the speakers after a barge-in.

The hold stays up until the model marks that turn interrupted or complete.
Audio from the cut-off reply must not start her talking again.
"""

from __future__ import annotations


def apply_output_hold(
    *,
    holding: bool,
    interrupted: bool,
    turn_complete: bool,
) -> tuple[bool, bool]:
    """Return ``(still_holding, release_playback)``."""
    if holding and (interrupted or turn_complete):
        return False, True
    return holding, False
