from django.urls import path

from .views import AhpWeightsView, CaregiverListView, CbfPreviewView, PatientListView

urlpatterns = [
    path("caregivers/", CaregiverListView.as_view(), name="caregiver_list"),
    path("patients/", PatientListView.as_view(), name="patient_list"),
    path("match/cbf/", CbfPreviewView.as_view(), name="match_cbf_preview"),
    path("match/weights/", AhpWeightsView.as_view(), name="match_ahp_weights"),
]
