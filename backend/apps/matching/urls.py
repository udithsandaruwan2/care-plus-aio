from django.urls import path

from .views import (
    AhpWeightsView,
    CaregiverDetailView,
    CaregiverListView,
    CaregiverMeView,
    CbfPreviewView,
    MatchView,
    PatientListView,
    PatientMeView,
)

urlpatterns = [
    path("caregivers/", CaregiverListView.as_view(), name="caregiver_list"),
    path("caregivers/me/", CaregiverMeView.as_view(), name="caregiver_me"),
    path("caregivers/<int:pk>/", CaregiverDetailView.as_view(), name="caregiver_detail"),
    path("patients/", PatientListView.as_view(), name="patient_list"),
    path("patients/me/", PatientMeView.as_view(), name="patient_me"),
    path("match/", MatchView.as_view(), name="match"),
    path("match/cbf/", CbfPreviewView.as_view(), name="match_cbf_preview"),
    path("match/weights/", AhpWeightsView.as_view(), name="match_ahp_weights"),
]
