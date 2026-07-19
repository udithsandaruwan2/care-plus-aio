from django.urls import path

from .views import (
    AhpWeightsView,
    CaregiverListView,
    CbfPreviewView,
    MatchView,
    PatientListView,
)

urlpatterns = [
    path("caregivers/", CaregiverListView.as_view(), name="caregiver_list"),
    path("patients/", PatientListView.as_view(), name="patient_list"),
    path("match/", MatchView.as_view(), name="match"),
    path("match/cbf/", CbfPreviewView.as_view(), name="match_cbf_preview"),
    path("match/weights/", AhpWeightsView.as_view(), name="match_ahp_weights"),
]
