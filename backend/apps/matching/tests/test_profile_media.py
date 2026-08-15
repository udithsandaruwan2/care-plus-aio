"""Step 22d — profile photo + certification document uploads."""

import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.matching.models import CaregiverProfile, PatientProfile

User = get_user_model()


def _jpeg(name="photo.jpg", size=(12, 12), color="red"):
    buf = BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="JPEG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")


def _pdf(name="cert.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4 test-cert", content_type="application/pdf")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ProfileMediaTests(APITestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            email="pt.photo@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        PatientProfile.objects.create(
            user=self.patient,
            display_name="Photo Patient",
            city="Colombo",
            location=Point(79.86, 6.92, srid=4326),
        )
        self.caregiver = User.objects.create_user(
            email="cg.photo@example.com", password="pw-strong-123", role=Role.CAREGIVER
        )
        CaregiverProfile.objects.create(
            user=self.caregiver,
            display_name="Photo CG",
            location=Point(79.86, 6.93, srid=4326),
            languages=["English"],
            specialties=["diabetes"],
            care_levels=["basic"],
            is_active=True,
            is_approved=True,
        )

    def test_patient_photo_upload_and_signed_download(self):
        self.client.force_authenticate(self.patient)
        resp = self.client.post(
            reverse("v1:patient_me_photo"),
            {"file": _jpeg()},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        photo_url = resp.data.get("photo_url")
        self.assertTrue(photo_url)
        self.assertIn("/api/v1/profile-media/photos/", photo_url)

        self.client.force_authenticate(None)
        token = photo_url.split("token=", 1)[1]
        dl = self.client.get(reverse("v1:profile_photo_download"), {"token": token})
        self.assertEqual(dl.status_code, status.HTTP_200_OK)
        self.assertTrue(dl["Content-Type"].startswith("image/"))

    def test_rejects_non_image_photo(self):
        self.client.force_authenticate(self.patient)
        resp = self.client.post(
            reverse("v1:patient_me_photo"),
            {"file": _pdf("virus.exe.pdf")},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_caregiver_document_upload_and_signed_download(self):
        self.client.force_authenticate(self.caregiver)
        resp = self.client.post(
            reverse("v1:caregiver_me_documents"),
            {"file": _pdf()},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        docs = resp.data.get("certification_docs") or []
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["scan"]["status"], "clean")
        self.assertNotIn("storage_path", docs[0])
        download_url = docs[0]["download_url"]
        token = download_url.split("token=", 1)[1]

        self.client.force_authenticate(None)
        dl = self.client.get(reverse("v1:profile_document_download"), {"token": token})
        self.assertEqual(dl.status_code, status.HTTP_200_OK)
        self.assertEqual(dl["Content-Type"], "application/pdf")

    def test_photo_requires_auth(self):
        resp = self.client.post(
            reverse("v1:caregiver_me_photo"),
            {"file": _jpeg()},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_expired_or_garbage_token_rejected(self):
        resp = self.client.get(reverse("v1:profile_photo_download"), {"token": "not-a-token"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
