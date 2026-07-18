from django.urls import path

from .views import CaregiverListView, PatientListView

urlpatterns = [
    path("caregivers/", CaregiverListView.as_view(), name="caregiver_list"),
    path("patients/", PatientListView.as_view(), name="patient_list"),
]
