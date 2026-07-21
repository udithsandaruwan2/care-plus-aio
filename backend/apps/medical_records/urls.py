from django.urls import path

from .views import (
    MedicalRecordAttachmentDownloadUrlView,
    MedicalRecordAttachmentDownloadView,
    MedicalRecordAttachmentUploadView,
    MedicalRecordDetailView,
    MedicalRecordListCreateView,
)

urlpatterns = [
    path("medical-records/", MedicalRecordListCreateView.as_view(), name="medical_record_list"),
    path("medical-records/<int:pk>/", MedicalRecordDetailView.as_view(), name="medical_record_detail"),
    path(
        "medical-records/<int:pk>/attachments/",
        MedicalRecordAttachmentUploadView.as_view(),
        name="medical_record_attachment_upload",
    ),
    path(
        "medical-records/attachments/<int:pk>/download-url/",
        MedicalRecordAttachmentDownloadUrlView.as_view(),
        name="medical_record_attachment_download_url",
    ),
    path(
        "medical-records/attachments/download/",
        MedicalRecordAttachmentDownloadView.as_view(),
        name="medical_record_attachment_download",
    ),
]
