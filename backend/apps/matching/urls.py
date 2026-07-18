from django.urls import path

from .views import CaregiverListView, CbfPreviewView, PatientListView

urlpatterns = [
    path("caregivers/", CaregiverListView.as_view(), name="caregiver_list"),
    path("patients/", PatientListView.as_view(), name="patient_list"),
    path("match/cbf/", CbfPreviewView.as_view(), name="match_cbf_preview"),
]
