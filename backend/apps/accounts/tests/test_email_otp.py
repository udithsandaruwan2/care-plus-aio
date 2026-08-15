"""Step 22f — optional email OTP elevation for hire / pay / records."""

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.matching.models import CaregiverProfile, PatientProfile

User = get_user_model()


def _patient():
    user = User.objects.create_user(
        email="otp.pt@example.com", password="pw-strong-123", role=Role.PATIENT
    )
    PatientProfile.objects.create(
        user=user,
        display_name="OTP Patient",
        city="Colombo",
        location=Point(79.86, 6.92, srid=4326),
        preferred_language="English",
        languages=["English"],
        care_level="basic",
        conditions=["diabetes"],
        height_cm=170,
        weight_kg=70,
        blood_type="O+",
        emergency_contact_name="EC",
        emergency_contact_phone="+94770000000",
    )
    return user


def _caregiver():
    user = User.objects.create_user(
        email="otp.cg@example.com", password="pw-strong-123", role=Role.CAREGIVER
    )
    profile = CaregiverProfile.objects.create(
        user=user,
        display_name="OTP CG",
        location=Point(79.86, 6.93, srid=4326),
        certifications=["First Aid"],
        specialties=["diabetes"],
        languages=["English"],
        care_levels=["basic"],
        trust_score=0.9,
        is_active=True,
        is_approved=True,
        is_available=True,
    )
    return user, profile


@override_settings(
    OTP_ENABLED=True,
    OTP_DUMMY=True,
    OTP_DUMMY_CODE="123456",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class EmailOtpTests(APITestCase):
    def setUp(self):
        self.patient = _patient()
        self.cg_user, self.caregiver = _caregiver()

    def _login(self, user, password="pw-strong-123"):
        resp = self.client.post(
            reverse("v1:token_obtain_pair"),
            {"email": user.email, "password": password},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
        return resp.data

    def test_password_login_is_not_otp_verified(self):
        self._login(self.patient)
        me = self.client.get(reverse("v1:me"))
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertTrue(me.data["otp_enabled"])
        self.assertFalse(me.data["otp_verified"])

    def test_hire_blocked_until_otp_then_allowed(self):
        self._login(self.patient)
        blocked = self.client.post(
            reverse("v1:care_request_list"),
            {"caregiver_id": self.caregiver.pk, "message": "Need help"},
            format="json",
        )
        self.assertEqual(blocked.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("OTP", str(blocked.data.get("detail") or ""))

        req = self.client.post(reverse("v1:otp_request"), {}, format="json")
        self.assertEqual(req.status_code, status.HTTP_200_OK)
        self.assertTrue(req.data["demo"])
        self.assertEqual(req.data["demo_code"], "123456")
        self.assertEqual(len(mail.outbox), 0)
        verified = self.client.post(
            reverse("v1:otp_verify"), {"code": req.data["demo_code"]}, format="json"
        )
        self.assertEqual(verified.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {verified.data['access']}")

        me = self.client.get(reverse("v1:me"))
        self.assertTrue(me.data["otp_verified"])

        allowed = self.client.post(
            reverse("v1:care_request_list"),
            {"caregiver_id": self.caregiver.pk, "message": "Need help"},
            format="json",
        )
        self.assertEqual(allowed.status_code, status.HTTP_201_CREATED)

    def test_records_list_requires_otp(self):
        self._login(self.patient)
        blocked = self.client.get(reverse("v1:medical_record_list"))
        self.assertEqual(blocked.status_code, status.HTTP_403_FORBIDDEN)

    def test_wrong_code_rejected(self):
        self._login(self.patient)
        self.client.post(reverse("v1:otp_request"), {}, format="json")
        bad = self.client.post(reverse("v1:otp_verify"), {"code": "000000"}, format="json")
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(OTP_ENABLED=False)
class EmailOtpDisabledTests(APITestCase):
    def test_me_reports_verified_when_flag_off(self):
        user = User.objects.create_user(
            email="otp.off@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        resp = self.client.post(
            reverse("v1:token_obtain_pair"),
            {"email": user.email, "password": "pw-strong-123"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
        me = self.client.get(reverse("v1:me"))
        self.assertFalse(me.data["otp_enabled"])
        self.assertTrue(me.data["otp_verified"])
