"""Localized notification email copy (Step 40)."""

from __future__ import annotations

from typing import Any

# template_key → {subject, body} per language (en|si|ta)
EMAIL_COPY: dict[str, dict[str, dict[str, str]]] = {
    "care_request_received": {
        "subject": {
            "en": "Care Plus: new care request",
            "si": "Care Plus: නව සත්කාර ඉල්ලීමක්",
            "ta": "Care Plus: புதிய பராமரிப்பு கோரிக்கை",
        },
        "body": {
            "en": (
                "Hi {caregiver_name},\n\n"
                "{patient_label} sent you a care request on Care Plus.\n"
                "Message: {message}\n"
                "Request #{request_id} · expires {expires_at}\n\n"
                "Open your inbox to accept or decline.\n\n— Care Plus"
            ),
            "si": (
                "ආයුබෝවන් {caregiver_name},\n\n"
                "{patient_label} Care Plus හරහා ඔබට සත්කාර ඉල්ලීමක් යැව්වා.\n"
                "පණිවිඩය: {message}\n"
                "ඉල්ලීම #{request_id} · කල් ඉකුත් වන්නේ {expires_at}\n\n"
                "පිළිගැනීමට හෝ ප්‍රතික්ෂේප කිරීමට ඔබේ එන ලිපි පෙට්ටිය විවෘත කරන්න.\n\n— Care Plus"
            ),
            "ta": (
                "வணக்கம் {caregiver_name},\n\n"
                "{patient_label} Care Plus வழியாக உங்களுக்கு பராமரிப்பு கோரிக்கை அனுப்பியுள்ளார்.\n"
                "செய்தி: {message}\n"
                "கோரிக்கை #{request_id} · காலாவதி {expires_at}\n\n"
                "ஏற்க அல்லது நிராகரிக்க உங்கள் இன்பாக்ஸைத் திறக்கவும்.\n\n— Care Plus"
            ),
        },
    },
    "care_request_accepted": {
        "subject": {
            "en": "Care Plus: caregiver accepted your request",
            "si": "Care Plus: සත්කාරක ඔබේ ඉල්ලීම පිළිගත්තා",
            "ta": "Care Plus: பராமரிப்பாளர் உங்கள் கோரிக்கையை ஏற்றார்",
        },
        "body": {
            "en": (
                "Hi {patient_name},\n\n"
                "{caregiver_name} accepted your care request.\n"
                "Complete checkout to activate your care link.\n"
                "{checkout_url}\n\n— Care Plus"
            ),
            "si": (
                "ආයුබෝවන් {patient_name},\n\n"
                "{caregiver_name} ඔබේ සත්කාර ඉල්ලීම පිළිගත්තා.\n"
                "සත්කාර සබඳතාව සක්‍රිය කිරීමට ගෙවීම සම්පූර්ණ කරන්න.\n"
                "{checkout_url}\n\n— Care Plus"
            ),
            "ta": (
                "வணக்கம் {patient_name},\n\n"
                "{caregiver_name} உங்கள் பராமரிப்பு கோரிக்கையை ஏற்றுள்ளார்.\n"
                "பராமரிப்பு இணைப்பை செயல்படுத்த கட்டணத்தை முடிக்கவும்.\n"
                "{checkout_url}\n\n— Care Plus"
            ),
        },
    },
    "payment_due": {
        "subject": {
            "en": "Care Plus: payment due to start care",
            "si": "Care Plus: සත්කාර ආරම්භ කිරීමට ගෙවීම අවශ්‍යයි",
            "ta": "Care Plus: பராமரிப்பைத் தொடங்க கட்டணம் தேவை",
        },
        "body": {
            "en": (
                "Hi {patient_name},\n\n"
                "Your care package with {caregiver_name} is ready.\n"
                "Amount due: {amount_lkr}\n"
                "Pay now to activate care: {checkout_url}\n\n— Care Plus"
            ),
            "si": (
                "ආයුබෝවන් {patient_name},\n\n"
                "{caregiver_name} සමඟ ඔබේ සත්කාර පැකේජය සූදානම්.\n"
                "ගෙවිය යුතු මුදල: {amount_lkr}\n"
                "සත්කාර සක්‍රිය කිරීමට දැන් ගෙවන්න: {checkout_url}\n\n— Care Plus"
            ),
            "ta": (
                "வணக்கம் {patient_name},\n\n"
                "{caregiver_name} உடனான உங்கள் பராமரிப்பு தொகுப்பு தயார்.\n"
                "செலுத்த வேண்டிய தொகை: {amount_lkr}\n"
                "பராமரிப்பை செயல்படுத்த இப்போது செலுத்துங்கள்: {checkout_url}\n\n— Care Plus"
            ),
        },
    },
    "anomaly_alert": {
        "subject": {
            "en": "Care Plus security alert: {alert_title}",
            "si": "Care Plus ආරක්ෂක අනතුරු ඇඟවීම: {alert_title}",
            "ta": "Care Plus பாதுகாப்பு எச்சரிக்கை: {alert_title}",
        },
        "body": {
            "en": (
                "Hi {user_name},\n\n"
                "We detected unusual activity on your Care Plus account.\n"
                "Alert: {alert_title}\n"
                "Details: {detail}\n\n"
                "If this was not you, contact support immediately.\n\n— Care Plus Security"
            ),
            "si": (
                "ආයුබෝවන් {user_name},\n\n"
                "ඔබේ Care Plus ගිණුමේ අසාමාන්‍ය ක්‍රියාකාරකමක් අප හඳුනාගත්තා.\n"
                "අනතුරු ඇඟවීම: {alert_title}\n"
                "විස්තර: {detail}\n\n"
                "මෙය ඔබ නොවේ නම්, වහාම සහාය අමතන්න.\n\n— Care Plus Security"
            ),
            "ta": (
                "வணக்கம் {user_name},\n\n"
                "உங்கள் Care Plus கணக்கில் அசாதாரண செயல்பாட்டைக் கண்டறிந்தோம்.\n"
                "எச்சரிக்கை: {alert_title}\n"
                "விவரங்கள்: {detail}\n\n"
                "இது நீங்கள் அல்ல என்றால், உடனடியாக ஆதரவைத் தொடர்பு கொள்ளுங்கள்.\n\n— Care Plus Security"
            ),
        },
    },
}


def supported_template_keys() -> frozenset[str]:
    return frozenset(EMAIL_COPY.keys())
