"""Whether model audio may reach the speakers after a barge-in.

The hold stays up until the model marks that turn complete.
An interrupt flag alone is not the end: more audio from the cut-off line can follow it.
"""

from __future__ import annotations


def apply_output_hold(
    *,
    holding: bool,
    interrupted: bool,
    turn_complete: bool,
) -> tuple[bool, bool]:
    """Return ``(still_holding, release_playback)``."""
    if holding and turn_complete:
        return False, True
    # Audio after the interrupt flag is still the cut-off line.
    if holding and interrupted:
        return True, False
    return holding, False


def hold_expired(held_for_ms: int, limit_ms: int = 2500) -> bool:
    """Release a barge hold if the model never closes the interrupted turn."""
    return held_for_ms >= limit_ms


def hold_should_release(
    *,
    held_for_ms: int,
    idle_for_ms: int,
    limit_ms: int = 2500,
    idle_ms: int = 2000,
    max_ms: int = 15000,
) -> bool:
    """True when the hold may lift.

    Past the limit, a reply that is still streaming is the cut-off line and
    stays dropped. A phrase pause is not the end of that line. The hold lifts
    after a longer quiet stretch, or at max_ms so a later reply is not muted
    forever.
    """
    if held_for_ms >= max_ms:
        return True
    if held_for_ms < limit_ms:
        return False
    return idle_for_ms >= idle_ms
