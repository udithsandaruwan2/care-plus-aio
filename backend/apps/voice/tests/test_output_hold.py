"""Barge-in holds playback until the interrupted model turn actually ends."""

from django.test import SimpleTestCase

from apps.voice.output_hold import apply_output_hold, hold_expired, hold_should_release


class OutputHoldTests(SimpleTestCase):
    def test_barge_keeps_the_old_reply_quiet_until_the_turn_ends(self):
        holding, release = apply_output_hold(
            holding=True, interrupted=False, turn_complete=False
        )
        self.assertTrue(holding)
        self.assertFalse(release)

        holding, release = apply_output_hold(
            holding=True, interrupted=True, turn_complete=False
        )
        self.assertFalse(holding)
        self.assertTrue(release)

    def test_a_normal_turn_end_does_not_toggle_playback(self):
        holding, release = apply_output_hold(
            holding=False, interrupted=False, turn_complete=True
        )
        self.assertFalse(holding)
        self.assertFalse(release)

    def test_a_hold_expires_when_the_model_never_closes_the_turn(self):
        self.assertFalse(hold_expired(2000))
        self.assertTrue(hold_expired(2500))

    def test_a_streaming_cut_off_does_not_resume_when_the_timer_ends(self):
        self.assertFalse(hold_should_release(held_for_ms=2600, idle_for_ms=50))
        self.assertTrue(hold_should_release(held_for_ms=2600, idle_for_ms=400))
        self.assertFalse(hold_should_release(held_for_ms=2000, idle_for_ms=2000))
        self.assertTrue(hold_should_release(held_for_ms=15000, idle_for_ms=0))
