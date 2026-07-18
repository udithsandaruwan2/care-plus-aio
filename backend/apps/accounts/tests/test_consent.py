"""Step 7 acceptance: the PDPA/GDPR consent gate.

Verifies the append-only consent ledger, the /consent API, and that the
AI-processing gate returns 401 unauthenticated, 451 without consent, and 200
once consent is granted (then 451 again after revocation).
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import ConsentLog, ConsentScope

User = get_user_model()


class ConsentApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="patient@example.com", password="pw-strong-123")
        self.consent_url = reverse("v1:consent")
        self.gate_url = reverse("v1:consent_gate_check")

    def _grant(self, scope=ConsentScope.AI_PROCESSING, granted=True):
        return self.client.post(
            self.consent_url, {"scope": scope, "granted": granted}, format="json"
        )

    def test_grant_records_row_and_current_state(self):
        self.client.force_authenticate(self.user)
        resp = self._grant()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        state = self.client.get(self.consent_url).data
        self.assertTrue(state["current"][ConsentScope.AI_PROCESSING])
        self.assertIn(ConsentScope.HEALTH_MONITORING, state["scopes"])

    def test_consent_ledger_is_append_only(self):
        self.client.force_authenticate(self.user)
        self._grant(granted=True)
        self._grant(granted=False)

        rows = ConsentLog.objects.filter(user=self.user, scope=ConsentScope.AI_PROCESSING)
        self.assertEqual(rows.count(), 2)
        # Latest row wins → consent is currently revoked.
        self.assertFalse(ConsentLog.is_granted(self.user, ConsentScope.AI_PROCESSING))

    def test_gate_requires_authentication(self):
        resp = self.client.get(self.gate_url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_gate_blocks_without_consent_then_allows(self):
        self.client.force_authenticate(self.user)

        blocked = self.client.get(self.gate_url)
        self.assertEqual(blocked.status_code, status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS)

        self._grant(granted=True)
        allowed = self.client.get(self.gate_url)
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)
        self.assertTrue(allowed.data["ok"])

        self._grant(granted=False)
        revoked = self.client.get(self.gate_url)
        self.assertEqual(revoked.status_code, status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS)
