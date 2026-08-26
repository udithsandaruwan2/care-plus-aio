"""Voice action payload + rank/name resolver."""

from django.test import SimpleTestCase

from apps.voice.actions import (
    build_voice_action,
    last_serah_text,
    parse_name_query,
    parse_rank,
    resolve_hit,
)
from apps.voice.router import classify_turn


COMPLETE = {
    "condition": "diabetes",
    "language": "Sinhala",
    "care_level": "basic",
}

RESULTS = [
    {
        "caregiver_id": 10,
        "rank": 1,
        "display_name": "Mohamed Rizwan",
        "explanation": "strong skill match",
    },
    {
        "caregiver_id": 20,
        "rank": 2,
        "display_name": "Nimal Perera",
        "explanation": "nearby",
    },
]


class ActionResolverTests(SimpleTestCase):
    def test_parse_rank_ordinals_and_numbers(self):
        self.assertEqual(parse_rank("request the first one"), 1)
        self.assertEqual(parse_rank("open number 3"), 3)
        self.assertEqual(parse_rank("review #2"), 2)
        self.assertEqual(parse_rank("hire the second"), 2)

    def test_parse_name_query_strips_verbs(self):
        self.assertIn("rizwan", parse_name_query("review Mohamed Rizwan").lower())
        self.assertEqual(parse_name_query("yes"), "")

    def test_resolve_hit_fuzzy_name(self):
        hit = resolve_hit(RESULTS, name_query="Rizwan")
        self.assertEqual(hit["caregiver_id"], 10)

    def test_build_request_action_defaults_to_top(self):
        action = build_voice_action("request", "send the request", {"results": RESULTS})
        self.assertEqual(action["type"], "request")
        self.assertEqual(action["caregiver_id"], 10)
        self.assertEqual(action["rank"], 1)

    def test_build_view_profile_by_rank(self):
        action = build_voice_action("view_profile", "review number two", {"results": RESULTS})
        self.assertEqual(action["type"], "view_profile")
        self.assertEqual(action["caregiver_id"], 20)

    def test_last_serah_text(self):
        history = [
            {"role": "user", "text": "hi"},
            {"role": "serah", "text": "Would you like to check his profile?"},
        ]
        self.assertIn("profile", last_serah_text(history))


class RouterActionFixtureTests(SimpleTestCase):
    def test_review_profile_phrase(self):
        d = classify_turn("review Mohamed Rizwan", COMPLETE, has_prior_match=True)
        self.assertEqual(d.route, "ACTION")
        self.assertEqual(d.situation, "view_profile")

    def test_send_request_phrase(self):
        d = classify_turn("send the request", COMPLETE, has_prior_match=True)
        self.assertEqual(d.route, "ACTION")
        self.assertEqual(d.situation, "request")

    def test_tell_me_more_is_describe(self):
        d = classify_turn("tell me more about them", COMPLETE, has_prior_match=True)
        self.assertEqual(d.route, "ACTION")
        self.assertEqual(d.situation, "describe_caregiver")

    def test_yes_after_profile_offer(self):
        d = classify_turn(
            "yes",
            COMPLETE,
            has_prior_match=True,
            last_serah_text="Would you like to go ahead and check his profile?",
        )
        self.assertEqual(d.route, "ACTION")
        self.assertEqual(d.situation, "view_profile")

    def test_yes_after_request_offer(self):
        d = classify_turn(
            "yes",
            COMPLETE,
            has_prior_match=True,
            last_serah_text="Shall I send a care request to Mohamed?",
        )
        self.assertEqual(d.route, "ACTION")
        self.assertEqual(d.situation, "request")

    def test_bare_yes_without_offer_stays_affirm(self):
        d = classify_turn("yes", COMPLETE, has_prior_match=True, last_serah_text="Got it.")
        self.assertEqual(d.route, "CHAT")
        self.assertEqual(d.situation, "affirm")
