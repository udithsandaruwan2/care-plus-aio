"""Gemini Live voice-activity settings for google-genai 1.14.

Low start sensitivity and a short speech pad keep an inhale from opening a
turn. A real start of speech still interrupts the assistant.
"""

from __future__ import annotations


def live_realtime_input_config() -> dict:
    return {
        "automatic_activity_detection": {
            "disabled": False,
            "start_of_speech_sensitivity": "START_SENSITIVITY_LOW",
            "end_of_speech_sensitivity": "END_SENSITIVITY_LOW",
            "prefix_padding_ms": 280,
            "silence_duration_ms": 650,
        },
        "activity_handling": "START_OF_ACTIVITY_INTERRUPTS",
    }
