# Step 53 — audit action for shift conflict VEHMF fallback

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0013_step51_shift_booking"),
    ]

    operations = [
        migrations.AlterField(
            model_name="auditlog",
            name="action",
            field=models.CharField(
                choices=[
                    ("view_health", "View patient health data"),
                    ("view_caregiver", "View caregiver public profile"),
                    ("grant_consent", "Grant processing consent"),
                    ("revoke_consent", "Revoke processing consent"),
                    ("login", "User login"),
                    ("create_care_request", "Patient created care request"),
                    ("cancel_care_request", "Patient cancelled care request"),
                    ("accept_care_request", "Caregiver accepted care request"),
                    ("reject_care_request", "Caregiver rejected care request"),
                    ("activate_care_relationship", "Care relationship activated"),
                    ("end_care_relationship", "Care relationship ended"),
                    ("create_order", "Patient created checkout order"),
                    ("create_payment_intent", "Patient created payment intent"),
                    ("confirm_payment", "Payment confirmed (mock or webhook)"),
                    ("payment_webhook", "Payment provider webhook received"),
                    ("receipt_sent", "Payment receipt emailed to patient"),
                    ("create_medical_record", "Patient created medical record"),
                    ("update_medical_record", "Patient updated medical record"),
                    ("delete_medical_record", "Patient soft-deleted medical record"),
                    ("book_shift", "Patient booked a caregiver shift"),
                    ("cancel_shift", "Shift booking cancelled"),
                    ("shift_conflict_fallback", "Shift conflict offered VEHMF fallback"),
                ],
                max_length=64,
            ),
        ),
    ]
