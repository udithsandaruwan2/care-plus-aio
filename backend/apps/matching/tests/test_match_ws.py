"""Step 20 — JWT-authenticated match WebSocket."""

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Role
from careplus.asgi import application

User = get_user_model()


class MatchWebSocketTests(TransactionTestCase):
    def test_rejects_missing_token(self):
        user = User.objects.create_user(
            email="ws.patient@example.com", password="pw-strong-123", role=Role.PATIENT
        )

        async def _run():
            communicator = WebsocketCommunicator(application, f"/ws/match/{user.pk}/")
            connected, code = await communicator.connect()
            self.assertFalse(connected)
            self.assertEqual(code, 4401)

        async_to_sync(_run)()

    def test_rejects_other_patients_channel(self):
        owner = User.objects.create_user(
            email="ws.owner@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        other = User.objects.create_user(
            email="ws.other@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        token = str(RefreshToken.for_user(other).access_token)

        async def _run():
            communicator = WebsocketCommunicator(
                application, f"/ws/match/{owner.pk}/?token={token}"
            )
            connected, code = await communicator.connect()
            self.assertFalse(connected)
            self.assertEqual(code, 4401)

        async_to_sync(_run)()

    def test_accepts_own_channel_and_ready(self):
        user = User.objects.create_user(
            email="ws.ok@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        token = str(RefreshToken.for_user(user).access_token)

        async def _run():
            communicator = WebsocketCommunicator(
                application, f"/ws/match/{user.pk}/?token={token}"
            )
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            msg = await communicator.receive_json_from()
            self.assertEqual(msg["type"], "match.ready")
            self.assertEqual(msg["patient_id"], user.pk)
            await communicator.disconnect()

        async_to_sync(_run)()

    def test_forwards_turn_stages(self):
        user = User.objects.create_user(
            email="ws.turn@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        token = str(RefreshToken.for_user(user).access_token)

        async def _run():
            communicator = WebsocketCommunicator(
                application, f"/ws/match/{user.pk}/?token={token}"
            )
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            ready = await communicator.receive_json_from()
            self.assertEqual(ready["type"], "match.ready")

            from channels.layers import get_channel_layer

            layer = get_channel_layer()
            await layer.group_send(
                f"match_{user.pk}",
                {
                    "type": "turn.transcript",
                    "payload": {
                        "stage": "transcript",
                        "transcript": "need a nurse",
                        "request_id": "abc123",
                    },
                },
            )
            msg = await communicator.receive_json_from()
            self.assertEqual(msg["type"], "turn.transcript")
            self.assertEqual(msg["payload"]["transcript"], "need a nurse")
            self.assertEqual(msg["payload"]["stage"], "transcript")

            await layer.group_send(
                f"match_{user.pk}",
                {
                    "type": "turn.reply_text",
                    "payload": {
                        "stage": "reply_text",
                        "reply": "On it.",
                        "request_id": "abc123",
                    },
                },
            )
            msg = await communicator.receive_json_from()
            self.assertEqual(msg["type"], "turn.reply_text")
            self.assertEqual(msg["payload"]["reply"], "On it.")
            await communicator.disconnect()

        async_to_sync(_run)()
