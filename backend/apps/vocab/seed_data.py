"""Sri Lanka–relevant condition seed (≥30) for Step 15b.

Each row: (slug, canonical_en, synonyms dict, notes).
"""

from __future__ import annotations

SEED_CONDITIONS: list[tuple[str, str, dict[str, list[str]], str]] = [
    (
        "diabetes",
        "Diabetes",
        {
            "en": ["diabetes", "diabetic", "sugar problem", "blood sugar", "sugar disease"],
            "si": ["දියවැඩියාව", "දියවැඩ"],
            "ta": ["நீரிழிவு", "சர்க்கரை நோய்"],
        },
        "From voice map + old KnownCondition",
    ),
    (
        "hypertension",
        "Hypertension",
        {
            "en": ["hypertension", "high blood pressure", "blood pressure", "bp"],
            "si": ["අධි රුධිර පීඩනය", "රුධිර පීඩනය", "අධිරුධිර"],
            "ta": ["இரத்த அழுத்தம்", "உயர் இரத்த அழுத்தம்"],
        },
        "",
    ),
    (
        "asthma",
        "Asthma",
        {
            "en": ["asthma", "wheeze", "breathing problem"],
            "si": ["ඇදුම"],
            "ta": ["ஆஸ்துமா"],
        },
        "",
    ),
    (
        "cardiac",
        "Cardiac",
        {
            "en": ["cardiac", "heart", "heart disease", "heart problem"],
            "si": ["හෘද", "හදවත්"],
            "ta": ["இதய", "இதய நோய்"],
        },
        "",
    ),
    (
        "stroke",
        "Stroke",
        {
            "en": ["stroke", "paralysis", "stroke recovery"],
            "si": ["ආඝාතය", "ආඝාත"],
            "ta": ["பக்கவாதம்"],
        },
        "",
    ),
    (
        "dengue",
        "Dengue",
        {
            "en": ["dengue", "dengue fever"],
            "si": ["ඩෙංගු", "ඩෙංගු උණ"],
            "ta": ["டெங்கு", "டெங்கு காய்ச்சல்"],
        },
        "Sri Lanka endemic",
    ),
    (
        "cancer",
        "Cancer",
        {
            "en": ["cancer", "oncology", "tumor"],
            "si": ["පිළිකා"],
            "ta": ["புற்றுநோய்"],
        },
        "",
    ),
    (
        "elderly-care",
        "Elderly care",
        {
            "en": ["elderly", "geriatric", "senior care", "old age care"],
            "si": ["වයෝවෘද්ධ", "වැඩිහිටි"],
            "ta": ["முதியோர் பராமரிப்பு"],
        },
        "",
    ),
    (
        "dementia",
        "Dementia",
        {
            "en": ["dementia", "alzheimer", "alzheimers", "memory loss"],
            "si": ["මතක නැතිවීම", "ඩිමෙන්ෂියා"],
            "ta": ["நினைவு இழப்பு", "டிமென்ஷியா"],
        },
        "",
    ),
    (
        "arthritis",
        "Arthritis",
        {
            "en": ["arthritis", "joint pain", "rheumatoid"],
            "si": ["වාත රෝගය", "සන්ධි වේදනාව"],
            "ta": ["மூட்டு வலி", "வாதம்"],
        },
        "",
    ),
    (
        "depression",
        "Depression",
        {
            "en": ["depression", "depressed", "low mood"],
            "si": ["මානසික අවපීඩනය"],
            "ta": ["மனச்சோர்வு"],
        },
        "",
    ),
    (
        "adhd",
        "ADHD",
        {
            "en": ["adhd", "attention deficit", "hyperactivity"],
            "si": ["ඒඩීඑච්ඩී"],
            "ta": ["ஏடிஹெச்டி"],
        },
        "",
    ),
    (
        "autism",
        "Autism",
        {
            "en": ["autism", "asd", "autistic"],
            "si": ["ඔටිසම්"],
            "ta": ["ஆட்டிசம்"],
        },
        "",
    ),
    (
        "post-surgery",
        "Post-surgery",
        {
            "en": ["post surgery", "after surgery", "post-op", "postoperative"],
            "si": ["ශල්‍යකර්මයෙන් පසු"],
            "ta": ["அறுவை சிகிச்சைக்குப் பிறகு"],
        },
        "",
    ),
    (
        "mobility-support",
        "Mobility support",
        {
            "en": ["mobility", "walking support", "wheelchair"],
            "si": ["ගමන් පහසුකම"],
            "ta": ["நடமாட்ட உதவி"],
        },
        "",
    ),
    (
        "wound-care",
        "Wound care",
        {
            "en": ["wound", "wound care", "dressing", "ulcer"],
            "si": ["තුවාල සත්කාර"],
            "ta": ["காயம் பராமரிப்பு"],
        },
        "",
    ),
    (
        "palliative",
        "Palliative",
        {
            "en": ["palliative", "hospice", "end of life", "comfort care"],
            "si": ["සනාථ සත්කාර"],
            "ta": ["ஆறுதல் பராமரிப்பு"],
        },
        "",
    ),
    (
        "pediatric-support",
        "Pediatric support",
        {
            "en": ["pediatric", "child care", "kids care", "children"],
            "si": ["ළමා සත්කාර"],
            "ta": ["குழந்தை பராமரிப்பு"],
        },
        "",
    ),
    (
        "dialysis-support",
        "Dialysis support",
        {
            "en": ["dialysis", "kidney dialysis", "hemodialysis"],
            "si": ["ඩයලිසිස්"],
            "ta": ["டயாலிசிஸ்"],
        },
        "",
    ),
    (
        "ckd",
        "Chronic kidney disease",
        {
            "en": ["ckd", "kidney disease", "renal failure", "chronic kidney"],
            "si": ["වකුගඩු රෝගය"],
            "ta": ["சிறுநீரக நோய்"],
        },
        "",
    ),
    (
        "copd",
        "COPD",
        {
            "en": ["copd", "chronic obstructive", "emphysema", "chronic bronchitis"],
            "si": ["සීඕපීඩී", "නිදන්ගත ශ්වසන"],
            "ta": ["நாள்பட்ட சுவாச நோய்"],
        },
        "",
    ),
    (
        "tuberculosis",
        "Tuberculosis",
        {
            "en": ["tuberculosis", "tb", "consumption"],
            "si": ["ක්ෂය රෝගය", "ටීබී"],
            "ta": ["காசநோய்"],
        },
        "",
    ),
    (
        "malaria",
        "Malaria",
        {
            "en": ["malaria"],
            "si": ["මැලේරියා"],
            "ta": ["மலேரியா"],
        },
        "",
    ),
    (
        "chikungunya",
        "Chikungunya",
        {
            "en": ["chikungunya", "chikungunya fever"],
            "si": ["චිකුන්ගුන්යා"],
            "ta": ["சிக்குன்குனியா"],
        },
        "",
    ),
    (
        "typhoid",
        "Typhoid",
        {
            "en": ["typhoid", "enteric fever"],
            "si": ["ටයිෆොයිඩ්"],
            "ta": ["டைபாய்டு"],
        },
        "",
    ),
    (
        "hepatitis",
        "Hepatitis",
        {
            "en": ["hepatitis", "hepatitis b", "hepatitis c", "liver infection"],
            "si": ["හෙපටයිටිස්", "අක්මා ආසාදනය"],
            "ta": ["ஹெபடைடிஸ்"],
        },
        "",
    ),
    (
        "anemia",
        "Anemia",
        {
            "en": ["anemia", "anaemia", "low blood", "iron deficiency"],
            "si": ["රුධිරහීනතාව"],
            "ta": ["இரத்த சோகை"],
        },
        "",
    ),
    (
        "epilepsy",
        "Epilepsy",
        {
            "en": ["epilepsy", "seizure", "seizures", "fits"],
            "si": ["අපස්මාරය", "වලිප්පුව"],
            "ta": ["வலிப்பு"],
        },
        "",
    ),
    (
        "parkinsons",
        "Parkinson's",
        {
            "en": ["parkinson", "parkinsons", "parkinson's"],
            "si": ["පාකින්සන්"],
            "ta": ["பார்கின்சன்"],
        },
        "",
    ),
    (
        "anxiety",
        "Anxiety disorder",
        {
            "en": ["anxiety", "panic", "anxious"],
            "si": ["කාංසාව"],
            "ta": ["பதட்டம்"],
        },
        "",
    ),
    (
        "antenatal-care",
        "Antenatal care",
        {
            "en": ["antenatal", "pregnancy", "pregnant", "prenatal"],
            "si": ["ගර්භණී සත්කාර"],
            "ta": ["கர்ப்பகால பராமரிப்பு"],
        },
        "",
    ),
    (
        "postpartum-care",
        "Postpartum care",
        {
            "en": ["postpartum", "post natal", "after birth", "new mother"],
            "si": ["ප්‍රසවයෙන් පසු සත්කාර"],
            "ta": ["பிரசவத்திற்குப் பின் பராமரிப்பு"],
        },
        "",
    ),
    (
        "bedridden-care",
        "Bedridden care",
        {
            "en": ["bedridden", "bed bound", "immobility", "bed patient"],
            "si": ["ඇඳේ වැතිර සිටින"],
            "ta": ["படுக்கையில் இருக்கும் நோயாளி"],
        },
        "",
    ),
    (
        "pressure-ulcer",
        "Pressure ulcer",
        {
            "en": ["pressure ulcer", "bedsore", "bed sores", "pressure sore"],
            "si": ["ඇඳ තුවාල"],
            "ta": ["படுக்கைப் புண்"],
        },
        "",
    ),
    (
        "fracture-recovery",
        "Fracture recovery",
        {
            "en": ["fracture", "broken bone", "orthopedic recovery", "bone break"],
            "si": ["අස්ථි බිඳීම", "ඇටකටු කැඩීම"],
            "ta": ["எலும்பு முறிவு"],
        },
        "",
    ),
    (
        "thalassemia",
        "Thalassemia",
        {
            "en": ["thalassemia", "thalassaemia"],
            "si": ["තැලසීමියා"],
            "ta": ["தலசீமியா"],
        },
        "Common in Sri Lanka",
    ),
    (
        "cataract-support",
        "Cataract / vision support",
        {
            "en": ["cataract", "vision support", "eye care", "blind care"],
            "si": ["සුදු ඉවුම", "දෘෂ්ටි සහාය"],
            "ta": ["கண் புரை", "பார்வை உதவி"],
        },
        "",
    ),
]
