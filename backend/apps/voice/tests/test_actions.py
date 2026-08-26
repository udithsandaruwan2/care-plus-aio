"""Voice action payload + rank/name resolver."""

from django.test import SimpleTestCase

from apps.voice.actions import (
    build_voice_action,
    last_serah_text,
    parse_addon_query,
    parse_days,
    parse_name_query,
    parse_package_query,
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

    def test_parse_days_and_package_addons(self):
        self.assertEqual(parse_days("Basic for 7 days"), 7)
        self.assertEqual(parse_days("a week of care"), 7)
        self.assertEqual(parse_package_query("standard package").lower(), "standard package")
        self.assertIn("meal", parse_addon_query("with meals and hospital escort").lower())

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

    def test_build_describe_by_name(self):
        action = build_voice_action(
            "describe_caregiver",
            "tell me more about Mohamed Rizwan",
            {"results": RESULTS},
        )
        self.assertEqual(action["type"], "describe_caregiver")
        self.assertEqual(action["caregiver_id"], 10)

    def test_build_request_status_and_cancel_flow(self):
        status = build_voice_action("request_status", "any update?", {"results": RESULTS})
        self.assertEqual(status["type"], "request_status")

        cancel = build_voice_action("cancel_flow", "never mind", {"results": RESULTS})
        self.assertEqual(cancel["type"], "cancel_flow")
        self.assertEqual(cancel.get("addon_ids"), [])

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

    def test_request_status_phrases(self):
        for phrase in (
            "any update?",
            "what's the status",
            "did they accept",
            "still waiting",
            "check on the request",
        ):
            d = classify_turn(phrase, COMPLETE, has_prior_match=True)
            self.assertEqual(d.route, "ACTION", phrase)
            self.assertEqual(d.situation, "request_status", phrase)

    def test_request_status_without_prior_match(self):
        d = classify_turn("any update on the request?", COMPLETE, has_prior_match=False)
        self.assertEqual(d.route, "ACTION")
        self.assertEqual(d.situation, "request_status")

    def test_select_package_phrases(self):
        for phrase in (
            "Basic Home Care for 7 days",
            "pick the first package",
            "intermediate with meals",
            "standard for a week",
            "add meal support",
        ):
            d = classify_turn(phrase, COMPLETE, has_prior_match=True)
            self.assertEqual(d.route, "ACTION", phrase)
            self.assertEqual(d.situation, "select_package", phrase)

    def test_confirm_checkout_phrases(self):
        for phrase in (
            "continue to payment",
            "go to checkout",
            "confirm checkout",
            "take me to pay",
        ):
            d = classify_turn(phrase, COMPLETE, has_prior_match=True)
            self.assertEqual(d.route, "ACTION", phrase)
            self.assertEqual(d.situation, "confirm_checkout", phrase)

    def test_yes_after_package_selected_confirms_checkout(self):
        d = classify_turn(
            "yes",
            COMPLETE,
            has_prior_match=True,
            last_serah_text="Got it — Basic Home Care for 7 days. Say continue to payment when you’re ready.",
        )
        self.assertEqual(d.route, "ACTION")
        self.assertEqual(d.situation, "confirm_checkout")

    def test_yes_after_tap_pay_stays_affirm(self):
        d = classify_turn(
            "yes",
            COMPLETE,
            has_prior_match=True,
            last_serah_text="I’ve filled the order — tap Pay on this screen to confirm.",
        )
        self.assertEqual(d.route, "CHAT")
        self.assertEqual(d.situation, "affirm")

    def test_cancel_flow_after_match(self):
        for phrase in ("never mind", "cancel the request", "forget it"):
            d = classify_turn(phrase, COMPLETE, has_prior_match=True)
            self.assertEqual(d.route, "ACTION", phrase)
            self.assertEqual(d.situation, "cancel_flow", phrase)
            self.assertFalse(d.clear_match, phrase)

    def test_cancel_flow_with_history_match_only(self):
        d = classify_turn("cancel", COMPLETE, has_prior_match=False, has_history_match=True)
        self.assertEqual(d.route, "ACTION")
        self.assertEqual(d.situation, "cancel_flow")

    def test_cancel_pre_match_clears_search(self):
        d = classify_turn("stop searching", COMPLETE, has_prior_match=False)
        self.assertEqual(d.route, "CHAT")
        self.assertEqual(d.situation, "cancel")
        self.assertTrue(d.clear_match)


class PackageActionBuilderTests(SimpleTestCase):
    def test_build_select_package_parses_days_and_addons(self):
        action = build_voice_action(
            "select_package",
            "Basic Home Care for 7 days with meals",
            {"results": RESULTS},
        )
        self.assertEqual(action["type"], "select_package")
        self.assertIn("basic", str(action.get("package_id") or "").lower())
        self.assertEqual(action["days"], 7)
        self.assertIn("meal", action.get("addon_query", ""))

    def test_build_confirm_checkout_action(self):
        action = build_voice_action("confirm_checkout", "continue to payment", None)
        self.assertEqual(action["type"], "confirm_checkout")
