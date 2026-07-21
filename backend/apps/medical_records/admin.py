from django.contrib import admin

from .models import MedicalRecord, MedicalRecordAttachment


class MedicalRecordAttachmentInline(admin.TabularInline):
    model = MedicalRecordAttachment
    extra = 0
    readonly_fields = ("original_name", "content_type", "size_bytes", "uploaded_at")
    fields = ("original_name", "content_type", "size_bytes", "file", "uploaded_at")


@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "condition", "title", "recorded_at", "created_at")
    list_filter = ("condition", "recorded_at")
    search_fields = ("title", "patient__email", "condition__slug")
    readonly_fields = (
        "sensitive_notes_ciphertext",
        "created_at",
        "updated_at",
    )
    inlines = [MedicalRecordAttachmentInline]


@admin.register(MedicalRecordAttachment)
class MedicalRecordAttachmentAdmin(admin.ModelAdmin):
    list_display = ("id", "record", "original_name", "content_type", "size_bytes", "uploaded_at")
    search_fields = ("original_name", "record__title")
    readonly_fields = ("uploaded_at",)
