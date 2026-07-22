"""Step 38 — messaging WebSocket tests."""

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import TransactionTestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Role
from apps.matching.models import (
    CaregiverProfile,
    CareRelationship,
    CareRelationshipStatus,
    PatientProfile,
)
from apps.messaging.models import MessageThread
from careplus.asgi import application

User = get_user_model()


def _setup_relationship():
    patient = User.objects.create_user(
        email="ws.msg.pt@example.com", password="pw-strong-123", role=Role.PATIENT
    )
    PatientProfile.objects.create(
        user=patient,
        display_name="WS Patient",
        city="Colombo",
        location=Point(79.86, 6.92, srid=4326),
        preferred_language="English",
        languages=["English"],
        care_level="basic",
        conditions=["dengue"],
        height_cm=170,
        weight_kg=70,
        blood_type="O+",
        emergency_contact_name="EC",
        emergency_contact_phone="+94770000000",
    )
    cg_user = User.objects.create_user(
        email="ws.msg.cg@example.com", password="pw-strong-123", role=Role.CAREGIVER
    )
    caregiver = CaregiverProfile.objects.create(
        user=cg_user,
        display_name="WS CG",
        location=Point(79.86, 6.93, srid=4326),
        certifications=["First Aid"],
        specialties=["dengue"],
        languages=["English"],
        care_levels=["basic"],
        trust_score=0.9,
        is_active=True,
        is_approved=True,
        is_available=True,
    )
    rel = CareRelationship.objects.create(
        patient=patient,
        caregiver=caregiver,
        status=CareRelationshipStatus.ACTIVE,
        is_primary=True,
    )
    thread = MessageThread.objects.create(relationship=rel)
    return patient, cg_user, thread


class MessageWebSocketTests(TransactionTestCase):
    def test_rejects_unauthenticated(self):
        _, _, thread = _setup_relationship()

        async def _run():
            communicator = WebsocketCommunicator(
                application, f"/ws/messages/{thread.pk}/"
            )
            connected, code = await communicator.connect()
            self.assertFalse(connected)
            self.assertEqual(code, 4401)

        async_to_sync(_run)()

    def test_participant_receives_push(self):
        patient, cg_user, thread = _setup_relationship()
        token = str(RefreshToken.for_user(cg_user).access_token)

        async def _run():
            communicator = WebsocketCommunicator(
                application, f"/ws/messages/{thread.pk}/?token={token}"
            )
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            ready = await communicator.receive_json_from()
            self.assertEqual(ready["type"], "message.ready")
            self.assertEqual(ready["thread_id"], thread.pk)

            from channels.layers import get_channel_layer

            layer = get_channel_layer()
            await layer.group_send(
                f"message_thread_{thread.pk}",
                {
                    "type": "message.created",
                    "payload": {"id": 99, "body": "Realtime hello", "sender_id": patient.pk},
                },
            )
            pushed = await communicator.receive_json_from()
            self.assertEqual(pushed["type"], "message.created")
            self.assertEqual(pushed["payload"]["body"], "Realtime hello")
            await communicator.disconnect()

        async_to_sync(_run)()

    def test_outsider_rejected(self):
        outsider = User.objects.create_user(
            email="ws.msg.out@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        _, _, thread = _setup_relationship()
        token = str(RefreshToken.for_user(outsider).access_token)

        async def _run():
            communicator = WebsocketCommunicator(
                application, f"/ws/messages/{thread.pk}/?token={token}"
            )
            connected, code = await communicator.connect()
            self.assertFalse(connected)
            self.assertEqual(code, 4403)

        async_to_sync(_run)()
