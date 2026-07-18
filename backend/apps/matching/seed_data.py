"""Sri Lanka geodata + realistic caregiver/patient seed rows for VEHMF (Step 16)."""

from __future__ import annotations

# (name, lon, lat) — WGS84. Lon first for GEOS Point(x, y).
SRI_LANKA_CITIES: list[tuple[str, float, float]] = [
    ("Colombo", 79.8612, 6.9271),
    ("Dehiwala", 79.8730, 6.8400),
    ("Moratuwa", 79.8816, 6.7730),
    ("Negombo", 79.8358, 7.2083),
    ("Kandy", 80.6337, 7.2906),
    ("Galle", 80.2210, 6.0535),
    ("Matara", 80.5550, 5.9549),
    ("Jaffna", 80.0255, 9.6615),
    ("Batticaloa", 81.6924, 7.7102),
    ("Trincomalee", 81.2152, 8.5874),
    ("Anuradhapura", 80.4037, 8.3114),
    ("Kurunegala", 80.3623, 7.4863),
    ("Ratnapura", 80.3992, 6.7056),
    ("Badulla", 81.0550, 6.9934),
    ("Kalutara", 79.9590, 6.5854),
    ("Gampaha", 79.9925, 7.0840),
    ("Nuwara Eliya", 80.7829, 6.9497),
    ("Hambantota", 81.1185, 6.1244),
    ("Puttalam", 79.8283, 8.0362),
    ("Vavuniya", 80.4870, 8.7514),
]

CERTIFICATIONS = [
    "NVQ Level 4 Caregiving",
    "First Aid (Red Cross)",
    "CPR Certified",
    "Dementia Care Certificate",
    "Diabetes Educator (basic)",
    "Wound Care Basics",
    "Medication Administration",
    "Elder Care Specialist",
    "Pediatric First Aid",
    "Mental Health First Aid",
]

SPECIALTIES = [
    "diabetes",
    "hypertension",
    "dementia",
    "stroke recovery",
    "elderly care",
    "post-surgery",
    "mobility support",
    "wound care",
    "palliative",
    "pediatric support",
    "asthma",
    "dialysis support",
]

CARE_LEVELS = ["basic", "intermediate", "advanced"]
LANGUAGES = ["Sinhala", "Tamil", "English"]

# Sinhala / Tamil / English-leaning display names (synthetic).
CAREGIVER_NAMES = [
    "Nimali Perera",
    "Kamala Fernando",
    "Samanthi Jayasuriya",
    "Ruwan Silva",
    "Tharushi Wickramasinghe",
    "Anjali Rajendran",
    "Mohamed Rizwan",
    "Fathima Nazeer",
    "Priya Nadarajah",
    "Suresh Kumar",
    "Chathuri Bandara",
    "Dinesh Gunasekara",
    "Ishara Mendis",
    "Lakmali Herath",
    "Vasanthini Pillai",
    "Arun Balasubramaniam",
    "Meena Krishnan",
    "Hashan Cooray",
    "Sanduni Amarasinghe",
    "Roshan Pathirana",
    "Nadeesha Weerasinghe",
    "Kavitha Selvarajah",
    "Imran Cassim",
    "Dilani Abeysekera",
    "Janaka Rathnayake",
    "Shanika Wijesinghe",
    "Gayan Senanayake",
    "Niluka Dissanayake",
    "Ayesha Farook",
    "Pradeep Jayawardena",
]

PATIENT_NAMES = [
    "Sunil Jayawardena",
    "Malini Silva",
    "Ravi Chandran",
    "Kumari Perera",
    "Ahamed Yusuf",
    "Nirosha Fernando",
    "Elderly Care Demo",
    "Post-op Recovery Demo",
]
