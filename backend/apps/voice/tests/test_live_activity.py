"""Live activity config stays strict about breaths and still allows barge-in."""

from django.test import SimpleTestCase

from apps.voice.live_activity import live_realtime_input_config


class LiveActivityTests(SimpleTestCase):
    def test_breath_does_not_open_a_turn_and_speech_still_interrupts(self):
        cfg = live_realtime_input_config()
        det = cfg["automatic_activity_detection"]
        self.assertFalse(det["disabled"])
        self.assertEqual(det["start_of_speech_sensitivity"], "START_SENSITIVITY_LOW")
        self.assertEqual(det["end_of_speech_sensitivity"], "END_SENSITIVITY_LOW")
        self.assertGreaterEqual(det["prefix_padding_ms"], 250)
        self.assertGreaterEqual(det["silence_duration_ms"], 500)
        self.assertEqual(cfg["activity_handling"], "START_OF_ACTIVITY_INTERRUPTS")
